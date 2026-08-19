"""Motor de ejecución: convierte señales en órdenes, trades y posiciones."""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy.orm import Session

from app.brokers.broker import Broker
from app.config import Settings
from app.database.models.account_snapshot import AccountSnapshot
from app.database.models.order import Order
from app.database.models.position import Position
from app.database.models.risk_event import RiskEvent
from app.database.models.signal import Signal
from app.database.models.trade import Trade
from app.execution.order_manager import OrderManager
from app.models.signal import SignalCreate
from app.risk.engine import RiskEngine
from app.risk.risk_manager import RiskManager

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Coordina riesgo, broker y persistencia para ejecutar señales."""

    def __init__(
        self,
        broker: Broker,
        risk_manager: RiskManager,
        session: Session,
        settings: Settings,
        risk_engine: RiskEngine | None = None,
        order_manager: OrderManager | None = None,
        user_id: int = 0,
    ) -> None:
        self.broker = broker
        self.risk_manager = risk_manager
        self.session = session
        self.settings = settings
        self.risk_engine = risk_engine
        self.order_manager = order_manager
        self.user_id = user_id

    def process_signal(self, signal_create: SignalCreate, account: AccountSnapshot | None = None) -> Order | None:
        """Persiste la señal, evalúa riesgo y, si aplica, envía orden al broker.

        Si se pasa account, se usa en lugar de broker.get_account() para
        permitir override del capital disponible (ej: capital asignado).
        """
        if self.settings.TRADING_MODE == "live" and not self.settings.LIVE_TRADING_ENABLED:
            self._log_risk_event(
                signal_create,
                "Trading live deshabilitado por configuración",
                "high",
            )
            return None

        try:
            signal_db = self._persist_signal(signal_create)
            if account is None:
                account = self.broker.get_account()
            open_positions = self._get_open_positions()

            risk_result = self.risk_manager.evaluate_signal(signal_create, account, open_positions)
            if not risk_result.allowed:
                reason = risk_result.reason or "Rechazado por riesgo"
                logger.info("Señal %s %s rechazada: %s", signal_create.signal_type, signal_create.symbol, reason)
                self._log_risk_event(
                    signal_create,
                    reason,
                    "medium",
                )
                return None

            # RiskEngine determinista con circuit breaker (veto adicional)
            engine_decision = None
            if self.risk_engine is not None:
                engine_decision = self.risk_engine.evaluate_order(
                    side=signal_create.signal_type.lower(),
                    symbol=signal_create.symbol,
                    entry_price=signal_create.entry_price or Decimal("0"),
                    stop_loss=signal_create.suggested_stop_loss,
                    account_cash=account.cash if account else Decimal("0"),
                    account_equity=account.equity if account else Decimal("0"),
                    daily_pnl=account.daily_pnl if account else Decimal("0"),
                    open_positions=[{"symbol": p.symbol, "status": p.status} for p in open_positions],
                    open_positions_count=len(open_positions),
                )
                if not engine_decision.allowed:
                    logger.info(
                        "RiskEngine veto: %s %s - %s (CB: %s)",
                        signal_create.signal_type,
                        signal_create.symbol,
                        engine_decision.reason,
                        engine_decision.circuit_breaker_state.value,
                    )
                    self._log_risk_event(
                        signal_create,
                        f"RiskEngine: {engine_decision.reason}",
                        engine_decision.severity,
                    )
                    return None

            if signal_create.signal_type == "BUY":
                return self._execute_buy(signal_create, signal_db, account, engine_decision)
            if signal_create.signal_type == "SELL":
                return self._execute_sell(signal_create, signal_db, open_positions)

            return None
        except Exception:
            self.session.rollback()
            raise

    def _persist_signal(self, signal_create: SignalCreate) -> Signal:
        signal = Signal(
            broker_id=self.broker.name,
            timestamp=signal_create.timestamp,
            symbol=signal_create.symbol,
            signal_type=signal_create.signal_type,
            confidence=signal_create.confidence,
            entry_price=signal_create.entry_price,
            suggested_stop_loss=signal_create.suggested_stop_loss,
            suggested_take_profit=signal_create.suggested_take_profit,
            strategy_name=signal_create.strategy_name,
            explanation=signal_create.explanation,
            metadata_json=signal_create.metadata_json,
            status="active",
        )
        self.session.add(signal)
        self.session.flush()
        return signal

    def _get_open_positions(self) -> list[Position]:
        # Include user_id=0 (AI Agent / manual positions) alongside the current user's
        return self.session.query(Position).where(
            Position.status == "open",
            (Position.user_id == self.user_id) | (Position.user_id == 0),
        ).with_for_update().all()

    def _get_live_price(self, symbol: str) -> Decimal | None:
        """Get real-time price from WebSocket if available."""
        try:
            from app.data.price_stream import get_price_stream
            stream = get_price_stream()
            if stream and stream.is_connected:
                price = stream.get_price(symbol)
                if price and price > 0:
                    return price
        except Exception:
            pass
        return None

    def _execute_buy(
        self,
        signal: SignalCreate,
        signal_db: Signal,
        account: AccountSnapshot,
        engine_decision=None,
    ) -> Order:
        price = self._get_live_price(signal.symbol) or signal.entry_price or self.broker.get_quote(signal.symbol)
        quantity = self.risk_manager.calculate_position_size(signal, account)
        # If RiskEngine computed an adjusted_quantity (e.g. circuit breaker reduced it), use that
        if engine_decision is not None and getattr(engine_decision, "adjusted_quantity", None) is not None:
            quantity = engine_decision.adjusted_quantity

        if self.order_manager is not None:
            order = self.order_manager.process_order_lifecycle(
                signal, signal_db, quantity, price, side="BUY",
            )
            if order is None:
                return None  # type: ignore[return-value]
            if order.internal_status == "PENDING_APPROVAL":
                logger.info("Order %s pending human approval", order.id)
                return order
            if order.internal_status == "FILLED" and order.filled_quantity > 0:
                self._record_trade_and_position(order, signal_db)
                self._place_exchange_sl_tp(order, signal_db)
            elif order.internal_status == "PARTIALLY_FILLED" and order.filled_quantity > 0:
                self._record_trade_and_position(order, signal_db)
                self._place_exchange_sl_tp(order, signal_db)
            self._notify_trade(order, signal_db)
            self.session.commit()
            return order

        # Fallback: legacy path without OrderManager
        order = Order(
            user_id=self.user_id,
            broker_id=self.broker.name,
            client_order_id=self._generate_client_order_id(),
            idempotency_key=uuid4().hex[:36],
            broker_order_id=None,
            timestamp=datetime.now(tz=UTC),
            symbol=signal.symbol,
            side="BUY",
            order_type="market",
            quantity=quantity,
            filled_quantity=Decimal("0"),
            price=price,
            status="pending",
            internal_status="DRAFT",
            signal_id=signal_db.id,
            metadata_json={"source": "execution_engine", "signal_id": signal_db.id},
        )
        self.session.add(order)
        self.session.flush()

        filled_order = self.broker.place_order(order)
        self.session.add(filled_order)

        try:
            if filled_order.status in ("filled", "partially_filled") and filled_order.filled_quantity > 0:
                self._record_trade_and_position(filled_order, signal_db)
                self._place_exchange_sl_tp(filled_order, signal_db)

            self._notify_trade(filled_order, signal_db)
            self.session.commit()
        except Exception:
            self.session.rollback()
            # Re-add the signal and order so we at least persist them, then commit
            # The signal must be re-added first so the FK constraint on orders.signal_id is satisfied
            self.session.add(signal_db)
            self.session.flush()  # re-assign signal_db.id
            filled_order.signal_id = signal_db.id  # re-link to the re-persisted signal
            self.session.add(filled_order)
            self.session.commit()
            logger.error(
                "Post-fill tracking failed for %s %s — order persisted but trade/position may be missing",
                filled_order.side, filled_order.symbol, exc_info=True,
            )
        return filled_order

    def _execute_sell(
        self,
        signal: SignalCreate,
        signal_db: Signal,
        open_positions: list[Position],
    ) -> Order:
        position = next(
            (p for p in open_positions if p.symbol == signal.symbol and p.status == "open"), None,
        )
        if position is None:
            logger.warning("SELL signal for %s but no open position found — skipping", signal.symbol)
            self._log_risk_event(signal, "No hay posición abierta para vender", "medium")
            return None  # type: ignore[return-value]
        price = self._get_live_price(signal.symbol) or signal.entry_price or self.broker.get_quote(signal.symbol)

        if self.order_manager is not None:
            order = self.order_manager.process_order_lifecycle(
                signal, signal_db, position.quantity, price, side="SELL",
            )
            if order is None:
                return None  # type: ignore[return-value]
            if order.internal_status == "PENDING_APPROVAL":
                logger.info("Sell order %s pending human approval", order.id)
                return order
            if order.internal_status == "FILLED" and order.filled_quantity > 0:
                self._close_position(order, position, signal_db)
            self.session.commit()
            return order

        # Fallback: legacy path without OrderManager
        order = Order(
            user_id=self.user_id,
            broker_id=self.broker.name,
            client_order_id=self._generate_client_order_id(),
            idempotency_key=uuid4().hex[:36],
            broker_order_id=None,
            timestamp=datetime.now(tz=UTC),
            symbol=signal.symbol,
            side="SELL",
            order_type="market",
            quantity=position.quantity,
            filled_quantity=Decimal("0"),
            price=price,
            status="pending",
            internal_status="DRAFT",
            signal_id=signal_db.id,
            metadata_json={"source": "execution_engine", "closing_position_id": position.id},
        )
        self.session.add(order)
        self.session.flush()

        filled_order = self.broker.place_order(order)
        self.session.add(filled_order)

        try:
            if filled_order.status == "filled" and filled_order.filled_quantity > 0:
                self._close_position(filled_order, position, signal_db)
            self.session.commit()
        except Exception:
            self.session.rollback()
            self.session.add(signal_db)
            self.session.flush()
            filled_order.signal_id = signal_db.id
            self.session.add(filled_order)
            self.session.commit()
            logger.error(
                "Post-fill tracking failed for SELL %s — order persisted but position may not be closed",
                filled_order.symbol, exc_info=True,
            )
        return filled_order

    def _record_trade_and_position(
        self,
        order: Order,
        signal_db: Signal,
    ) -> None:
        trade = Trade(
            user_id=self.user_id,
            broker_id=self.broker.name,
            timestamp=datetime.now(tz=UTC),
            symbol=order.symbol,
            side="BUY",
            quantity=order.filled_quantity,
            price=order.price or Decimal("0"),
            commission=Decimal("0"),
            slippage=Decimal("0"),
            realized_pnl=Decimal("0"),
            strategy_name=signal_db.strategy_name,
            order_id=order.id,
            position_id=None,
            metadata_json={"entry": True},
        )
        self.session.add(trade)
        self.session.flush()

        position = Position(
            user_id=self.user_id,
            broker_id=self.broker.name,
            symbol=order.symbol,
            opened_at=datetime.now(tz=UTC),
            closed_at=None,
            side="long",
            quantity=order.filled_quantity,
            entry_price=order.price or Decimal("0"),
            current_price=order.price,
            stop_loss=signal_db.suggested_stop_loss,
            take_profit=signal_db.suggested_take_profit,
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            status="open",
            strategy_name=signal_db.strategy_name,
            metadata_json={"entry_trade_id": trade.id},
        )
        self.session.add(position)
        self.session.flush()

        trade.position_id = position.id
        self.session.add(trade)

    def _close_position(
        self,
        order: Order,
        position: Position,
        signal_db: Signal,
    ) -> None:
        sell_price = order.price or Decimal("0")
        entry_price = position.entry_price
        qty = order.filled_quantity
        realized = (sell_price - entry_price) * qty

        # Handle partial fills: only close position if fully sold
        if qty < position.quantity:
            # Partial close: reduce quantity, keep position open
            position.quantity = position.quantity - qty
            position.realized_pnl = (position.realized_pnl or Decimal("0")) + realized
            position.current_price = sell_price
            logger.info(
                "Partial close %s: sold %s of %s, %s remaining",
                order.symbol, qty, position.quantity + qty, position.quantity,
            )
        else:
            # Full close
            position.closed_at = datetime.now(tz=UTC)
            position.status = "closed"
            position.realized_pnl = realized
            position.current_price = sell_price
        self.session.add(position)
        self.session.flush()

        trade = Trade(
            user_id=self.user_id,
            timestamp=datetime.now(tz=UTC),
            symbol=order.symbol,
            side="SELL",
            quantity=qty,
            price=sell_price,
            commission=Decimal("0"),
            slippage=Decimal("0"),
            realized_pnl=realized,
            strategy_name=signal_db.strategy_name,
            order_id=order.id,
            position_id=position.id,
            metadata_json={"exit": True, "closing_signal_id": signal_db.id},
        )
        self.session.add(trade)

    def _log_risk_event(
        self,
        signal: SignalCreate,
        reason: str,
        severity: str,
    ) -> None:
        event = RiskEvent(
            timestamp=datetime.now(tz=UTC),
            event_type="risk_rejected",
            symbol=signal.symbol,
            signal_id=None,
            reason=reason,
            severity=severity,
            details={
                "signal_type": signal.signal_type,
                "strategy_name": signal.strategy_name,
                "entry_price": str(signal.entry_price) if signal.entry_price else None,
            },
        )
        self.session.add(event)
        self.session.commit()

    def _generate_client_order_id(self) -> str:
        return uuid4().hex[:36]

    def _place_exchange_sl_tp(self, order: Order, signal_db: Signal) -> None:
        """Place real stop-loss and take-profit orders on the exchange if broker supports it."""
        sl_price = signal_db.suggested_stop_loss
        tp_price = signal_db.suggested_take_profit
        if not sl_price or not tp_price:
            return
        try:
            if hasattr(self.broker, "place_stop_loss"):
                sl_order = self.broker.place_stop_loss(
                    order.symbol, order.filled_quantity, sl_price,
                )
                self.session.add(sl_order)
                logger.info("Exchange SL placed: %s @ %s (id=%s)", order.symbol, sl_price, sl_order.broker_order_id)
            if hasattr(self.broker, "place_take_profit"):
                tp_order = self.broker.place_take_profit(
                    order.symbol, order.filled_quantity, tp_price,
                )
                self.session.add(tp_order)
                logger.info("Exchange TP placed: %s @ %s (id=%s)", order.symbol, tp_price, tp_order.broker_order_id)
        except Exception as exc:
            logger.warning("Failed to place exchange SL/TP for %s: %s", order.symbol, exc)

    def _notify_trade(self, order: Order, signal_db: Signal) -> None:
        """Send WhatsApp notification for executed trade if configured."""
        try:
            from app.notifications.whatsapp import notify_trade_executed
            notify_trade_executed(
                side=order.side,
                symbol=order.symbol,
                quantity=str(order.filled_quantity),
                price=str(order.price) if order.price else "N/A",
                strategy=signal_db.strategy_name or "",
                phone_number_id=self.settings.WHATSAPP_PHONE_NUMBER_ID or "",
                access_token=self.settings.WHATSAPP_ACCESS_TOKEN or "",
                to_number=self.settings.WHATSAPP_TO_NUMBER or "",
            )
        except Exception:
            pass
