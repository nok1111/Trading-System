"""Pruebas del cálculo de métricas."""

from datetime import date
from decimal import Decimal

import pandas as pd

from app.reporting.metrics import MetricsCalculator


class TestMetricsCalculator:
    def test_basic_metrics(self) -> None:
        equity = pd.Series(
            [100.0, 110.0, 105.0, 120.0],
            index=pd.date_range("2024-01-01", periods=4),
        )
        trades = pd.DataFrame(
            {
                "side": ["SELL"],
                "realized_pnl": [10.0],
            }
        )
        metrics = MetricsCalculator.calculate(
            equity, trades, 100.0, date(2024, 1, 1), date(2024, 1, 4)
        )
        assert metrics["total_return_percent"] == Decimal("20")
        assert metrics["total_trades"] == 1
        assert metrics["win_rate"] == Decimal("1")

    def test_empty_trades(self) -> None:
        equity = pd.Series(
            [100.0, 100.0, 100.0],
            index=pd.date_range("2024-01-01", periods=3),
        )
        trades = pd.DataFrame(columns=["side", "realized_pnl"])
        metrics = MetricsCalculator.calculate(
            equity, trades, 100.0, date(2024, 1, 1), date(2024, 1, 3)
        )
        assert metrics["total_trades"] == 0
        assert metrics["win_rate"] == Decimal("0")
        assert metrics["profit_factor"] == Decimal("0")

    def test_drawdown(self) -> None:
        equity = pd.Series(
            [100.0, 120.0, 90.0],
            index=pd.date_range("2024-01-01", periods=3),
        )
        trades = pd.DataFrame(columns=["side", "realized_pnl"])
        metrics = MetricsCalculator.calculate(
            equity, trades, 100.0, date(2024, 1, 1), date(2024, 1, 3)
        )
        assert metrics["max_drawdown_percent"] < Decimal("0")
        assert metrics["total_return_percent"] < Decimal("0")
