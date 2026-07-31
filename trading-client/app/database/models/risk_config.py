"""RiskConfig model — per-user risk management configuration persisted in DB."""

from datetime import datetime
from typing import Literal

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


# Default risk config values (same as the old in-memory _risk_config)
DEFAULTS = {
    "trailing_stop_pct": 2.0,
    "hard_stop_loss_pct": 3.0,
    "take_profit_pct": 6.0,
    "max_position_size_pct": 10.0,
    "max_open_positions": 5,
    "daily_loss_limit_pct": 5.0,
    "circuit_breaker_enabled": True,
    "auto_sell_rsi_overbought": 70.0,
    "auto_sell_max_position_hours": 24.0,
    "auto_sell_min_volume_relative": 0.5,
    "auto_sell_macd_bearish": True,
    "auto_sell_rsi_enabled": True,
    "auto_sell_time_enabled": True,
    "auto_sell_volume_enabled": True,
}


class RiskConfig(Base):
    """Per-user risk management configuration.

    Replaces the old in-memory _risk_config dict so that each user
    has their own persistent risk settings.
    """

    __tablename__ = "risk_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)

    trailing_stop_pct: Mapped[float] = mapped_column(Float, nullable=False, default=2.0)
    hard_stop_loss_pct: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    take_profit_pct: Mapped[float] = mapped_column(Float, nullable=False, default=6.0)
    max_position_size_pct: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)
    max_open_positions: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    daily_loss_limit_pct: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    circuit_breaker_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    auto_sell_rsi_overbought: Mapped[float] = mapped_column(Float, nullable=False, default=70.0)
    auto_sell_max_position_hours: Mapped[float] = mapped_column(Float, nullable=False, default=24.0)
    auto_sell_min_volume_relative: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    auto_sell_macd_bearish: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_sell_rsi_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_sell_time_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_sell_volume_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), server_default=func.now(), onupdate=func.now()
    )
