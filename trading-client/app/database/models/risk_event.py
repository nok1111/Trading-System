from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class RiskEvent(Base):
    """Evento de riesgo que bloquea, advierte o detiene el sistema."""

    __tablename__ = "risk_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(16), nullable=True)
    signal_id: Mapped[int | None] = mapped_column(
        ForeignKey("signals.id"), nullable=True, index=True
    )
    reason: Mapped[str] = mapped_column(nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="warning"
    )  # warning, block, kill
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_risk_events_timestamp", "timestamp"),
        Index("ix_risk_events_severity", "severity"),
        Index("ix_risk_events_event_type", "event_type"),
    )
