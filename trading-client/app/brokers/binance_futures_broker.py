"""Adaptador de broker para Binance Futures (USDT-M Perpetuals).

Usa fapi.binance.com con soporte para:
- positionSide LONG/SHORT (Hedge Mode)
- Leverage management
- Margin type (isolated/cross)
- MARKET y LIMIT orders en futuros

Requiere que la cuenta tenga activado Hedge Mode en Binance Futures.
"""

import hashlib
import hmac
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import httpx

from app.brokers.binance_broker import BinanceBrokerError
from app.brokers.broker import Broker
from app.database.models.account_snapshot import AccountSnapshot
from app.database.models.order import Order

_FUTURES_BASE_URL = "https://fapi.binance.com"

_FUTURES_ORDER_TYPE_MAP = {
    "market": "MARKET",
    "limit": "LIMIT",
    "stop": "STOP_MARKET",
    "stop_limit": "STOP",
    "take_profit": "TAKE_PROFIT_MARKET",
    "take_profit_limit": "TAKE_PROFIT",
}

_SIDE_MAP = {
    "buy": "BUY",
    "sell": "SELL",
}


class BinanceFuturesBroker(Broker):
    """Broker para Binance USDT-M Futures con soporte de shorts y leverage.

    Requiere BROKER_API_KEY y BROKER_API_SECRET con permisos de Futures.
    La cuenta debe tener Hedge Mode activado para usar positionSide.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = _FUTURES_BASE_URL,
        testnet: bool = False,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret.encode("utf-8")
        self._timeout = timeout
        if testnet:
            self._base_url = "https://testnet.binancefuture.com"
        else:
            self._base_url = base_url.rstrip("/")
        self._leverage_cache: dict[str, int] = {}
        self._margin_type_cache: dict[str, str] = {}

    @property
    def name(self) -> str:
        return "binance_futures"

    def set_leverage(self, symbol: str, leverage: int) -> dict:
        """Set leverage for a symbol (1x-125x). Cached to avoid repeated API calls."""
        symbol = symbol.upper()
        if symbol in self._leverage_cache and self._leverage_cache[symbol] == leverage:
            return {"symbol": symbol, "leverage": leverage, "maxNotionalValue": 0}
        try:
            resp = self._signed_request("POST", "/fapi/v1/leverage", {
                "symbol": symbol,
                "leverage": leverage,
            })
            self._leverage_cache[symbol] = leverage
            return resp
        except BinanceBrokerError as exc:
            # If leverage already set, Binance returns error — ignore
            if "No need to change leverage" in str(exc):
                self._leverage_cache[symbol] = leverage
                return {"symbol": symbol, "leverage": leverage}
            raise

    def set_margin_type(self, symbol: str, margin_type: str = "ISOLATED") -> dict:
        """Set margin type: ISOLATED or CROSSED."""
        symbol = symbol.upper()
        margin_type = margin_type.upper()
        if symbol in self._margin_type_cache and self._margin_type_cache[symbol] == margin_type:
            return {"symbol": symbol, "marginType": margin_type}
        try:
            resp = self._signed_request("POST", "/fapi/v1/marginType", {
                "symbol": symbol,
                "marginType": margin_type,
            })
            self._margin_type_cache[symbol] = margin_type
            return resp
        except BinanceBrokerError as exc:
            if "No need to change margin type" in str(exc):
                self._margin_type_cache[symbol] = margin_type
                return {"symbol": symbol, "marginType": margin_type}
            raise

    def place_order(self, order: Order) -> Order:
        """Place a futures order with positionSide support.

        For SHORT positions: side=SELL, positionSide=SHORT
        For LONG positions: side=BUY, positionSide=LONG
        For closing SHORT: side=BUY, positionSide=SHORT
        For closing LONG: side=SELL, positionSide=LONG
        """
        meta = order.metadata_json or {}
        position_side = meta.get("position_side", "LONG").upper()  # LONG or SHORT
        leverage = meta.get("leverage", 1)

        # Set leverage before placing order
        if leverage and leverage > 1:
            try:
                self.set_leverage(order.symbol, int(leverage))
            except Exception:
                pass  # Non-critical, order will still work with default leverage

        params: dict[str, Any] = {
            "symbol": order.symbol.upper(),
            "side": _SIDE_MAP.get(order.side.lower(), order.side.upper()),
            "type": _FUTURES_ORDER_TYPE_MAP.get(order.order_type.lower(), "MARKET"),
            "positionSide": position_side,
            "quantity": f"{order.quantity:.8f}".rstrip("0").rstrip("."),
        }

        if order.order_type.lower() == "limit" and order.price:
            params["price"] = f"{order.price:.8f}".rstrip("0").rstrip(".")
            params["timeInForce"] = "GTC"

        # Stop-loss / take-profit for futures
        if order.order_type.lower() in ("stop", "stop_limit") and order.price:
            params["stopPrice"] = f"{order.price:.8f}".rstrip("0").rstrip(".")
            params["reduceOnly"] = "true"

        if order.order_type.lower() in ("take_profit", "take_profit_limit") and order.price:
            params["stopPrice"] = f"{order.price:.8f}".rstrip("0").rstrip(".")
            params["reduceOnly"] = "true"

        try:
            resp = self._signed_request("POST", "/fapi/v1/order", params)
        except BinanceBrokerError as exc:
            order.status = "rejected"
            order.metadata_json = {**(order.metadata_json or {}), "error": str(exc)}
            return order

        order.broker_order_id = str(resp.get("orderId", ""))
        order.status = self._map_status(resp.get("status", "NEW"))
        order.filled_quantity = Decimal(str(resp.get("executedQty", "0")))
        if resp.get("avgPrice") and float(resp["avgPrice"]) > 0:
            order.price = Decimal(str(resp["avgPrice"]))
        elif resp.get("price") and float(resp["price"]) > 0:
            order.price = Decimal(str(resp["price"]))
        return order

    def cancel_order(self, broker_order_id: str) -> Order | None:
        try:
            # For futures, need symbol + orderId
            # broker_order_id format: "symbol:orderId" or just "orderId"
            parts = broker_order_id.split(":")
            if len(parts) == 2:
                symbol, order_id = parts
            else:
                # Try to get from stored orders
                return None
            self._signed_request("DELETE", "/fapi/v1/order", {
                "symbol": symbol.upper(),
                "orderId": order_id,
            })
        except BinanceBrokerError:
            return None
        return None

    def get_order(self, broker_order_id: str) -> Order | None:
        parts = broker_order_id.split(":")
        if len(parts) != 2:
            return None
        symbol, order_id = parts
        try:
            resp = self._signed_request("GET", "/fapi/v1/order", {
                "symbol": symbol.upper(),
                "orderId": order_id,
            })
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
            price=Decimal(str(resp.get("avgPrice", "0"))) or None,
        )

    def get_account(self) -> AccountSnapshot:
        """Get futures account balance."""
        resp = self._signed_request("GET", "/fapi/v2/balance", {})
        cash = Decimal("0")
        positions_count = 0
        margin_used = Decimal("0")

        for item in resp:
            asset = item.get("asset", "")
            balance = Decimal(str(item.get("balance", "0")))
            if asset in ("USDT", "BUSD", "USDC"):
                cash += balance
            # Count open positions
            if item.get("positionAmt") and float(item.get("positionAmt", 0)) != 0:
                positions_count += 1
            margin_used += Decimal(str(item.get("maintMargin", "0")))

        # Also get positions for equity calculation
        equity = cash
        try:
            pos_resp = self._signed_request("GET", "/fapi/v2/positionRisk", {})
            for p in pos_resp:
                pos_amt = float(p.get("positionAmt", 0))
                if pos_amt != 0:
                    entry = float(p.get("entryPrice", 0))
                    mark = float(p.get("markPrice", 0))
                    unrealized = float(p.get("unRealizedProfit", 0))
                    equity += Decimal(str(unrealized))
        except Exception:
            pass

        return AccountSnapshot(
            timestamp=datetime.now(tz=UTC),
            cash=cash,
            equity=equity,
            buying_power=cash,
            margin_used=margin_used,
            daily_pnl=Decimal("0"),
            total_pnl=Decimal("0"),
            open_positions_count=positions_count,
            strategy_run_id=None,
        )

    def get_quote(self, symbol: str) -> Decimal:
        try:
            resp = httpx.get(
                f"{self._base_url}/fapi/v1/ticker/price",
                params={"symbol": symbol.upper()},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return Decimal(str(resp.json()["price"]))
        except httpx.HTTPError as exc:
            raise BinanceBrokerError(f"No se pudo obtener precio de futures {symbol}: {exc}") from exc

    def get_open_positions(self) -> list[dict]:
        """Get all open futures positions with details."""
        try:
            resp = self._signed_request("GET", "/fapi/v2/positionRisk", {})
            positions = []
            for p in resp:
                pos_amt = float(p.get("positionAmt", 0))
                if pos_amt != 0:
                    positions.append({
                        "symbol": p.get("symbol", ""),
                        "position_amt": pos_amt,
                        "entry_price": float(p.get("entryPrice", 0)),
                        "mark_price": float(p.get("markPrice", 0)),
                        "unrealized_pnl": float(p.get("unRealizedProfit", 0)),
                        "leverage": int(p.get("leverage", 1)),
                        "margin_type": p.get("marginType", "cross"),
                        "position_side": p.get("positionSide", "BOTH"),
                        "side": "short" if pos_amt < 0 else "long",
                    })
            return positions
        except BinanceBrokerError:
            return []

    def _signed_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Signed request for Binance Futures API (same HMAC-SHA256 as spot)."""
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
            try:
                err_data = exc.response.json()
                err_msg = err_data.get("msg", str(err_data))
                err_code = err_data.get("code", "?")
                raise BinanceBrokerError(f"Binance Futures error {err_code}: {err_msg}") from exc
            except Exception:
                raise BinanceBrokerError(f"Error HTTP {exc.response.status_code} en {path}: {exc.response.text[:200]}") from exc
        except httpx.HTTPError as exc:
            raise BinanceBrokerError(f"Error de conexión en {path}: {exc}") from exc

        data = resp.json()
        if isinstance(data, dict) and "code" in data and "msg" in data:
            raise BinanceBrokerError(f"Binance Futures error {data['code']}: {data['msg']}")
        return data

    @staticmethod
    def _map_status(bin_status: str) -> str:
        mapping = {
            "NEW": "submitted",
            "PARTIALLY_FILLED": "partial",
            "FILLED": "filled",
            "CANCELED": "cancelled",
            "REJECTED": "rejected",
            "EXPIRED": "expired",
            "WORKING": "submitted",
            "PENDING_NEW": "pending",
        }
        return mapping.get(bin_status.upper(), bin_status.lower())
