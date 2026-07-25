from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Trade(Base):
    """Ejecución real o simulada de una orden."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    commission: Mapped[Decimal] = mapped_column(
        Numeric(19, 8), nullable=False, default=Decimal("0")
    )
    slippage: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False, default=Decimal("0"))
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(19, 8), nullable=False, default=Decimal("0")
    )
    strategy_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True, index=True)
    position_id: Mapped[int | None] = mapped_column(
        ForeignKey("positions.id"), nullable=True, index=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_trades_symbol", "symbol"),
        Index("ix_trades_timestamp", "timestamp"),
    )
