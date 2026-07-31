from datetime import datetime

from sqlalchemy import Boolean, Float, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class PriceAlert(Base):
    """Persistent price alert stored in DB, per user."""

    __tablename__ = "price_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    condition: Mapped[str] = mapped_column(String(10), nullable=False)  # above, below
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    triggered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=func.now(), server_default=func.now())
    triggered_at: Mapped[datetime | None] = mapped_column(nullable=True)
    triggered_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("ix_price_alerts_user", "user_id"),
        Index("ix_price_alerts_triggered", "triggered"),
    )
