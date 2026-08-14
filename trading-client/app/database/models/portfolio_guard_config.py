"""Portfolio Guard configuration — per-user risk automation settings."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class PortfolioGuardConfig(Base):
    """Per-user Portfolio Guard configuration.

    Controls automated portfolio-level risk management:
    - Correlation monitoring with auto-reduce
    - Drawdown circuit breaker with auto-close
    - Category exposure limits
    """

    __tablename__ = "portfolio_guard_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)

    # Master toggle
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # "manual" = suggestions only, "auto" = execute actions automatically
    mode: Mapped[str] = mapped_column(String(10), nullable=False, default="manual")

    # Thresholds
    max_correlation: Mapped[float] = mapped_column(Float, nullable=False, default=0.85)
    max_drawdown_pct: Mapped[float] = mapped_column(Float, nullable=False, default=15.0)
    max_category_exposure: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    auto_close_worst: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Tracking
    last_check: Mapped[datetime | None] = mapped_column(nullable=True)
    actions_taken: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

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
        Index("ix_portfolio_guard_user", "user_id"),
    )
