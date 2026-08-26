"""Audit log endpoints — query security audit trail.

Endpoints:
  GET  /api/audit/logs       — query audit logs with filters
  GET  /api/audit/summary    — get audit summary for monitoring
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.services.audit_log import get_audit_logs, get_audit_summary
from app.services.auth import LocalUser, get_current_user

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/logs")
def list_logs(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    source: Annotated[str | None, Query(description="Filter by source (auth, broker, trading, etc.)")] = None,
    level: Annotated[str | None, Query(description="Filter by level (info, warning, error, critical)")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    """Query audit logs for the current user.

    Results are sorted by timestamp descending (newest first).
    """
    return get_audit_logs(
        user_id=current_user.id,
        source=source,
        level=level,
        limit=limit,
        offset=offset,
    )


@router.get("/summary")
def summary(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
) -> dict:
    """Get audit summary for the current user.

    Returns event counts by level and source, plus recent critical events.
    """
    return get_audit_summary(user_id=current_user.id, hours=hours)
