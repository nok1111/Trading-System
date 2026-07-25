from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models.backtest_run import BacktestRun
from app.database.models.market_bar import MarketBar
from app.database.models.order import Order
from app.database.models.position import Position
from app.database.models.signal import Signal
from app.database.models.strategy_run import StrategyRun


class TestDatabaseModels:
    def test_market_bar_unique_constraint(self, db_session: Session) -> None:
        ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        bar1 = MarketBar(
            timestamp=ts,
            symbol="AAPL",
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.50"),
            volume=Decimal("1000"),
            timeframe="1d",
            source="test",
        )
        db_session.add(bar1)
        db_session.commit()

        bar2 = MarketBar(
            timestamp=ts,
            symbol="AAPL",
            open=Decimal("100.10"),
            high=Decimal("101.10"),
            low=Decimal("99.10"),
            close=Decimal("100.60"),
            volume=Decimal("2000"),
            timeframe="1d",
            source="test",
        )
        db_session.add(bar2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_signal_lifecycle(self, db_session: Session) -> None:
        signal = Signal(
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
            symbol="SPY",
            signal_type="BUY",
            confidence=Decimal("0.85"),
            entry_price=Decimal("450.00"),
            suggested_stop_loss=Decimal("440.00"),
            suggested_take_profit=Decimal("470.00"),
            strategy_name="TrendMomentum",
            explanation="Cruce alcista de EMAs con RSI neutral.",
        )
        db_session.add(signal)
        db_session.commit()

        result = db_session.execute(select(Signal).where(Signal.symbol == "SPY")).scalar_one()
        assert result.signal_type == "BUY"
        assert result.confidence == Decimal("0.85")
        assert result.status == "generated"

    def test_order_creation(self, db_session: Session) -> None:
        order = Order(
            client_order_id="order-001",
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
            symbol="AAPL",
            side="BUY",
            order_type="market",
            quantity=Decimal("10"),
            price=Decimal("150.00"),
            status="submitted",
        )
        db_session.add(order)
        db_session.commit()

        assert order.id is not None
        assert order.filled_quantity == Decimal("0")

    def test_position_open_and_close(self, db_session: Session) -> None:
        position = Position(
            symbol="MSFT",
            opened_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
            side="long",
            quantity=Decimal("5"),
            entry_price=Decimal("300.00"),
            current_price=Decimal("305.00"),
            stop_loss=Decimal("290.00"),
            take_profit=Decimal("320.00"),
            strategy_name="TrendMomentum",
        )
        db_session.add(position)
        db_session.commit()

        position.status = "closed"
        position.closed_at = datetime(2024, 1, 2, 12, 0, 0, tzinfo=UTC)
        position.realized_pnl = Decimal("25.00")
        db_session.commit()

        result = db_session.execute(select(Position).where(Position.symbol == "MSFT")).scalar_one()
        assert result.status == "closed"
        assert result.realized_pnl == Decimal("25.00")

    def test_strategy_run_and_backtest_run(self, db_session: Session) -> None:
        run = StrategyRun(
            strategy_name="TrendMomentum",
            mode="backtest",
            config={"fast_ema": 10, "slow_ema": 30},
            status="completed",
        )
        db_session.add(run)
        db_session.commit()

        backtest = BacktestRun(
            strategy_name="TrendMomentum",
            symbols=["SPY"],
            start_date=datetime(2023, 1, 1).date(),
            end_date=datetime(2023, 12, 31).date(),
            initial_cash=Decimal("100000"),
            final_equity=Decimal("105000"),
            total_return_percent=Decimal("5.0000"),
            total_trades=10,
            config={"fast_ema": 10, "slow_ema": 30},
        )
        db_session.add(backtest)
        db_session.commit()

        assert run.id is not None
        assert backtest.id is not None
        assert backtest.total_trades == 10
