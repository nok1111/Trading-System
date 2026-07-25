"""Pruebas del broker mock."""

from datetime import UTC, datetime
from decimal import Decimal

from app.brokers import MockBroker
from app.database.models.order import Order


def _sample_order(status: str = "pending") -> Order:
    return Order(
        client_order_id="test-1",
        broker_order_id=None,
        timestamp=datetime.now(tz=UTC),
        symbol="AAPL",
        side="BUY",
        order_type="market",
        quantity=Decimal("10"),
        filled_quantity=Decimal("0"),
        price=Decimal("100"),
        status=status,
        signal_id=None,
        metadata_json={},
    )


class TestMockBroker:
    def test_place_order_fills_immediately(self) -> None:
        broker = MockBroker()
        order = _sample_order()
        filled = broker.place_order(order)
        assert filled.status == "filled"
        assert filled.filled_quantity == Decimal("10")
        assert filled.broker_order_id.startswith("MOCK-")

    def test_get_order(self) -> None:
        broker = MockBroker()
        order = _sample_order()
        broker.place_order(order)
        retrieved = broker.get_order(order.broker_order_id)
        assert retrieved is order

    def test_cancel_pending_order(self) -> None:
        broker = MockBroker(fill_delay_orders=True)
        order = _sample_order()
        broker.place_order(order)
        assert order.status == "pending"
        cancelled = broker.cancel_order(order.broker_order_id)
        assert cancelled is not None
        assert cancelled.status == "cancelled"

    def test_get_account(self) -> None:
        broker = MockBroker(initial_cash=Decimal("75000"))
        account = broker.get_account()
        assert account.equity == Decimal("75000")
        assert account.buying_power == Decimal("75000")

    def test_get_quote(self) -> None:
        broker = MockBroker()
        assert broker.get_quote("SPY") == Decimal("100.00")

    def test_deposit_increases_cash(self) -> None:
        broker = MockBroker(initial_cash=Decimal("1000"))
        new_cash = broker.deposit(Decimal("500"))
        assert new_cash == Decimal("1500")
        assert broker.get_account().cash == Decimal("1500")

    def test_deposit_rejects_negative(self) -> None:
        broker = MockBroker(initial_cash=Decimal("1000"))
        try:
            broker.deposit(Decimal("-100"))
            assert False, "Should have raised"
        except ValueError:
            pass
