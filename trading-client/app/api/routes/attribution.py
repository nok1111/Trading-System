"""Performance Attribution endpoints.

Endpoints:
  GET /api/attribution          — get performance attribution
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.services.auth import LocalUser, get_current_user
from app.services.performance_attribution import get_performance_attribution

router = APIRouter(prefix="/api/attribution", tags=["attribution"])


@router.get("")
def attribution(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> dict:
    """Get performance attribution for the current user's portfolio.

    Breaks down returns by asset, broker, and strategy.
    """
    return get_performance_attribution(current_user.id, days)
