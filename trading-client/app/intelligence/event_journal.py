"""Event Journal — stores all market intelligence events for multi-user dashboard."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.intelligence_event import IntelligenceEvent


class EventJournal:
    """Read/write service for the intelligence event journal."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        event_type: str,
        title: str,
        *,
        asset: str | None = None,
        detail: str | None = None,
        severity: str = "info",
        scope: str = "global",
        agent_source: str = "System",
        metadata: dict[str, Any] | None = None,
    ) -> IntelligenceEvent:
        """Insert a new event into the journal."""
        event = IntelligenceEvent(
            event_type=event_type,
            asset=asset,
            title=title,
            detail=detail,
            severity=severity,
            scope=scope,
            agent_source=agent_source,
            metadata_json=metadata or {},
        )
        self._session.add(event)
        self._session.commit()
        self._session.refresh(event)
        return event

    def get_since(
        self,
        since: datetime,
        *,
        asset_filter: list[str] | None = None,
        scope_filter: str | None = None,
        event_type_filter: str | None = None,
        limit: int = 50,
    ) -> list[IntelligenceEvent]:
        """Query events since a timestamp with optional filters."""
        stmt = select(IntelligenceEvent).where(IntelligenceEvent.created_at > since)
        if asset_filter:
            stmt = stmt.where(IntelligenceEvent.asset.in_(asset_filter))
        if scope_filter:
            stmt = stmt.where(IntelligenceEvent.scope == scope_filter)
        if event_type_filter:
            stmt = stmt.where(IntelligenceEvent.event_type == event_type_filter)
        stmt = stmt.order_by(IntelligenceEvent.created_at.desc()).limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def get_for_user(
        self,
        since: datetime,
        user_assets: list[str],
        *,
        limit: int = 20,
    ) -> list[IntelligenceEvent]:
        """Get events relevant to a user: global critical + asset-specific + opportunities."""
        stmt = select(IntelligenceEvent).where(IntelligenceEvent.created_at > since)

        # Build OR conditions: global critical, user assets, or new opportunities
        conditions = []
        conditions.append(
            (IntelligenceEvent.scope == "global")
            & (IntelligenceEvent.severity == "critical")
        )
        if user_assets:
            conditions.append(IntelligenceEvent.asset.in_(user_assets))
        conditions.append(IntelligenceEvent.event_type == "new_opportunity")

        from sqlalchemy import or_
        stmt = stmt.where(or_(*conditions))
        stmt = stmt.order_by(IntelligenceEvent.created_at.desc()).limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def get_recent(self, *, hours: int = 24, limit: int = 20) -> list[IntelligenceEvent]:
        """Get recent events for the activity timeline."""
        since = datetime.now(UTC) - timedelta(hours=hours)
        stmt = (
            select(IntelligenceEvent)
            .where(IntelligenceEvent.created_at > since)
            .order_by(IntelligenceEvent.created_at.desc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars().all())
