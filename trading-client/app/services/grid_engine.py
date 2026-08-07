"""Grid Trading Engine — lógica de grid trading orientada a CCXT.

Estrategia: divide el rango [lower, upper] en N niveles de precio.
- Coloca buy orders en niveles inferiores
- Coloca sell orders en niveles superiores
- Cuando un buy se ejecuta, coloca un sell en el nivel superior
- Cuando un sell se ejecuta, coloca un buy en el nivel inferior
- Profit = diferencia entre niveles × cantidad por nivel

CCXT-oriented: usa OrderRequest para CCXTAdapter, fallback a Order para MockBroker.
Verifica fills reales via fetch_open_orders (CCXT) o simulación por precio (Mock).
Funciona con cualquier exchange soportado por CCXT (Binance, Bybit, OKX, etc.)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from app.database.models.grid_bot import GridBot

logger = logging.getLogger(__name__)


class GridEngine:
    """Motor de grid trading que gestiona un GridBot — CCXT-oriented."""

    def __init__(self, broker, bot: GridBot) -> None:
        """Args:
            broker: Instancia del broker (MockBroker, BinanceBroker, o CCXTAdapter).
            bot: GridBot configuration from DB.
        """
        self._broker = broker
        self._bot = bot
        # Detect broker interface type
        self._is_ccxt = self._detect_ccxt()

    def _detect_ccxt(self) -> bool:
        """Detect if broker uses CCXT interface (OrderRequest -> OrderExecutionResult)."""
        # CCXTAdapter and other adapters have 'adapter_type' or use OrderRequest
        broker_class = type(self._broker).__name__
        if broker_class in ("CCXTAdapter", "BybitAdapter", "OKXAdapter", "KrakenAdapter",
                            "CoinbaseAdapter", "BinanceAdapter"):
            return True
        # Check if place_order signature matches CCXT (takes OrderRequest, not Order)
        import inspect
        try:
            sig = inspect.signature(self._broker.place_order)
            first_param = list(sig.parameters.values())[0]
            param_name = first_param.annotation
            if hasattr(param_name, '__name__'):
                return param_name.__name__ == "OrderRequest"
            return "OrderRequest" in str(param_name)
        except Exception:
            return False

    def _calculate_grid_levels(self) -> list[Decimal]:
        """Calculate the price levels for the grid."""
        lower = self._bot.lower_price
        upper = self._bot.upper_price
        n = self._bot.grid_count
        step = (upper - lower) / n
        return [lower + step * i for i in range(n + 1)]

    def _get_order_quantity(self) -> Decimal:
        """Calculate quantity per grid level based on investment."""
        qty_per_level = self._bot.investment_usd / self._bot.grid_count
        mid_price = (self._bot.lower_price + self._bot.upper_price) / 2
        if mid_price <= 0:
            return Decimal("0")
        return qty_per_level / mid_price

    def _get_current_price(self) -> Decimal | None:
        """Get current price from broker."""
        try:
            price = self._broker.get_quote(self._bot.symbol)
            return Decimal(str(price))
        except Exception as exc:
            logger.warning(f"GridEngine: No se pudo obtener precio de {self._bot.symbol}: {exc}")
            return None

    def initialize_grid(self) -> dict:
        """Initialize the grid by placing initial buy and sell orders via CCXT.

        Places buy orders below current price and sell orders above.
        Returns summary of placed orders.
        """
        current_price = self._get_current_price()
        if current_price is None:
            return {"error": "No se pudo obtener precio actual"}

        levels = self._calculate_grid_levels()
        qty = self._get_order_quantity()
        if qty <= 0:
            return {"error": "Cantidad calculada es 0"}

        state = self._bot.grid_state or {}
        buys_placed = 0
        sells_placed = 0

        for i, level_price in enumerate(levels):
            level_key = f"level_{i}"
            if level_key in state:
                continue

            if level_price < current_price:
                result = self._place_order("buy", level_price, qty)
                if result.get("success"):
                    state[level_key] = {
                        "side": "buy",
                        "price": str(level_price),
                        "qty": str(qty),
                        "order_id": result.get("order_id"),
                        "status": "open",
                    }
                    buys_placed += 1
            elif level_price > current_price:
                # Spot: only sell if we have position. Futures: can short.
                if self._bot.market_type in ("future", "swap"):
                    result = self._place_order("sell", level_price, qty)
                    if result.get("success"):
                        state[level_key] = {
                            "side": "sell",
                            "price": str(level_price),
                            "qty": str(qty),
                            "order_id": result.get("order_id"),
                            "status": "open",
                        }
                        sells_placed += 1

        self._bot.grid_state = state
        self._bot.orders_placed += buys_placed + sells_placed
        self._bot.last_run_at = datetime.now(tz=UTC)

        return {
            "initialized": True,
            "buys_placed": buys_placed,
            "sells_placed": sells_placed,
            "current_price": str(current_price),
            "grid_levels": len(levels),
            "broker_type": "ccxt" if self._is_ccxt else "legacy",
        }

    def _place_order(self, side: str, price: Decimal, qty: Decimal) -> dict:
        """Place a limit order via the broker — CCXT or legacy interface."""
        client_order_id = f"GRID-{self._bot.id}-{side}-{int(price * 100)}"

        try:
            if self._is_ccxt:
                return self._place_order_ccxt(side, price, qty, client_order_id)
            else:
                return self._place_order_legacy(side, price, qty, client_order_id)
        except Exception as exc:
            logger.error(f"GridEngine: Error placing {side} order at {price}: {exc}")
            return {"success": False, "error": str(exc)}

    def _place_order_ccxt(self, side: str, price: Decimal, qty: Decimal, client_order_id: str) -> dict:
        """Place order via CCXT interface (OrderRequest -> OrderExecutionResult)."""
        from app.brokers.models import OrderRequest, OrderSide, OrderType

        request = OrderRequest(
            symbol=self._bot.symbol,
            side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=qty,
            price=price,
            client_order_id=client_order_id,
            time_in_force="GTC",  # Good till cancelled — essential for grid
            metadata={
                "source": "grid_bot",
                "bot_id": self._bot.id,
                "grid_price": str(price),
                "market_type": self._bot.market_type,
            },
        )

        result = self._broker.place_order(request)

        if result.success and result.order:
            return {
                "success": True,
                "order_id": result.order.broker_order_id,
                "status": str(result.order.status),
                "client_order_id": client_order_id,
            }
        return {"success": False, "error": result.error or "unknown"}

    def _place_order_legacy(self, side: str, price: Decimal, qty: Decimal, client_order_id: str) -> dict:
        """Place order via legacy interface (Order -> Order) for MockBroker/BinanceBroker."""
        from app.database.models.order import Order as OrderModel

        order = OrderModel(
            user_id=self._bot.user_id,
            broker_id=self._bot.broker_id,
            client_order_id=client_order_id,
            idempotency_key=f"grid-{self._bot.id}-{side}-{int(price * 100)}",
            timestamp=datetime.now(tz=UTC),
            symbol=self._bot.symbol,
            side=side,
            order_type="limit",
            quantity=qty,
            price=price,
            status="submitted",
            metadata_json={
                "source": "grid_bot",
                "bot_id": self._bot.id,
                "grid_price": str(price),
            },
        )

        executed = self._broker.place_order(order)
        if executed.status == "filled":
            return {"success": True, "order_id": executed.broker_order_id, "status": "filled"}
        elif executed.status == "rejected":
            return {"success": False, "error": "rejected"}
        return {"success": True, "order_id": executed.broker_order_id, "status": executed.status}

    def _check_fills_via_ccxt(self, state: dict) -> list[str]:
        """Check which open orders have been filled via CCXT fetch_open_orders.

        Returns list of level keys that were filled.
        """
        filled_keys = []
        try:
            # CCXT: fetch_open_orders returns open (unfilled) orders
            # If an order is NOT in open_orders, it was filled or cancelled
            open_orders = self._broker._exchange.fetch_open_orders(self._bot.symbol) \
                if hasattr(self._broker, '_exchange') else []

            # Get set of client_order_ids still open
            open_client_ids = set()
            for oo in open_orders:
                cid = oo.get("clientOrderId") or oo.get("id")
                if cid:
                    open_client_ids.add(str(cid))

            for level_key, level_data in state.items():
                if level_data.get("status") != "open":
                    continue
                order_id = str(level_data.get("order_id", ""))
                client_id = f"GRID-{self._bot.id}-{level_data.get('side')}-{int(Decimal(str(level_data.get('price', 0))) * 100)}"

                # If order_id not in open orders, it was filled
                if order_id and order_id not in open_client_ids and client_id not in open_client_ids:
                    filled_keys.append(level_key)

        except Exception as exc:
            logger.warning(f"GridEngine: Could not fetch open orders from CCXT: {exc}")
        return filled_keys

    def _check_fills_via_price(self, state: dict, current_price: Decimal) -> list[str]:
        """Check fills by price simulation (fallback for MockBroker)."""
        filled_keys = []
        for level_key, level_data in state.items():
            if level_data.get("status") != "open":
                continue
            order_price = Decimal(str(level_data.get("price", 0)))
            side = level_data.get("side")

            if side == "buy" and current_price <= order_price:
                filled_keys.append(level_key)
            elif side == "sell" and current_price >= order_price:
                filled_keys.append(level_key)
        return filled_keys

    def check_and_rebalance(self) -> dict:
        """Check grid orders and rebalance: fill → place opposite order at adjacent level.

        CCXT: uses fetch_open_orders to detect real fills.
        Legacy: uses price simulation.
        """
        current_price = self._get_current_price()
        if current_price is None:
            return {"error": "No price"}

        state = self._bot.grid_state or {}
        levels = self._calculate_grid_levels()
        qty = self._get_order_quantity()

        # Detect fills — CCXT real or price simulation
        if self._is_ccxt:
            filled_keys = self._check_fills_via_ccxt(state)
        else:
            filled_keys = self._check_fills_via_price(state, current_price)

        fills_detected = 0
        new_orders = 0

        for level_key in filled_keys:
            level_data = state[level_key]
            side = level_data.get("side")
            # Find level index
            try:
                i = int(level_key.split("_")[1])
            except (IndexError, ValueError):
                continue

            # Mark as filled
            level_data["status"] = "filled"
            level_data["filled_at"] = datetime.now(tz=UTC).isoformat()
            fills_detected += 1
            self._bot.orders_filled += 1

            # Calculate profit and place opposite order
            if side == "buy" and i + 1 < len(levels):
                sell_price = levels[i + 1]
                result = self._place_order("sell", sell_price, qty)
                if result.get("success"):
                    next_key = f"level_{i + 1}"
                    state[next_key] = {
                        "side": "sell",
                        "price": str(sell_price),
                        "qty": str(qty),
                        "order_id": result.get("order_id"),
                        "status": "open",
                    }
                    new_orders += 1
                    profit = (sell_price - Decimal(str(level_data.get("price", 0)))) * qty
                    self._bot.realized_pnl += profit

            elif side == "sell" and i > 0:
                buy_price = levels[i - 1]
                result = self._place_order("buy", buy_price, qty)
                if result.get("success"):
                    prev_key = f"level_{i - 1}"
                    state[prev_key] = {
                        "side": "buy",
                        "price": str(buy_price),
                        "qty": str(qty),
                        "order_id": result.get("order_id"),
                        "status": "open",
                    }
                    new_orders += 1
                    profit = (Decimal(str(level_data.get("price", 0))) - buy_price) * qty
                    self._bot.realized_pnl += profit

        self._bot.grid_state = state
        self._bot.last_run_at = datetime.now(tz=UTC)

        return {
            "fills_detected": fills_detected,
            "new_orders": new_orders,
            "current_price": str(current_price),
            "realized_pnl": str(self._bot.realized_pnl),
            "fill_method": "ccxt" if self._is_ccxt else "price_sim",
        }

    def stop_grid(self) -> dict:
        """Stop the grid bot. Cancel all open orders via CCXT if possible."""
        state = self._bot.grid_state or {}
        cancelled = 0

        for level_key, level_data in state.items():
            if level_data.get("status") != "open":
                continue

            # Try to cancel via CCXT
            if self._is_ccxt and level_data.get("order_id"):
                try:
                    from app.brokers.models import CancelOrderRequest
                    self._broker.cancel_order(CancelOrderRequest(
                        broker_order_id=level_data["order_id"],
                        symbol=self._bot.symbol,
                    ))
                except Exception as exc:
                    logger.warning(f"GridEngine: Could not cancel order {level_data.get('order_id')}: {exc}")

            level_data["status"] = "cancelled"
            cancelled += 1

        self._bot.grid_state = state
        self._bot.is_active = False
        self._bot.status = "stopped"
        return {"cancelled": cancelled}

    def get_status(self) -> dict:
        """Get current grid bot status."""
        state = self._bot.grid_state or {}
        open_orders = sum(1 for v in state.values() if v.get("status") == "open")
        filled_orders = sum(1 for v in state.values() if v.get("status") == "filled")
        return {
            "bot_id": self._bot.id,
            "name": self._bot.name,
            "symbol": self._bot.symbol,
            "is_active": self._bot.is_active,
            "status": self._bot.status,
            "orders_placed": self._bot.orders_placed,
            "orders_filled": self._bot.orders_filled,
            "open_orders": open_orders,
            "filled_orders": filled_orders,
            "realized_pnl": str(self._bot.realized_pnl),
            "last_run_at": self._bot.last_run_at.isoformat() if self._bot.last_run_at else None,
            "grid_levels": self._bot.grid_count,
            "lower_price": str(self._bot.lower_price),
            "upper_price": str(self._bot.upper_price),
            "investment": str(self._bot.investment_usd),
            "broker_type": "ccxt" if self._is_ccxt else "legacy",
        }
