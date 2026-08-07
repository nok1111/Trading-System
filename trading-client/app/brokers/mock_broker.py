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
        self._positions: dict[str, Decimal] = {}  # positive=long, negative=short
        self._short_proceeds: Decimal = Decimal("0")  # cash from short sales
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
        meta = order.metadata_json or {}
        position_side = meta.get("position_side", "").upper()  # LONG, SHORT, or empty (spot)

        if side == "buy":
            if position_side == "SHORT":
                # Closing a short position: buy back the asset
                held_short = abs(min(Decimal("0"), self._positions.get(order.symbol, Decimal("0"))))
                if held_short >= order.quantity:
                    # Close short: return the proceeds difference
                    self._cash += total  # Return the short proceeds we held
                    self._cash -= total  # Pay for buying back
                    # Actually: short proceeds were already added when opening short
                    # Now we just pay to buy back, and release the held proceeds
                    self._short_proceeds -= total
                    self._cash += total  # Release held proceeds
                    self._cash -= total  # Pay for buyback
                    self._positions[order.symbol] = self._positions.get(order.symbol, Decimal("0")) + order.quantity
                    if self._positions[order.symbol] >= 0:
                        self._positions.pop(order.symbol, None)
                else:
                    order.status = "rejected"
                    return
            else:
                # Normal buy (open long or spot)
                if self._cash < total:
                    order.status = "rejected"
                    return
                self._cash -= total
                self._positions[order.symbol] = self._positions.get(order.symbol, Decimal("0")) + order.quantity
        elif side == "sell":
            if position_side == "SHORT":
                # Opening a short position: sell asset we don't own
                # Proceeds are held as collateral (margin)
                self._short_proceeds += total
                self._cash += total  # Add proceeds to cash (simplified margin model)
                self._positions[order.symbol] = self._positions.get(order.symbol, Decimal("0")) - order.quantity
            else:
                # Normal sell (close long or spot)
                held = self._positions.get(order.symbol, Decimal("0"))
                if held < order.quantity:
                    # Selling more than held — treat as partial sell
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
            # Calculate equity: cash + long positions value - short positions liability
            equity = self._cash
            positions_count = 0
            for symbol, qty in self._positions.items():
                price = self.get_quote(symbol)
                if qty > 0:
                    # Long position: adds value
                    equity += qty * price
                    positions_count += 1
                elif qty < 0:
                    # Short position: liability = qty * price (qty is negative)
                    # Equity already includes short proceeds, subtract current liability
                    equity += qty * price  # qty is negative, so this subtracts
                    positions_count += 1
            return AccountSnapshot(
                timestamp=datetime.now(tz=UTC),
                cash=self._cash,
                equity=equity,
                buying_power=self._cash,
                margin_used=Decimal("0"),
                daily_pnl=Decimal("0"),
                total_pnl=Decimal("0"),
                open_positions_count=positions_count,
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
            short_proceeds = Decimal("0")
            for pos in open_positions:
                if pos.status == "open":
                    side = getattr(pos, "side", "long").lower()
                    if side == "short":
                        # Short position: quantity is negative in our internal model
                        self._positions[pos.symbol] = -pos.quantity
                        self._prices[pos.symbol] = pos.entry_price
                        short_proceeds += pos.entry_price * pos.quantity
                    else:
                        self._positions[pos.symbol] = pos.quantity
                        self._prices[pos.symbol] = pos.entry_price
                        cost_basis += pos.entry_price * pos.quantity
            self._short_proceeds = short_proceeds
            self._cash = initial_cash - cost_basis + short_proceeds
