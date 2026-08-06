"""Local auth shim for Trading Client.

In the Trading Client, authentication is handled by the license middleware
which validates the JWT against the Auth Server and attaches license info
to request.state. This module provides a get_current_user dependency that
extracts that info, plus a simple User-like object for compatibility with
existing router code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request


@dataclass
class LocalUser:
    """Lightweight user object populated from Auth Server license validation."""

    id: int
    email: str
    username: str
    subscription: str
    risk_profile: str = "moderate"
    is_active: bool = True
    # API keys are NOT stored here — they come from local .env
    binance_api_key_enc: str | None = None
    binance_api_secret_enc: str | None = None
    ai_groq_key_enc: str | None = None
    ai_gemini_key_enc: str | None = None
    ai_premium_key_enc: str | None = None
    ai_premium_provider: str | None = None
    ai_premium_base_url: str | None = None
    ai_premium_model: str | None = None
    telegram_chat_id: str | None = None
    telegram_alerts: bool = False


def get_current_user(request: Request) -> LocalUser:
    """Extract user info from request.state (populated by license middleware).

    The license middleware validates the JWT against the Auth Server and
    attaches the license response to request.state.user.
    """
    license_info = getattr(request.state, "user", None)
    if not license_info:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado — license middleware no procesó esta request",
        )
    return LocalUser(
        id=license_info.get("user_id", 0),
        email=license_info.get("email", ""),
        username=license_info.get("username", ""),
        subscription=license_info.get("subscription", "free"),
    )


def get_optional_user(request: Request) -> LocalUser | None:
    """Like get_current_user but returns None instead of raising 401.

    Use for endpoints that work for both authenticated and anonymous users
    (e.g. public catalog endpoints that skip the license middleware).
    """
    license_info = getattr(request.state, "user", None)
    if not license_info:
        return None
    return LocalUser(
        id=license_info.get("user_id", 0),
        email=license_info.get("email", ""),
        username=license_info.get("username", ""),
        subscription=license_info.get("subscription", "free"),
    )
