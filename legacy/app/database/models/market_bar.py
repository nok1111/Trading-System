from datetime import datetime
from decimal import Decimal

from sqlalchemy import Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class MarketBar(Base):
    """Vela OHLCV histórica o reciente."""

    __tablename__ = "market_bars"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False, default=Decimal("0"))
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_market_bars_timestamp", "timestamp"),
        Index("ix_market_bars_symbol", "symbol"),
        Index("ix_market_bars_symbol_timeframe", "symbol", "timeframe"),
        Index(
            "ix_market_bars_unique",
            "timestamp",
            "symbol",
            "timeframe",
            unique=True,
        ),
    )
