"""License validation endpoint — used by the Trading Client to verify subscriptions."""

import hashlib
import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from app.config import get_settings
from app.database.models.user import User
from app.services.auth import get_current_user
from app.services.rate_limit import get_plan_limits

router = APIRouter(prefix="/api/license", tags=["license"])
settings = get_settings()


class LicenseResponse(BaseModel):
    valid: bool
    user_id: int
    email: str
    username: str
    subscription: str
    plan_limits: dict


@router.post("/validate", response_model=LicenseResponse)
def validate_license(
    current_user: Annotated[User, Depends(get_current_user)],
) -> LicenseResponse:
    """Validate that the JWT is valid and the subscription is active.

    Called by the Trading Client on startup and periodically to verify
    that the user has an active subscription.

    Returns:
        valid: True if the user is active and subscription is valid
        subscription: The user's current plan (free, pro, premium)
        plan_limits: Dict with max_pairs, max_positions, features, etc.
    """
    limits = get_plan_limits(current_user.subscription)
    return LicenseResponse(
        valid=True,
        user_id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        subscription=current_user.subscription,
        plan_limits=limits,
    )


@router.post("/verify-hmac")
def verify_hmac(
    x_hmac_signature: Annotated[str | None, Header()] = None,
    x_hmac_timestamp: Annotated[str | None, Header()] = None,
    x_hmac_nonce: Annotated[str | None, Header()] = None,
) -> dict:
    """Verify HMAC signature from the AI Server (service-to-service).

    The AI Server calls this endpoint to verify that its HMAC secret is valid
    and synchronized with the Auth Server. This is used for key rotation
    and health checks.
    """
    if not x_hmac_signature or not x_hmac_timestamp or not x_hmac_nonce:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing HMAC headers",
        )

    hmac_secret = getattr(settings, "HMAC_SECRET", None)
    if not hmac_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="HMAC_SECRET not configured on server",
        )
    payload = f"{x_hmac_timestamp}\n{x_hmac_nonce}\nverify"
    expected = hmac.new(hmac_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, x_hmac_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid HMAC signature",
        )

    return {"valid": True, "service": "ai-server"}


@router.get("/check", response_model=LicenseResponse)
def check_license(
    current_user: Annotated[User, Depends(get_current_user)],
) -> LicenseResponse:
    """GET version of license validation (for simple health checks from client)."""
    limits = get_plan_limits(current_user.subscription)
    return LicenseResponse(
        valid=True,
        user_id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        subscription=current_user.subscription,
        plan_limits=limits,
    )
