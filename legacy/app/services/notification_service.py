"""Notification service — create, fetch, and manage user notifications."""

import logging
from datetime import datetime, UTC
from typing import Any

from sqlalchemy import desc, func, select, update
from sqlalchemy.orm import Session

from app.database.models.notification import Notification

logger = logging.getLogger(__name__)


def create_notification(
    session: Session,
    *,
    type: str,
    title: str,
    message: str = "",
    severity: str = "info",
    asset: str | None = None,
    action_url: str | None = None,
    metadata: dict | None = None,
    user_id: int = 0,
) -> Notification | None:
    """Create a notification and persist it to the DB."""
    try:
        notif = Notification(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            severity=severity,
            asset=asset,
            action_url=action_url,
            metadata_json=metadata or {},
        )
        session.add(notif)
        session.commit()
        session.refresh(notif)
        return notif
    except Exception as exc:
        logger.warning("Failed to create notification: %s", exc)
        session.rollback()
        return None


def get_notifications(
    session: Session,
    *,
    user_id: int = 0,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Fetch notifications for a user, newest first."""
    query = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(desc(Notification.created_at))
    )
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    query = query.limit(limit).offset(offset)

    rows = session.execute(query).scalars().all()
    return [_to_dict(n) for n in rows]


def get_unread_count(session: Session, *, user_id: int = 0) -> int:
    """Get the count of unread notifications for the badge."""
    result = session.execute(
        select(func.count(Notification.id))
        .where(Notification.user_id == user_id)
        .where(Notification.read_at.is_(None))
    )
    return int(result.scalar() or 0)


def mark_read(session: Session, notif_id: int, *, user_id: int = 0) -> bool:
    """Mark a single notification as read."""
    result = session.execute(
        update(Notification)
        .where(Notification.id == notif_id)
        .where(Notification.user_id == user_id)
        .values(read_at=datetime.now(UTC))
    )
    session.commit()
    return result.rowcount > 0


def mark_all_read(session: Session, *, user_id: int = 0) -> int:
    """Mark all unread notifications as read for a user. Returns count updated."""
    result = session.execute(
        update(Notification)
        .where(Notification.user_id == user_id)
        .where(Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    session.commit()
    return result.rowcount


def _to_dict(n: Notification) -> dict[str, Any]:
    """Serialize a Notification to a dict for the API."""
    return {
        "id": n.id,
        "type": n.type,
        "title": n.title,
        "message": n.message,
        "severity": n.severity,
        "asset": n.asset,
        "action_url": n.action_url,
        "metadata": n.metadata_json if isinstance(n.metadata_json, dict) else {},
        "read": n.read_at is not None,
        "timestamp": n.created_at.isoformat() if n.created_at else "",
    }
