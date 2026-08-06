"""Broker simulado para backtesting y paper trading."""

from datetime import UTC, datetime
from decimal import Decimal
from threading import Lock

from app.brokers.broker import Broker
from app.database.models.account_snapshot import AccountSnapshot
from app.database.models.order import Order


class MockBroker(Broker):
    """Broker mock que ejecuta órdenes inmediatamente a un precio fijo o de mercado."""

    def __init__(
        self,
        initial_cash: Decimal = Decimal("100000.00"),
        fill_delay_orders: bool = False,
    ) -> None:
        self._cash = initial_cash
        self._positions: dict[str, Decimal] = {}
        self._prices: dict[str, Decimal] = {}
        self._orders: dict[str, Order] = {}
        self._fill_delay_orders = fill_delay_orders
        self._counter = 0
        self._lock = Lock()

    @property
    def name(self) -> str:
        return "mock"

    def place_order(self, order: Order) -> Order:
        with self._lock:
            self._counter += 1
            broker_id = f"MOCK-{self._counter:06d}"
            order.broker_order_id = broker_id
            if self._fill_delay_orders:
                order.status = "pending"
            else:
                self._fill_order(order)
            self._orders[broker_id] = order
            return order

    def _fill_order(self, order: Order) -> None:
        fill_price = order.price or self.get_quote(order.symbol)
        total = order.quantity * fill_price
        side = order.side.lower()

        if side == "buy":
            if self._cash < total:
                order.status = "rejected"
                return
            self._cash -= total
            self._positions[order.symbol] = self._positions.get(order.symbol, Decimal("0")) + order.quantity
        elif side == "sell":
            held = self._positions.get(order.symbol, Decimal("0"))
            if held < order.quantity:
                self._cash += total
                if held > 0:
                    self._positions.pop(order.symbol, None)
            else:
                self._cash += total
                self._positions[order.symbol] -= order.quantity
                if self._positions[order.symbol] <= 0:
                    self._positions.pop(order.symbol, None)
        else:
            order.status = "rejected"
            return

        order.status = "filled"
        order.filled_quantity = order.quantity
        order.price = fill_price
        self._prices[order.symbol] = fill_price

    def cancel_order(self, broker_order_id: str) -> Order | None:
        order = self._orders.get(broker_order_id)
        if order is None:
            return None
        if order.status == "pending":
            order.status = "cancelled"
        return order

    def get_order(self, broker_order_id: str) -> Order | None:
        return self._orders.get(broker_order_id)

    def get_account(self) -> AccountSnapshot:
        with self._lock:
            equity = self._cash + sum(
                qty * self.get_quote(symbol) for symbol, qty in self._positions.items()
            )
            return AccountSnapshot(
                timestamp=datetime.now(tz=UTC),
                cash=self._cash,
                equity=equity,
                buying_power=self._cash,
                margin_used=Decimal("0"),
                daily_pnl=Decimal("0"),
                total_pnl=Decimal("0"),
                open_positions_count=len(self._positions),
                strategy_run_id=None,
            )

    def get_quote(self, symbol: str) -> Decimal:
        """Retorna precio en tiempo real, o último precio conocido, o $100 fallback."""
        try:
            from app.data.price_stream import get_price_stream
            stream = get_price_stream()
            if stream and stream.is_connected:
                price = stream.get_price(symbol)
                if price and price > 0:
                    self._prices[symbol] = Decimal(str(price))
                    return Decimal(str(price))
        except Exception:
            pass
        if symbol in self._prices:
            return self._prices[symbol]
        return Decimal("100.00")

    def set_cash(self, cash: Decimal) -> None:
        self._cash = cash

    def set_price(self, symbol: str, price: Decimal) -> None:
        """Actualiza el precio conocido de un símbolo."""
        with self._lock:
            self._prices[symbol] = price

    def deposit(self, amount: Decimal) -> Decimal:
        """Agrega fondos a la cuenta y retorna el nuevo balance de cash."""
        if amount <= 0:
            raise ValueError("El monto del depósito debe ser positivo")
        with self._lock:
            self._cash += amount
            return self._cash

    @property
    def positions(self) -> dict[str, Decimal]:
        return self._positions.copy()

    def sync_from_db(self, open_positions: list, initial_cash: Decimal) -> None:
        """Sync internal state from DB positions after a scheduler restart."""
        with self._lock:
            self._positions = {}
            self._prices = {}
            cost_basis = Decimal("0")
            for pos in open_positions:
                if pos.status == "open":
                    self._positions[pos.symbol] = pos.quantity
                    self._prices[pos.symbol] = pos.entry_price
                    cost_basis += pos.entry_price * pos.quantity
            self._cash = initial_cash - cost_basis
