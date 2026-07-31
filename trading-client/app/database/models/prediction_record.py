"""Registro de predicciones ML para feedback en paper trading."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class PredictionRecord(Base):
    """Cada prediccion que hace MLStrategy durante paper trading."""

    __tablename__ = "prediction_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY, SELL, HOLD
    probability: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal("0"))
    price_at_prediction: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    forward_window: Mapped[int] = mapped_column(nullable=False, default=5)
    strategy_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("strategy_runs.id"), nullable=True, index=True
    )
    evaluated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    actual_direction: Mapped[str | None] = mapped_column(String(10), nullable=True)  # UP, DOWN
    correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    price_at_evaluation: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)
    evaluated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_prediction_records_timestamp", "timestamp"),
        Index("ix_prediction_records_symbol", "symbol"),
        Index("ix_prediction_records_evaluated", "evaluated"),
    )
