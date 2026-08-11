"""Social trading — follow relationships and copy trades."""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class SocialFollow(Base):
    """Relación de follow: un usuario sigue/copia a un líder."""

    __tablename__ = "social_follows"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    follower_id: Mapped[int] = mapped_column(nullable=False, default=0)
    leader_id: Mapped[int] = mapped_column(nullable=False)  # FK a social_leaders.id

    # Configuración de copy
    auto_copy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    copy_pct: Mapped[float] = mapped_column(nullable=False, default=100.0)  # % del capital a asignar
    max_positions: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    symbol_filter: Mapped[str] = mapped_column(String(500), nullable=False, default="")  # "BTC,ETH" = solo esos
    max_drawdown_pct: Mapped[float] = mapped_column(nullable=False, default=20.0)  # auto-stop si pierde >20%

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

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
        Index("ix_social_follows_follower_id", "follower_id"),
        Index("ix_social_follows_leader_id", "leader_id"),
        Index("ix_social_follows_active", "active"),
    )


class SocialCopyTrade(Base):
    """Trade copiado por un follower (auditoría)."""

    __tablename__ = "social_copy_trades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    follow_id: Mapped[int] = mapped_column(nullable=False)
    signal_id: Mapped[int] = mapped_column(nullable=False)  # FK a social_signals.id
    follower_id: Mapped[int] = mapped_column(nullable=False, default=0)
    leader_id: Mapped[int] = mapped_column(nullable=False)

    # Datos del trade copiado
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    size_usd: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)

    # Broker del follower (puede ser diferente al del líder)
    broker_id: Mapped[str] = mapped_column(String(50), nullable=False, default="binance")
    broker_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Estado: pending, executed, failed, closed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    pnl: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False, default=Decimal("0"))
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_social_copy_trades_follow_id", "follow_id"),
        Index("ix_social_copy_trades_signal_id", "signal_id"),
        Index("ix_social_copy_trades_follower_id", "follower_id"),
        Index("ix_social_copy_trades_leader_id", "leader_id"),
        Index("ix_social_copy_trades_status", "status"),
    )
