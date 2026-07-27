"""Intelligence Event Journal model — stores all market intelligence events."""

from datetime import datetime

from sqlalchemy import JSON, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class IntelligenceEvent(Base):
    """Market intelligence event for the multi-user dashboard.

    Events are written by AI agents during their scheduled cycles and
    queried on-demand when a user logs in to build the 'Since Last Visit'
    and 'AI Activity' sections.
    """

    __tablename__ = "intelligence_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # consensus_change, new_opportunity, invalidated, institutional_flow,
    # risk_change, news_high_impact, macro_event, whale_move, portfolio_change
    asset: Mapped[str | None] = mapped_column(String(20), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    detail: Mapped[str | None] = mapped_column(nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    # info, warning, critical
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="global")
    # global, asset, portfolio
    agent_source: Mapped[str] = mapped_column(String(50), nullable=False, default="System")
    # Technical, News, On-chain, Contrarian, Consensus, Macro
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_intel_events_created", "created_at"),
        Index("ix_intel_events_asset", "asset"),
        Index("ix_intel_events_type", "event_type"),
        Index("ix_intel_events_scope", "scope"),
    )
