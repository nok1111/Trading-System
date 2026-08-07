"""Grid Trading Engine — lógica de grid trading usando CCXT.

Estrategia: divide el rango [lower, upper] en N niveles de precio.
- Coloca buy orders en niveles inferiores
- Coloca sell orders en niveles superiores
- Cuando un buy se ejecuta, coloca un sell en el nivel superior
- Cuando un sell se ejecuta, coloca un buy en el nivel inferior
- Profit = diferencia entre niveles × cantidad por nivel

Funciona con cualquier exchange soportado por CCXT (Binance, Bybit, OKX, etc.)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from app.database.models.grid_bot import GridBot

logger = logging.getLogger(__name__)


class GridEngine:
    """Motor de grid trading que gestiona un GridBot."""

    def __init__(self, broker, bot: GridBot) -> None:
        """Args:
            broker: Instancia del broker (MockBroker, BinanceBroker, o CCXTAdapter).
            bot: GridBot configuration from DB.
        """
        self._broker = broker
        self._bot = bot

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
        # Use mid-price as reference for quantity calculation
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
        """Initialize the grid by placing initial buy and sell orders.

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
                continue  # Already has an order at this level

            if level_price < current_price:
                # Place buy order
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
                # Place sell order (only if we have position)
                # For spot: skip sells if no position. For futures: can short.
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
        }

    def _place_order(self, side: str, price: Decimal, qty: Decimal) -> dict:
        """Place a limit order via the broker."""
        try:
            from app.database.models.order import Order as OrderModel

            order = OrderModel(
                user_id=self._bot.user_id,
                broker_id=self._bot.broker_id,
                client_order_id=f"GRID-{self._bot.id}-{side}-{int(price * 100)}",
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

            # Execute via broker
            executed = self._broker.place_order(order)
            if executed.status == "filled":
                return {"success": True, "order_id": executed.broker_order_id, "status": "filled"}
            elif executed.status == "rejected":
                return {"success": False, "error": "rejected"}
            return {"success": True, "order_id": executed.broker_order_id, "status": executed.status}
        except Exception as exc:
            logger.error(f"GridEngine: Error placing {side} order at {price}: {exc}")
            return {"success": False, "error": str(exc)}

    def check_and_rebalance(self) -> dict:
        """Check grid orders and rebalance: fill → place opposite order at adjacent level.

        This is the main loop function called by the scheduler.
        """
        current_price = self._get_current_price()
        if current_price is None:
            return {"error": "No price"}

        state = self._bot.grid_state or {}
        levels = self._calculate_grid_levels()
        qty = self._get_order_quantity()

        fills_detected = 0
        new_orders = 0

        for i, level_key in enumerate([f"level_{j}" for j in range(len(levels))]):
            if level_key not in state:
                continue
            level_data = state[level_key]
            if level_data.get("status") != "open":
                continue

            # Check if order was filled (price crossed the level)
            order_price = Decimal(str(level_data.get("price", 0)))
            side = level_data.get("side")

            was_filled = False
            if side == "buy" and current_price <= order_price:
                was_filled = True
            elif side == "sell" and current_price >= order_price:
                was_filled = True

            if was_filled:
                # Mark as filled
                level_data["status"] = "filled"
                level_data["filled_at"] = datetime.now(tz=UTC).isoformat()
                fills_detected += 1
                self._bot.orders_filled += 1

                # Calculate profit (sell above buy)
                if side == "buy" and i + 1 < len(levels):
                    # Place sell at next level up
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
                        # Track profit
                        profit = (sell_price - order_price) * qty
                        self._bot.realized_pnl += profit

                elif side == "sell" and i > 0:
                    # Place buy at next level down
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
                        profit = (order_price - buy_price) * qty
                        self._bot.realized_pnl += profit

        self._bot.grid_state = state
        self._bot.last_run_at = datetime.now(tz=UTC)

        return {
            "fills_detected": fills_detected,
            "new_orders": new_orders,
            "current_price": str(current_price),
            "realized_pnl": str(self._bot.realized_pnl),
        }

    def stop_grid(self) -> dict:
        """Stop the grid bot. Mark all open orders for cancellation."""
        state = self._bot.grid_state or {}
        cancelled = 0
        for level_key, level_data in state.items():
            if level_data.get("status") == "open":
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
        }
