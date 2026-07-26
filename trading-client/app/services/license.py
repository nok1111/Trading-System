"""License validation service — validates JWT against the Auth Server."""

from __future__ import annotations

import httpx

from app.config import get_settings


def validate_license(jwt_token: str) -> dict | None:
    """Validate the user's JWT against the Auth Server.

    Returns:
        dict with {valid, user_id, email, subscription, plan_limits} if valid.
        None if the token is invalid, expired, or the Auth Server is unreachable.
    """
    settings = get_settings()
    try:
        resp = httpx.post(
            f"{settings.AUTH_SERVER_URL}/api/license/validate",
            headers={"Authorization": f"Bearer {jwt_token}"},
            timeout=10.0,
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


def check_auth_server_health() -> bool:
    """Check if the Auth Server is reachable."""
    settings = get_settings()
    try:
        resp = httpx.get(f"{settings.AUTH_SERVER_URL}/health", timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False


def request_ai_grant(jwt_token: str) -> dict | None:
    """Request a short-lived, signed grant from the Auth Server for one AI cycle.

    Returns:
        dict with {granted, grant_token, grant_id, quota_used, quota_limit,
                   quota_remaining, expires_in_seconds} if successful.
        None if the grant could not be obtained (quota exhausted, auth failed,
        or server unreachable).
    """
    settings = get_settings()
    try:
        resp = httpx.post(
            f"{settings.AUTH_SERVER_URL}/api/ai/authorize",
            headers={"Authorization": f"Bearer {jwt_token}"},
            timeout=10.0,
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


def report_ai_usage(
    jwt_token: str, grant_id: str, grant_token: str, success: bool = True
) -> dict | None:
    """Report AI cycle completion to the Auth Server to consume the grant.

    Returns:
        dict with {reported, quota_used, quota_limit, quota_remaining} if successful.
        None if the report failed.
    """
    settings = get_settings()
    try:
        resp = httpx.post(
            f"{settings.AUTH_SERVER_URL}/api/ai/report",
            headers={"Authorization": f"Bearer {jwt_token}"},
            json={
                "grant_id": grant_id,
                "grant_token": grant_token,
                "success": success,
            },
            timeout=10.0,
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None
