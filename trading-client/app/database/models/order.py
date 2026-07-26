from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Order(Base):
    """Orden enviada o simulada hacia un broker."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_order_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    broker_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY, SELL
    order_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="market"
    )  # market, limit, stop
    quantity: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    filled_quantity: Mapped[Decimal] = mapped_column(
        Numeric(19, 8), nullable=False, default=Decimal("0")
    )
    price: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="submitted",  # submitted, pending, filled, cancelled, rejected
    )
    signal_id: Mapped[int | None] = mapped_column(
        ForeignKey("signals.id"), nullable=True, index=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
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
        Index("ix_orders_symbol", "symbol"),
        Index("ix_orders_status", "status"),
        Index("ix_orders_timestamp", "timestamp"),
    )
