"""AgentSession model — tracks AI agent start/stop sessions per user."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AgentSession(Base):
    """A trading session of the AI agent.

    Records when the agent started, stopped, what mode it ran in,
    how many cycles it completed, and how many trades it executed.
    """

    __tablename__ = "agent_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    mode: Mapped[str] = mapped_column(String(10), nullable=False, default="paper")
    # paper, live
    broker_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    auto_trade: Mapped[bool] = mapped_column(nullable=False, default=True)
    cycle_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trades_executed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    # running, stopped, crashed
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_agent_sessions_user_started", "user_id", "started_at"),
    )
