"""Admin endpoints — user management, server maintenance, AI quota control.

All endpoints require admin privileges (is_admin=True on the user).
"""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database.models.ai_usage import AIUsageLog
from app.database.models.user import SubscriptionPlan, User
from app.database.session import SessionLocal, get_db
from app.services.auth import get_current_user, hash_password

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """Dependency that ensures the current user is an admin."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado — se requieren privilegios de administrador",
        )
    return current_user


# ─── Schemas ───


class CreateUserRequest(BaseModel):
    email: str
    username: str
    password: str
    subscription: str = "free"
    is_admin: bool = False


class UpdateUserRequest(BaseModel):
    email: str | None = None
    username: str | None = None
    password: str | None = None
    subscription: str | None = None
    is_active: bool | None = None
    is_admin: bool | None = None
    risk_profile: str | None = None


class ServerActionRequest(BaseModel):
    action: str  # "restart", "status", "clear_logs"


# ─── User Management ───


@router.get("/users")
def list_users(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """List all users with their subscription and status."""
    users = db.execute(select(User).order_by(User.created_at.desc())).scalars().all()
    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "username": u.username,
                "subscription": u.subscription,
                "is_active": u.is_active,
                "is_admin": u.is_admin,
                "risk_profile": u.risk_profile,
                "created_at": str(u.created_at) if u.created_at else None,
            }
            for u in users
        ],
        "total": len(users),
    }


@router.post("/users")
def create_user(
    req: CreateUserRequest,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Create a new user with specific subscription and admin flag."""
    existing = db.execute(select(User).where(User.email == req.email)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email ya registrado")

    existing_user = db.execute(select(User).where(User.username == req.username)).scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username ya registrado")

    valid_plans = [p.value for p in SubscriptionPlan]
    if req.subscription not in valid_plans:
        raise HTTPException(
            status_code=400,
            detail=f"Plan inválido. Opciones: {', '.join(valid_plans)}",
        )

    user = User(
        email=req.email,
        username=req.username,
        hashed_password=hash_password(req.password),
        subscription=req.subscription,
        is_admin=req.is_admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "created": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "subscription": user.subscription,
            "is_admin": user.is_admin,
        },
    }


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    req: UpdateUserRequest,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Update a user's attributes (subscription, active, admin, password, etc.)."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if req.email is not None:
        existing = db.execute(select(User).where(User.email == req.email, User.id != user_id)).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Email ya en uso")
        user.email = req.email

    if req.username is not None:
        existing = db.execute(select(User).where(User.username == req.username, User.id != user_id)).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Username ya en uso")
        user.username = req.username

    if req.password is not None:
        user.hashed_password = hash_password(req.password)

    if req.subscription is not None:
        valid_plans = [p.value for p in SubscriptionPlan]
        if req.subscription not in valid_plans:
            raise HTTPException(status_code=400, detail=f"Plan inválido. Opciones: {', '.join(valid_plans)}")
        user.subscription = req.subscription

    if req.is_active is not None:
        user.is_active = req.is_active

    if req.is_admin is not None:
        user.is_admin = req.is_admin

    if req.risk_profile is not None:
        user.risk_profile = req.risk_profile

    db.commit()
    return {
        "updated": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "subscription": user.subscription,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "risk_profile": user.risk_profile,
        },
    }


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Delete a user and their AI usage logs."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta")

    db.execute(delete(AIUsageLog).where(AIUsageLog.user_id == user_id))
    db.delete(user)
    db.commit()
    return {"deleted": True, "user_id": user_id}


# ─── AI Quota Management ───


@router.get("/ai-usage")
def list_ai_usage(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """List AI usage stats for all users today."""
    today = datetime.now(UTC).date()
    logs = db.execute(
        select(AIUsageLog, User)
        .join(User, AIUsageLog.user_id == User.id)
        .where(AIUsageLog.date == today)
        .order_by(AIUsageLog.request_count.desc())
    ).all()
    return {
        "date": str(today),
        "usage": [
            {
                "user_id": log.user_id,
                "email": user.email,
                "username": user.username,
                "subscription": user.subscription,
                "request_count": log.request_count,
                "last_grant_id": log.last_grant_id,
            }
            for log, user in logs
        ],
    }


@router.post("/ai-usage/clear")
def clear_ai_usage(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Clear all AI usage logs (reset all quotas)."""
    result = db.execute(delete(AIUsageLog))
    db.commit()
    return {"cleared": True, "rows_deleted": result.rowcount}


@router.post("/ai-usage/clear/{user_id}")
def clear_user_ai_usage(
    user_id: int,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Clear AI usage for a specific user (reset their quota)."""
    result = db.execute(delete(AIUsageLog).where(AIUsageLog.user_id == user_id))
    db.commit()
    return {"cleared": True, "user_id": user_id, "rows_deleted": result.rowcount}


# ─── Server Maintenance ───


@router.get("/server/status")
def server_status(
    admin: Annotated[User, Depends(require_admin)],
) -> dict:
    """Get server status information."""
    try:
        uptime_result = subprocess.run(
            ["uptime"], capture_output=True, text=True, timeout=5
        )
        uptime_str = uptime_result.stdout.strip()
    except Exception:
        uptime_str = "No disponible"

    try:
        disk_result = subprocess.run(
            ["df", "-h", "/"], capture_output=True, text=True, timeout=5
        )
        disk_str = disk_result.stdout.strip()
    except Exception:
        disk_str = "No disponible"

    try:
        mem_result = subprocess.run(
            ["free", "-h"], capture_output=True, text=True, timeout=5
        )
        mem_str = mem_result.stdout.strip()
    except Exception:
        mem_str = "No disponible"

    return {
        "status": "running",
        "timestamp": datetime.now(UTC).isoformat(),
        "pid": os.getpid(),
        "uptime": uptime_str,
        "disk": disk_str,
        "memory": mem_str,
    }


@router.post("/server/restart")
def restart_server(
    admin: Annotated[User, Depends(require_admin)],
) -> dict:
    """Restart the auth-server service via systemd."""
    try:
        result = subprocess.run(
            ["systemctl", "restart", "auth-server"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return {"restarted": True, "message": "auth-server reiniciado correctamente"}
        return {
            "restarted": False,
            "error": result.stderr.strip() or "No se pudo reiniciar (¿systemd configurado?)",
        }
    except Exception as exc:
        return {"restarted": False, "error": str(exc)}


@router.post("/server/restart-db")
def restart_db(
    admin: Annotated[User, Depends(require_admin)],
) -> dict:
    """Restart PostgreSQL service."""
    try:
        result = subprocess.run(
            ["systemctl", "restart", "postgresql"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return {"restarted": True, "message": "PostgreSQL reiniciado correctamente"}
        return {
            "restarted": False,
            "error": result.stderr.strip() or "No se pudo reiniciar PostgreSQL",
        }
    except Exception as exc:
        return {"restarted": False, "error": str(exc)}


@router.get("/server/logs")
def server_logs(
    admin: Annotated[User, Depends(require_admin)],
    lines: int = 50,
) -> dict:
    """Get recent auth-server logs from systemd journal."""
    try:
        result = subprocess.run(
            ["journalctl", "-u", "auth-server", "--no-pager", "-n", str(lines)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return {"logs": result.stdout.strip().split("\n") if result.stdout else []}
    except Exception as exc:
        return {"logs": [], "error": str(exc)}
