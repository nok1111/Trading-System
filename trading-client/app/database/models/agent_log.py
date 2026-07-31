"""AgentLog model — persists AI agent cycle logs per user in DB."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AgentLog(Base):
    """A single log entry from the AI agent's execution cycle.

    Replaces the in-memory self._log list so that logs persist
    across backend restarts and are accessible per user.
    """

    __tablename__ = "agent_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), server_default=func.now()
    )
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    # info, warning, error
    message: Mapped[str] = mapped_column(Text, nullable=False)
    cycle: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_agent_logs_user_ts", "user_id", "timestamp"),
    )
