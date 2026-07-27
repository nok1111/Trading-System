"""Modelos de dominio normalizados para brokers.

Todos los importes monetarios y cantidades usan Decimal. Prohibido float.
Los simbolos usan formato canonico con slash: BTC/USDT, ETH/USDT, etc.
Cada adaptador traduce al formato del broker (BTCUSDT, XBTUSDT, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class MarketType(StrEnum):
    SPOT = "spot"
    MARGIN = "margin"
    FUTURES = "futures"


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"


class OrderStatus(StrEnum):
    PENDING = "pending"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class BrokerAccountStatus(StrEnum):
    PENDING_VALIDATION = "pending_validation"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    API_KEY_INVALID = "api_key_invalid"
    RATE_LIMITED = "rate_limited"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    SECURITY_BLOCKED = "security_blocked"


@dataclass(frozen=True)
class BrokerInfo:
    """Metadatos estaticos de un broker."""

    broker_id: str
    display_name: str
    supported_markets: tuple[MarketType, ...]
    logo_url: str | None = None
    website_url: str | None = None
    api_docs_url: str | None = None


@dataclass(frozen=True)
class BrokerCredentials:
    """Credenciales normalizadas para un broker."""

    broker_id: str
    api_key: str
    api_secret: str
    passphrase: str | None = None
    testnet: bool = False
    extra: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CredentialValidationResult:
    """Resultado de validacion de credenciales."""

    valid: bool
    status: BrokerAccountStatus
    error_message: str | None = None
    permissions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Balance:
    """Saldo de un activo individual."""

    asset: str
    free: Decimal
    locked: Decimal

    @property
    def total(self) -> Decimal:
        return self.free + self.locked


@dataclass(frozen=True)
class PortfolioSnapshot:
    """Snapshot completo del portfolio en un momento dado."""

    timestamp: datetime
    balances: tuple[Balance, ...]
    total_usd: Decimal
    total_btc: Decimal | None = None


@dataclass(frozen=True)
class Position:
    """Posicion abierta en un simbolo."""

    symbol: str
    side: str
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal | None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    status: str = "open"
    strategy_name: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class OrderRequest:
    """Peticion de orden normalizada (antes de validacion)."""

    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Decimal | None = None
    stop_price: Decimal | None = None
    client_order_id: str | None = None
    time_in_force: str = "GTC"
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ValidatedOrderRequest:
    """Orden validada lista para enviar al broker."""

    symbol: str
    broker_symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Decimal | None = None
    stop_price: Decimal | None = None
    client_order_id: str | None = None
    time_in_force: str = "GTC"
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerOrder:
    """Orden devuelta por el broker tras su envio o consulta."""

    broker_order_id: str | None
    client_order_id: str | None
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    filled_quantity: Decimal
    price: Decimal | None
    status: OrderStatus
    avg_fill_price: Decimal | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class OrderExecutionResult:
    """Resultado de la ejecucion de una orden."""

    success: bool
    order: BrokerOrder | None = None
    error: str | None = None


@dataclass(frozen=True)
class CancelOrderRequest:
    """Peticion de cancelacion de orden."""

    broker_order_id: str | None = None
    client_order_id: str | None = None
    symbol: str | None = None


@dataclass(frozen=True)
class OrderCancellationResult:
    """Resultado de cancelacion de orden."""

    success: bool
    broker_order_id: str | None = None
    status: OrderStatus | None = None
    error: str | None = None


@dataclass(frozen=True)
class MarketInfo:
    """Informacion de mercado para un par de trading."""

    symbol: str
    broker_symbol: str
    base_asset: str
    quote_asset: str
    min_quantity: Decimal | None = None
    max_quantity: Decimal | None = None
    step_size: Decimal | None = None
    min_notional: Decimal | None = None
    price_precision: int | None = None
    quantity_precision: int | None = None
    status: str = "TRADING"


@dataclass(frozen=True)
class Ticker:
    """Cotizacion en tiempo real de un simbolo."""

    symbol: str
    price: Decimal
    bid: Decimal | None = None
    ask: Decimal | None = None
    volume_24h: Decimal | None = None
    price_change_24h: Decimal | None = None
    price_change_percent_24h: Decimal | None = None
    timestamp: datetime | None = None


@dataclass(frozen=True)
class Candle:
    """Vela OHLCV normalizada."""

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    interval: str = "1m"


@dataclass(frozen=True)
class Fee:
    """Comision de una operacion."""

    asset: str
    amount: Decimal
    currency: str = "USDT"


def normalize_symbol(symbol: str) -> str:
    """Normaliza un simbolo al formato canonico con slash.

    Ejemplos:
        BTCUSDT -> BTC/USDT
        BTC/USDT -> BTC/USDT
        btcusdt -> BTC/USDT
        ETH-USDT -> ETH/USDT
    """
    s = symbol.upper().strip()
    for sep in ("/", "-", "_"):
        if sep in s:
            parts = s.split(sep)
            if len(parts) == 2:
                return f"{parts[0]}/{parts[1]}"
    if s.endswith("USDT"):
        return f"{s[:-4]}/USDT"
    if s.endswith("BUSD"):
        return f"{s[:-4]}/BUSD"
    if s.endswith("BTC"):
        return f"{s[:-3]}/BTC"
    if s.endswith("ETH"):
        return f"{s[:-3]}/ETH"
    return s


def denormalize_symbol(symbol: str, broker_id: str) -> str:
    """Convierte un simbolo canonico al formato de un broker.

    Ejemplos:
        BTC/USDT, binance -> BTCUSDT
        BTC/USDT, kraken -> XBTUSDT
    """
    s = symbol.upper().strip().replace("/", "").replace("-", "").replace("_", "")
    if broker_id == "kraken":
        s = s.replace("BTC", "XBT", 1) if s.startswith("BTC") else s
    return s
