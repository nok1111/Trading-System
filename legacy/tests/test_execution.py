"""Pruebas del motor de ejecución."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.brokers import MockBroker
from app.config import Settings
from app.database.models.order import Order
from app.database.models.position import Position
from app.database.models.risk_event import RiskEvent
from app.database.models.trade import Trade
from app.execution import ExecutionEngine
from app.models.signal import SignalCreate
from app.risk import RiskManager


@pytest.fixture
def exec_engine(db_session: Session) -> ExecutionEngine:
    settings = Settings(
        _env_file=None,
        APP_ENV="testing",
        DATABASE_URL="sqlite:///./test.db",
        TRADING_MODE="backtest",
        LIVE_TRADING_ENABLED=False,
        MAX_OPEN_POSITIONS=2,
        MAX_POSITION_SIZE_PERCENT=10.0,
        MAX_RISK_PER_TRADE_PERCENT=1.0,
        MAX_DAILY_LOSS_PERCENT=3.0,
    )
    broker = MockBroker(initial_cash=Decimal("100000"))
    risk = RiskManager(settings)
    return ExecutionEngine(broker, risk, db_session, settings)


def _signal(symbol: str, signal_type: str, entry: Decimal) -> SignalCreate:
    return SignalCreate(
        timestamp=datetime.now(tz=UTC),
        symbol=symbol,
        signal_type=signal_type,  # type: ignore[arg-type]
        confidence=Decimal("0.8"),
        entry_price=entry,
        suggested_stop_loss=entry * Decimal("0.98") if signal_type == "BUY" else None,
        strategy_name="TestStrategy",
        explanation="test",
    )


class TestExecutionEngine:
    def test_buy_signal_creates_order_trade_and_position(
        self,
        exec_engine: ExecutionEngine,
        db_session: Session,
    ) -> None:
        signal = _signal("AAPL", "BUY", Decimal("100"))
        order = exec_engine.process_signal(signal)
        assert order is not None
        assert order.status == "filled"
        assert db_session.query(Order).count() == 1
        assert db_session.query(Trade).count() == 1
        assert db_session.query(Position).filter_by(status="open").count() == 1

    def test_hold_signal_does_not_create_order(
        self,
        exec_engine: ExecutionEngine,
        db_session: Session,
    ) -> None:
        signal = _signal("AAPL", "HOLD", Decimal("100"))
        order = exec_engine.process_signal(signal)
        assert order is None
        assert db_session.query(Order).count() == 0
        assert db_session.query(RiskEvent).count() == 1

    def test_risk_rejection_creates_risk_event(
        self,
        exec_engine: ExecutionEngine,
        db_session: Session,
    ) -> None:
        # Dos señales en distintos símbolos para alcanzar MAX_OPEN_POSITIONS=2
        for symbol in ("AAPL", "MSFT"):
            signal = _signal(symbol, "BUY", Decimal("100"))
            result = exec_engine.process_signal(signal)
            assert result is not None

        # Tercera señal debe ser rechazada por límite de posiciones
        signal = _signal("TSLA", "BUY", Decimal("100"))
        order = exec_engine.process_signal(signal)
        assert order is None
        assert db_session.query(RiskEvent).count() >= 1

    def test_sell_signal_closes_position(
        self,
        exec_engine: ExecutionEngine,
        db_session: Session,
    ) -> None:
        buy = _signal("AAPL", "BUY", Decimal("100"))
        exec_engine.process_signal(buy)

        sell = _signal("AAPL", "SELL", Decimal("110"))
        order = exec_engine.process_signal(sell)
        assert order is not None
        assert order.status == "filled"
        assert db_session.query(Position).filter_by(status="closed").count() == 1
        assert db_session.query(Trade).count() == 2

        closed = db_session.query(Position).filter_by(status="closed").first()
        assert closed is not None
        assert closed.realized_pnl == Decimal("1000")

    def test_position_size_respects_risk(
        self,
        exec_engine: ExecutionEngine,
        db_session: Session,
    ) -> None:
        signal = _signal("AAPL", "BUY", Decimal("100"))
        order = exec_engine.process_signal(signal)
        assert order is not None
        # 1% riesgo sobre 100k con stop del 2% => ~500 acciones
        assert order.quantity <= Decimal("600")
