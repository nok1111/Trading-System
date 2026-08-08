"""Admin endpoints — user management, server maintenance, AI quota control.

All endpoints require admin privileges (is_admin=True on the user).
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import uuid as _uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.models.ai_usage import AIUsageLog
from app.database.models.user import SubscriptionPlan, User
from app.database.session import SessionLocal, get_db
from app.services.auth import get_current_user, hash_password

router = APIRouter(prefix="/api/admin", tags=["admin"])
settings = get_settings()

# OmniRoute SQLite database path (same VPS)
OMNIROUTE_DB = Path.home() / ".omniroute" / "storage.sqlite"
OMNIROUTE_URL = "http://localhost:20128"


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


# ─── Services & AI Agents Status ───


@router.get("/services/status")
def services_status(
    admin: Annotated[User, Depends(require_admin)],
) -> dict:
    """Get status of all services: Auth Server, Trading Client, AI Server, and AI agents."""
    services = []

    # 1) Auth Server (self)
    services.append({
        "name": "Auth Server",
        "url": "",
        "status": "online",
        "detail": f"PID {os.getpid()}",
    })

    # 2) Trading Client
    tc_url = settings.TRADING_CLIENT_URL
    tc_status = {"name": "Trading Client", "url": tc_url, "status": "offline", "detail": ""}
    try:
        resp = httpx.get(f"{tc_url}/health", timeout=5)
        if resp.status_code == 200:
            tc_status["status"] = "online"
            tc_status["detail"] = "Health check OK"
        else:
            tc_status["status"] = "error"
            tc_status["detail"] = f"HTTP {resp.status_code}"
    except Exception as exc:
        tc_status["detail"] = str(exc)[:100]
    services.append(tc_status)

    # 3) AI Server
    ai_url = settings.AI_SERVER_URL
    ai_status = {"name": "AI Server", "url": ai_url, "status": "offline", "detail": ""}
    try:
        resp = httpx.get(f"{ai_url}/health", timeout=5)
        if resp.status_code == 200:
            ai_status["status"] = "online"
            ai_status["detail"] = "Health check OK"
        else:
            ai_status["status"] = "error"
            ai_status["detail"] = f"HTTP {resp.status_code}"
    except Exception as exc:
        ai_status["detail"] = str(exc)[:100]
    services.append(ai_status)

    # 4) AI Agents from AI Server (12 intelligence agents)
    agents = []
    try:
        resp = httpx.get(f"{ai_url}/v1/intelligence/agents", timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            agents = data.get("agents", [])
    except Exception:
        pass

    # 5) AI Server scheduler status (24/7 consensus scheduler)
    scheduler = None
    try:
        resp = httpx.get(f"{ai_url}/v1/intelligence/scheduler/status", timeout=5)
        if resp.status_code == 200:
            scheduler = resp.json()
    except Exception:
        pass

    return {
        "services": services,
        "agents": agents,
        "scheduler": scheduler,
        "timestamp": datetime.now(UTC).isoformat(),
    }


# ─── OmniRoute Status ───


def _omniroute_db() -> sqlite3.Connection | None:
    """Open OmniRoute SQLite DB read-only."""
    if not OMNIROUTE_DB.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{OMNIROUTE_DB}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        return None


@router.get("/omniroute/status")
def omniroute_status(
    admin: Annotated[User, Depends(require_admin)],
) -> dict:
    """Get OmniRoute provider status, rate limits, and token usage.

    Reads directly from OmniRoute's SQLite database (~/.omniroute/storage.sqlite)
    and queries the HTTP API for model list and health.
    """
    result: dict = {
        "server_online": False,
        "version": None,
        "models_count": 0,
        "providers": [],
        "configured_connections": [],
        "circuit_breakers": [],
        "lockouts": [],
        "provider_stats": [],
        "recent_errors": [],
        "total_calls": 0,
        "total_ok": 0,
        "total_errors": 0,
        "total_tokens_in": 0,
        "total_tokens_out": 0,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # 1) Check if OmniRoute server is online via /v1/models (no auth required)
    try:
        resp = httpx.get(f"{OMNIROUTE_URL}/v1/models", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            models = data.get("data", [])
            result["server_online"] = True
            result["models_count"] = len(models)
            result["models"] = [
                {"id": m.get("id"), "owned_by": m.get("owned_by")}
                for m in models[:50]
            ]
    except Exception:
        pass

    # 2) Query SQLite DB for provider stats
    conn = _omniroute_db()
    if conn is None:
        result["db_available"] = False
        return result
    result["db_available"] = True

    try:
        # 2a) Configured provider connections
        rows = conn.execute(
            """SELECT id, provider, name, display_name, is_active,
                      test_status, error_code, last_error, last_error_at,
                      rate_limited_until, backoff_level, last_used_at,
                      consecutive_use_count, default_model
               FROM provider_connections ORDER BY is_active DESC, provider"""
        ).fetchall()
        result["configured_connections"] = [
            {
                "id": r["id"],
                "provider": r["provider"],
                "name": r["name"] or r["display_name"],
                "is_active": bool(r["is_active"]),
                "test_status": r["test_status"],
                "error_code": r["error_code"],
                "last_error": r["last_error"],
                "last_error_at": r["last_error_at"],
                "rate_limited_until": r["rate_limited_until"],
                "backoff_level": r["backoff_level"],
                "last_used_at": r["last_used_at"],
                "consecutive_use_count": r["consecutive_use_count"],
                "default_model": r["default_model"],
            }
            for r in rows
        ]
    except Exception:
        pass

    try:
        # 2b) Circuit breakers (rate limit / exhaustion state)
        rows = conn.execute(
            """SELECT name, state, failure_count, last_failure_time
               FROM domain_circuit_breakers ORDER BY failure_count DESC"""
        ).fetchall()
        result["circuit_breakers"] = [
            {
                "name": r["name"],
                "state": r["state"],
                "failure_count": r["failure_count"],
                "last_failure_time": r["last_failure_time"],
            }
            for r in rows
        ]
    except Exception:
        pass

    try:
        # 2c) Lockout state (providers locked due to rate limits)
        rows = conn.execute(
            """SELECT identifier, attempts, locked_until
               FROM domain_lockout_state WHERE locked_until IS NOT NULL"""
        ).fetchall()
        now_ts = datetime.now(UTC).timestamp()
        result["lockouts"] = [
            {
                "identifier": r["identifier"],
                "attempts": r["attempts"],
                "locked_until": r["locked_until"],
                "is_locked": r["locked_until"] is not None and r["locked_until"] > now_ts,
            }
            for r in rows
        ]
    except Exception:
        pass

    try:
        # 2d) Provider stats from call_logs (aggregated)
        rows = conn.execute(
            """SELECT provider, model,
                      COUNT(*) as total,
                      SUM(CASE WHEN status=200 THEN 1 ELSE 0 END) as ok,
                      SUM(CASE WHEN status!=200 THEN 1 ELSE 0 END) as err,
                      SUM(tokens_in) as tok_in,
                      SUM(tokens_out) as tok_out,
                      AVG(duration) as avg_ms,
                      MAX(timestamp) as last_call
               FROM call_logs GROUP BY provider, model ORDER BY total DESC"""
        ).fetchall()
        stats = []
        for r in rows:
            total = r["total"] or 0
            ok = r["ok"] or 0
            err = r["err"] or 0
            stats.append({
                "provider": r["provider"],
                "model": r["model"],
                "total": total,
                "ok": ok,
                "err": err,
                "success_rate": round(ok / total * 100, 1) if total else 0,
                "tokens_in": r["tok_in"] or 0,
                "tokens_out": r["tok_out"] or 0,
                "avg_latency_ms": round(r["avg_ms"] or 0, 1),
                "last_call": r["last_call"],
                "exhausted": err > ok and ok == 0,
                "rate_limited": err > 0 and ok > 0 and err / total > 0.5,
            })
        result["provider_stats"] = stats
        result["total_calls"] = sum(s["total"] for s in stats)
        result["total_ok"] = sum(s["ok"] for s in stats)
        result["total_errors"] = sum(s["err"] for s in stats)
        result["total_tokens_in"] = sum(s["tokens_in"] for s in stats)
        result["total_tokens_out"] = sum(s["tokens_out"] for s in stats)
    except Exception:
        pass

    try:
        # 2e) Recent error calls (last 20)
        rows = conn.execute(
            """SELECT timestamp, provider, model, status, error_summary, duration
               FROM call_logs WHERE status != 200
               ORDER BY timestamp DESC LIMIT 20"""
        ).fetchall()
        result["recent_errors"] = [
            {
                "timestamp": r["timestamp"],
                "provider": r["provider"],
                "model": r["model"],
                "status": r["status"],
                "error": r["error_summary"],
                "duration_ms": r["duration"],
            }
            for r in rows
        ]
    except Exception:
        pass

    try:
        # 2f) Daily usage summary
        rows = conn.execute(
            """SELECT provider, model, date,
                      total_requests, total_input_tokens, total_output_tokens, total_cost
               FROM daily_usage_summary ORDER BY date DESC LIMIT 30"""
        ).fetchall()
        result["daily_usage"] = [
            {
                "provider": r["provider"],
                "model": r["model"],
                "date": r["date"],
                "requests": r["total_requests"],
                "tokens_in": r["total_input_tokens"],
                "tokens_out": r["total_output_tokens"],
                "cost": r["total_cost"],
            }
            for r in rows
        ]
    except Exception:
        pass

    conn.close()
    return result


# ─── OmniRoute Providers Management ───

# Catalog of all providers supported by OmniRoute
# free=True means no API key needed (built-in free tier)
OMNIROUTE_PROVIDER_CATALOG = [
    # Paid providers (require API key)
    {"id": "groq", "name": "Groq", "category": "api-key", "free": False,
     "url": "https://console.groq.com/keys",
     "test_model": "groq/llama-3.1-8b-instant",
     "description": "Llama 3.3 70B, ultra-fast inference (gratis con rate limit alto)"},
    {"id": "google", "name": "Google AI (Gemini)", "category": "api-key", "free": False,
     "url": "https://aistudio.google.com/apikey",
     "test_model": "google/gemini-2.0-flash",
     "description": "Gemini 2.0 Flash, Gemini Pro (gratis con rate limit)"},
    {"id": "openai", "name": "OpenAI", "category": "api-key", "free": False,
     "url": "https://platform.openai.com/api-keys",
     "test_model": "openai/gpt-4o-mini",
     "description": "GPT-4o, GPT-4o mini, o1 (pago)"},
    {"id": "anthropic", "name": "Anthropic (Claude)", "category": "api-key", "free": False,
     "url": "https://console.anthropic.com/settings/keys",
     "test_model": "anthropic/claude-sonnet-4-5",
     "description": "Claude Sonnet 4.5, Claude Opus, Claude Haiku (pago)"},
    {"id": "openrouter", "name": "OpenRouter", "category": "api-key", "free": False,
     "url": "https://openrouter.ai/keys",
     "test_model": "openrouter/auto",
     "description": "Gateway a 100+ modelos (Claude, GPT, DeepSeek, etc.) — $1 credit gratis"},
    {"id": "mistral", "name": "Mistral AI", "category": "api-key", "free": False,
     "url": "https://console.mistral.ai/api-keys",
     "test_model": "mistral/mistral-small-latest",
     "description": "Mistral Large, Small, Codestral (free tier disponible)"},
    # Free providers (no key needed, built-in)
    {"id": "felo-web", "name": "Felo (Free)", "category": "free", "free": True,
     "url": None,
     "test_model": "felo/felo-chat",
     "description": "Felo Chat, Search, Scholar — gratis sin key (rate limit)"},
    {"id": "duckduckgo-web", "name": "DuckDuckGo (Free)", "category": "free", "free": True,
     "url": None,
     "test_model": "ddgw/gpt-5.4-mini",
     "description": "GPT-5.4 mini, Claude Haiku, Mistral Small — gratis sin key"},
    {"id": "auggie", "name": "Auggie (Free)", "category": "free", "free": True,
     "url": None,
     "test_model": "aug/haiku4.5",
     "description": "Sonnet 4.6, Fable 5, Haiku 4.5 — gratis sin key"},
    {"id": "chipotle", "name": "Chipotle (Free)", "category": "free", "free": True,
     "url": None,
     "test_model": "pepper/pepper-1",
     "description": "Pepper-1 — gratis sin key"},
]


class SaveProviderKeyRequest(BaseModel):
    api_key: str


@router.get("/omniroute/providers")
def omniroute_providers(
    admin: Annotated[User, Depends(require_admin)],
) -> dict:
    """List all available OmniRoute providers with current key status.

    Returns the actual API key for configured providers (admin only).
    """
    conn = _omniroute_db()
    connections_map: dict[str, dict] = {}
    if conn:
        try:
            rows = conn.execute(
                """SELECT id, provider, name, is_active, api_key,
                          test_status, error_code, last_error, last_error_at,
                          rate_limited_until, backoff_level, last_used_at
                   FROM provider_connections"""
            ).fetchall()
            for r in rows:
                connections_map[r["provider"]] = {
                    "connection_id": r["id"],
                    "name": r["name"],
                    "is_active": bool(r["is_active"]),
                    "api_key": r["api_key"] or "",
                    "test_status": r["test_status"],
                    "error_code": r["error_code"],
                    "last_error": r["last_error"],
                    "last_error_at": r["last_error_at"],
                    "rate_limited_until": r["rate_limited_until"],
                    "backoff_level": r["backoff_level"],
                    "last_used_at": r["last_used_at"],
                }
        except Exception:
            pass
        conn.close()

    providers = []
    for p in OMNIROUTE_PROVIDER_CATALOG:
        conn_data = connections_map.get(p["id"])
        providers.append({
            "id": p["id"],
            "name": p["name"],
            "category": p["category"],
            "free": p["free"],
            "url": p["url"],
            "description": p["description"],
            "test_model": p["test_model"],
            "configured": conn_data is not None,
            "is_active": conn_data["is_active"] if conn_data else False,
            "api_key": conn_data["api_key"] if conn_data else "",
            "test_status": conn_data["test_status"] if conn_data else None,
            "last_error": conn_data["last_error"] if conn_data else None,
            "rate_limited_until": conn_data["rate_limited_until"] if conn_data else None,
            "backoff_level": conn_data["backoff_level"] if conn_data else 0,
            "last_used_at": conn_data["last_used_at"] if conn_data else None,
        })

    return {
        "providers": providers,
        "total": len(providers),
        "configured": sum(1 for p in providers if p["configured"]),
        "free_active": sum(1 for p in providers if p["free"]),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.post("/omniroute/providers/{provider_id}")
def omniroute_save_provider_key(
    provider_id: str,
    req: SaveProviderKeyRequest,
    admin: Annotated[User, Depends(require_admin)],
) -> dict:
    """Save or update an API key for an OmniRoute provider.

    Inserts a new provider_connection or updates the existing one.
    """
    # Validate provider exists in catalog
    catalog_entry = next((p for p in OMNIROUTE_PROVIDER_CATALOG if p["id"] == provider_id), None)
    if not catalog_entry:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' no encontrado en el catálogo")

    api_key = req.api_key.strip()
    if not api_key and not catalog_entry["free"]:
        raise HTTPException(status_code=400, detail="API key requerida para providers de pago")

    conn = _omniroute_db()
    if conn is None:
        raise HTTPException(status_code=500, detail="Base de datos de OmniRoute no disponible")

    now = datetime.now(UTC).isoformat()
    try:
        # Check if connection already exists
        existing = conn.execute(
            "SELECT id FROM provider_connections WHERE provider = ?", (provider_id,)
        ).fetchone()

        if existing:
            # Update existing
            conn.execute(
                """UPDATE provider_connections
                   SET api_key = ?, is_active = 1, test_status = 'pending',
                       error_code = NULL, last_error = NULL, backoff_level = 0,
                       rate_limited_until = NULL, updated_at = ?
                   WHERE provider = ?""",
                (api_key, now, provider_id),
            )
            conn.commit()
            action = "updated"
        else:
            # Insert new
            conn_id = str(_uuid.uuid4())
            conn.execute(
                """INSERT INTO provider_connections
                   (id, provider, auth_type, name, display_name, is_active,
                    api_key, test_status, backoff_level, consecutive_use_count,
                    created_at, updated_at)
                   VALUES (?, ?, 'api_key', ?, ?, 1, ?, 'pending', 0, 0, ?, ?)""",
                (conn_id, provider_id, catalog_entry["name"], catalog_entry["name"],
                 api_key, now, now),
            )
            conn.commit()
            action = "created"

        conn.close()
        return {
            "saved": True,
            "provider": provider_id,
            "action": action,
            "message": f"API key para {catalog_entry['name']} guardada correctamente",
        }
    except Exception as exc:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Error guardando key: {exc}")


@router.delete("/omniroute/providers/{provider_id}")
def omniroute_delete_provider_key(
    provider_id: str,
    admin: Annotated[User, Depends(require_admin)],
) -> dict:
    """Remove a provider connection from OmniRoute."""
    conn = _omniroute_db()
    if conn is None:
        raise HTTPException(status_code=500, detail="Base de datos de OmniRoute no disponible")
    try:
        conn.execute("DELETE FROM provider_connections WHERE provider = ?", (provider_id,))
        conn.commit()
        conn.close()
        return {"deleted": True, "provider": provider_id}
    except Exception as exc:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Error eliminando provider: {exc}")


@router.post("/omniroute/providers/{provider_id}/test")
def omniroute_test_provider(
    provider_id: str,
    admin: Annotated[User, Depends(require_admin)],
) -> dict:
    """Test a provider connection by sending a simple chat request via OmniRoute."""
    catalog_entry = next((p for p in OMNIROUTE_PROVIDER_CATALOG if p["id"] == provider_id), None)
    if not catalog_entry:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' no encontrado")

    test_model = catalog_entry["test_model"]
    start = datetime.now(UTC)

    try:
        resp = httpx.post(
            f"{OMNIROUTE_URL}/v1/chat/completions",
            headers={
                "Authorization": "Bearer omniroute",
                "Content-Type": "application/json",
            },
            json={
                "model": test_model,
                "messages": [{"role": "user", "content": "Responde solo: OK"}],
                "max_tokens": 10,
                "stream": False,
                "temperature": 0,
            },
            timeout=30,
        )
        elapsed = (datetime.now(UTC) - start).total_seconds()

        if resp.status_code == 200:
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            tokens = data.get("usage", {}).get("total_tokens", 0)
            return {
                "success": True,
                "provider": provider_id,
                "model": test_model,
                "status": 200,
                "response": content[:100],
                "tokens": tokens,
                "latency_ms": round(elapsed * 1000),
                "message": f"✓ {catalog_entry['name']} funciona correctamente ({round(elapsed*1000)}ms)",
            }
        else:
            error_body = resp.text[:300]
            return {
                "success": False,
                "provider": provider_id,
                "model": test_model,
                "status": resp.status_code,
                "error": error_body,
                "latency_ms": round(elapsed * 1000),
                "message": f"✗ {catalog_entry['name']} devolvió HTTP {resp.status_code}",
            }
    except httpx.ConnectError:
        return {
            "success": False,
            "provider": provider_id,
            "error": "OmniRoute no está corriendo",
            "message": "✗ OmniRoute no disponible. Ejecuta: systemctl start omniroute",
        }
    except Exception as exc:
        return {
            "success": False,
            "provider": provider_id,
            "error": str(exc)[:300],
            "message": f"✗ Error testeando {catalog_entry['name']}: {str(exc)[:100]}",
        }
