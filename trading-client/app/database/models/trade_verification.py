"""Trade Verification — HMAC-signed trades for social trading verification.

Each trade published by a leader is signed with HMAC-SHA256 using the broker
API key as the secret. Followers can verify that trades are real and came
from the actual broker, not fabricated.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class TradeVerification(Base):
    """HMAC signature of a trade for verification purposes."""

    __tablename__ = "trade_verifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_id: Mapped[int | None] = mapped_column(
        ForeignKey("trades.id"), nullable=True, index=True
    )
    leader_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    broker_id: Mapped[str] = mapped_column(String(50), nullable=False, default="binance")
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[str] = mapped_column(String(30), nullable=False)
    price: Mapped[str] = mapped_column(String(30), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    hmac_signature: Mapped[str] = mapped_column(String(128), nullable=False)
    broker_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_trade_verif_leader", "leader_id"),
        Index("ix_trade_verif_broker", "broker_id"),
        Index("ix_trade_verif_verified", "verified"),
    )
