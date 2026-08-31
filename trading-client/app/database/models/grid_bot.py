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


class ScalpBot(Base):
    """Bot de scalping en futuros: 1 posición, ranking de volatilidad + filtro IA."""

    __tablename__ = "scalp_bots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    broker_id: Mapped[str] = mapped_column(String(50), nullable=False, default="binance")

    max_capital_usd: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False, default=Decimal("100"))
    risk_per_trade_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("20"))
    leverage: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    tp_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0.50"))
    sl_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0.35"))
    max_daily_loss_usd: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False, default=Decimal("15"))
    min_atr_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0.80"))
    max_hold_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    ai_refresh_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=180)
    use_ai_filter: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="stopped")

    last_heartbeat_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(nullable=True)

    trades_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False, default=Decimal("0"))
    daily_pnl: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False, default=Decimal("0"))
    daily_pnl_date: Mapped[str | None] = mapped_column(String(10), nullable=True)

    current_symbol: Mapped[str | None] = mapped_column(String(30), nullable=True)
    current_side: Mapped[str | None] = mapped_column(String(10), nullable=True)
    current_qty: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)
    current_entry: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)
    current_opened_at: Mapped[datetime | None] = mapped_column(nullable=True)
    current_sl: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)
    current_tp: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)

    state_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
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
        Index("ix_scalp_bots_status", "status"),
        Index("ix_scalp_bots_user_id", "user_id"),
    )


class ScalpBotLog(Base):
    """Log de eventos del scalp bot (scan, AI, buy, sell, skip, error)."""

    __tablename__ = "scalp_bot_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now()
    )
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    event: Mapped[str] = mapped_column(String(40), nullable=False, default="info")
    symbol: Mapped[str | None] = mapped_column(String(30), nullable=True)
    side: Mapped[str | None] = mapped_column(String(10), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)
    pnl: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)
    message: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    __table_args__ = (
        Index("ix_scalp_bot_logs_bot_ts", "bot_id", "timestamp"),
    )
