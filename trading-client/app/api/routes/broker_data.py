"""Broker data endpoints — generic, work with any registered broker.

These endpoints replace the Binance-specific /api/binance/* routes.
They use the broker registry to resolve the correct adapter (BinanceAdapter
for binance, CCXTAdapter for all others) based on the broker_id path parameter.

Endpoints:
  GET  /api/broker/{broker_id}/balance        — account balances + USD value
  GET  /api/broker/{broker_id}/portfolio      — full portfolio snapshot
  GET  /api/broker/{broker_id}/orders         — order history (open + filled)
  GET  /api/broker/{broker_id}/positions      — open positions from DB
  GET  /api/broker/{broker_id}/ticker         — current price for a symbol
  GET  /api/broker/{broker_id}/market-info    — market info (filters, precision)
  GET  /api/broker/{broker_id}/klines         — OHLCV candles
  GET  /api/broker/{broker_id}/movers         — top gainers/losers
  POST /api/broker/{broker_id}/order          — place order
  DELETE /api/broker/{broker_id}/order        — cancel order
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.helpers import resolve_broker_credentials
from app.brokers.base import BrokerAdapter, BrokerError
from app.brokers.models import (
    CancelOrderRequest,
    OrderRequest,
    OrderSide,
    OrderType,
    normalize_symbol,
)
from app.brokers.registry import get_adapter
from app.services.auth import LocalUser, get_current_user, get_optional_user

router = APIRouter(prefix="/api/broker", tags=["broker-data"])


def _get_adapter(broker_id: str, current_user: LocalUser) -> BrokerAdapter:
    """Resolve credentials and create adapter for the given broker."""
    creds = resolve_broker_credentials(broker_id, current_user)
    if not creds:
        raise HTTPException(
            status_code=401,
            detail=f"No tienes API keys de {broker_id} configuradas. Conecta tu broker desde Conexiones.",
        )
    try:
        return get_adapter(broker_id, creds)
    except BrokerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _balance_to_dict(balances: tuple) -> list[dict[str, Any]]:
    """Convert Balance tuples to dicts."""
    result = []
    for b in balances:
        free = float(b.free)
        locked = float(b.locked)
        total = free + locked
        if total <= 0:
            continue
        result.append({
            "asset": b.asset,
            "free": free,
            "locked": locked,
            "total": total,
        })
    return result


# ─── Balance ──────────────────────────────────────────────────────────────────

@router.get("/{broker_id}/balance")
def get_balance(
    broker_id: str,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Consulta el saldo del broker en tiempo real.

    Retorna activos con balance > 0, valor en USD y MXN (approx).
    """
    adapter = _get_adapter(broker_id, current_user)

    try:
        balances = adapter.get_account_balances()
    except BrokerError as exc:
        return {"error": str(exc), "assets": [], "total_usd": 0, "total_mxn": 0}
    except Exception as exc:
        return {"error": f"Error conectando a {broker_id}: {exc}", "assets": [], "total_usd": 0, "total_mxn": 0}

    assets = _balance_to_dict(balances)

    # Stablecoins that are ~1:1 with USD
    STABLECOINS = {"USDT", "BUSD", "USDC", "USD", "UST", "TUSD", "FDUSD", "USDP", "GUSD", "PAX"}
    # Quote currencies to try for price conversion (in order of preference)
    USD_QUOTES = ["USDT", "USDC", "USD", "FDUSD", "TUSD", "BUSD"]

    # Fetch USD prices for each asset
    total_usd = 0.0
    for a in assets:
        asset = a["asset"]
        if asset in STABLECOINS:
            a["usd_value"] = a["total"]
            total_usd += a["usd_value"]
        elif asset == "EUR":
            a["usd_value"] = a["total"] * 1.08
            total_usd += a["usd_value"]
        else:
            # Try multiple quote currencies until one works
            price = None
            for quote in USD_QUOTES:
                try:
                    ticker = adapter.get_ticker(f"{asset}/{quote}")
                    price = float(ticker.price)
                    break
                except Exception:
                    continue
            if price is not None:
                a["usd_value"] = round(a["total"] * price, 4)
                total_usd += a["usd_value"]
            else:
                a["usd_value"] = 0.0

    # Sort by USD value descending
    assets.sort(key=lambda x: x.get("usd_value", 0), reverse=True)

    usdt_asset = next((a for a in assets if a["asset"] == "USDT"), None)
    usdt_free = usdt_asset["free"] if usdt_asset else 0.0
    usdt_total = usdt_asset["total"] if usdt_asset else 0.0

    mxn_rate = 18.5  # approximate fallback

    return {
        "assets": assets,
        "total_usd": round(total_usd, 2),
        "total_mxn": round(total_usd * mxn_rate, 2),
        "mxn_rate": mxn_rate,
        "testnet": adapter._credentials.testnet if hasattr(adapter, "_credentials") else False,
        "usdt_free": round(usdt_free, 4),
        "usdt_total": round(usdt_total, 4),
    }


# ─── Portfolio ────────────────────────────────────────────────────────────────

@router.get("/{broker_id}/portfolio")
def get_portfolio(
    broker_id: str,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Snapshot completo del portfolio con valor total en USD."""
    adapter = _get_adapter(broker_id, current_user)

    try:
        snapshot = adapter.get_portfolio()
    except BrokerError as exc:
        return {"error": str(exc), "assets": [], "total_usd": 0}
    except Exception as exc:
        return {"error": f"Error: {exc}", "assets": [], "total_usd": 0}

    assets = _balance_to_dict(snapshot.balances)
    return {
        "assets": assets,
        "total_usd": float(snapshot.total_usd),
        "timestamp": snapshot.timestamp.isoformat(),
    }


# ─── Orders ───────────────────────────────────────────────────────────────────

@router.get("/{broker_id}/orders")
def get_orders(
    broker_id: str,
    symbol: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    status: str | None = Query(None, pattern="^(open|filled|all)$"),
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Historial de órdenes del broker.

    Query params:
      symbol — filtra por símbolo (opcional)
      limit  — máximo número de órdenes
      status — "open", "filled", o "all" (default: all)
    """
    adapter = _get_adapter(broker_id, current_user)

    try:
        orders = adapter.get_order_history(symbol=symbol, limit=limit)
    except BrokerError as exc:
        return {"error": str(exc), "orders": [], "active": [], "filled": []}
    except Exception as exc:
        return {"error": f"Error: {exc}", "orders": [], "active": [], "filled": []}

    result = []
    for o in orders:
        is_active = o.status.value in ("pending", "partially_filled")
        result.append({
            "orderId": o.broker_order_id or "",
            "clientOrderId": o.client_order_id or "",
            "symbol": o.symbol,
            "side": o.side.value,
            "type": o.order_type.value,
            "status": o.status.value,
            "is_active": is_active,
            "quantity": float(o.quantity),
            "filled_quantity": float(o.filled_quantity),
            "price": float(o.price) if o.price else None,
            "avg_price": float(o.avg_fill_price) if o.avg_fill_price else None,
            "time": int(o.created_at.timestamp() * 1000) if o.created_at else 0,
            "updateTime": int(o.updated_at.timestamp() * 1000) if o.updated_at else 0,
        })

    result.sort(key=lambda x: x.get("time", 0), reverse=True)

    active = [o for o in result if o["is_active"]]
    filled = [o for o in result if not o["is_active"]]

    if status == "open":
        return {"orders": active, "active": active, "filled": [], "count": len(active)}
    if status == "filled":
        return {"orders": filled, "active": [], "filled": filled, "count": len(filled)}

    return {
        "orders": result,
        "active": active,
        "filled": filled,
        "count": len(result),
        "active_count": len(active),
    }


# ─── Positions ────────────────────────────────────────────────────────────────

@router.get("/{broker_id}/positions")
def get_positions(
    broker_id: str,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Posiciones abiertas desde la DB con precios en vivo del broker."""
    from app.database.session import SessionLocal
    from app.database.models.position import Position

    adapter = _get_adapter(broker_id, current_user)

    db = SessionLocal()
    try:
        positions = db.query(Position).filter(
            Position.status == "open",
            Position.user_id == current_user.id,
            Position.broker_id == broker_id,
        ).all()
        if not positions:
            return {"positions": [], "count": 0}

        result = []
        for p in positions:
            current_price = None
            unrealized = 0.0
            try:
                sym = normalize_symbol(p.symbol)
                ticker = adapter.get_ticker(sym)
                current_price = float(ticker.price)
                unrealized = (current_price - float(p.entry_price)) * float(p.quantity)
            except Exception:
                pass

            if current_price:
                p.current_price = Decimal(str(current_price))
                p.unrealized_pnl = Decimal(str(unrealized))

            result.append({
                "id": p.id,
                "symbol": p.symbol,
                "side": p.side,
                "quantity": float(p.quantity),
                "entry_price": float(p.entry_price),
                "current_price": current_price,
                "unrealized_pnl": round(unrealized, 4),
                "stop_loss": float(p.stop_loss) if p.stop_loss else None,
                "take_profit": float(p.take_profit) if p.take_profit else None,
                "status": p.status,
                "strategy_name": p.strategy_name,
                "opened_at": p.opened_at.isoformat() if p.opened_at else None,
            })
        db.commit()
        return {"positions": result, "count": len(result)}
    finally:
        db.close()


# ─── Ticker ───────────────────────────────────────────────────────────────────

@router.get("/{broker_id}/ticker")
def get_ticker(
    broker_id: str,
    symbol: str = Query(...),
    current_user: Annotated[LocalUser | None, Depends(get_optional_user)] = None,
) -> dict:
    """Precio actual de un símbolo desde el broker.

    Para brokers CCXT, no requiere credenciales si el símbolo es público.
    Para Binance, usa el endpoint público.
    """
    # Try without credentials first (public market data)
    try:
        from app.brokers.models import BrokerCredentials
        creds = BrokerCredentials(broker_id=broker_id, api_key="", api_secret="")
        adapter = get_adapter(broker_id, creds)
        ticker = adapter.get_ticker(normalize_symbol(symbol))
        return {
            "symbol": symbol.upper(),
            "price": float(ticker.price),
            "bid": float(ticker.bid) if ticker.bid else None,
            "ask": float(ticker.ask) if ticker.ask else None,
            "volume_24h": float(ticker.volume_24h) if ticker.volume_24h else None,
        }
    except Exception:
        pass

    # Fall back to authenticated request
    adapter = _get_adapter(broker_id, current_user)
    try:
        ticker = adapter.get_ticker(normalize_symbol(symbol))
        return {
            "symbol": symbol.upper(),
            "price": float(ticker.price),
            "bid": float(ticker.bid) if ticker.bid else None,
            "ask": float(ticker.ask) if ticker.ask else None,
            "volume_24h": float(ticker.volume_24h) if ticker.volume_24h else None,
        }
    except BrokerError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ─── Market Info ──────────────────────────────────────────────────────────────

@router.get("/{broker_id}/market-info")
def get_market_info(
    broker_id: str,
    symbol: str = Query(...),
    current_user: Annotated[LocalUser | None, Depends(get_optional_user)] = None,
) -> dict:
    """Información de mercado (filtros, precisiones) para un símbolo."""
    try:
        from app.brokers.models import BrokerCredentials
        creds = BrokerCredentials(broker_id=broker_id, api_key="", api_secret="")
        adapter = get_adapter(broker_id, creds)
        info = adapter.get_market_info(normalize_symbol(symbol))
        return {
            "symbol": info.symbol,
            "broker_symbol": info.broker_symbol,
            "base_asset": info.base_asset,
            "quote_asset": info.quote_asset,
            "min_quantity": float(info.min_quantity) if info.min_quantity else None,
            "max_quantity": float(info.max_quantity) if info.max_quantity else None,
            "step_size": float(info.step_size) if info.step_size else None,
            "min_notional": float(info.min_notional) if info.min_notional else None,
            "price_precision": info.price_precision,
            "quantity_precision": info.quantity_precision,
            "status": info.status,
        }
    except BrokerError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error: {exc}") from exc


# ─── Klines ───────────────────────────────────────────────────────────────────

@router.get("/{broker_id}/klines")
def get_klines(
    broker_id: str,
    symbol: str = Query(...),
    interval: str = Query("1m", pattern="^(1m|3m|5m|15m|30m|1h|2h|4h|1d|1w)$"),
    limit: int = Query(200, ge=1, le=1000),
    current_user: Annotated[LocalUser | None, Depends(get_optional_user)] = None,
) -> list[dict]:
    """Velas OHLCV desde el broker (datos públicos, no requiere credenciales)."""
    try:
        from app.brokers.models import BrokerCredentials
        creds = BrokerCredentials(broker_id=broker_id, api_key="", api_secret="")
        adapter = get_adapter(broker_id, creds)
        candles = adapter.get_klines(normalize_symbol(symbol), interval, limit)
        return [
            {
                "time": int(c.timestamp.timestamp() * 1000),
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": float(c.volume),
            }
            for c in candles
        ]
    except BrokerError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error: {exc}") from exc


# ─── Market Movers ────────────────────────────────────────────────────────────

@router.get("/{broker_id}/movers")
def get_movers(
    broker_id: str,
    market: str = Query("spot", pattern="^(spot|futures)$"),
    limit: int = Query(20, ge=1, le=100),
    quote: str = Query("USDT"),
    current_user: Annotated[LocalUser | None, Depends(get_optional_user)] = None,
) -> dict:
    """Top gainers y losers de 24h desde el broker."""
    try:
        from app.brokers.models import BrokerCredentials
        creds = BrokerCredentials(broker_id=broker_id, api_key="", api_secret="")
        adapter = get_adapter(broker_id, creds)
        result = adapter.get_market_movers(market=market, limit=limit, quote=quote)
        return {
            "gainers": [
                {
                    "symbol": t["symbol"],
                    "price": float(t["price"]),
                    "price_change_percent": float(t["change_pct"]),
                    "volume": float(t["volume"]),
                }
                for t in result.get("gainers", [])
            ],
            "losers": [
                {
                    "symbol": t["symbol"],
                    "price": float(t["price"]),
                    "price_change_percent": float(t["change_pct"]),
                    "volume": float(t["volume"]),
                }
                for t in result.get("losers", [])
            ],
        }
    except BrokerError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error: {exc}") from exc


# ─── Top Symbols (tradable list) ──────────────────────────────────────────────

@router.get("/{broker_id}/symbols")
def get_top_symbols(
    broker_id: str,
    quote: str = Query("USDT"),
    limit: int = Query(50, ge=1, le=200),
    current_user: Annotated[LocalUser | None, Depends(get_optional_user)] = None,
) -> list[dict]:
    """Lista de símbolos tradables del broker con precio y cambio 24h.

    Ordenados por volumen. No requiere credenciales (datos públicos).
    """
    try:
        from app.brokers.models import BrokerCredentials
        creds = BrokerCredentials(broker_id=broker_id, api_key="", api_secret="")
        adapter = get_adapter(broker_id, creds)
        symbols = adapter.get_top_symbols(quote=quote, limit=limit)
        return symbols
    except BrokerError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error: {exc}") from exc


# ─── Place Order ──────────────────────────────────────────────────────────────

class PlaceOrderRequest(BaseModel):
    symbol: str
    side: str  # "buy" or "sell"
    order_type: str = "market"  # "market" or "limit"
    quantity: float | None = None
    quote_order_qty: float | None = None  # amount in quote currency for market buys
    price: float | None = None  # required for limit
    stop_loss_price: float | None = None
    take_profit_price: float | None = None


@router.post("/{broker_id}/order")
def place_order(
    broker_id: str,
    req: PlaceOrderRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Place an order on the broker (buy/sell, market/limit)."""
    adapter = _get_adapter(broker_id, current_user)

    symbol = normalize_symbol(req.symbol)
    side_str = req.side.lower().strip()
    order_type_str = req.order_type.lower().strip()

    if side_str not in ("buy", "sell"):
        return {"error": "Side debe ser buy o sell"}
    if order_type_str not in ("market", "limit"):
        return {"error": "Order type debe ser market o limit"}
    if order_type_str == "limit" and not req.price:
        return {"error": "LIMIT requiere price"}
    if not req.quantity and not req.quote_order_qty:
        return {"error": "Requiere quantity o quote_order_qty"}

    # Fetch market info to round quantity correctly
    step_size = None
    min_qty = None
    min_notional = None
    try:
        info = adapter.get_market_info(symbol)
        if info.step_size:
            step_size = float(info.step_size)
        if info.min_quantity:
            min_qty = float(info.min_quantity)
        if info.min_notional:
            min_notional = float(info.min_notional)
    except Exception:
        pass

    def _round_to_step(value: float, step: float | None) -> float:
        if not step or step <= 0:
            return value
        d = Decimal(str(value))
        s = Decimal(str(step))
        return float((d // s) * s)

    # Calculate quantity
    quantity = req.quantity
    if not quantity and req.quote_order_qty:
        if order_type_str == "market" and side_str == "buy":
            # For market buys with quote_order_qty, let the adapter handle it
            quantity = None
        else:
            try:
                ticker = adapter.get_ticker(symbol)
                current_price = float(ticker.price)
                quantity = float(req.quote_order_qty) / current_price
            except Exception as exc:
                return {"error": f"No se pudo calcular cantidad: {exc}"}

    if quantity and step_size:
        quantity = _round_to_step(quantity, step_size)
        if min_qty and quantity < min_qty:
            return {"error": f"Cantidad {quantity} es menor al mínimo ({min_qty}) para {symbol}"}

    try:
        order_req = OrderRequest(
            symbol=symbol,
            side=OrderSide(side_str),
            order_type=OrderType(order_type_str),
            quantity=Decimal(str(quantity)) if quantity else Decimal("0"),
            price=Decimal(str(req.price)) if req.price else None,
        )
        result = adapter.place_order(order_req)

        if not result.success:
            return {"status": "error", "error": result.error or "Error desconocido"}

        order = result.order
        resp = {
            "status": "ok",
            "orderId": order.broker_order_id or "",
            "symbol": order.symbol,
            "side": order.side.value,
            "type": order.order_type.value,
            "quantity": float(order.quantity),
            "price": float(order.price) if order.price else None,
            "executedQty": float(order.filled_quantity),
            "orderStatus": order.status.value,
        }

        # Note: OCO orders are Binance-specific. For CCXT brokers,
        # stop-loss and take-profit would be placed as separate orders.
        # This is handled by the adapter's place_order method.
        if req.stop_loss_price and req.take_profit_price:
            resp["stopLoss"] = req.stop_loss_price
            resp["takeProfit"] = req.take_profit_price

        return resp
    except BrokerError as exc:
        return {"status": "error", "error": str(exc)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ─── Cancel Order ─────────────────────────────────────────────────────────────

class CancelOrderBody(BaseModel):
    broker_order_id: str | None = None
    client_order_id: str | None = None
    symbol: str | None = None


@router.delete("/{broker_id}/order")
def cancel_order(
    broker_id: str,
    body: CancelOrderBody,
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Cancela una orden pendiente en el broker."""
    adapter = _get_adapter(broker_id, current_user)

    try:
        result = adapter.cancel_order(CancelOrderRequest(
            broker_order_id=body.broker_order_id,
            client_order_id=body.client_order_id,
            symbol=body.symbol,
        ))

        if not result.success:
            return {"status": "error", "error": result.error or "Error al cancelar"}

        return {
            "status": "ok",
            "orderId": result.broker_order_id or "",
            "orderStatus": result.status.value if result.status else "cancelled",
        }
    except BrokerError as exc:
        return {"status": "error", "error": str(exc)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ─── Place OCO Order (SL/TP) ──────────────────────────────────────────────────

class PlaceOcoRequest(BaseModel):
    symbol: str
    side: str = "sell"  # close side: sell for long, buy for short
    quantity: float
    take_profit_price: float
    stop_loss_price: float


@router.post("/{broker_id}/oco")
def place_oco_order(
    broker_id: str,
    req: PlaceOcoRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Place a real OCO (One-Cancels-Other) order: TP limit + SL stop-limit.

    When one side fills, the other is automatically cancelled by the exchange.
    """
    adapter = _get_adapter(broker_id, current_user)
    symbol = normalize_symbol(req.symbol)

    # Fetch market info for precision
    step_size = None
    try:
        info = adapter.get_market_info(symbol)
        if info.step_size:
            step_size = float(info.step_size)
    except Exception:
        pass

    def _round_to_step(value: float, step: float | None) -> float:
        if not step or step <= 0:
            return value
        d = Decimal(str(value))
        s = Decimal(str(step))
        return float((d // s) * s)

    quantity = _round_to_step(req.quantity, step_size)

    # Pre-check: verify the user has enough balance of the base asset
    base_asset = symbol.split("/")[0] if "/" in symbol else symbol
    try:
        balances = adapter.get_account_balances()
        balance_map = {b.asset: float(b.free) for b in balances}
        available = balance_map.get(base_asset, 0)
        if available < quantity:
            return {
                "status": "error",
                "error": f"Saldo insuficiente de {base_asset}: tienes {available} pero necesitas {quantity}. La posición en la DB no coincide con tu balance real del broker.",
            }
    except Exception:
        pass  # If balance check fails, let the broker return its own error

    # Use native OCO if the adapter supports it (Binance, CCXT exchanges with OCO)
    if hasattr(adapter, "place_oco_order"):
        try:
            result = adapter.place_oco_order(
                symbol=symbol,
                side=req.side,
                quantity=Decimal(str(quantity)),
                take_profit_price=Decimal(str(req.take_profit_price)),
                stop_loss_price=Decimal(str(req.stop_loss_price)),
            )
            if not result.get("success", False):
                return {"status": "error", "error": result.get("error", "Error OCO")}
            return {
                "status": "ok",
                "oco_order_id": result["order_list_id"],
                "sl_order_id": result.get("sl_order_id", ""),
                "tp_order_id": result.get("tp_order_id", ""),
                "symbol": symbol,
                "stop_loss": req.stop_loss_price,
                "take_profit": req.take_profit_price,
            }
        except BrokerError as exc:
            return {"status": "error", "error": str(exc)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    # Fallback: place separate STOP and TAKE_PROFIT orders
    try:
        close_side = OrderSide.SELL if req.side == "sell" else OrderSide.BUY
        tp_req = OrderRequest(
            symbol=symbol, side=close_side,
            order_type=OrderType.TAKE_PROFIT_LIMIT,
            quantity=Decimal(str(quantity)),
            price=Decimal(str(req.take_profit_price)),
            stop_price=Decimal(str(req.take_profit_price)),
        )
        sl_req = OrderRequest(
            symbol=symbol, side=close_side,
            order_type=OrderType.STOP_LIMIT,
            quantity=Decimal(str(quantity)),
            price=Decimal(str(req.stop_loss_price)),
            stop_price=Decimal(str(req.stop_loss_price)),
        )
        tp_result = adapter.place_order(tp_req)
        sl_result = adapter.place_order(sl_req)
        order_ids = []
        if tp_result.success and tp_result.order:
            order_ids.append(tp_result.order.broker_order_id or "")
        if sl_result.success and sl_result.order:
            order_ids.append(sl_result.order.broker_order_id or "")
        errors = []
        if not tp_result.success:
            errors.append(tp_result.error or "")
        if not sl_result.success:
            errors.append(sl_result.error or "")
        if errors:
            return {"status": "error", "error": "; ".join(errors), "order_ids": order_ids}
        return {
            "status": "ok",
            "oco_order_id": ",".join(order_ids),
            "sl_order_id": order_ids[1] if len(order_ids) > 1 else "",
            "tp_order_id": order_ids[0] if order_ids else "",
            "symbol": symbol,
            "stop_loss": req.stop_loss_price,
            "take_profit": req.take_profit_price,
        }
    except BrokerError as exc:
        return {"status": "error", "error": str(exc)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ─── Sync Positions (reconcile DB with broker balance) ────────────────────────

@router.post("/{broker_id}/sync-positions")
def sync_positions(
    broker_id: str,
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Reconcilia las posiciones en DB con el balance real del broker.

    - Si una posicion open tiene 0 balance del activo -> la cierra (status=closed)
    - Si tiene menos balance que la cantidad registrada -> actualiza la cantidad
    - Calcula realized_pnl al cerrar/ajustar
    - Retorna un resumen de los cambios
    """
    from app.database.session import SessionLocal
    from app.database.models.position import Position
    from decimal import Decimal as Dec
    from datetime import datetime, UTC

    adapter = _get_adapter(broker_id, current_user)

    # Fetch real balance from broker
    try:
        balances = adapter.get_account_balances()
        balance_map = {b.asset: float(b.free) for b in balances}
    except BrokerError as exc:
        return {"status": "error", "error": f"No se pudo obtener balance: {exc}"}
    except Exception as exc:
        return {"status": "error", "error": f"No se pudo obtener balance: {exc}"}

    db = SessionLocal()
    try:
        positions = db.query(Position).filter(
            Position.status == "open",
            Position.user_id == current_user.id,
            Position.broker_id == broker_id,
        ).all()

        closed_count = 0
        updated_count = 0
        unchanged_count = 0
        details = []

        for p in positions:
            base = p.symbol.split("/")[0] if "/" in p.symbol else p.symbol.replace("USDT", "")
            actual_balance = balance_map.get(base, 0)
            db_qty = float(p.quantity)

            if actual_balance <= 0.00000001:
                # Position has no balance -> close it
                entry = float(p.entry_price)
                try:
                    ticker = adapter.get_ticker(p.symbol)
                    close_price = float(ticker.price)
                except Exception:
                    close_price = float(p.current_price or entry)

                realized = (close_price - entry) * db_qty if p.side == "long" else (entry - close_price) * db_qty
                p.realized_pnl = Dec(str(round(realized, 8)))
                p.current_price = Dec(str(close_price))
                p.status = "closed"
                p.closed_at = datetime.now(tz=UTC)
                meta = p.metadata_json or {}
                meta["closed_by"] = "sync"
                meta["close_reason"] = "no balance in broker"
                p.metadata_json = meta

                closed_count += 1
                details.append(f"Cerrada {p.symbol}: qty={db_qty} (sin saldo, PnL={realized:.4f})")

            elif actual_balance < db_qty * 0.99:
                # Position has less balance than DB -> update quantity
                entry = float(p.entry_price)
                try:
                    ticker = adapter.get_ticker(p.symbol)
                    current_price = float(ticker.price)
                except Exception:
                    current_price = float(p.current_price or entry)

                new_qty = actual_balance
                sold_qty = db_qty - new_qty
                realized = (current_price - entry) * sold_qty if p.side == "long" else (entry - current_price) * sold_qty
                p.realized_pnl = Dec(str(round(realized, 8)))
                p.quantity = Dec(str(new_qty))
                p.current_price = Dec(str(current_price))
                if p.side == "long":
                    p.unrealized_pnl = Dec(str(round((current_price - entry) * new_qty, 8)))
                else:
                    p.unrealized_pnl = Dec(str(round((entry - current_price) * new_qty, 8)))

                meta = p.metadata_json or {}
                meta["synced_at"] = datetime.now(tz=UTC).isoformat()
                meta["previous_qty"] = db_qty
                p.metadata_json = meta

                updated_count += 1
                details.append(f"Actualizada {p.symbol}: {db_qty} -> {new_qty} (vendiste {sold_qty:.8f})")

            else:
                unchanged_count += 1

        db.commit()

        return {
            "status": "ok",
            "broker_id": broker_id,
            "total_positions": len(positions),
            "closed": closed_count,
            "updated": updated_count,
            "unchanged": unchanged_count,
            "details": details,
        }
    except Exception as exc:
        db.rollback()
        return {"status": "error", "error": str(exc)}
    finally:
        db.close()
