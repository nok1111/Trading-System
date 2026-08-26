"""Tests for Monte Carlo simulation and strategy comparison."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _make_mock_backtest_result(
    trades: list[dict] | None = None,
    total_return: float = 10.0,
    max_dd: float = 5.0,
    initial_cash: float = 10000.0,
):
    """Create a mock BacktestResult for testing."""
    from app.services.backtest_service import BacktestResult

    if trades is None:
        # Generate 20 trades with 60% win rate
        trades = []
        for i in range(20):
            pnl = 100 if i % 5 < 3 else -50  # 3 wins, 2 losses per 5
            trades.append({"pnl": pnl, "side": "buy" if i % 2 == 0 else "sell"})

    return BacktestResult(
        symbol="BTC/USDT",
        strategy="test",
        interval="1h",
        initial_cash=initial_cash,
        final_equity=initial_cash * (1 + total_return / 100),
        total_return_pct=total_return,
        annualized_return_pct=total_return * 2,
        sharpe_ratio=1.5,
        max_drawdown_pct=max_dd,
        win_rate=0.6,
        profit_factor=1.8,
        total_trades=len(trades),
        avg_trade_pnl=50.0,
        equity_curve=[{"equity": initial_cash + i * 50} for i in range(len(trades) + 1)],
        trades=trades,
    )


class TestMonteCarlo:
    """Tests for Monte Carlo simulation."""

    def test_monte_carlo_basic(self):
        """Should run simulation and return results."""
        from app.services.monte_carlo import run_monte_carlo

        result = _make_mock_backtest_result()
        mc = run_monte_carlo(result, num_simulations=100, seed=42)

        assert mc.num_simulations == 100
        assert 0 <= mc.actual_return_percentile <= 100
        assert 0 <= mc.actual_drawdown_percentile <= 100
        assert 0 <= mc.ruin_probability <= 1
        assert isinstance(mc.median_return_pct, float)
        assert isinstance(mc.p5_return_pct, float)
        assert isinstance(mc.p95_return_pct, float)

    def test_monte_carlo_with_seed_reproducible(self):
        """Same seed should produce same results."""
        from app.services.monte_carlo import run_monte_carlo

        result = _make_mock_backtest_result()
        mc1 = run_monte_carlo(result, num_simulations=50, seed=123)
        mc2 = run_monte_carlo(result, num_simulations=50, seed=123)

        assert mc1.median_return_pct == mc2.median_return_pct
        assert mc1.p5_return_pct == mc2.p5_return_pct

    def test_monte_carlo_empty_trades(self):
        """Should handle empty trades gracefully."""
        from app.services.monte_carlo import run_monte_carlo

        result = _make_mock_backtest_result(trades=[], total_return=0)
        mc = run_monte_carlo(result, num_simulations=100)

        assert mc.num_simulations == 0
        assert mc.ruin_probability == 0.0

    def test_monte_carlo_to_dict(self):
        """Should serialize to dict correctly."""
        from app.services.monte_carlo import run_monte_carlo

        result = _make_mock_backtest_result()
        mc = run_monte_carlo(result, num_simulations=50, seed=42)
        d = mc.to_dict()

        assert "num_simulations" in d
        assert "actual_return_percentile" in d
        assert "ruin_probability" in d
        assert "equity_curves" in d

    def test_monte_carlo_ruin_probability(self):
        """Should detect ruin when trades are very negative."""
        from app.services.monte_carlo import run_monte_carlo

        # All trades are huge losses
        trades = [{"pnl": -2000} for _ in range(10)]
        result = _make_mock_backtest_result(trades=trades, total_return=-90, max_dd=90)
        mc = run_monte_carlo(result, num_simulations=100, ruin_threshold_pct=0.5, seed=42)

        # With 10 trades of -2000 each, starting from 10000, ruin is certain
        assert mc.ruin_probability > 0.5


class TestStrategyComparison:
    """Tests for strategy comparison."""

    def test_compare_basic(self):
        """Should compare multiple strategies and find best."""
        from app.services.monte_carlo import compare_strategies

        r1 = _make_mock_backtest_result(total_return=15, max_dd=3)
        r2 = _make_mock_backtest_result(total_return=8, max_dd=2)
        r3 = _make_mock_backtest_result(total_return=12, max_dd=5)

        comparison = compare_strategies([
            ("strategy_a", r1),
            ("strategy_b", r2),
            ("strategy_c", r3),
        ])

        assert comparison.best_by_return == "strategy_a"  # 15%
        assert comparison.best_by_drawdown == "strategy_b"  # 2%
        assert len(comparison.strategies) == 3

    def test_compare_empty(self):
        """Should handle empty list gracefully."""
        from app.services.monte_carlo import compare_strategies

        comparison = compare_strategies([])
        assert comparison.best_by_return == ""
        assert comparison.strategies == []

    def test_compare_to_dict(self):
        """Should serialize to dict correctly."""
        from app.services.monte_carlo import compare_strategies

        r1 = _make_mock_backtest_result(total_return=15)
        r2 = _make_mock_backtest_result(total_return=8)

        comparison = compare_strategies([("a", r1), ("b", r2)])
        d = comparison.to_dict()

        assert "strategies" in d
        assert "best_by_return" in d
        assert "best_by_sharpe" in d
        assert len(d["strategies"]) == 2

    def test_compare_correlation(self):
        """Should compute correlation matrix when equity curves available."""
        from app.services.monte_carlo import compare_strategies

        r1 = _make_mock_backtest_result(total_return=15)
        r2 = _make_mock_backtest_result(total_return=8)

        comparison = compare_strategies([("a", r1), ("b", r2)])

        # Correlation matrix should be computed
        assert comparison.correlation_matrix is not None
        assert "a" in comparison.correlation_matrix
        assert "b" in comparison.correlation_matrix
        # Self-correlation should be 1.0
        assert comparison.correlation_matrix["a"]["a"] == 1.0
