"""Tests for the order execution service (idempotency + retry)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.brokers.base import (
    BrokerError,
    BrokerRateLimitError,
    BrokerTimeoutError,
    BrokerAuthError,
    InsufficientBalanceError,
)
from app.brokers.models import OrderExecutionResult, OrderRequest, OrderSide, OrderType
from app.database.base import Base


@pytest.fixture(autouse=True)
def setup_db():
    """Use in-memory SQLite for each test."""
    # Override settings
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["APP_ENV"] = "development"

    from sqlalchemy.pool import StaticPool
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_session = sessionmaker(bind=test_engine)

    # Patch SessionLocal in the order_execution module
    import app.services.order_execution as oe
    import app.database.session as ds

    Base.metadata.create_all(bind=test_engine)
    original_session = ds.SessionLocal
    oe.SessionLocal = test_session

    yield test_session

    oe.SessionLocal = original_session
    Base.metadata.drop_all(bind=test_engine)


def _make_mock_adapter(success: bool = True, side_effect: Exception | None = None) -> MagicMock:
    """Create a mock broker adapter."""
    adapter = MagicMock()
    if side_effect:
        adapter.place_order.side_effect = side_effect
    else:
        result = MagicMock()
        result.success = success
        result.error = None if success else "Test error"
        order = MagicMock()
        order.broker_order_id = "test-order-123"
        order.symbol = "BTC/USDT"
        order.side.value = "buy"
        order.order_type.value = "market"
        order.quantity = 0.1
        order.price = None
        order.filled_quantity = 0.1
        order.status.value = "filled"
        result.order = order
        adapter.place_order.return_value = result
    return adapter


def _make_order_request() -> OrderRequest:
    return OrderRequest(
        symbol="BTC/USDT",
        side=OrderSide("buy"),
        order_type=OrderType("market"),
        quantity=0.1,
    )


class TestRetryWithBackoff:
    """Tests for the _retry_with_backoff function."""

    def test_success_first_try(self):
        from app.services.order_execution import _retry_with_backoff

        fn = MagicMock(return_value="success")
        result = _retry_with_backoff(fn, max_retries=3, base_delay=0.01)
        assert result == "success"
        assert fn.call_count == 1

    def test_retries_on_rate_limit(self):
        from app.services.order_execution import _retry_with_backoff

        fn = MagicMock(side_effect=[
            BrokerRateLimitError("Rate limited"),
            BrokerRateLimitError("Rate limited"),
            "success",
        ])
        result = _retry_with_backoff(fn, max_retries=3, base_delay=0.01)
        assert result == "success"
        assert fn.call_count == 3

    def test_fails_after_max_retries(self):
        from app.services.order_execution import _retry_with_backoff

        fn = MagicMock(side_effect=BrokerRateLimitError("Rate limited"))
        with pytest.raises(BrokerRateLimitError):
            _retry_with_backoff(fn, max_retries=2, base_delay=0.01)
        assert fn.call_count == 3  # initial + 2 retries

    def test_no_retry_on_auth_error(self):
        from app.services.order_execution import _retry_with_backoff

        fn = MagicMock(side_effect=BrokerAuthError("Invalid key"))
        with pytest.raises(BrokerAuthError):
            _retry_with_backoff(fn, max_retries=3, base_delay=0.01)
        assert fn.call_count == 1

    def test_no_retry_on_insufficient_balance(self):
        from app.services.order_execution import _retry_with_backoff

        fn = MagicMock(side_effect=InsufficientBalanceError("Not enough funds"))
        with pytest.raises(InsufficientBalanceError):
            _retry_with_backoff(fn, max_retries=3, base_delay=0.01)
        assert fn.call_count == 1

    def test_retries_on_timeout(self):
        from app.services.order_execution import _retry_with_backoff

        fn = MagicMock(side_effect=[
            BrokerTimeoutError("Timeout"),
            "success",
        ])
        result = _retry_with_backoff(fn, max_retries=3, base_delay=0.01)
        assert result == "success"
        assert fn.call_count == 2


class TestPlaceOrderWithIdempotency:
    """Tests for the place_order_with_idempotency function."""

    def test_successful_order(self, setup_db):
        from app.services.order_execution import place_order_with_idempotency

        adapter = _make_mock_adapter(success=True)
        result = place_order_with_idempotency(
            user_id=1,
            broker_id="binance",
            adapter=adapter,
            order_request=_make_order_request(),
            idempotency_key="test-key-1",
        )

        assert result["status"] == "ok"
        assert result["orderId"] == "test-order-123"
        assert result["idempotency_key"] == "test-key-1"
        assert adapter.place_order.call_count == 1

    def test_duplicate_key_returns_cached(self, setup_db):
        from app.services.order_execution import place_order_with_idempotency

        adapter = _make_mock_adapter(success=True)

        # First call
        result1 = place_order_with_idempotency(
            user_id=1,
            broker_id="binance",
            adapter=adapter,
            order_request=_make_order_request(),
            idempotency_key="dup-key-1",
        )
        assert result1["status"] == "ok"

        # Second call with same key should return duplicate
        result2 = place_order_with_idempotency(
            user_id=1,
            broker_id="binance",
            adapter=adapter,
            order_request=_make_order_request(),
            idempotency_key="dup-key-1",
        )
        assert result2["status"] == "duplicate"
        assert result2["orderId"] == "test-order-123"
        # Adapter should only be called once
        assert adapter.place_order.call_count == 1

    def test_failed_order_marks_record(self, setup_db):
        from app.services.order_execution import place_order_with_idempotency

        adapter = _make_mock_adapter(success=False)
        result = place_order_with_idempotency(
            user_id=1,
            broker_id="binance",
            adapter=adapter,
            order_request=_make_order_request(),
            idempotency_key="fail-key-1",
        )

        assert result["status"] == "error"

        # Subsequent call with same key should return error (not retry)
        result2 = place_order_with_idempotency(
            user_id=1,
            broker_id="binance",
            adapter=adapter,
            order_request=_make_order_request(),
            idempotency_key="fail-key-1",
        )
        assert result2["status"] == "error"
        # Adapter should only be called once (second call returns cached error)
        assert adapter.place_order.call_count == 1

    def test_auto_generates_key(self, setup_db):
        from app.services.order_execution import place_order_with_idempotency

        adapter = _make_mock_adapter(success=True)
        result = place_order_with_idempotency(
            user_id=1,
            broker_id="binance",
            adapter=adapter,
            order_request=_make_order_request(),
            idempotency_key=None,  # auto-generate
        )

        assert result["status"] == "ok"
        assert "idempotency_key" in result
        assert len(result["idempotency_key"]) > 0

    def test_retries_on_rate_limit_then_succeeds(self, setup_db):
        from app.services.order_execution import place_order_with_idempotency

        adapter = _make_mock_adapter(success=True)
        adapter.place_order.side_effect = [
            BrokerRateLimitError("Rate limited"),
            adapter.place_order.return_value,  # success on retry
        ]

        result = place_order_with_idempotency(
            user_id=1,
            broker_id="binance",
            adapter=adapter,
            order_request=_make_order_request(),
            idempotency_key="retry-key-1",
        )

        assert result["status"] == "ok"
        assert adapter.place_order.call_count == 2
