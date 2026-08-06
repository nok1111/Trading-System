"""CCXTAdapter — adaptador generico para 100+ exchanges via CCXT.

Implementa la interfaz BrokerAdapter usando la libreria CCXT (MIT, gratis).
Una sola clase soporta cualquier exchange de CCXT: Bybit, Kraken, Coinbase,
OKX, KuCoin, Bitget, MEXC, Gate.io, etc.

CCXT normaliza:
  - Autenticacion (API key + secret + passphrase opcional)
  - Formato de simbolos (BTC/USDT canonico)
  - Tipos de orden (market, limit, stop)
  - Estados de orden
  - Saldos y balances
  - Datos de mercado (precisiones, limites)

El adapter traduce entre los modelos normalizados de Alvora (brokers/models.py)
y las respuestas de CCXT.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import ccxt

from app.brokers.base import (
    BrokerAdapter,
    BrokerAuthError,
    BrokerError,
    BrokerRateLimitError,
    BrokerTimeoutError,
    DuplicateOrderError,
    InsufficientBalanceError,
    InvalidSymbolError,
    MinNotionalError,
)
from app.brokers.capabilities import BrokerCapabilities
from app.brokers.models import (
    Balance,
    BrokerAccountStatus,
    BrokerCredentials,
    BrokerInfo,
    BrokerOrder,
    CancelOrderRequest,
    Candle,
    CredentialValidationResult,
    MarketInfo,
    MarketType,
    OrderCancellationResult,
    OrderExecutionResult,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    PortfolioSnapshot,
    Position,
    Ticker,
    normalize_symbol,
)

logger = logging.getLogger(__name__)

# Metadatos estaticos para los exchanges mas populares.
# Los que no esten aqui usan defaults derivados de CCXT.
_EXCHANGE_META: dict[str, dict[str, Any]] = {
    "bybit": {
        "display_name": "Bybit",
        "website": "https://www.bybit.com",
        "api_docs": "https://bybit-exchange.github.io/docs/v5/intro",
        "markets": (MarketType.SPOT, MarketType.FUTURES),
        "passphrase": False,
        "sandbox": True,
    },
    "kraken": {
        "display_name": "Kraken",
        "website": "https://www.kraken.com",
        "api_docs": "https://docs.kraken.com",
        "markets": (MarketType.SPOT, MarketType.FUTURES),
        "passphrase": False,
        "sandbox": False,
    },
    "coinbase": {
        "display_name": "Coinbase",
        "website": "https://www.coinbase.com",
        "api_docs": "https://docs.cloud.coinbase.com",
        "markets": (MarketType.SPOT,),
        "passphrase": False,
        "sandbox": True,
    },
    "okx": {
        "display_name": "OKX",
        "website": "https://www.okx.com",
        "api_docs": "https://www.okx.com/docs-v5",
        "markets": (MarketType.SPOT, MarketType.FUTURES),
        "passphrase": True,
        "sandbox": True,
    },
    "kucoin": {
        "display_name": "KuCoin",
        "website": "https://www.kucoin.com",
        "api_docs": "https://docs.kucoin.com",
        "markets": (MarketType.SPOT, MarketType.FUTURES),
        "passphrase": True,
        "sandbox": True,
    },
    "bitget": {
        "display_name": "Bitget",
        "website": "https://www.bitget.com",
        "api_docs": "https://www.bitget.com/api-doc",
        "markets": (MarketType.SPOT, MarketType.FUTURES),
        "passphrase": True,
        "sandbox": False,
    },
    "mexc": {
        "display_name": "MEXC",
        "website": "https://www.mexc.com",
        "api_docs": "https://mexcdevelop.github.io/apidocs",
        "markets": (MarketType.SPOT, MarketType.FUTURES),
        "passphrase": False,
        "sandbox": False,
    },
    "gate": {
        "display_name": "Gate.io",
        "website": "https://www.gate.io",
        "api_docs": "https://www.gate.io/docs/developers/apiv4",
        "markets": (MarketType.SPOT, MarketType.FUTURES),
        "passphrase": False,
        "sandbox": False,
    },
    "htx": {
        "display_name": "HTX",
        "website": "https://www.htx.com",
        "api_docs": "https://www.htx.com/en-us/opend/",
        "markets": (MarketType.SPOT,),
        "passphrase": False,
        "sandbox": False,
    },
    "bitfinex": {
        "display_name": "Bitfinex",
        "website": "https://www.bitfinex.com",
        "api_docs": "https://docs.bitfinex.com",
        "markets": (MarketType.SPOT, MarketType.MARGIN),
        "passphrase": False,
        "sandbox": False,
    },
    "poloniex": {
        "display_name": "Poloniex",
        "website": "https://www.poloniex.com",
        "api_docs": "https://docs.poloniex.com",
        "markets": (MarketType.SPOT,),
        "passphrase": False,
        "sandbox": False,
    },
    "gemini": {
        "display_name": "Gemini",
        "website": "https://www.gemini.com",
        "api_docs": "https://docs.gemini.com",
        "markets": (MarketType.SPOT,),
        "passphrase": False,
        "sandbox": True,
    },
    "bitstamp": {
        "display_name": "Bitstamp",
        "website": "https://www.bitstamp.net",
        "api_docs": "https://www.bitstamp.net/api",
        "markets": (MarketType.SPOT,),
        "passphrase": False,
        "sandbox": False,
    },
    "bithumb": {
        "display_name": "Bithumb",
        "website": "https://www.bithumb.com",
        "api_docs": "https://apidocs.bithumb.com",
        "markets": (MarketType.SPOT,),
        "passphrase": False,
        "sandbox": False,
    },
    "okcoin": {
        "display_name": "OKCoin",
        "website": "https://www.okcoin.com",
        "api_docs": "https://www.okcoin.com/docs",
        "markets": (MarketType.SPOT,),
        "passphrase": True,
        "sandbox": True,
    },
    "ascendex": {
        "display_name": "AscendEX",
        "website": "https://ascendex.com",
        "api_docs": "https://ascendex.github.io/ascendex-pro-api",
        "markets": (MarketType.SPOT,),
        "passphrase": False,
        "sandbox": False,
    },
    "bingx": {
        "display_name": "BingX",
        "website": "https://www.bingx.com",
        "api_docs": "https://bingx-api.github.io",
        "markets": (MarketType.SPOT, MarketType.FUTURES),
        "passphrase": False,
        "sandbox": False,
    },
    "coinex": {
        "display_name": "CoinEx",
        "website": "https://www.coinex.com",
        "api_docs": "https://docs.coinex.com",
        "markets": (MarketType.SPOT, MarketType.FUTURES),
        "passphrase": False,
        "sandbox": False,
    },
    "crypto_com": {
        "display_name": "Crypto.com",
        "website": "https://crypto.com/exchange",
        "api_docs": "https://exchange-docs.crypto.com",
        "markets": (MarketType.SPOT, MarketType.FUTURES),
        "passphrase": False,
        "sandbox": True,
    },
    "upbit": {
        "display_name": "Upbit",
        "website": "https://upbit.com",
        "api_docs": "https://docs.upbit.com",
        "markets": (MarketType.SPOT,),
        "passphrase": False,
        "sandbox": False,
    },
}

# Exchanges CCXT que se exponen al usuario (subset curado de los mas confiables).
# Se puede ampliar facilmente anadiendo el exchange_id aqui + metadatos arriba.
_CURATED_EXCHANGES: tuple[str, ...] = tuple(_EXCHANGE_META.keys())

# Mapeo de tipos de orden Alvora -> CCXT
_ORDER_TYPE_TO_CCXT = {
    OrderType.MARKET: "market",
    OrderType.LIMIT: "limit",
    OrderType.STOP: "stop",
    OrderType.STOP_LIMIT: "stop_limit",
    OrderType.TAKE_PROFIT: "take_profit",
    OrderType.TAKE_PROFIT_LIMIT: "take_profit_limit",
}

# Mapeo de estados de orden CCXT -> Alvora
_CCXT_STATUS_MAP = {
    "open": OrderStatus.PENDING,
    "closed": OrderStatus.FILLED,
    "canceled": OrderStatus.CANCELLED,
    "cancelled": OrderStatus.CANCELLED,
    "expired": OrderStatus.EXPIRED,
    "rejected": OrderStatus.REJECTED,
}


def _map_ccxt_error(exc: Exception) -> BrokerError:
    """Mapea una excepcion de CCXT a la excepcion tipada de Alvora."""
    msg = str(exc)
    exc_type = type(exc).__name__

    if "AuthenticationError" in exc_type or "AuthorizationError" in exc_type:
        return BrokerAuthError(msg)
    if "RateLimitExceeded" in exc_type or "DDoSProtection" in exc_type:
        return BrokerRateLimitError(msg)
    if "BadSymbol" in exc_type or "InvalidSymbol" in exc_type:
        return InvalidSymbolError(msg)
    if "InsufficientFunds" in exc_type:
        return InsufficientBalanceError(msg)
    if "InvalidOrder" in exc_type and "minNotional" in msg.lower():
        return MinNotionalError(msg)
    if "DuplicateOrder" in exc_type:
        return DuplicateOrderError(msg)
    if "NetworkError" in exc_type or "Timeout" in exc_type:
        return BrokerTimeoutError(msg)

    # Fallback: buscar por mensaje
    lower = msg.lower()
    if "429" in msg or "rate limit" in lower:
        return BrokerRateLimitError(msg)
    if "timeout" in lower or "timed out" in lower:
        return BrokerTimeoutError(msg)
    if "insufficient" in lower and ("fund" in lower or "balance" in lower):
        return InsufficientBalanceError(msg)
    if "invalid api key" in lower or "invalid key" in lower or "unauthorized" in lower:
        return BrokerAuthError(msg)

    return BrokerError(msg)


def _to_decimal(value: Any) -> Decimal:
    """Convierte cualquier valor de CCXT a Decimal de forma segura."""
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _parse_ccxt_order(order: dict[str, Any]) -> BrokerOrder:
    """Convierte una orden de CCXT al modelo BrokerOrder de Alvora."""
    raw_status = order.get("status", "open")
    status = _CCXT_STATUS_MAP.get(raw_status, OrderStatus.PENDING)

    side_str = order.get("side", "buy")
    try:
        side = OrderSide(side_str)
    except ValueError:
        side = OrderSide.BUY

    order_type_str = order.get("type", "market")
    try:
        order_type = OrderType(order_type_str)
    except ValueError:
        order_type = OrderType.MARKET

    symbol = normalize_symbol(order.get("symbol", ""))
    timestamp = order.get("timestamp") or order.get("lastUpdateTimestamp")
    created_at = datetime.fromtimestamp(timestamp / 1000, tz=UTC) if timestamp else None

    return BrokerOrder(
        broker_order_id=str(order.get("id", "")) or None,
        client_order_id=order.get("clientOrderId"),
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=_to_decimal(order.get("amount", 0)),
        filled_quantity=_to_decimal(order.get("filled", 0)),
        price=_to_decimal(order.get("price")) if order.get("price") else None,
        status=status,
        avg_fill_price=_to_decimal(order.get("average")) if order.get("average") else None,
        created_at=created_at,
        updated_at=created_at,
        metadata=order,
    )


class CCXTAdapter(BrokerAdapter):
    """Adaptador generico para cualquier exchange soportado por CCXT.

    Una sola clase maneja 100+ exchanges. El exchange_id se pasa en el
    constructor y determina que instancia de ccxt.Exchange se crea.

    Binance sigue usando BinanceAdapter nativo (optimizado con HMAC propio,
    cache de exchangeInfo, y soporte de futures OCO). CCXTAdapter se usa
    para todos los demas exchanges.
    """

    def __init__(self, credentials: BrokerCredentials, exchange_id: str) -> None:
        self._credentials = credentials
        self._exchange_id = exchange_id

        exchange_class = getattr(ccxt, exchange_id, None)
        if exchange_class is None:
            raise BrokerError(f"Exchange CCXT no encontrado: {exchange_id}")

        config: dict[str, Any] = {
            "apiKey": credentials.api_key,
            "secret": credentials.api_secret,
            "enableRateLimit": True,
            "options": {"builderFee": False},
        }

        if credentials.passphrase:
            config["password"] = credentials.passphrase

        if credentials.testnet:
            sandbox_config = self._get_sandbox_config(exchange_id)
            if sandbox_config:
                config.update(sandbox_config)

        self._exchange = exchange_class(config)

    @staticmethod
    def _get_sandbox_config(exchange_id: str) -> dict[str, Any]:
        """Devuelve config para sandbox/testnet si el exchange lo soporta."""
        try:
            ex = getattr(ccxt, exchange_id)({})
            if hasattr(ex, "set_sandbox_mode"):
                return {"sandbox": True}
        except Exception:
            pass
        return {}

    @property
    def _meta(self) -> dict[str, Any]:
        return _EXCHANGE_META.get(
            self._exchange_id,
            {
                "display_name": self._exchange_id.title(),
                "website": None,
                "api_docs": None,
                "markets": (MarketType.SPOT,),
                "passphrase": False,
                "sandbox": False,
            },
        )

    def get_broker_info(self) -> BrokerInfo:
        return BrokerInfo(
            broker_id=self._exchange_id,
            display_name=self._meta["display_name"],
            supported_markets=self._meta["markets"],
            website_url=self._meta.get("website"),
            api_docs_url=self._meta.get("api_docs"),
        )

    def get_capabilities(self) -> BrokerCapabilities:
        markets = self._meta["markets"]
        return BrokerCapabilities(
            spot=MarketType.SPOT in markets,
            margin=MarketType.MARGIN in markets,
            futures=MarketType.FUTURES in markets,
            staking=False,
            earn=False,
            websocket=False,
            market_orders=True,
            limit_orders=True,
            stop_orders=False,
            withdrawals=False,
        )

    def validate_credentials(self) -> CredentialValidationResult:
        try:
            self._exchange.fetch_balance()
            return CredentialValidationResult(
                valid=True,
                status=BrokerAccountStatus.ACTIVE,
                permissions=["spot_trading"],
            )
        except ccxt.AuthenticationError as exc:
            return CredentialValidationResult(
                valid=False,
                status=BrokerAccountStatus.API_KEY_INVALID,
                error_message=str(exc),
            )
        except ccxt.NetworkError as exc:
            return CredentialValidationResult(
                valid=False,
                status=BrokerAccountStatus.RATE_LIMITED,
                error_message=f"Error de red: {exc}",
            )
        except Exception as exc:
            mapped = _map_ccxt_error(exc)
            if isinstance(mapped, BrokerAuthError):
                return CredentialValidationResult(
                    valid=False,
                    status=BrokerAccountStatus.API_KEY_INVALID,
                    error_message=str(exc),
                )
            return CredentialValidationResult(
                valid=False,
                status=BrokerAccountStatus.SECURITY_BLOCKED,
                error_message=str(exc),
            )

    def get_account_balances(self) -> tuple[Balance, ...]:
        try:
            resp = self._exchange.fetch_balance()
        except Exception as exc:
            raise _map_ccxt_error(exc) from exc

        balances: list[Balance] = []
        for asset, amounts in resp.get("total", {}).items():
            if amounts is None:
                continue
            total = _to_decimal(amounts)
            if total <= 0:
                continue
            free = _to_decimal(resp.get("free", {}).get(asset, 0))
            used = _to_decimal(resp.get("used", {}).get(asset, 0))
            balances.append(Balance(asset=asset, free=free, locked=used))
        return tuple(balances)

    def get_portfolio(self) -> PortfolioSnapshot:
        balances = self.get_account_balances()
        total_usd = Decimal("0")
        STABLECOINS = {"USDT", "BUSD", "USDC", "USD", "UST", "TUSD", "FDUSD", "USDP"}
        USD_QUOTES = ["USDT", "USDC", "USD", "FDUSD", "TUSD", "BUSD"]

        for bal in balances:
            if bal.asset in STABLECOINS:
                total_usd += bal.total
            else:
                # Try multiple quote currencies until one works
                priced = False
                for quote in USD_QUOTES:
                    try:
                        ticker = self._exchange.fetch_ticker(f"{bal.asset}/{quote}")
                        price = _to_decimal(ticker.get("last", 0))
                        total_usd += bal.total * price
                        priced = True
                        break
                    except Exception:
                        continue

        return PortfolioSnapshot(
            timestamp=datetime.now(tz=UTC),
            balances=balances,
            total_usd=total_usd,
        )

    def get_open_positions(self) -> tuple[Position, ...]:
        return ()

    def get_order_history(self, symbol: str | None = None, limit: int = 50) -> tuple[BrokerOrder, ...]:
        ccxt_symbol = symbol if symbol else None
        try:
            orders = self._exchange.fetch_orders(ccxt_symbol, limit=limit)
        except Exception as exc:
            raise _map_ccxt_error(exc) from exc
        return tuple(_parse_ccxt_order(o) for o in orders)

    def get_market_info(self, symbol: str) -> MarketInfo:
        try:
            markets = self._exchange.load_markets()
        except Exception as exc:
            raise _map_ccxt_error(exc) from exc

        market = markets.get(symbol)
        if market is None:
            raise InvalidSymbolError(f"Simbolo no encontrado: {symbol}")

        limits = market.get("limits", {})
        precision = market.get("precision", {})

        return MarketInfo(
            symbol=symbol,
            broker_symbol=market.get("id", symbol),
            base_asset=market.get("base", ""),
            quote_asset=market.get("quote", ""),
            min_quantity=_to_decimal(limits.get("amount", {}).get("min")) if limits.get("amount") else None,
            max_quantity=_to_decimal(limits.get("amount", {}).get("max")) if limits.get("amount") else None,
            step_size=_to_decimal(precision.get("amount")) if precision.get("amount") else None,
            min_notional=_to_decimal(limits.get("cost", {}).get("min")) if limits.get("cost") else None,
            price_precision=int(precision.get("price", 8)) if precision.get("price") else None,
            quantity_precision=int(precision.get("amount", 8)) if precision.get("amount") else None,
            status=market.get("active", True) and "TRADING" or "CLOSED",
        )

    def get_ticker(self, symbol: str) -> Ticker:
        try:
            t = self._exchange.fetch_ticker(symbol)
        except Exception as exc:
            raise _map_ccxt_error(exc) from exc

        timestamp = t.get("timestamp")
        ts = datetime.fromtimestamp(timestamp / 1000, tz=UTC) if timestamp else None

        return Ticker(
            symbol=symbol,
            price=_to_decimal(t.get("last", 0)),
            bid=_to_decimal(t.get("bid")) if t.get("bid") else None,
            ask=_to_decimal(t.get("ask")) if t.get("ask") else None,
            volume_24h=_to_decimal(t.get("baseVolume")) if t.get("baseVolume") else None,
            price_change_24h=_to_decimal(t.get("change")) if t.get("change") else None,
            price_change_percent_24h=_to_decimal(t.get("percentage")) if t.get("percentage") else None,
            timestamp=ts,
        )

    def place_order(self, request: OrderRequest) -> OrderExecutionResult:
        ccxt_type = _ORDER_TYPE_TO_CCXT.get(request.order_type, "market")
        ccxt_side = request.side.value

        params: dict[str, Any] = {}
        if request.client_order_id:
            params["clientOrderId"] = request.client_order_id

        extra_price = None
        if request.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT, OrderType.TAKE_PROFIT_LIMIT):
            extra_price = request.price
        elif request.stop_price:
            params["stopPrice"] = float(request.stop_price)

        try:
            result = self._exchange.create_order(
                symbol=request.symbol,
                type=ccxt_type,
                side=ccxt_side,
                amount=float(request.quantity),
                price=float(extra_price) if extra_price else None,
                params=params,
            )
        except Exception as exc:
            mapped = _map_ccxt_error(exc)
            return OrderExecutionResult(success=False, error=str(mapped))

        order = _parse_ccxt_order(result)
        return OrderExecutionResult(success=True, order=order)

    def cancel_order(self, request: CancelOrderRequest) -> OrderCancellationResult:
        if not request.broker_order_id:
            return OrderCancellationResult(success=False, error="Se requiere broker_order_id")

        try:
            self._exchange.cancel_order(request.broker_order_id, request.symbol or None)
            return OrderCancellationResult(
                success=True,
                broker_order_id=request.broker_order_id,
                status=OrderStatus.CANCELLED,
            )
        except Exception as exc:
            mapped = _map_ccxt_error(exc)
            return OrderCancellationResult(
                success=False,
                broker_order_id=request.broker_order_id,
                error=str(mapped),
            )

    def get_order_status(self, broker_order_id: str, symbol: str | None = None) -> BrokerOrder:
        try:
            order = self._exchange.fetch_order(broker_order_id, symbol or None)
        except Exception as exc:
            raise _map_ccxt_error(exc) from exc
        return _parse_ccxt_order(order)

    def get_klines(self, symbol: str, interval: str, limit: int = 200) -> list[Candle]:
        try:
            ohlcv = self._exchange.fetch_ohlcv(symbol, timeframe=interval, limit=limit)
        except Exception as exc:
            raise _map_ccxt_error(exc) from exc

        candles: list[Candle] = []
        for entry in ohlcv:
            if not entry or len(entry) < 6:
                continue
            ts = datetime.fromtimestamp(entry[0] / 1000, tz=UTC) if entry[0] else datetime.now(tz=UTC)
            candles.append(
                Candle(
                    timestamp=ts,
                    open=_to_decimal(entry[1]),
                    high=_to_decimal(entry[2]),
                    low=_to_decimal(entry[3]),
                    close=_to_decimal(entry[4]),
                    volume=_to_decimal(entry[5]),
                    interval=interval,
                )
            )
        return candles

    def get_market_movers(
        self, market: str = "spot", limit: int = 20, quote: str = "USDT"
    ) -> dict:
        try:
            tickers = self._exchange.fetch_tickers()
        except Exception as exc:
            raise _map_ccxt_error(exc) from exc

        movers: list[dict[str, Any]] = []
        for sym, t in tickers.items():
            if not sym.endswith(f"/{quote}"):
                continue
            pct = t.get("percentage")
            if pct is None:
                continue
            movers.append({
                "symbol": sym,
                "price": t.get("last", 0),
                "change_pct": pct,
                "volume": t.get("quoteVolume", 0),
            })

        movers.sort(key=lambda x: x["change_pct"], reverse=True)
        gainers = movers[:limit]
        losers = list(reversed(movers[-limit:]))
        return {"gainers": gainers, "losers": losers}

    def get_top_symbols(
        self, quote: str = "USDT", limit: int = 50
    ) -> list[dict]:
        """Top símbolos por volumen via CCXT fetch_tickers."""
        try:
            tickers = self._exchange.fetch_tickers()
        except Exception as exc:
            raise _map_ccxt_error(exc) from exc

        result = []
        for sym, t in tickers.items():
            if not sym.endswith(f"/{quote}"):
                continue
            base = sym.split("/")[0]
            vol = t.get("quoteVolume", 0) or 0
            if vol <= 0:
                continue
            result.append({
                "symbol": sym,
                "base": base,
                "quote": quote,
                "price": float(t.get("last", 0) or 0),
                "change_24h_pct": float(t.get("percentage", 0) or 0),
                "volume": float(vol),
            })
        result.sort(key=lambda x: x["volume"], reverse=True)
        return result[:limit]


def get_curated_exchange_ids() -> tuple[str, ...]:
    """Devuelve los IDs de exchanges CCXT curados para mostrar al usuario."""
    return _CURATED_EXCHANGES


def get_exchange_meta(exchange_id: str) -> dict[str, Any]:
    """Devuelve los metadatos de un exchange CCXT."""
    return _EXCHANGE_META.get(exchange_id, {})
