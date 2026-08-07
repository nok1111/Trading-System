"""DCA Engine — Dollar Cost Averaging usando CCXT.

Estrategia: compra una cantidad fija de USD cada X minutos.
- Reduce el impacto de la volatilidad promediando el precio de entrada
- Optional take-profit: vende todo cuando el precio sube X%
- Funciona con cualquier exchange soportado por CCXT
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.database.models.dca_bot import DCABot

logger = logging.getLogger(__name__)


class DCAEngine:
    """Motor de DCA que gestiona un DCABot."""

    def __init__(self, broker, bot: DCABot) -> None:
        self._broker = broker
        self._bot = bot

    def _get_current_price(self) -> Decimal | None:
        """Get current price from broker."""
        try:
            price = self._broker.get_quote(self._bot.symbol)
            return Decimal(str(price))
        except Exception as exc:
            logger.warning(f"DCAEngine: No se pudo obtener precio de {self._bot.symbol}: {exc}")
            return None

    def should_buy_now(self) -> bool:
        """Check if enough time has passed since last buy."""
        if not self._bot.is_active:
            return False

        # Check max buys limit
        if self._bot.max_buys > 0 and self._bot.buys_executed >= self._bot.max_buys:
            return False

        # Check interval
        if self._bot.last_buy_at is None:
            return True  # First buy

        elapsed = datetime.now(tz=UTC) - self._bot.last_buy_at
        if elapsed < timedelta(minutes=self._bot.interval_minutes):
            return False

        return True

    def execute_buy(self) -> dict:
        """Execute a DCA buy: purchase buy_amount_usd worth of the symbol."""
        current_price = self._get_current_price()
        if current_price is None or current_price <= 0:
            return {"error": "No se pudo obtener precio"}

        buy_amount = self._bot.buy_amount_usd
        qty = buy_amount / current_price

        try:
            from app.database.models.order import Order as OrderModel

            order = OrderModel(
                user_id=self._bot.user_id,
                broker_id=self._bot.broker_id,
                client_order_id=f"DCA-{self._bot.id}-{self._bot.buys_executed + 1}",
                idempotency_key=f"dca-{self._bot.id}-{self._bot.buys_executed + 1}",
                timestamp=datetime.now(tz=UTC),
                symbol=self._bot.symbol,
                side="buy",
                order_type="market",
                quantity=qty,
                status="submitted",
                metadata_json={
                    "source": "dca_bot",
                    "bot_id": self._bot.id,
                    "buy_number": self._bot.buys_executed + 1,
                },
            )

            executed = self._broker.place_order(order)
            if executed.status == "rejected":
                return {"error": "Orden rechazada", "reason": "Saldo insuficiente o error del broker"}

            fill_price = Decimal(str(executed.price)) if executed.price else current_price
            fill_qty = Decimal(str(executed.filled_quantity)) if executed.filled_quantity else qty

            # Update bot tracking
            self._bot.buys_executed += 1
            self._bot.total_invested += buy_amount
            self._bot.total_quantity += fill_qty

            # Recalculate average entry price
            if self._bot.total_quantity > 0:
                self._bot.avg_entry_price = self._bot.total_invested / self._bot.total_quantity

            self._bot.last_buy_at = datetime.now(tz=UTC)

            return {
                "executed": True,
                "buy_number": self._bot.buys_executed,
                "price": str(fill_price),
                "quantity": str(fill_qty),
                "amount_usd": str(buy_amount),
                "avg_entry": str(self._bot.avg_entry_price),
                "total_invested": str(self._bot.total_invested),
                "total_quantity": str(self._bot.total_quantity),
            }

        except Exception as exc:
            logger.error(f"DCAEngine: Error ejecutando buy: {exc}")
            return {"error": str(exc)}

    def check_take_profit(self) -> dict:
        """Check if take-profit target has been reached. If so, sell all."""
        if self._bot.take_profit_pct <= 0:
            return {"take_profit": False, "reason": "TP no configurado"}

        if self._bot.total_quantity <= 0:
            return {"take_profit": False, "reason": "Sin posición"}

        current_price = self._get_current_price()
        if current_price is None:
            return {"take_profit": False, "reason": "Sin precio"}

        avg_entry = self._bot.avg_entry_price
        if avg_entry <= 0:
            return {"take_profit": False, "reason": "Sin avg entry"}

        pnl_pct = ((current_price - avg_entry) / avg_entry) * 100
        if pnl_pct < self._bot.take_profit_pct:
            return {
                "take_profit": False,
                "current_pnl_pct": str(pnl_pct),
                "target_pct": str(self._bot.take_profit_pct),
            }

        # Execute take profit: sell all
        try:
            from app.database.models.order import Order as OrderModel

            sell_qty = self._bot.total_quantity
            order = OrderModel(
                user_id=self._bot.user_id,
                broker_id=self._bot.broker_id,
                client_order_id=f"DCA-TP-{self._bot.id}-{self._bot.buys_executed}",
                idempotency_key=f"dca-tp-{self._bot.id}-{self._bot.buys_executed}",
                timestamp=datetime.now(tz=UTC),
                symbol=self._bot.symbol,
                side="sell",
                order_type="market",
                quantity=sell_qty,
                status="submitted",
                metadata_json={
                    "source": "dca_bot",
                    "bot_id": self._bot.id,
                    "take_profit": True,
                },
            )

            executed = self._broker.place_order(order)
            if executed.status == "rejected":
                return {"error": "TP sell rechazada"}

            fill_price = Decimal(str(executed.price)) if executed.price else current_price
            proceeds = fill_price * sell_qty
            profit = proceeds - self._bot.total_invested

            self._bot.realized_pnl += profit
            self._bot.total_quantity = Decimal("0")
            self._bot.total_invested = Decimal("0")
            self._bot.avg_entry_price = Decimal("0")

            return {
                "take_profit": True,
                "sell_price": str(fill_price),
                "quantity": str(sell_qty),
                "proceeds": str(proceeds),
                "profit": str(profit),
                "realized_pnl": str(self._bot.realized_pnl),
            }
        except Exception as exc:
            logger.error(f"DCAEngine: Error en TP sell: {exc}")
            return {"error": str(exc)}

    def run_cycle(self) -> dict:
        """Main cycle: check if should buy, execute buy, check TP."""
        if not self._bot.is_active:
            return {"action": "inactive"}

        results = {}

        # Check take profit first
        tp_result = self.check_take_profit()
        if tp_result.get("take_profit"):
            results["take_profit"] = tp_result
            # After TP, reset and continue buying (bot stays active)
            return results

        # Check if should buy
        if self.should_buy_now():
            buy_result = self.execute_buy()
            results["buy"] = buy_result
        else:
            results["action"] = "waiting"
            if self._bot.last_buy_at:
                next_buy = self._bot.last_buy_at + timedelta(minutes=self._bot.interval_minutes)
                results["next_buy_at"] = next_buy.isoformat()

        return results

    def get_status(self) -> dict:
        """Get current DCA bot status."""
        next_buy = None
        if self._bot.is_active and self._bot.last_buy_at:
            next_buy = (self._bot.last_buy_at + timedelta(minutes=self._bot.interval_minutes)).isoformat()

        current_price = self._get_current_price()
        unrealized_pnl = Decimal("0")
        current_value = Decimal("0")
        if current_price and self._bot.total_quantity > 0:
            current_value = current_price * self._bot.total_quantity
            unrealized_pnl = current_value - self._bot.total_invested

        return {
            "bot_id": self._bot.id,
            "name": self._bot.name,
            "symbol": self._bot.symbol,
            "is_active": self._bot.is_active,
            "status": self._bot.status,
            "buy_amount_usd": str(self._bot.buy_amount_usd),
            "interval_minutes": self._bot.interval_minutes,
            "buys_executed": self._bot.buys_executed,
            "max_buys": self._bot.max_buys,
            "total_invested": str(self._bot.total_invested),
            "total_quantity": str(self._bot.total_quantity),
            "avg_entry_price": str(self._bot.avg_entry_price),
            "current_price": str(current_price) if current_price else None,
            "current_value": str(current_value),
            "unrealized_pnl": str(unrealized_pnl),
            "realized_pnl": str(self._bot.realized_pnl),
            "take_profit_pct": str(self._bot.take_profit_pct),
            "last_buy_at": self._bot.last_buy_at.isoformat() if self._bot.last_buy_at else None,
            "next_buy_at": next_buy,
        }
