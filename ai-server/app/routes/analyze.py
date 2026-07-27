"""Endpoints /v1/agents and /v1/usage — agent listing and token usage.

The legacy /v1/analyze endpoint has been removed in favor of the
Intelligence Platform scheduler + /v1/intelligence/* endpoints.
"""

from __future__ import annotations

import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.config import get_settings
from app.services.intelligence_agents import list_intelligence_agents
from app.services.token_accounting import get_all_usage, get_user_usage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["ai-analysis"])
settings = get_settings()


# --- JWT Validation ---

def _validate_jwt(jwt_token: str) -> dict | None:
    """Validate JWT against the Auth Server."""
    try:
        resp = httpx.post(
            f"{settings.AUTH_SERVER_URL}/api/license/validate",
            headers={"Authorization": f"Bearer {jwt_token}"},
            timeout=10.0,
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as exc:
        logger.error(f"JWT validation failed: {exc}")
        return None


# --- Dependencies ---

async def verify_jwt(authorization: Annotated[str | None, Header()] = None) -> dict:
    """Verify JWT token from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    token = authorization.removeprefix("Bearer ")
    payload = _validate_jwt(token)
    if not payload or not payload.get("valid"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT invalid or expired",
        )
    return payload


# --- Endpoints ---

@router.get("/agents")
async def list_agents() -> dict:
    """List available intelligence agents."""
    return {"agents": list_intelligence_agents()}


@router.get("/usage/{user_id_hash}")
async def get_usage(
    user_id_hash: str,
    user: Annotated[dict, Depends(verify_jwt)],
) -> dict:
    """Get token usage for a user."""
    return get_user_usage(user_id_hash)


@router.get("/usage")
async def get_all_usage_endpoint(
    user: Annotated[dict, Depends(verify_jwt)],
) -> dict:
    """Get token usage for all users (admin only)."""
    if user.get("subscription") != "premium":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return get_all_usage()
