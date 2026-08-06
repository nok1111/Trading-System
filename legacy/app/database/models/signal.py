from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Signal(Base):
    """Señal generada por una estrategia antes de pasar por riesgo/ejecución."""

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    signal_type: Mapped[str] = mapped_column(
        String(10), nullable=False, default="HOLD"
    )  # BUY, SELL, HOLD
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal("0"))
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)
    suggested_stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)
    suggested_take_profit: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False)
    explanation: Mapped[str | None] = mapped_column(nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="generated",  # generated, sent, rejected, executed
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_signals_timestamp", "timestamp"),
        Index("ix_signals_symbol", "symbol"),
        Index("ix_signals_strategy", "strategy_name"),
        Index("ix_signals_status", "status"),
    )
