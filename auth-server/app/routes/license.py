"""License validation endpoint — used by the Trading Client to verify subscriptions."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.database.models.user import User
from app.services.auth import get_current_user
from app.services.rate_limit import get_plan_limits

router = APIRouter(prefix="/api/license", tags=["license"])


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
