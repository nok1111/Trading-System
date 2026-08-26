"""Audit Log Service — records security-relevant actions for compliance.

Logs events like:
- Login/logout
- API key validation
- Broker connect/disconnect
- Order placement/cancellation
- Settings changes
- 2FA enable/disable
- Session creation/revocation

All audit logs are persisted to the SystemEvent table and can be queried
for compliance and security review.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database.models.system_event import SystemEvent
from app.database.session import SessionLocal

logger = logging.getLogger(__name__)

# Audit event sources
SOURCES = {
    "auth": "Authentication",
    "broker": "Broker Management",
    "trading": "Trading",
    "security": "Security",
    "settings": "Settings",
    "copilot": "AI Copilot",
    "api": "API Access",
}

# Audit event levels
LEVELS = ("info", "warning", "error", "critical")


def log_audit(
    user_id: int,
    source: str,
    message: str,
    level: str = "info",
    details: dict[str, Any] | None = None,
) -> SystemEvent | None:
    """Record an audit log entry.

    Args:
        user_id: User ID (0 for system events)
        source: Event source (auth, broker, trading, security, settings, copilot, api)
        message: Human-readable event description
        level: info, warning, error, or critical
        details: Optional structured details (JSON)

    Returns:
        The created SystemEvent, or None if logging failed
    """
    if level not in LEVELS:
        level = "info"

    db = SessionLocal()
    try:
        event = SystemEvent(
            user_id=user_id,
            timestamp=datetime.now(tz=UTC).replace(tzinfo=None),
            level=level,
            source=source,
            message=message,
            details=details or {},
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event
    except Exception as exc:
        logger.warning("Failed to write audit log: %s", exc)
        db.rollback()
        return None
    finally:
        db.close()


def get_audit_logs(
    user_id: int | None = None,
    source: str | None = None,
    level: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Query audit logs with optional filters.

    Args:
        user_id: Filter by user (None = all users)
        source: Filter by source (auth, broker, etc.)
        level: Filter by level (info, warning, error, critical)
        limit: Max results (default 100, max 500)
        offset: Pagination offset

    Returns:
        {
            "logs": [{...}],
            "total": int,
            "limit": int,
            "offset": int,
        }
    """
    limit = min(limit, 500)
    db = SessionLocal()
    try:
        query = db.query(SystemEvent)

        if user_id is not None:
            query = query.filter(SystemEvent.user_id == user_id)
        if source:
            query = query.filter(SystemEvent.source == source)
        if level:
            query = query.filter(SystemEvent.level == level)

        total = query.count()
        logs = (
            query.order_by(desc(SystemEvent.timestamp))
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "logs": [
                {
                    "id": log.id,
                    "user_id": log.user_id,
                    "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                    "level": log.level,
                    "source": log.source,
                    "message": log.message,
                    "details": log.details,
                }
                for log in logs
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except Exception as exc:
        logger.warning("Failed to query audit logs: %s", exc)
        return {"logs": [], "total": 0, "limit": limit, "offset": offset}
    finally:
        db.close()


def get_audit_summary(user_id: int | None = None, hours: int = 24) -> dict[str, Any]:
    """Get a summary of audit events for monitoring.

    Args:
        user_id: Filter by user (None = all users)
        hours: Look back window in hours

    Returns:
        {
            "total_events": int,
            "by_level": {"info": N, "warning": N, "error": N, "critical": N},
            "by_source": {"auth": N, "broker": N, ...},
            "recent_critical": [...],
        }
    """
    db = SessionLocal()
    try:
        from datetime import timedelta

        since = datetime.now(tz=UTC).replace(tzinfo=None) - timedelta(hours=hours)
        query = db.query(SystemEvent).filter(SystemEvent.timestamp >= since)

        if user_id is not None:
            query = query.filter(SystemEvent.user_id == user_id)

        all_logs = query.all()

        by_level: dict[str, int] = {"info": 0, "warning": 0, "error": 0, "critical": 0}
        by_source: dict[str, int] = {}
        recent_critical: list[dict] = []

        for log in all_logs:
            by_level[log.level] = by_level.get(log.level, 0) + 1
            by_source[log.source] = by_source.get(log.source, 0) + 1
            if log.level == "critical":
                recent_critical.append({
                    "id": log.id,
                    "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                    "source": log.source,
                    "message": log.message,
                })

        return {
            "total_events": len(all_logs),
            "by_level": by_level,
            "by_source": by_source,
            "recent_critical": recent_critical[:10],
            "hours": hours,
        }
    except Exception as exc:
        logger.warning("Failed to get audit summary: %s", exc)
        return {
            "total_events": 0,
            "by_level": {"info": 0, "warning": 0, "error": 0, "critical": 0},
            "by_source": {},
            "recent_critical": [],
            "hours": hours,
        }
    finally:
        db.close()


# Convenience functions for common audit events
def log_login(user_id: int, success: bool, ip: str | None = None) -> None:
    log_audit(
        user_id=user_id,
        source="auth",
        message=f"Login {'succeeded' if success else 'failed'}",
        level="info" if success else "warning",
        details={"ip": ip} if ip else None,
    )


def log_logout(user_id: int) -> None:
    log_audit(user_id=user_id, source="auth", message="User logged out")


def log_broker_connect(user_id: int, broker_id: str, success: bool, error: str | None = None) -> None:
    log_audit(
        user_id=user_id,
        source="broker",
        message=f"Broker connect {'succeeded' if success else 'failed'}: {broker_id}",
        level="info" if success else "warning",
        details={"broker_id": broker_id, "error": error} if error else {"broker_id": broker_id},
    )


def log_broker_disconnect(user_id: int, broker_id: str) -> None:
    log_audit(
        user_id=user_id,
        source="broker",
        message=f"Broker disconnected: {broker_id}",
        details={"broker_id": broker_id},
    )


def log_order_placed(user_id: int, broker_id: str, symbol: str, side: str, quantity: float, order_type: str) -> None:
    log_audit(
        user_id=user_id,
        source="trading",
        message=f"Order placed: {side} {quantity} {symbol} on {broker_id} ({order_type})",
        details={
            "broker_id": broker_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": order_type,
        },
    )


def log_order_cancelled(user_id: int, broker_id: str, order_id: str, symbol: str) -> None:
    log_audit(
        user_id=user_id,
        source="trading",
        message=f"Order cancelled: {order_id} {symbol} on {broker_id}",
        level="warning",
        details={"broker_id": broker_id, "order_id": order_id, "symbol": symbol},
    )


def log_2fa_change(user_id: int, enabled: bool) -> None:
    log_audit(
        user_id=user_id,
        source="security",
        message=f"2FA {'enabled' if enabled else 'disabled'}",
        level="warning" if not enabled else "info",
        details={"enabled": enabled},
    )


def log_settings_change(user_id: int, setting: str, old_value: Any, new_value: Any) -> None:
    log_audit(
        user_id=user_id,
        source="settings",
        message=f"Setting changed: {setting}",
        details={"setting": setting, "old": str(old_value), "new": str(new_value)},
    )
