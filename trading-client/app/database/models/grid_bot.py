"""Modelo de Grid Bot — estrategia de grid trading para cualquier exchange via CCXT."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class GridBot(Base):
    """Bot de grid trading que coloca órdenes de compra y venta en niveles de precio.

    Funciona en rango: divide [lower_price, upper_price] en N niveles.
    Coloca buy orders abajo, sell orders arriba.
    Cuando un buy se ejecuta, coloca un sell en el nivel superior.
    Cuando un sell se ejecuta, coloca un buy en el nivel inferior.
    """

    __tablename__ = "grid_bots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    broker_id: Mapped[str] = mapped_column(String(50), nullable=False, default="binance")
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)  # BTC/USDT (CCXT format)
    market_type: Mapped[str] = mapped_column(String(10), nullable=False, default="spot")  # spot, future

    # Grid parameters
    lower_price: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    upper_price: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    grid_count: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    investment_usd: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="stopped")  # running, stopped, error

    # Tracking
    orders_placed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    orders_filled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False, default=Decimal("0"))
    last_run_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Grid state (which levels have buy/sell orders, filled entries)
    grid_state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

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
        Index("ix_grid_bots_symbol", "symbol"),
        Index("ix_grid_bots_status", "status"),
        Index("ix_grid_bots_user_id", "user_id"),
    )


class DCABot(Base):
    """Bot de Dollar Cost Averaging — compra periódica de un símbolo.

    Compra una cantidad fija de USD cada X intervalo.
    Reduce el impacto de la volatilidad promediando el precio de entrada.
    """

    __tablename__ = "dca_bots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    broker_id: Mapped[str] = mapped_column(String(50), nullable=False, default="binance")
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)  # BTC/USDT
    market_type: Mapped[str] = mapped_column(String(10), nullable=False, default="spot")

    # DCA parameters
    buy_amount_usd: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=1440)  # 1440 = daily
    max_buys: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0 = unlimited
    take_profit_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0")
    )  # 0 = no TP

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="stopped")

    # Tracking
    buys_executed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_invested: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False, default=Decimal("0"))
    total_quantity: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False, default=Decimal("0"))
    avg_entry_price: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False, default=Decimal("0"))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False, default=Decimal("0"))
    last_buy_at: Mapped[datetime | None] = mapped_column(nullable=True)

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
        Index("ix_dca_bots_symbol", "symbol"),
        Index("ix_dca_bots_status", "status"),
        Index("ix_dca_bots_user_id", "user_id"),
    )
