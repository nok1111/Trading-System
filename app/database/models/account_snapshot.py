from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AccountSnapshot(Base):
    """Instantánea del estado de la cuenta en un momento dado."""

    __tablename__ = "account_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    cash: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False, default=Decimal("0"))
    equity: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False, default=Decimal("0"))
    buying_power: Mapped[Decimal] = mapped_column(
        Numeric(19, 8), nullable=False, default=Decimal("0")
    )
    margin_used: Mapped[Decimal] = mapped_column(
        Numeric(19, 8), nullable=False, default=Decimal("0")
    )
    daily_pnl: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False, default=Decimal("0"))
    total_pnl: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False, default=Decimal("0"))
    open_positions_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    strategy_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("strategy_runs.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_account_snapshots_timestamp", "timestamp"),
        Index("ix_account_snapshots_strategy_run_id", "strategy_run_id"),
    )
