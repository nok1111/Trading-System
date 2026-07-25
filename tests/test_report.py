"""Pruebas del generador de reportes."""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database.models.backtest_run import BacktestRun
from app.reporting import ReportGenerator


class TestReportGenerator:
    def test_generate_backtest_report(self, db_session: Session) -> None:
        run = BacktestRun(
            strategy_name="TestStrategy",
            symbols=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 2),
            initial_cash=Decimal("10000"),
            final_equity=Decimal("11000"),
            total_return_percent=Decimal("10"),
            total_trades=4,
            win_rate=Decimal("0.5"),
            profit_factor=Decimal("2.0"),
            max_drawdown_percent=Decimal("-5"),
            sharpe_ratio=Decimal("1.2"),
            config={},
        )
        db_session.add(run)
        db_session.commit()

        generator = ReportGenerator()
        report = generator.generate_backtest_report(run)

        assert report.strategy_name == "TestStrategy"
        assert report.symbols == ["AAPL"]
        assert report.total_return_percent == 10.0
        assert report.win_rate_percent == 50.0
        assert "TestStrategy" in report.summary
        assert "10.00%" in report.summary
