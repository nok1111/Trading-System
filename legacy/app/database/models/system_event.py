from datetime import datetime

from sqlalchemy import JSON, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SystemEvent(Base):
    """Evento genérico del sistema para auditoría y observabilidad."""

    __tablename__ = "system_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)  # info, warning, error, critical
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_system_events_timestamp", "timestamp"),
        Index("ix_system_events_level", "level"),
        Index("ix_system_events_source", "source"),
    )
