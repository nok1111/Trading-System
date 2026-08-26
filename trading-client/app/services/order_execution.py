"""Order execution service — idempotency, retry with backoff, and compensation.

Ensures reliable order placement even in the face of rate limits, timeouts,
and network errors. Uses idempotency keys to prevent duplicate orders.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.brokers.base import (
    BrokerAdapter,
    BrokerAuthError,
    BrokerError,
    BrokerRateLimitError,
    BrokerTimeoutError,
    DuplicateOrderError,
    InsufficientBalanceError,
    InvalidSymbolError,
    MinNotionalError,
)
from app.brokers.models import OrderExecutionResult, OrderRequest, OrderSide, OrderType
from app.database.models.order_idempotency import OrderIdempotencyRecord
from app.database.session import SessionLocal

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
BASE_DELAY = 1.0  # seconds
MAX_DELAY = 10.0  # seconds


def _retry_with_backoff(
    fn: Any,
    max_retries: int = MAX_RETRIES,
    base_delay: float = BASE_DELAY,
    max_delay: float = MAX_DELAY,
) -> Any:
    """Execute a function with exponential backoff retry.

    Retries on BrokerRateLimitError and BrokerTimeoutError.
    Raises immediately on other errors (auth, insufficient balance, etc.).
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except (BrokerRateLimitError, BrokerTimeoutError) as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = min(base_delay * (2 ** attempt), max_delay)
                logger.warning(
                    "Order retry %d/%d after %s in %.1fs",
                    attempt + 1,
                    max_retries,
                    type(exc).__name__,
                    delay,
                )
                time.sleep(delay)
            else:
                raise
        except DuplicateOrderError as exc:
            # This might be a retry that actually succeeded — log and re-raise
            # The caller should check if the order was actually placed
            logger.warning("DuplicateOrderError: %s", exc)
            raise
        except (BrokerAuthError, InsufficientBalanceError, InvalidSymbolError, MinNotionalError):
            # These errors are not retryable
            raise
        except BrokerError as exc:
            # Generic broker errors — retry once
            last_exc = exc
            if attempt < 1:
                time.sleep(base_delay)
            else:
                raise
    raise last_exc  # type: ignore


def place_order_with_idempotency(
    user_id: int,
    broker_id: str,
    adapter: BrokerAdapter,
    order_request: OrderRequest,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Place an order with idempotency protection and retry logic.

    If idempotency_key is provided and already exists in the database,
    returns the previous result instead of placing a new order.

    If idempotency_key is None, a new UUID is generated.

    Returns a dict with:
        - status: "ok" | "error" | "duplicate"
        - orderId, symbol, side, quantity, price, orderStatus (on success)
        - error (on failure)
        - idempotency_key: the key used
    """
    if idempotency_key is None:
        idempotency_key = str(uuid.uuid4())

    db = SessionLocal()
    try:
        # Check if this idempotency key already exists
        existing = db.query(OrderIdempotencyRecord).filter(
            OrderIdempotencyRecord.idempotency_key == idempotency_key,
            OrderIdempotencyRecord.user_id == user_id,
        ).first()

        if existing:
            if existing.status == "executed":
                return {
                    "status": "duplicate",
                    "idempotency_key": idempotency_key,
                    "orderId": existing.broker_order_id or "",
                    "symbol": existing.symbol,
                    "side": existing.side,
                    "quantity": existing.quantity,
                    "price": existing.price,
                    "orderStatus": "filled",
                    "message": "Orden ya fue ejecutada previamente",
                }
            elif existing.status == "failed":
                return {
                    "status": "error",
                    "idempotency_key": idempotency_key,
                    "error": existing.error or "Orden falló previamente",
                    "message": "Esta orden ya fue intentada y falló",
                }
            else:  # pending
                return {
                    "status": "pending",
                    "idempotency_key": idempotency_key,
                    "message": "Orden en progreso, espera",
                }

        # Create idempotency record
        record = OrderIdempotencyRecord(
            user_id=user_id,
            idempotency_key=idempotency_key,
            broker_id=broker_id,
            symbol=order_request.symbol,
            side=order_request.side.value,
            order_type=order_request.order_type.value,
            quantity=float(order_request.quantity),
            price=float(order_request.price) if order_request.price else None,
            status="pending",
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        record_id = record.id
    except Exception as exc:
        db.rollback()
        logger.error("Idempotency record creation failed: %s", exc)
        # If we can't create the record, still try to place the order
        # but without idempotency protection
        return _place_order_direct(adapter, order_request, idempotency_key)
    finally:
        db.close()

    # Place the order with retry
    try:
        result = _retry_with_backoff(lambda: adapter.place_order(order_request))

        # Update record
        db = SessionLocal()
        try:
            record = db.query(OrderIdempotencyRecord).filter(
                OrderIdempotencyRecord.id == record_id
            ).first()
            if record:
                if result.success:
                    record.status = "executed"
                    record.broker_order_id = result.order.broker_order_id if result.order else None
                    record.executed_at = datetime.now(tz=UTC)
                else:
                    record.status = "failed"
                    record.error = result.error or "Error desconocido"
            db.commit()
        finally:
            db.close()

        if not result.success:
            return {
                "status": "error",
                "idempotency_key": idempotency_key,
                "error": result.error or "Error desconocido",
            }

        order = result.order
        return {
            "status": "ok",
            "idempotency_key": idempotency_key,
            "orderId": order.broker_order_id or "",
            "symbol": order.symbol,
            "side": order.side.value,
            "type": order.order_type.value,
            "quantity": float(order.quantity),
            "price": float(order.price) if order.price else None,
            "executedQty": float(order.filled_quantity),
            "orderStatus": order.status.value,
        }
    except (BrokerRateLimitError, BrokerTimeoutError) as exc:
        _mark_record_failed(record_id, str(exc))
        return {
            "status": "error",
            "idempotency_key": idempotency_key,
            "error": f"Broker no disponible tras {MAX_RETRIES} intentos: {exc}",
        }
    except (BrokerAuthError, InsufficientBalanceError, InvalidSymbolError, MinNotionalError) as exc:
        _mark_record_failed(record_id, str(exc))
        return {
            "status": "error",
            "idempotency_key": idempotency_key,
            "error": str(exc),
        }
    except Exception as exc:
        _mark_record_failed(record_id, str(exc))
        logger.error("Order execution failed: %s", exc)
        return {
            "status": "error",
            "idempotency_key": idempotency_key,
            "error": str(exc),
        }


def _place_order_direct(
    adapter: BrokerAdapter,
    order_request: OrderRequest,
    idempotency_key: str,
) -> dict[str, Any]:
    """Place order without idempotency tracking (fallback)."""
    try:
        result = _retry_with_backoff(lambda: adapter.place_order(order_request))
        if not result.success:
            return {"status": "error", "idempotency_key": idempotency_key, "error": result.error or "Error"}
        order = result.order
        return {
            "status": "ok",
            "idempotency_key": idempotency_key,
            "orderId": order.broker_order_id or "",
            "symbol": order.symbol,
            "side": order.side.value,
            "type": order.order_type.value,
            "quantity": float(order.quantity),
            "price": float(order.price) if order.price else None,
            "executedQty": float(order.filled_quantity),
            "orderStatus": order.status.value,
        }
    except Exception as exc:
        return {"status": "error", "idempotency_key": idempotency_key, "error": str(exc)}


def _mark_record_failed(record_id: int, error: str) -> None:
    """Mark an idempotency record as failed."""
    db = SessionLocal()
    try:
        record = db.query(OrderIdempotencyRecord).filter(
            OrderIdempotencyRecord.id == record_id
        ).first()
        if record:
            record.status = "failed"
            record.error = error[:500]  # truncate
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
