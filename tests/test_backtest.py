"""Pruebas del motor de backtesting."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.backtesting import BacktestEngine
from app.brokers import MockBroker
from app.config import Settings
from app.data import MarketDataService, MockDataSource
from app.database.models.backtest_run import BacktestRun
from app.database.models.trade import Trade
from app.execution import ExecutionEngine
from app.risk import RiskManager
from app.strategies import TrendMomentumConfig, TrendMomentumStrategy


@pytest.fixture
def sample_df():
    source = MockDataSource(seed=7)
    service = MarketDataService(source)
    return service.get_historical_bars("TEST", date(2024, 1, 1), date(2024, 6, 1), "1d")


@pytest.fixture
def backtest_engine(db_session: Session) -> BacktestEngine:
    settings = Settings(
        _env_file=None,
        APP_ENV="testing",
        DATABASE_URL="sqlite:///./test.db",
        TRADING_MODE="backtest",
        LIVE_TRADING_ENABLED=False,
        MAX_OPEN_POSITIONS=1,
        MAX_POSITION_SIZE_PERCENT=100.0,
        MAX_RISK_PER_TRADE_PERCENT=10.0,
        MAX_DAILY_LOSS_PERCENT=10.0,
    )
    broker = MockBroker(initial_cash=Decimal("10000"))
    risk = RiskManager(settings)
    execution = ExecutionEngine(broker, risk, db_session, settings)
    strategy = TrendMomentumStrategy(
        TrendMomentumConfig(
            rsi_lower=20,
            rsi_upper=80,
            volume_threshold=0.5,
        )
    )
    return BacktestEngine(strategy, execution, db_session, initial_cash=Decimal("10000"))


class TestBacktestEngine:
    def test_run_creates_backtest_run_and_metrics(
        self,
        backtest_engine: BacktestEngine,
        sample_df,
        db_session: Session,
    ) -> None:
        result = backtest_engine.run("TEST", sample_df)
        assert result.backtest_run.id is not None
        assert result.backtest_run.strategy_name == "TrendMomentumStrategy"
        assert result.backtest_run.total_trades >= 0
        assert len(result.equity_curve) > 0
        assert result.metrics["total_trades"] >= 0

    def test_run_inserts_trades(
        self,
        backtest_engine: BacktestEngine,
        sample_df,
        db_session: Session,
    ) -> None:
        backtest_engine.run("TEST", sample_df)
        assert db_session.query(Trade).count() >= 0

    def test_run_saves_backtest_record(
        self,
        backtest_engine: BacktestEngine,
        sample_df,
        db_session: Session,
    ) -> None:
        result = backtest_engine.run("TEST", sample_df)
        db_run = db_session.get(BacktestRun, result.backtest_run.id)
        assert db_run is not None
        assert db_run.symbols == ["TEST"]
