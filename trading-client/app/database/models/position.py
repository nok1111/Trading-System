from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Position(Base):
    """Posición abierta o cerrada en un símbolo."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(nullable=False, default=0, index=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # long, short
    quantity: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)
    take_profit: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)
    unrealized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(19, 8), nullable=False, default=Decimal("0")
    )
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(19, 8), nullable=False, default=Decimal("0")
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="open",  # open, closed
    )
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    auto_sell_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
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
        Index("ix_positions_symbol", "symbol"),
        Index("ix_positions_status", "status"),
        Index("ix_positions_strategy", "strategy_name"),
        Index("ix_positions_opened_at", "opened_at"),
    )
