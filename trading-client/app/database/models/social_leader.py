"""Social trading — leader profile and stats."""

from datetime import datetime
from sqlalchemy import Boolean, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class SocialLeader(Base):
    """Perfil público de un trader que publica señales para copy trading."""

    __tablename__ = "social_leaders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(nullable=False, default=0, index=True)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    bio: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    avatar_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Broker que usa el líder (informativo — las señales son cross-broker)
    broker_id: Mapped[str] = mapped_column(String(50), nullable=False, default="binance")

    # Visibilidad
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Configuración de copy trading
    fee_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_copy_amount_usd: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    # Stats cache (actualizado por scheduler)
    roi_30d: Mapped[float] = mapped_column(nullable=False, default=0.0)
    roi_90d: Mapped[float] = mapped_column(nullable=False, default=0.0)
    roi_all: Mapped[float] = mapped_column(nullable=False, default=0.0)
    win_rate: Mapped[float] = mapped_column(nullable=False, default=0.0)
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_followers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_drawdown: Mapped[float] = mapped_column(nullable=False, default=0.0)
    sharpe_ratio: Mapped[float] = mapped_column(nullable=False, default=0.0)
    open_positions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stats_updated_at: Mapped[datetime | None] = mapped_column(nullable=True)

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
        Index("ix_social_leaders_user_id", "user_id"),
        Index("ix_social_leaders_is_public", "is_public"),
    )
