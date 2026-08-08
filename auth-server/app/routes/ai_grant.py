"""AI Agent authorization endpoints — signed grant + daily quota system.

The Trading Client requests a short-lived, single-use grant token before each
AI agent cycle. The server validates the user's subscription, checks the daily
quota, and issues a signed JWT grant. After the cycle completes, the client
reports usage back to decrement the quota.
"""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.models.ai_usage import AIUsageLog
from app.database.models.user import User
from app.database.session import get_db
from app.services.auth import get_current_user
from app.services.rate_limit import get_plan_limits

router = APIRouter(prefix="/api/ai", tags=["ai-grant"])

settings = get_settings()

GRANT_EXPIRE_MINUTES = 5
GRANT_ALGORITHM = settings.JWT_ALGORITHM

# In-memory store of consumed grant IDs for single-use enforcement.
# Grants expire in 5 minutes, so entries are cleaned up after 10 minutes.
_consumed_grants: dict[str, float] = {}
_consumed_lock = threading.Lock()


def _cleanup_consumed() -> None:
    now = time.time()
    with _consumed_lock:
        expired = [gid for gid, ts in _consumed_grants.items() if now - ts > 600]
        for gid in expired:
            _consumed_grants.pop(gid, None)


def _create_grant_token(user_id: int, grant_id: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=GRANT_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "jti": grant_id,
        "iat": datetime.now(UTC),
        "exp": expire,
        "type": "ai_grant",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=GRANT_ALGORITHM)


def _decode_grant_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[GRANT_ALGORITHM])
    except jwt.PyJWTError:
        return None


class AuthorizeResponse(BaseModel):
    granted: bool
    grant_token: str
    grant_id: str
    quota_used: int
    quota_limit: int
    quota_remaining: int
    expires_in_seconds: int


class ReportRequest(BaseModel):
    grant_id: str
    grant_token: str
    success: bool = True
    actions_executed: int = 0


class ReportResponse(BaseModel):
    reported: bool
    quota_used: int
    quota_limit: int
    quota_remaining: int


@router.post("/authorize", response_model=AuthorizeResponse)
def authorize_ai_cycle(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AuthorizeResponse:
    """Issue a short-lived, single-use grant for one AI agent cycle.

    Validates:
    - User JWT is valid (via get_current_user)
    - User subscription is active
    - Daily AI request quota not exceeded

    Returns a signed grant token with a 5-minute expiry.
    """
    _cleanup_consumed()

    limits = get_plan_limits(current_user.subscription)
    max_per_day = limits["max_ai_requests_per_day"]

    today = datetime.now(UTC).date()
    usage = db.execute(
        select(AIUsageLog).where(
            AIUsageLog.user_id == current_user.id,
            AIUsageLog.date == today,
        )
    ).scalar_one_or_none()

    used = usage.request_count if usage else 0

    if used >= max_per_day:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Cuota diaria de IA agotada ({used}/{max_per_day}). Reinicia mañana.",
        )

    grant_id = str(uuid4())
    grant_token = _create_grant_token(current_user.id, grant_id)

    return AuthorizeResponse(
        granted=True,
        grant_token=grant_token,
        grant_id=grant_id,
        quota_used=used,
        quota_limit=max_per_day,
        quota_remaining=max_per_day - used,
        expires_in_seconds=GRANT_EXPIRE_MINUTES * 60,
    )


@router.post("/report", response_model=ReportResponse)
def report_ai_usage(
    req: ReportRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ReportResponse:
    """Report AI cycle completion and consume the grant.

    - Verifies the grant token is valid and not expired
    - Verifies the grant has not already been consumed (single-use)
    - Increments the daily usage counter
    """
    _cleanup_consumed()

    # Decode and validate the grant token
    payload = _decode_grant_token(req.grant_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Grant token inválido o expirado",
        )

    if payload.get("type") != "ai_grant":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token no es un grant de IA",
        )

    if payload.get("jti") != req.grant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Grant ID no coincide con el token",
        )

    if str(payload.get("sub")) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Grant no pertenece a este usuario",
        )

    # Check single-use: has this grant already been consumed?
    with _consumed_lock:
        if req.grant_id in _consumed_grants:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Grant ya fue consumido (single-use)",
            )
        _consumed_grants[req.grant_id] = time.time()

    # DB-backed single-use check: survives server restarts (anti-replay)
    today = datetime.now(UTC).date()
    existing = db.execute(
        select(AIUsageLog).where(
            AIUsageLog.user_id == current_user.id,
            AIUsageLog.last_grant_id == req.grant_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Grant ya fue consumido (single-use, DB check)",
        )

    # Only count successful cycles
    if not req.success:
        limits = get_plan_limits(current_user.subscription)
        today = datetime.now(UTC).date()
        usage = db.execute(
            select(AIUsageLog).where(
                AIUsageLog.user_id == current_user.id,
                AIUsageLog.date == today,
            )
        ).scalar_one_or_none()
        used = usage.request_count if usage else 0
        return ReportResponse(
            reported=False,
            quota_used=used,
            quota_limit=limits["max_ai_requests_per_day"],
            quota_remaining=limits["max_ai_requests_per_day"] - used,
        )

    # Increment daily usage
    today = datetime.now(UTC).date()
    usage = db.execute(
        select(AIUsageLog).where(
            AIUsageLog.user_id == current_user.id,
            AIUsageLog.date == today,
        )
    ).scalar_one_or_none()

    if not usage:
        usage = AIUsageLog(
            user_id=current_user.id,
            date=today,
            request_count=0,
        )
        db.add(usage)

    usage.request_count += 1
    usage.last_grant_id = req.grant_id
    db.commit()

    limits = get_plan_limits(current_user.subscription)
    return ReportResponse(
        reported=True,
        quota_used=usage.request_count,
        quota_limit=limits["max_ai_requests_per_day"],
        quota_remaining=limits["max_ai_requests_per_day"] - usage.request_count,
    )


@router.get("/quota")
def get_ai_quota(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Check current daily AI quota usage without requesting a grant."""
    limits = get_plan_limits(current_user.subscription)
    max_per_day = limits["max_ai_requests_per_day"]

    today = datetime.now(UTC).date()
    usage = db.execute(
        select(AIUsageLog).where(
            AIUsageLog.user_id == current_user.id,
            AIUsageLog.date == today,
        )
    ).scalar_one_or_none()

    used = usage.request_count if usage else 0
    return {
        "quota_used": used,
        "quota_limit": max_per_day,
        "quota_remaining": max_per_day - used,
        "subscription": current_user.subscription,
    }
