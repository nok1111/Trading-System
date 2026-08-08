"""Order Manager — Fase 6.

Gestiona el ciclo de vida completo de órdenes con:
- Idempotency key (UUID) por orden para evitar duplicados.
- 14 estados internos: DRAFT → VALIDATED → RISK_APPROVED → PENDING_APPROVAL → APPROVED →
  SUBMITTED → PARTIALLY_FILLED → FILLED (o ramas de cancelación/rechazo/expiración).
- Reconciliación periódica: poll del estado real en el broker vs estado interno.
- Aprobación humana cuando LIVE_CONFIRMATION_REQUIRED=True.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy.orm import Session

from app.brokers.broker import Broker
from app.config import Settings
from app.database.models.order import Order
from app.database.models.order_reconciliation import OrderReconciliation

if TYPE_CHECKING:
    from app.database.models.signal import Signal
    from app.models.signal import SignalCreate

logger = logging.getLogger(__name__)

# Transiciones válidas del estado interno
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"VALIDATED", "CANCELLED", "FAILED"},
    "VALIDATED": {"RISK_APPROVED", "CANCELLED", "FAILED"},
    "RISK_APPROVED": {"PENDING_APPROVAL", "SUBMITTED", "CANCELLED", "FAILED"},
    "PENDING_APPROVAL": {"APPROVED", "CANCELLED", "EXPIRED"},
    "APPROVED": {"SUBMITTED", "CANCELLED", "FAILED"},
    "SUBMITTED": {"PARTIALLY_FILLED", "FILLED", "CANCELLED", "REJECTED", "EXPIRED", "RECONCILING"},
    "PARTIALLY_FILLED": {"FILLED", "CANCELLED", "REJECTED", "RECONCILING"},
    "RECONCILING": {"RECONCILED", "FILLED", "CANCELLED", "REJECTED", "FAILED"},
    "RECONCILED": {"FILLED", "CANCELLED", "REJECTED", "FAILED"},
    "FILLED": set(),  # Terminal
    "CANCELLED": set(),  # Terminal
    "REJECTED": set(),  # Terminal
    "EXPIRED": set(),  # Terminal
    "FAILED": set(),  # Terminal
}

# Estados que permiten envío al broker
_SUBMITTABLE_STATES = {"RISK_APPROVED", "APPROVED"}

# Estados terminales
_TERMINAL_STATES = {"FILLED", "CANCELLED", "REJECTED", "EXPIRED", "FAILED"}


class OrderManager:
    """Gestiona el ciclo de vida de órdenes con idempotencia y 14 estados."""

    def __init__(
        self,
        broker: Broker,
        session: Session,
        settings: Settings,
        user_id: int = 0,
    ) -> None:
        self.broker = broker
        self.session = session
        self.settings = settings
        self.user_id = user_id

    def create_draft(
        self,
        signal: SignalCreate,
        signal_db: Signal,
        quantity: Decimal,
        price: Decimal,
        side: str = "BUY",
        order_type: str = "market",
        idempotency_key: str | None = None,
    ) -> Order:
        """Crea una orden en estado DRAFT con idempotency key única."""
        if idempotency_key:
            existing = self.find_by_idempotency_key(idempotency_key)
            if existing is not None:
                logger.info("Order with idempotency_key=%s already exists (status=%s), returning existing", idempotency_key, existing.internal_status)
                return existing
        idempotency_key = idempotency_key or uuid4().hex[:36]
        client_order_id = uuid4().hex[:36]

        order = Order(
            user_id=self.user_id,
            client_order_id=client_order_id,
            idempotency_key=idempotency_key,
            broker_order_id=None,
            timestamp=datetime.now(tz=UTC),
            symbol=signal.symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            filled_quantity=Decimal("0"),
            price=price,
            status="pending",
            internal_status="DRAFT",
            signal_id=signal_db.id,
            metadata_json={
                "source": "order_manager",
                "signal_id": signal_db.id,
                "strategy": signal.strategy_name,
            },
        )
        self.session.add(order)
        self.session.flush()
        return order

    def validate(self, order: Order) -> Order:
        """Valida la orden — símbolo, cantidad, precio."""
        if order.internal_status != "DRAFT":
            raise ValueError(f"Cannot validate order in state {order.internal_status}")

        if not order.symbol:
            raise ValueError("Order has no symbol")
        if order.quantity <= 0:
            raise ValueError("Order quantity must be positive")
        if order.side not in ("BUY", "SELL"):
            raise ValueError(f"Invalid side: {order.side}")

        self._transition(order, "VALIDATED")
        self.session.add(order)
        self.session.flush()
        return order

    def risk_approve(self, order: Order) -> Order:
        """Marca la orden como aprobada por riesgo."""
        if order.internal_status != "VALIDATED":
            raise ValueError(f"Cannot risk_approve order in state {order.internal_status}")

        self._transition(order, "RISK_APPROVED")
        self.session.add(order)
        self.session.flush()
        return order

    def request_human_approval(self, order: Order) -> Order:
        """Solicita aprobación humana cuando LIVE_CONFIRMATION_REQUIRED=True."""
        if order.internal_status != "RISK_APPROVED":
            raise ValueError(f"Cannot request approval from {order.internal_status}")

        self._transition(order, "PENDING_APPROVAL")
        self.session.add(order)
        self.session.flush()
        return order

    def approve(self, order: Order) -> Order:
        """Aprueba la orden humanamente."""
        if order.internal_status != "PENDING_APPROVAL":
            raise ValueError(f"Cannot approve order in state {order.internal_status}")

        self._transition(order, "APPROVED")
        self.session.add(order)
        self.session.flush()
        return order

    def submit(self, order: Order) -> Order:
        """Envía la orden al broker."""
        if order.internal_status not in _SUBMITTABLE_STATES:
            raise ValueError(f"Cannot submit order in state {order.internal_status}")

        self._transition(order, "SUBMITTED")
        order.status = "submitted"
        self.session.add(order)
        self.session.flush()

        filled_order = self.broker.place_order(order)
        self.session.add(filled_order)

        if filled_order.status == "filled" and filled_order.filled_quantity > 0:
            if filled_order.filled_quantity < filled_order.quantity:
                self._transition(filled_order, "PARTIALLY_FILLED")
            else:
                self._transition(filled_order, "FILLED")
        elif filled_order.status == "rejected":
            self._transition(filled_order, "REJECTED")
        elif filled_order.status == "cancelled":
            self._transition(filled_order, "CANCELLED")

        self.session.add(filled_order)
        self.session.flush()
        return filled_order

    def cancel(self, order: Order) -> Order:
        """Cancela la orden si no está en estado terminal."""
        if order.internal_status in _TERMINAL_STATES:
            raise ValueError(f"Cannot cancel order in terminal state {order.internal_status}")

        self._transition(order, "CANCELLED")
        order.status = "cancelled"
        self.session.add(order)
        self.session.flush()
        return order

    def reconcile(self, order: Order) -> Order:
        """Reconcilia el estado interno con el estado real del broker.

        Poll del broker, compara con estado interno, registra discrepancias.
        """
        if order.internal_status in _TERMINAL_STATES:
            return order

        self._transition(order, "RECONCILING")
        self.session.add(order)
        self.session.flush()

        # Obtener estado real del broker
        broker_status = self._get_broker_status(order)
        internal_status = order.internal_status

        if broker_status == order.status:
            # Sin discrepancia
            self._transition(order, "RECONCILED")
            if broker_status == "filled":
                self._transition(order, "FILLED")
            elif broker_status == "cancelled":
                self._transition(order, "CANCELLED")
            elif broker_status == "rejected":
                self._transition(order, "REJECTED")
        else:
            # Discrepancia detectada — registrar
            diff = f"internal={order.status} vs broker={broker_status}"
            recon = OrderReconciliation(
                order_id=order.id,
                broker_status=broker_status,
                internal_status=internal_status,
                diff=diff,
            )
            self.session.add(recon)

            # Actualizar al estado real del broker
            order.status = broker_status
            if broker_status == "filled":
                self._transition(order, "FILLED")
            elif broker_status == "cancelled":
                self._transition(order, "CANCELLED")
            elif broker_status == "rejected":
                self._transition(order, "REJECTED")
            else:
                self._transition(order, "RECONCILED")

        self.session.add(order)
        self.session.flush()
        return order

    def find_by_idempotency_key(self, key: str) -> Order | None:
        """Busca orden por idempotency key — evita duplicados."""
        return self.session.query(Order).where(
            Order.idempotency_key == key,
        ).first()

    def get_pending_reconciliation(self) -> list[Order]:
        """Obtiene órdenes que necesitan reconciliación."""
        non_terminal = [s for s in _VALID_TRANSITIONS if s not in _TERMINAL_STATES]
        return self.session.query(Order).where(
            Order.internal_status.in_(non_terminal),
        ).all()

    def _transition(self, order: Order, new_state: str) -> None:
        """Ejecuta transición de estado con validación."""
        current = order.internal_status
        allowed = _VALID_TRANSITIONS.get(current, set())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition: {current} → {new_state}. "
                f"Allowed: {allowed or '(terminal state)'}",
            )
        logger.debug("Order %s: %s → %s", order.id, current, new_state)
        order.internal_status = new_state

    def _get_broker_status(self, order: Order) -> str:
        """Obtiene el estado real de la orden en el broker."""
        if not order.broker_order_id:
            return order.status
        try:
            if hasattr(self.broker, "get_order_status"):
                return self.broker.get_order_status(order.broker_order_id)
        except Exception as exc:
            logger.warning("Failed to get broker status for order %s: %s", order.id, exc)
        return order.status

    def process_order_lifecycle(
        self,
        signal: SignalCreate,
        signal_db: Signal,
        quantity: Decimal,
        price: Decimal,
        side: str = "BUY",
        idempotency_key: str | None = None,
    ) -> Order | None:
        """Ejecuta el ciclo completo: DRAFT → VALIDATED → RISK_APPROVED → (PENDING_APPROVAL) → SUBMITTED → FILLED.

        Si LIVE_CONFIRMATION_REQUIRED=True, se detiene en PENDING_APPROVAL
        y devuelve la orden para aprobación manual posterior.

        Si se pasa idempotency_key, se verifica si ya existe una orden con
        esa key antes de crear una nueva (anti-duplicado).
        """
        order = self.create_draft(signal, signal_db, quantity, price, side, idempotency_key=idempotency_key)
        # If create_draft returned an existing order (idempotency hit), return it
        if order.internal_status not in ("DRAFT",):
            return order
        self.validate(order)
        self.risk_approve(order)

        if self.settings.LIVE_CONFIRMATION_REQUIRED and self.settings.TRADING_MODE == "live":
            self.request_human_approval(order)
            self.session.commit()
            logger.info(
                "Order %s pending human approval (%s %s)",
                order.id, order.side, order.symbol,
            )
            return order

        return self.submit(order)
