from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class BacktestRun(Base):
    """Resultado completo de una corrida de backtesting."""

    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False)
    symbols: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    start_date: Mapped[date] = mapped_column(nullable=False)
    end_date: Mapped[date] = mapped_column(nullable=False)
    initial_cash: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    final_equity: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)
    total_return_percent: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    annualized_return_percent: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    sharpe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    sortino_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    max_drawdown_percent: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    win_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    profit_factor: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    expectancy: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    total_trades: Mapped[int] = mapped_column(nullable=False, default=0)
    avg_position_duration: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    avg_exposure: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_backtest_runs_strategy_name", "strategy_name"),
        Index("ix_backtest_runs_start_date", "start_date"),
        Index("ix_backtest_runs_end_date", "end_date"),
    )
