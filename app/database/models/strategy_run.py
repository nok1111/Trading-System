from datetime import datetime

from sqlalchemy import JSON, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class StrategyRun(Base):
    """Ejecución concreta de una estrategia en un modo dado."""

    __tablename__ = "strategy_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False)
    mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="backtest"
    )  # backtest, paper, live
    started_at: Mapped[datetime] = mapped_column(nullable=False, default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="running",  # running, completed, stopped, error
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_strategy_runs_strategy_name", "strategy_name"),
        Index("ix_strategy_runs_mode", "mode"),
        Index("ix_strategy_runs_status", "status"),
    )
