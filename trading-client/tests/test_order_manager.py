"""Tests para OrderManager — Fase 6.

Cobertura:
- Creación de draft con idempotency key
- Transiciones válidas (14 estados)
- Transiciones inválidas rechazadas
- Idempotencia (find_by_idempotency_key)
- Aprobación humana (LIVE_CONFIRMATION_REQUIRED)
- Reconciliación con broker
- Cancelación
- Estados terminales
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database.base import Base
from app.database.models.order_reconciliation import OrderReconciliation
from app.database.models.signal import Signal
from app.execution.order_manager import OrderManager
from app.models.signal import SignalCreate


@pytest.fixture
def session():
    """In-memory SQLite session for tests."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine)
    session = session_local()
    yield session
    session.close()


@pytest.fixture
def mock_broker():
    broker = MagicMock()
    def _place_order(order):
        order.status = "filled"
        order.filled_quantity = order.quantity
        order.broker_order_id = "broker-" + str(order.id)
        return order
    broker.place_order = MagicMock(side_effect=_place_order)
    broker.get_order_status = MagicMock(return_value="filled")
    return broker


@pytest.fixture
def settings():
    return Settings(
        DATABASE_URL="sqlite:///:memory:",
        TRADING_MODE="paper",
        LIVE_TRADING_ENABLED=False,
        LIVE_CONFIRMATION_REQUIRED=False,
    )


@pytest.fixture
def order_manager(session, mock_broker, settings):
    return OrderManager(broker=mock_broker, session=session, settings=settings)


def _make_signal_db(session) -> Signal:
    signal = Signal(
        timestamp=datetime.now(tz=UTC),
        symbol="BTCUSDT",
        signal_type="BUY",
        confidence=0.8,
        entry_price=Decimal("50000"),
        suggested_stop_loss=Decimal("48000"),
        suggested_take_profit=Decimal("55000"),
        strategy_name="test",
        explanation="test",
        metadata_json={},
        status="active",
    )
    session.add(signal)
    session.flush()
    return signal


def _make_signal_create() -> SignalCreate:
    return SignalCreate(
        timestamp=datetime.now(tz=UTC),
        symbol="BTCUSDT",
        signal_type="BUY",
        confidence=0.8,
        entry_price=Decimal("50000"),
        suggested_stop_loss=Decimal("48000"),
        suggested_take_profit=Decimal("55000"),
        strategy_name="test",
        explanation="test",
        metadata_json={},
    )


class TestOrderManagerCreate:
    def test_create_draft(self, order_manager, session):
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order = order_manager.create_draft(
            signal_create, signal_db,
            quantity=Decimal("0.1"),
            price=Decimal("50000"),
        )
        assert order.internal_status == "DRAFT"
        assert order.idempotency_key is not None
        assert len(order.idempotency_key) == 32  # uuid4().hex is 32 chars
        assert order.client_order_id is not None
        assert order.side == "BUY"
        assert order.quantity == Decimal("0.1")

    def test_idempotency_key_is_unique(self, order_manager, session):
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order1 = order_manager.create_draft(signal_create, signal_db, Decimal("0.1"), Decimal("50000"))
        order2 = order_manager.create_draft(signal_create, signal_db, Decimal("0.2"), Decimal("51000"))
        assert order1.idempotency_key != order2.idempotency_key

    def test_find_by_idempotency_key(self, order_manager, session):
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order = order_manager.create_draft(signal_create, signal_db, Decimal("0.1"), Decimal("50000"))
        found = order_manager.find_by_idempotency_key(order.idempotency_key)
        assert found is not None
        assert found.id == order.id

    def test_find_by_idempotency_key_not_found(self, order_manager):
        found = order_manager.find_by_idempotency_key("nonexistent-key")
        assert found is None


class TestOrderManagerTransitions:
    def test_validate_draft(self, order_manager, session):
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order = order_manager.create_draft(signal_create, signal_db, Decimal("0.1"), Decimal("50000"))
        order_manager.validate(order)
        assert order.internal_status == "VALIDATED"

    def test_risk_approve(self, order_manager, session):
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order = order_manager.create_draft(signal_create, signal_db, Decimal("0.1"), Decimal("50000"))
        order_manager.validate(order)
        order_manager.risk_approve(order)
        assert order.internal_status == "RISK_APPROVED"

    def test_invalid_transition_raises(self, order_manager, session):
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order = order_manager.create_draft(signal_create, signal_db, Decimal("0.1"), Decimal("50000"))
        # Cannot risk_approve from DRAFT (must go through VALIDATED first)
        with pytest.raises(ValueError, match="Cannot risk_approve"):
            order_manager.risk_approve(order)

    def test_cancel_from_draft(self, order_manager, session):
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order = order_manager.create_draft(signal_create, signal_db, Decimal("0.1"), Decimal("50000"))
        order_manager.cancel(order)
        assert order.internal_status == "CANCELLED"

    def test_cancel_terminal_raises(self, order_manager, session):
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order = order_manager.create_draft(signal_create, signal_db, Decimal("0.1"), Decimal("50000"))
        order_manager.cancel(order)
        with pytest.raises(ValueError, match="terminal state"):
            order_manager.cancel(order)

    def test_request_human_approval(self, order_manager, session):
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order = order_manager.create_draft(signal_create, signal_db, Decimal("0.1"), Decimal("50000"))
        order_manager.validate(order)
        order_manager.risk_approve(order)
        order_manager.request_human_approval(order)
        assert order.internal_status == "PENDING_APPROVAL"

    def test_approve(self, order_manager, session):
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order = order_manager.create_draft(signal_create, signal_db, Decimal("0.1"), Decimal("50000"))
        order_manager.validate(order)
        order_manager.risk_approve(order)
        order_manager.request_human_approval(order)
        order_manager.approve(order)
        assert order.internal_status == "APPROVED"

    def test_approve_from_wrong_state_raises(self, order_manager, session):
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order = order_manager.create_draft(signal_create, signal_db, Decimal("0.1"), Decimal("50000"))
        with pytest.raises(ValueError, match="Cannot approve"):
            order_manager.approve(order)


class TestOrderManagerSubmit:
    def test_submit_from_risk_approved(self, order_manager, session, mock_broker):
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order = order_manager.create_draft(signal_create, signal_db, Decimal("0.1"), Decimal("50000"))
        order_manager.validate(order)
        order_manager.risk_approve(order)
        result = order_manager.submit(order)
        assert result.internal_status in ("FILLED", "PARTIALLY_FILLED", "SUBMITTED")
        mock_broker.place_order.assert_called_once()

    def test_submit_from_approved(self, order_manager, session, mock_broker):
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order = order_manager.create_draft(signal_create, signal_db, Decimal("0.1"), Decimal("50000"))
        order_manager.validate(order)
        order_manager.risk_approve(order)
        order_manager.request_human_approval(order)
        order_manager.approve(order)
        result = order_manager.submit(order)
        assert result.internal_status in ("FILLED", "PARTIALLY_FILLED")
        mock_broker.place_order.assert_called_once()

    def test_submit_from_draft_raises(self, order_manager, session):
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order = order_manager.create_draft(signal_create, signal_db, Decimal("0.1"), Decimal("50000"))
        with pytest.raises(ValueError, match="Cannot submit"):
            order_manager.submit(order)


class TestOrderManagerReconcile:
    def test_reconcile_filled(self, order_manager, session, mock_broker):
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order = order_manager.create_draft(signal_create, signal_db, Decimal("0.1"), Decimal("50000"))
        order_manager.validate(order)
        order_manager.risk_approve(order)
        order_manager.submit(order)
        # Order is now FILLED (terminal), reconcile should be no-op
        assert order.internal_status == "FILLED"
        result = order_manager.reconcile(order)
        assert result.internal_status == "FILLED"

    def test_reconcile_discrepancy(self, order_manager, session, mock_broker):
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order = order_manager.create_draft(signal_create, signal_db, Decimal("0.1"), Decimal("50000"))
        order_manager.validate(order)
        order_manager.risk_approve(order)
        # Don't submit — simulate a submitted order manually
        order.internal_status = "SUBMITTED"
        order.status = "submitted"
        session.add(order)
        session.flush()

        # Broker says it's filled but we think it's submitted
        mock_broker.get_order_status.return_value = "filled"
        order.broker_order_id = "test-broker-id"
        session.add(order)
        session.flush()

        result = order_manager.reconcile(order)
        assert result.internal_status == "FILLED"
        assert result.status == "filled"

        # Check reconciliation record was created
        recon = session.query(OrderReconciliation).first()
        assert recon is not None
        assert "filled" in recon.diff

    def test_get_pending_reconciliation(self, order_manager, session):
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order = order_manager.create_draft(signal_create, signal_db, Decimal("0.1"), Decimal("50000"))
        order_manager.validate(order)
        order_manager.risk_approve(order)
        pending = order_manager.get_pending_reconciliation()
        assert len(pending) >= 1


class TestOrderManagerLifecycle:
    def test_full_lifecycle_paper(self, order_manager, session, mock_broker):
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order = order_manager.process_order_lifecycle(
            signal_create, signal_db, Decimal("0.1"), Decimal("50000"),
        )
        assert order is not None
        assert order.internal_status in ("FILLED", "PARTIALLY_FILLED")
        mock_broker.place_order.assert_called_once()

    def test_lifecycle_with_human_approval(self, session, mock_broker):
        settings = Settings(
            DATABASE_URL="sqlite:///:memory:",
            TRADING_MODE="live",
            LIVE_TRADING_ENABLED=True,
            LIVE_CONFIRMATION_REQUIRED=True,
        )
        om = OrderManager(broker=mock_broker, session=session, settings=settings)
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order = om.process_order_lifecycle(
            signal_create, signal_db, Decimal("0.1"), Decimal("50000"),
        )
        assert order is not None
        assert order.internal_status == "PENDING_APPROVAL"
        # Broker should NOT have been called
        mock_broker.place_order.assert_not_called()

    def test_lifecycle_no_human_approval_live(self, session, mock_broker):
        settings = Settings(
            DATABASE_URL="sqlite:///:memory:",
            TRADING_MODE="live",
            LIVE_TRADING_ENABLED=True,
            LIVE_CONFIRMATION_REQUIRED=False,
        )
        om = OrderManager(broker=mock_broker, session=session, settings=settings)
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order = om.process_order_lifecycle(
            signal_create, signal_db, Decimal("0.1"), Decimal("50000"),
        )
        assert order is not None
        assert order.internal_status in ("FILLED", "PARTIALLY_FILLED")
        mock_broker.place_order.assert_called_once()


class TestOrderManagerValidation:
    def test_validate_empty_symbol_raises(self, order_manager, session):
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order = order_manager.create_draft(signal_create, signal_db, Decimal("0.1"), Decimal("50000"))
        order.symbol = ""
        with pytest.raises(ValueError, match="no symbol"):
            order_manager.validate(order)

    def test_validate_zero_quantity_raises(self, order_manager, session):
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order = order_manager.create_draft(signal_create, signal_db, Decimal("0"), Decimal("50000"))
        with pytest.raises(ValueError, match="quantity must be positive"):
            order_manager.validate(order)

    def test_validate_invalid_side_raises(self, order_manager, session):
        signal_db = _make_signal_db(session)
        signal_create = _make_signal_create()
        order = order_manager.create_draft(signal_create, signal_db, Decimal("0.1"), Decimal("50000"))
        order.side = "INVALID"
        with pytest.raises(ValueError, match="Invalid side"):
            order_manager.validate(order)
