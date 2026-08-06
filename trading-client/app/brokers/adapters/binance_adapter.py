"""BinanceAdapter — envuelve BinanceBroker por composicion.

No duplica la logica de firma HMAC-SHA256 ni la cache de exchangeInfo.
Traduce entre modelos normalizados (brokers/models.py) y el formato de Binance.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

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
from app.brokers.binance_broker import BinanceBroker, BinanceBrokerError
from app.brokers.capabilities import BrokerCapabilities
from app.brokers.models import (
    Balance,
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
    ValidatedOrderRequest,
    denormalize_symbol,
    normalize_symbol,
)

_BINANCE_BASE_URL = "https://api.binance.com"
_BINANCE_TESTNET_URL = "https://testnet.binance.vision"

_BINANCE_ERROR_MAP = {
    -2015: BrokerAuthError,
    -1121: InvalidSymbolError,
    -1013: MinNotionalError,
    -2010: InsufficientBalanceError,
    -2011: DuplicateOrderError,
}

_ORDER_TYPE_TO_BINANCE = {
    OrderType.MARKET: "MARKET",
    OrderType.LIMIT: "LIMIT",
    OrderType.STOP: "STOP_LOSS",
    OrderType.STOP_LIMIT: "STOP_LOSS_LIMIT",
    OrderType.TAKE_PROFIT: "TAKE_PROFIT",
    OrderType.TAKE_PROFIT_LIMIT: "TAKE_PROFIT_LIMIT",
}

_ORDER_SIDE_TO_BINANCE = {
    OrderSide.BUY: "BUY",
    OrderSide.SELL: "SELL",
}

_BINANCE_STATUS_MAP = {
    "NEW": OrderStatus.PENDING,
    "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
    "FILLED": OrderStatus.FILLED,
    "CANCELED": OrderStatus.CANCELLED,
    "REJECTED": OrderStatus.REJECTED,
    "EXPIRED": OrderStatus.EXPIRED,
    "PENDING_CANCEL": OrderStatus.PENDING,
    "PENDING_NEW": OrderStatus.PENDING,
}


def _map_binance_error(exc: BinanceBrokerError) -> BrokerError:
    """Mapea un BinanceBrokerError a la excepcion tipada correspondiente."""
    msg = str(exc)
    if "429" in msg or "rate limit" in msg.lower():
        return BrokerRateLimitError(msg)
    if "timeout" in msg.lower() or "timed out" in msg.lower():
        return BrokerTimeoutError(msg)
    for code, exc_cls in _BINANCE_ERROR_MAP.items():
        if f"API error {code}" in msg or f"error {code}:" in msg:
            return exc_cls(msg)
    return BrokerError(msg)


class BinanceAdapter(BrokerAdapter):
    """Adaptador de Binance que envuelve BinanceBroker por composicion.

    Reutiliza toda la logica de firma HMAC, cache de exchangeInfo y
    formateo de cantidades de BinanceBroker. No duplica nada.
    """

    def __init__(self, credentials: BrokerCredentials) -> None:
        self._credentials = credentials
        self._broker = BinanceBroker(
            api_key=credentials.api_key,
            api_secret=credentials.api_secret,
            testnet=credentials.testnet,
        )

    @property
    def _base_url(self) -> str:
        return _BINANCE_TESTNET_URL if self._credentials.testnet else _BINANCE_BASE_URL

    def get_broker_info(self) -> BrokerInfo:
        return BrokerInfo(
            broker_id="binance",
            display_name="Binance",
            supported_markets=(MarketType.SPOT,),
            website_url="https://www.binance.com",
            api_docs_url="https://binance-docs.github.io/apidocs",
        )

    def get_capabilities(self) -> BrokerCapabilities:
        return BrokerCapabilities(
            spot=True,
            margin=False,
            futures=False,
            staking=False,
            earn=True,
            websocket=True,
            market_orders=True,
            limit_orders=True,
            stop_orders=True,
            withdrawals=False,
        )

    def validate_credentials(self) -> CredentialValidationResult:
        from app.brokers.models import BrokerAccountStatus

        try:
            self._broker._signed_request("GET", "/api/v3/account", {})
            return CredentialValidationResult(
                valid=True,
                status=BrokerAccountStatus.ACTIVE,
                permissions=["spot_trading"],
            )
        except BinanceBrokerError as exc:
            mapped = _map_binance_error(exc)
            if isinstance(mapped, BrokerAuthError):
                return CredentialValidationResult(
                    valid=False,
                    status=BrokerAccountStatus.API_KEY_INVALID,
                    error_message=str(exc),
                )
            if isinstance(mapped, BrokerRateLimitError):
                return CredentialValidationResult(
                    valid=False,
                    status=BrokerAccountStatus.RATE_LIMITED,
                    error_message=str(exc),
                )
            return CredentialValidationResult(
                valid=False,
                status=BrokerAccountStatus.SECURITY_BLOCKED,
                error_message=str(exc),
            )

    def get_account_balances(self) -> tuple[Balance, ...]:
        try:
            resp = self._broker._signed_request("GET", "/api/v3/account", {})
        except BinanceBrokerError as exc:
            raise _map_binance_error(exc) from exc

        balances: list[Balance] = []
        for b in resp.get("balances", []):
            free = Decimal(str(b.get("free", "0")))
            locked = Decimal(str(b.get("locked", "0")))
            if free > 0 or locked > 0:
                balances.append(
                    Balance(
                        asset=b.get("asset", ""),
                        free=free,
                        locked=locked,
                    )
                )
        return tuple(balances)

    def get_portfolio(self) -> PortfolioSnapshot:
        balances = self.get_account_balances()
        total_usd = Decimal("0")

        for bal in balances:
            if bal.asset in ("USDT", "BUSD", "USDC", "UST", "USD"):
                total_usd += bal.total
            elif bal.asset == "EUR":
                try:
                    r = httpx.get(
                        f"{self._base_url}/api/v3/ticker/price",
                        params={"symbol": "EURUSDT"},
                        timeout=5,
                    )
                    if r.status_code == 200:
                        rate = Decimal(str(r.json()["price"]))
                        total_usd += bal.total * rate
                except Exception:
                    total_usd += bal.total * Decimal("1.08")
            else:
                try:
                    r = httpx.get(
                        f"{self._base_url}/api/v3/ticker/price",
                        params={"symbol": f"{bal.asset}USDT"},
                        timeout=5,
                    )
                    if r.status_code == 200:
                        rate = Decimal(str(r.json()["price"]))
                        total_usd += bal.total * rate
                except Exception:
                    pass

        return PortfolioSnapshot(
            timestamp=datetime.now(tz=UTC),
            balances=balances,
            total_usd=total_usd,
        )

    def get_open_positions(self) -> tuple[Position, ...]:
        return ()

    def get_order_history(self, symbol: str | None = None, limit: int = 50) -> tuple[BrokerOrder, ...]:
        params: dict[str, Any] = {"limit": limit}
        if symbol:
            params["symbol"] = denormalize_symbol(symbol, "binance")
        try:
            resp = self._broker._signed_request("GET", "/api/v3/allOrders", params)
        except BinanceBrokerError as exc:
            raise _map_binance_error(exc) from exc

        orders: list[BrokerOrder] = []
        for o in resp:
            orders.append(self._parse_binance_order(o))
        return tuple(orders)

    def get_market_info(self, symbol: str) -> MarketInfo:
        broker_symbol = denormalize_symbol(symbol, "binance")
        try:
            resp = httpx.get(
                f"{self._base_url}/api/v3/exchangeInfo",
                params={"symbol": broker_symbol},
                timeout=self._broker._timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise BrokerError(f"No se pudo obtener exchangeInfo para {symbol}: {exc}") from exc

        data = resp.json()
        symbols = data.get("symbols", [])
        if not symbols:
            raise InvalidSymbolError(f"Simbolo {symbol} no existe en Binance")

        s = symbols[0]
        filters = s.get("filters", [])
        min_qty = None
        max_qty = None
        step_size = None
        min_notional = None

        for f in filters:
            if f.get("filterType") == "LOT_SIZE":
                min_qty = Decimal(str(f.get("minQty", "0")))
                max_qty = Decimal(str(f.get("maxQty", "0")))
                step_size = Decimal(str(f.get("stepSize", "0")))
            elif f.get("filterType") in ("NOTIONAL", "MIN_NOTIONAL"):
                min_notional = Decimal(str(f.get("minNotional", f.get("notional", "0"))))

        return MarketInfo(
            symbol=normalize_symbol(symbol),
            broker_symbol=broker_symbol,
            base_asset=s.get("baseAsset", ""),
            quote_asset=s.get("quoteAsset", ""),
            min_quantity=min_qty,
            max_quantity=max_qty,
            step_size=step_size,
            min_notional=min_notional,
            price_precision=int(s.get("quotePrecision", 8)),
            quantity_precision=int(s.get("baseAssetPrecision", 8)),
            status=s.get("status", "TRADING"),
        )

    def get_ticker(self, symbol: str) -> Ticker:
        broker_symbol = denormalize_symbol(symbol, "binance")
        try:
            resp = httpx.get(
                f"{self._base_url}/api/v3/ticker/price",
                params={"symbol": broker_symbol},
                timeout=self._broker._timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 400:
                raise InvalidSymbolError(f"Simbolo {symbol} no existe en Binance") from exc
            if exc.response.status_code == 429:
                raise BrokerRateLimitError("Rate limit de Binance excedido") from exc
            raise BrokerError(f"Error HTTP {exc.response.status_code}: {exc}") from exc
        except httpx.HTTPError as exc:
            raise BrokerTimeoutError(f"Timeout conectando a Binance: {exc}") from exc

        price = Decimal(str(resp.json()["price"]))
        return Ticker(
            symbol=normalize_symbol(symbol),
            price=price,
            timestamp=datetime.now(tz=UTC),
        )

    def place_order(self, request: OrderRequest) -> OrderExecutionResult:
        broker_symbol = denormalize_symbol(request.symbol, "binance")
        ValidatedOrderRequest(
            symbol=request.symbol,
            broker_symbol=broker_symbol,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            price=request.price,
            stop_price=request.stop_price,
            client_order_id=request.client_order_id,
            time_in_force=request.time_in_force,
            metadata=request.metadata,
        )

        params: dict[str, Any] = {
            "symbol": broker_symbol,
            "side": _ORDER_SIDE_TO_BINANCE.get(request.side, request.side.value.upper()),
            "type": _ORDER_TYPE_TO_BINANCE.get(request.order_type, "MARKET"),
            "quantity": self._broker._format_quantity(request.quantity),
        }

        if request.order_type == OrderType.LIMIT and request.price:
            params["price"] = self._broker._format_price(request.price)
            params["timeInForce"] = request.time_in_force

        if request.stop_price:
            params["stopPrice"] = self._broker._format_price(request.stop_price)

        if request.client_order_id:
            params["newClientOrderId"] = request.client_order_id

        try:
            resp = self._broker._signed_request("POST", "/api/v3/order", params)
        except BinanceBrokerError as exc:
            mapped = _map_binance_error(exc)
            return OrderExecutionResult(success=False, error=str(mapped))

        order = self._parse_binance_order(resp)
        return OrderExecutionResult(success=True, order=order)

    def place_oco_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        take_profit_price: Decimal,
        stop_loss_price: Decimal,
    ) -> dict:
        """Place a real OCO (One-Cancels-Other) order on Binance.

        TP is a LIMIT order, SL is a STOP_LOSS_LIMIT order.
        When one fills, the other is automatically cancelled.
        Returns dict with order_list_id, sl_order_id, tp_order_id.
        """
        broker_symbol = denormalize_symbol(symbol, "binance")
        bin_side = "SELL" if side.lower() == "sell" else "BUY"

        def _fmt(v: Decimal) -> str:
            return f"{float(v):.8f}".rstrip("0").rstrip(".")

        params: dict[str, Any] = {
            "symbol": broker_symbol,
            "side": bin_side,
            "quantity": self._broker._format_quantity(quantity),
            "price": _fmt(take_profit_price),
            "stopPrice": _fmt(stop_loss_price),
            "stopLimitPrice": _fmt(stop_loss_price),
            "stopLimitTimeInForce": "GTC",
        }

        try:
            resp = self._broker._signed_request("POST", "/api/v3/order/oco", params)
        except BinanceBrokerError as exc:
            mapped = _map_binance_error(exc)
            return {"success": False, "error": str(mapped)}

        order_list_id = str(resp.get("orderListId", ""))
        orders = resp.get("orders", [])
        sl_id = ""
        tp_id = ""
        for o in orders:
            otype = o.get("type", "")
            oid = str(o.get("orderId", ""))
            if otype in ("STOP_LOSS_LIMIT", "STOP_LOSS"):
                sl_id = oid
            elif otype in ("LIMIT", "TAKE_PROFIT_LIMIT"):
                tp_id = oid

        return {
            "success": True,
            "order_list_id": order_list_id,
            "sl_order_id": sl_id,
            "tp_order_id": tp_id,
        }

    def cancel_order(self, request: CancelOrderRequest) -> OrderCancellationResult:
        params: dict[str, Any] = {}
        if request.broker_order_id:
            params["orderId"] = request.broker_order_id
        elif request.client_order_id:
            params["origClientOrderId"] = request.client_order_id
        else:
            return OrderCancellationResult(success=False, error="Se requiere broker_order_id o client_order_id")

        if request.symbol:
            params["symbol"] = denormalize_symbol(request.symbol, "binance")

        try:
            resp = self._broker._signed_request("DELETE", "/api/v3/order", params)
        except BinanceBrokerError as exc:
            mapped = _map_binance_error(exc)
            return OrderCancellationResult(
                success=False,
                broker_order_id=request.broker_order_id,
                error=str(mapped),
            )

        status = _BINANCE_STATUS_MAP.get(resp.get("status", "CANCELED"), OrderStatus.CANCELLED)
        return OrderCancellationResult(
            success=True,
            broker_order_id=str(resp.get("orderId", request.broker_order_id or "")),
            status=status,
        )

    def get_order_status(self, broker_order_id: str, symbol: str | None = None) -> BrokerOrder:
        params: dict[str, Any] = {"orderId": broker_order_id}
        if symbol:
            params["symbol"] = denormalize_symbol(symbol, "binance")
        else:
            params["symbol"] = ""

        try:
            resp = self._broker._signed_request("GET", "/api/v3/order", params)
        except BinanceBrokerError as exc:
            raise _map_binance_error(exc) from exc

        return self._parse_binance_order(resp)

    def get_klines(
        self, symbol: str, interval: str, limit: int = 200
    ) -> list[Candle]:
        """Devuelve velas OHLCV normalizadas con Decimal desde Binance public API."""
        broker_symbol = denormalize_symbol(symbol, "binance")
        try:
            resp = httpx.get(
                f"{self._base_url}/api/v3/klines",
                params={"symbol": broker_symbol, "interval": interval, "limit": limit},
                timeout=self._broker._timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 400:
                raise InvalidSymbolError(f"Simbolo {symbol} no existe en Binance") from exc
            if exc.response.status_code == 429:
                raise BrokerRateLimitError("Rate limit de Binance excedido") from exc
            raise BrokerError(f"Error HTTP {exc.response.status_code}: {exc}") from exc
        except httpx.HTTPError as exc:
            raise BrokerTimeoutError(f"Timeout conectando a Binance: {exc}") from exc

        raw = resp.json()
        candles: list[Candle] = []
        for k in raw:
            candles.append(
                Candle(
                    timestamp=datetime.fromtimestamp(k[0] / 1000, tz=UTC),
                    open=Decimal(str(k[1])),
                    high=Decimal(str(k[2])),
                    low=Decimal(str(k[3])),
                    close=Decimal(str(k[4])),
                    volume=Decimal(str(k[5])),
                    interval=interval,
                )
            )
        return candles

    def get_market_movers(
        self, market: str = "spot", limit: int = 20, quote: str = "USDT"
    ) -> dict:
        """Devuelve top gainers y losers de 24h desde Binance.

        Returns dict con 'gainers' y 'losers', cada uno una lista de dicts con
        symbol, price (Decimal), price_change_percent (Decimal), volume (Decimal).
        """
        if market == "futures":
            url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
        else:
            url = f"{self._base_url}/api/v3/ticker/24hr"

        try:
            resp = httpx.get(url, timeout=self._broker._timeout)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise BrokerError(f"Error al consultar ticker 24h de Binance: {exc}") from exc

        data = resp.json()
        tickers = []
        for item in data:
            sym = item.get("symbol", "")
            if not sym.endswith(quote):
                continue
            tickers.append({
                "symbol": sym,
                "price": Decimal(str(item.get("lastPrice", "0"))),
                "price_change_percent": Decimal(str(item.get("priceChangePercent", "0"))),
                "volume": Decimal(str(item.get("quoteVolume", "0"))),
            })

        tickers.sort(key=lambda x: x["price_change_percent"], reverse=True)
        gainers = tickers[:limit]
        losers = list(reversed(tickers[-limit:]))
        return {"gainers": gainers, "losers": losers}

    def get_top_symbols(
        self, quote: str = "USDT", limit: int = 50
    ) -> list[dict]:
        """Top símbolos por volumen de 24h desde Binance con precio y cambio."""
        url = f"{self._base_url}/api/v3/ticker/24hr"
        try:
            resp = httpx.get(url, timeout=self._broker._timeout)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise BrokerError(f"Error al consultar ticker 24h: {exc}") from exc

        tickers = []
        for item in resp.json():
            sym = item.get("symbol", "")
            if not sym.endswith(quote):
                continue
            base = sym[:-len(quote)] if quote else sym
            if not base or len(base) > 10:
                continue
            tickers.append({
                "symbol": f"{base}/{quote}",
                "base": base,
                "quote": quote,
                "price": float(item.get("lastPrice", "0")),
                "change_24h_pct": float(item.get("priceChangePercent", "0")),
                "volume": float(item.get("quoteVolume", "0")),
            })
        tickers.sort(key=lambda x: x["volume"], reverse=True)
        return tickers[:limit]

    def _parse_binance_order(self, data: dict) -> BrokerOrder:
        bin_status = data.get("status", "NEW")
        status = _BINANCE_STATUS_MAP.get(bin_status.upper(), OrderStatus.PENDING)

        side_str = data.get("side", "BUY").lower()
        side = OrderSide.BUY if side_str == "buy" else OrderSide.SELL

        type_str = data.get("type", "MARKET").lower()
        order_type = OrderType.MARKET
        for ot, bin_val in _ORDER_TYPE_TO_BINANCE.items():
            if bin_val.lower() == type_str:
                order_type = ot
                break

        price_str = data.get("price", "0")
        price = Decimal(str(price_str)) if price_str and price_str != "0" else None

        avg_price_str = data.get("avgPrice", "0")
        avg_fill_price = Decimal(str(avg_price_str)) if avg_price_str and avg_price_str != "0" else None

        return BrokerOrder(
            broker_order_id=str(data.get("orderId", "")),
            client_order_id=data.get("clientOrderId"),
            symbol=normalize_symbol(data.get("symbol", "")),
            side=side,
            order_type=order_type,
            quantity=Decimal(str(data.get("origQty", "0"))),
            filled_quantity=Decimal(str(data.get("executedQty", "0"))),
            price=price,
            avg_fill_price=avg_fill_price,
            status=status,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
            metadata=data,
        )

    def dust_transfer(self, assets: list[str]) -> dict:
        """Convert dust assets to BNB via Binance Dust Transfer endpoint.

        Args:
            assets: List of asset symbols to convert (e.g. ["AVAX", "DOGE"])

        Returns:
            dict with transfer result from Binance.
        """
        try:
            resp = self._broker._signed_request("POST", "/sapi/v1/asset/dust", {
                "asset": assets,
            })
            return {
                "success": True,
                "transfer_result": resp.get("transferResult", []),
                "total_bnb": resp.get("totalTransferedBnb", "0"),
                "dust_log": resp.get("dribbletLogs", []),
            }
        except BinanceBrokerError as exc:
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def get_dustable_assets_log(self) -> dict:
        """Get list of assets that can be converted to BNB (dust log)."""
        try:
            resp = self._broker._signed_request("POST", "/sapi/v1/asset/dust-btc", {})
            return {"success": True, "data": resp}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
