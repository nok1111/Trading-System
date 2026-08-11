"""Social trading — signals published by leaders."""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import JSON, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class SocialSignal(Base):
    """Señal publicada por un líder para que los followers la copien."""

    __tablename__ = "social_signals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    leader_id: Mapped[int] = mapped_column(nullable=False)  # FK a social_leaders.id
    user_id: Mapped[int] = mapped_column(nullable=False, default=0)

    # Datos de la señal (normalizados, cross-broker)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)  # ej: BTCUSDT
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY, SELL, CLOSE
    size_pct: Mapped[float] = mapped_column(nullable=False, default=5.0)  # % del portfolio

    # Precios de referencia
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)
    take_profit: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)

    # Broker del líder (informativo)
    broker_id: Mapped[str] = mapped_column(String(50), nullable=False, default="binance")

    # Estado: active, closed, cancelled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    # Resultado (cuando se cierra)
    close_price: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)
    pnl_pct: Mapped[float] = mapped_column(nullable=False, default=0.0)

    # Metadata
    comment: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_social_signals_leader_id", "leader_id"),
        Index("ix_social_signals_user_id", "user_id"),
        Index("ix_social_signals_status", "status"),
        Index("ix_social_signals_symbol", "symbol"),
        Index("ix_social_signals_created_at", "created_at"),
    )
