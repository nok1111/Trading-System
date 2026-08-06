"""Esquemas Pydantic para respuestas de la API (FASE 6)."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class SignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    symbol: str
    signal_type: str
    confidence: Decimal
    entry_price: Decimal | None = None
    suggested_stop_loss: Decimal | None = None
    suggested_take_profit: Decimal | None = None
    strategy_name: str
    explanation: str | None = None
    status: str
    created_at: datetime


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_order_id: str
    broker_order_id: str | None = None
    timestamp: datetime
    symbol: str
    side: str
    order_type: str
    quantity: Decimal
    filled_quantity: Decimal
    price: Decimal | None = None
    status: str
    signal_id: int | None = None
    created_at: datetime


class PositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    opened_at: datetime
    closed_at: datetime | None = None
    side: str
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    status: str
    strategy_name: str
    created_at: datetime


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    commission: Decimal
    slippage: Decimal
    realized_pnl: Decimal
    order_id: int | None = None
    position_id: int | None = None
    created_at: datetime


class StrategyRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    strategy_name: str
    mode: str
    started_at: datetime
    ended_at: datetime | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class BacktestRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    strategy_name: str
    symbols: list
    start_date: date
    end_date: date
    initial_cash: Decimal
    final_equity: Decimal | None = None
    total_return_percent: Decimal | None = None
    annualized_return_percent: Decimal | None = None
    sharpe_ratio: Decimal | None = None
    sortino_ratio: Decimal | None = None
    max_drawdown_percent: Decimal | None = None
    win_rate: Decimal | None = None
    profit_factor: Decimal | None = None
    expectancy: Decimal | None = None
    total_trades: int
    created_at: datetime


class AccountSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    cash: Decimal
    equity: Decimal
    buying_power: Decimal
    margin_used: Decimal
    daily_pnl: Decimal
    total_pnl: Decimal
    open_positions_count: int
    strategy_run_id: int | None = None
    created_at: datetime


class HealthOut(BaseModel):
    status: str
    trading_mode: str
    live_trading_enabled: bool
