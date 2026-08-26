"""Smart Alerts endpoints — AI-powered proactive alerts.

Endpoints:
  GET  /api/smart-alerts          — get generated alerts
  POST /api/smart-alerts/dismiss  — dismiss an alert
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.services.auth import LocalUser, get_current_user
from app.services.smart_alerts import dismiss_alert, generate_smart_alerts

router = APIRouter(prefix="/api/smart-alerts", tags=["smart-alerts"])


class DismissRequest(BaseModel):
    alert_id: str


@router.get("")
def get_alerts(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Get AI-powered smart alerts for the current user.

    Alerts are generated dynamically from portfolio analysis, market regime,
    and risk checks. Sorted by urgency (highest first).
    """
    return generate_smart_alerts(current_user.id)


@router.post("/dismiss")
def dismiss(
    req: DismissRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Dismiss a smart alert so it doesn't reappear."""
    return dismiss_alert(current_user.id, req.alert_id)
