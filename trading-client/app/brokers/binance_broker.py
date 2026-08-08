"""Adaptador de broker para Binance usando la API REST con firma HMAC-SHA256."""

import hashlib
import hmac
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import httpx

from app.brokers.broker import Broker
from app.database.models.account_snapshot import AccountSnapshot
from app.database.models.order import Order

_BINANCE_BASE_URL = "https://api.binance.com"

_ORDER_TYPE_MAP = {
    "market": "MARKET",
    "limit": "LIMIT",
    "stop": "STOP_LOSS",
    "stop_limit": "STOP_LOSS_LIMIT",
    "take_profit": "TAKE_PROFIT",
    "take_profit_limit": "TAKE_PROFIT_LIMIT",
}

_SIDE_MAP = {
    "buy": "BUY",
    "sell": "SELL",
}


class BinanceBrokerError(Exception):
    """Error devuelto por la API de Binance."""


class BinanceBroker(Broker):
    """Broker real para Binance que envía órdenes vía API REST firmada.

    Requiere BROKER_API_KEY y BROKER_API_SECRET configurados.
    """

    # Cache for exchange symbol filters: {symbol: {step_size, min_notional, ...}}
    _symbol_filters_cache: dict[str, dict] = {}

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = _BINANCE_BASE_URL,
        testnet: bool = False,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret.encode("utf-8")
        self._timeout = timeout
        if testnet:
            self._base_url = "https://testnet.binance.vision"
        else:
            self._base_url = base_url.rstrip("/")

    def _get_symbol_filters(self, symbol: str) -> dict:
        """Fetch and cache LOT_SIZE step, MIN_NOTIONAL, and PRICE_FILTER tickSize for a symbol."""
        symbol = symbol.upper()
        if symbol in self._symbol_filters_cache:
            return self._symbol_filters_cache[symbol]
        try:
            resp = httpx.get(
                f"{self._base_url}/api/v3/exchangeInfo",
                params={"symbol": symbol},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            filters = data.get("symbols", [{}])[0].get("filters", [])
            result = {"step_size": None, "min_notional": None, "tick_size": None}
            for f in filters:
                if f.get("filterType") == "LOT_SIZE":
                    result["step_size"] = Decimal(str(f.get("stepSize", "0")))
                elif f.get("filterType") in ("NOTIONAL", "MIN_NOTIONAL"):
                    result["min_notional"] = Decimal(str(f.get("minNotional", "0")))
                elif f.get("filterType") == "PRICE_FILTER":
                    result["tick_size"] = Decimal(str(f.get("tickSize", "0")))
            self._symbol_filters_cache[symbol] = result
            return result
        except Exception:
            return {"step_size": None, "min_notional": None, "tick_size": None}

    def _round_quantity(self, symbol: str, qty: Decimal) -> Decimal:
        """Round quantity to valid LOT_SIZE step for the symbol."""
        filters = self._get_symbol_filters(symbol)
        step = filters.get("step_size")
        if step and step > 0:
            # Round down to nearest step
            rounded = (qty // step) * step
            # Normalize to remove floating point artifacts
            return rounded.normalize()
        return qty

    @property
    def name(self) -> str:
        return "binance"

    def place_order(self, order: Order) -> Order:
        # Round quantity to valid LOT_SIZE step
        order.quantity = self._round_quantity(order.symbol, order.quantity)

        # Validate MIN_NOTIONAL
        filters = self._get_symbol_filters(order.symbol)
        min_notional = filters.get("min_notional")
        if min_notional and order.price:
            notional = order.quantity * order.price
            if notional < min_notional:
                raise BinanceBrokerError(
                    f"Orden de ${notional:.2f} menor al mínimo de ${min_notional} para {order.symbol}"
                )

        params: dict[str, Any] = {
            "symbol": order.symbol.upper(),
            "side": _SIDE_MAP.get(order.side.lower(), order.side.upper()),
            "type": _ORDER_TYPE_MAP.get(order.order_type.lower(), "MARKET"),
            "quantity": self._format_quantity(order.quantity),
        }

        if order.order_type.lower() == "limit" and order.price:
            params["price"] = self._format_price(order.symbol, order.price)
            params["timeInForce"] = "GTC"

        if order.client_order_id:
            params["newClientOrderId"] = order.client_order_id

        resp = self._signed_request("POST", "/api/v3/order", params)
        order.broker_order_id = str(resp["orderId"])
        order.status = self._map_status(resp.get("status", "NEW"))
        executed_qty = Decimal(str(resp.get("executedQty", "0")))
        order.filled_quantity = executed_qty
        if executed_qty > 0:
            avg_price = Decimal(str(resp.get("avgPrice", "0")))
            if avg_price <= 0:
                # Binance doesn't always return avgPrice for MARKET orders
                # Try to get current price as fallback
                try:
                    avg_price = self.get_quote(order.symbol)
                except Exception:
                    # Last resort: use order price if it was set
                    avg_price = order.price or Decimal("0")
            order.price = avg_price
        return order

    def place_stop_loss(self, symbol: str, quantity: Decimal, stop_price: Decimal, order_type: str = "stop", limit_price: Decimal | None = None) -> Order:
        """Places a STOP_LOSS or STOP_LOSS_LIMIT sell order on Binance.

        Args:
            symbol: Trading pair (e.g. BTCUSDT)
            quantity: Amount to sell when stop triggers
            stop_price: Trigger price for the stop loss
            order_type: 'stop' (market) or 'stop_limit' (limit)
            limit_price: Limit price for STOP_LOSS_LIMIT (defaults to 0.1% below stop to ensure fill)

        Returns the created Order with broker_order_id set.
        """
        params: dict[str, Any] = {
            "symbol": symbol.upper(),
            "side": "SELL",
            "type": _ORDER_TYPE_MAP.get(order_type, "STOP_LOSS"),
            "quantity": self._format_quantity(quantity),
            "stopPrice": self._format_price(symbol, stop_price),
        }
        if order_type == "stop_limit":
            # Limit price should be slightly below stop price to ensure fill on gap down
            eff_limit = limit_price if limit_price is not None else stop_price * Decimal("0.999")
            params["price"] = self._format_price(symbol, eff_limit)
            params["timeInForce"] = "GTC"

        resp = self._signed_request("POST", "/api/v3/order", params)
        return Order(
            client_order_id=f"sl-{symbol.lower()}-{int(time.time())}",
            broker_order_id=str(resp["orderId"]),
            timestamp=datetime.now(tz=UTC),
            symbol=symbol.upper(),
            side="sell",
            order_type=order_type,
            quantity=quantity,
            filled_quantity=Decimal("0"),
            status=self._map_status(resp.get("status", "NEW")),
            price=stop_price,
        )

    def place_take_profit(self, symbol: str, quantity: Decimal, tp_price: Decimal, order_type: str = "take_profit", limit_price: Decimal | None = None) -> Order:
        """Places a TAKE_PROFIT or TAKE_PROFIT_LIMIT sell order on Binance.

        Args:
            symbol: Trading pair (e.g. BTCUSDT)
            quantity: Amount to sell when take profit triggers
            tp_price: Trigger price for the take profit
            order_type: 'take_profit' (market) or 'take_profit_limit' (limit)
            limit_price: Limit price for TAKE_PROFIT_LIMIT (defaults to tp_price)

        Returns the created Order with broker_order_id set.
        """
        params: dict[str, Any] = {
            "symbol": symbol.upper(),
            "side": "SELL",
            "type": _ORDER_TYPE_MAP.get(order_type, "TAKE_PROFIT"),
            "quantity": self._format_quantity(quantity),
            "stopPrice": self._format_price(symbol, tp_price),
        }
        if order_type == "take_profit_limit":
            eff_limit = limit_price if limit_price is not None else tp_price
            params["price"] = self._format_price(symbol, eff_limit)
            params["timeInForce"] = "GTC"

        resp = self._signed_request("POST", "/api/v3/order", params)
        return Order(
            client_order_id=f"tp-{symbol.lower()}-{int(time.time())}",
            broker_order_id=str(resp["orderId"]),
            timestamp=datetime.now(tz=UTC),
            symbol=symbol.upper(),
            side="sell",
            order_type=order_type,
            quantity=quantity,
            filled_quantity=Decimal("0"),
            status=self._map_status(resp.get("status", "NEW")),
            price=tp_price,
        )

    def cancel_order(self, broker_order_id: str) -> Order | None:
        try:
            resp = self._signed_request(
                "DELETE",
                "/api/v3/order",
                {"orderId": broker_order_id},
            )
        except BinanceBrokerError:
            return None
        order = Order(
            client_order_id="cancel",
            broker_order_id=broker_order_id,
            timestamp=datetime.now(tz=UTC),
            symbol=resp.get("symbol", ""),
            side=resp.get("side", "").lower(),
            order_type="market",
            quantity=Decimal(str(resp.get("origQty", "0"))),
            filled_quantity=Decimal(str(resp.get("executedQty", "0"))),
            status=self._map_status(resp.get("status", "CANCELED")),
            price=None,
        )
        return order

    def get_order(self, broker_order_id: str) -> Order | None:
        try:
            resp = self._signed_request(
                "GET",
                "/api/v3/order",
                {"orderId": broker_order_id},
            )
        except BinanceBrokerError:
            return None
        return Order(
            client_order_id=resp.get("clientOrderId", ""),
            broker_order_id=broker_order_id,
            timestamp=datetime.now(tz=UTC),
            symbol=resp.get("symbol", ""),
            side=resp.get("side", "").lower(),
            order_type=resp.get("type", "MARKET").lower(),
            quantity=Decimal(str(resp.get("origQty", "0"))),
            filled_quantity=Decimal(str(resp.get("executedQty", "0"))),
            status=self._map_status(resp.get("status", "NEW")),
            price=Decimal(str(resp.get("price", "0"))) or None,
        )

    def get_account(self) -> AccountSnapshot:
        resp = self._signed_request("GET", "/api/v3/account", {})
        balances = resp.get("balances", [])
        cash = Decimal("0")
        positions_count = 0
        for b in balances:
            free = Decimal(str(b["free"]))
            if b["asset"] in ("USDT", "BUSD", "USDC", "UST"):
                cash += free
            elif free > 0:
                positions_count += 1

        equity = cash
        for b in balances:
            free = Decimal(str(b["free"]))
            asset = b["asset"]
            if asset not in ("USDT", "BUSD", "USDC", "UST") and free > 0:
                try:
                    price = self.get_quote(f"{asset}USDT")
                    equity += free * price
                except Exception:
                    pass

        return AccountSnapshot(
            timestamp=datetime.now(tz=UTC),
            cash=cash,
            equity=equity,
            buying_power=cash,
            margin_used=Decimal("0"),
            daily_pnl=Decimal("0"),
            total_pnl=Decimal("0"),
            open_positions_count=positions_count,
            strategy_run_id=None,
        )

    def get_quote(self, symbol: str) -> Decimal:
        try:
            resp = httpx.get(
                f"{self._base_url}/api/v3/ticker/price",
                params={"symbol": symbol.upper()},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return Decimal(str(resp.json()["price"]))
        except httpx.HTTPError as exc:
            raise BinanceBrokerError(f"No se pudo obtener precio de {symbol}: {exc}") from exc

    def _signed_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        params["timestamp"] = int(time.time() * 1000)
        query = urlencode(params)
        signature = hmac.new(
            self._api_secret,
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        headers = {"X-MBX-APIKEY": self._api_key}
        url = f"{self._base_url}{path}"

        try:
            if method == "GET":
                resp = httpx.get(url, params=params, headers=headers, timeout=self._timeout)
            elif method == "POST":
                resp = httpx.post(url, params=params, headers=headers, timeout=self._timeout)
            elif method == "DELETE":
                resp = httpx.delete(url, params=params, headers=headers, timeout=self._timeout)
            else:
                raise BinanceBrokerError(f"Método HTTP no soportado: {method}")
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Extract Binance error message from response body
            try:
                err_data = exc.response.json()
                err_msg = err_data.get("msg", str(err_data))
                err_code = err_data.get("code", "?")
                raise BinanceBrokerError(f"Binance API error {err_code}: {err_msg}") from exc
            except Exception:
                raise BinanceBrokerError(f"Error HTTP {exc.response.status_code} en {path}: {exc.response.text[:200]}") from exc
        except httpx.HTTPError as exc:
            raise BinanceBrokerError(f"Error de conexión en {path}: {exc}") from exc

        data = resp.json()
        if isinstance(data, dict) and "code" in data and "msg" in data:
            raise BinanceBrokerError(f"Binance API error {data['code']}: {data['msg']}")
        return data

    @staticmethod
    def _map_status(bin_status: str) -> str:
        mapping = {
            "NEW": "pending",
            "PARTIALLY_FILLED": "pending",
            "FILLED": "filled",
            "CANCELED": "cancelled",
            "REJECTED": "rejected",
            "EXPIRED": "rejected",
            "PENDING_CANCEL": "pending",
            "PENDING_NEW": "pending",
        }
        return mapping.get(bin_status.upper(), bin_status.lower())

    @staticmethod
    def _format_quantity(qty: Decimal) -> str:
        return f"{qty:.8f}".rstrip("0").rstrip(".") or "0"

    def _round_price(self, symbol: str, price: Decimal) -> Decimal:
        """Round price to valid PRICE_FILTER tickSize for the symbol."""
        filters = self._get_symbol_filters(symbol)
        tick = filters.get("tick_size")
        if tick and tick > 0:
            rounded = (price / tick).quantize(Decimal("1")) * tick
            return rounded.normalize()
        return price

    def _format_price(self, symbol: str, price: Decimal) -> str:
        """Format price, rounded to valid tickSize for the symbol."""
        rounded = self._round_price(symbol, price)
        return f"{rounded:.8f}".rstrip("0").rstrip(".") or "0"

    def sync_from_db(self, open_positions: list, initial_cash: Decimal) -> None:
        """Sync state from DB positions after a restart.

        For BinanceBroker, we don't manage internal cash/positions since
        the real balance lives on Binance. This is a no-op but exists
        for interface compatibility with MockBroker.
        """
        pass
