"""Pruebas del scheduler de paper trading (FASE 5)."""

from decimal import Decimal

import pytest

from app.brokers import MockBroker
from app.config import Settings
from app.data import MarketDataService, MockDataSource
from app.database.models.account_snapshot import AccountSnapshot
from app.database.models.strategy_run import StrategyRun
from app.database.session import SessionLocal
from app.paper_trading import PaperTradingScheduler
from app.risk import RiskManager
from app.strategies import TrendMomentumConfig, TrendMomentumStrategy


def _paper_settings() -> Settings:
    return Settings(
        _env_file=None,
        APP_ENV="testing",
        DATABASE_URL="sqlite:///./test.db",
        TRADING_MODE="paper",
        PAPER_TRADING_ENABLED=True,
        PAPER_TRADING_INTERVAL_SECONDS=9999,
        PAPER_TRADING_LOOKBACK_DAYS=60,
        PAPER_TRADING_INITIAL_CASH=Decimal("100000"),
        DEFAULT_SYMBOLS="AAPL",
    )


def _build_scheduler() -> PaperTradingScheduler:
    settings = _paper_settings()
    strategy = TrendMomentumStrategy(TrendMomentumConfig())
    data_service = MarketDataService(MockDataSource())
    broker = MockBroker(initial_cash=settings.PAPER_TRADING_INITIAL_CASH)
    risk = RiskManager(settings)
    return PaperTradingScheduler(
        settings=settings,
        strategy=strategy,
        data_service=data_service,
        broker=broker,
        risk_manager=risk,
        session_factory=SessionLocal,
    )


def _query_count(model: type) -> int:
    """Cuenta registros en una sesión de vida corta para evitar locks de SQLite."""
    session = SessionLocal()
    try:
        return session.query(model).count()
    finally:
        session.close()


def _get_strategy_run(run_id: int) -> StrategyRun | None:
    session = SessionLocal()
    try:
        return session.get(StrategyRun, run_id)
    finally:
        session.close()


class TestPaperTradingScheduler:
    def test_start_creates_running_strategy_run(self) -> None:
        scheduler = _build_scheduler()
        run = scheduler.start()

        assert run.status == "running"
        assert run.mode == "paper"
        assert run.id is not None
        assert scheduler.is_running

        scheduler.stop()
        run_final = _get_strategy_run(run.id)
        assert run_final is not None
        assert run_final.status == "stopped"

    def test_stop_before_start_is_safe(self) -> None:
        scheduler = _build_scheduler()
        scheduler.stop()
        assert not scheduler.is_running

    def test_tick_generates_signals_and_snapshot(self) -> None:
        scheduler = _build_scheduler()
        run = scheduler.start()

        result = scheduler.tick()
        assert result["status"] == "ok"
        assert result["symbols"] == ["AAPL"]

        assert _query_count(AccountSnapshot) >= 1

        scheduler.stop()
        run_final = _get_strategy_run(run.id)
        assert run_final is not None
        assert run_final.status == "stopped"

    def test_disabled_scheduler_raises(self) -> None:
        settings = _paper_settings()
        settings.PAPER_TRADING_ENABLED = False
        scheduler = PaperTradingScheduler(
            settings=settings,
            strategy=TrendMomentumStrategy(TrendMomentumConfig()),
            data_service=MarketDataService(MockDataSource()),
            broker=MockBroker(),
            risk_manager=RiskManager(settings),
            session_factory=SessionLocal,
        )
        with pytest.raises(RuntimeError, match="PAPER_TRADING_ENABLED"):
            scheduler.start()
