"""Monte Carlo Simulation for backtesting — tests strategy robustness.

Traditional backtests show ONE possible outcome. Monte Carlo simulates
thousands of possible trade orderings to answer:
- What's the probability of ruin (going to zero)?
- What's the expected range of returns?
- What's the worst-case drawdown?

How it works:
1. Take the trades from a backtest
2. Shuffle the trade order N times (preserving win/loss ratio)
3. Calculate equity curve for each shuffle
4. Compute percentile ranks of the actual result

This reveals whether the strategy's success depends on trade ordering
(luck) or is genuinely robust.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.services.backtest_service import BacktestResult

logger = logging.getLogger(__name__)


@dataclass
class MonteCarloResult:
    """Result of a Monte Carlo simulation."""

    num_simulations: int
    # Percentile of the actual result among simulations
    actual_return_percentile: float  # 0-100, higher = better than more sims
    actual_drawdown_percentile: float  # 0-100, higher = worse than more sims
    # Probability of ruin (equity goes below threshold)
    ruin_probability: float  # 0-1
    # Return distribution
    median_return_pct: float
    p5_return_pct: float  # 5th percentile (worst-case)
    p95_return_pct: float  # 95th percentile (best-case)
    # Drawdown distribution
    median_max_drawdown_pct: float
    p5_max_drawdown_pct: float  # 5th percentile (lucky)
    p95_max_drawdown_pct: float  # 95th percentile (unlucky)
    # Equity curve percentiles (sampled)
    equity_curves: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "num_simulations": self.num_simulations,
            "actual_return_percentile": round(self.actual_return_percentile, 1),
            "actual_drawdown_percentile": round(self.actual_drawdown_percentile, 1),
            "ruin_probability": round(self.ruin_probability, 4),
            "median_return_pct": round(self.median_return_pct, 2),
            "p5_return_pct": round(self.p5_return_pct, 2),
            "p95_return_pct": round(self.p95_return_pct, 2),
            "median_max_drawdown_pct": round(self.median_max_drawdown_pct, 2),
            "p5_max_drawdown_pct": round(self.p5_max_drawdown_pct, 2),
            "p95_max_drawdown_pct": round(self.p95_max_drawdown_pct, 2),
            "equity_curves": self.equity_curves,
        }


def run_monte_carlo(
    backtest_result: BacktestResult,
    num_simulations: int = 1000,
    ruin_threshold_pct: float = 0.5,  # ruin = equity drops to 50% of initial
    seed: int | None = None,
) -> MonteCarloResult:
    """Run Monte Carlo simulation on a backtest result.

    Args:
        backtest_result: The original backtest result with trades
        num_simulations: Number of shuffled simulations (default 1000)
        ruin_threshold_pct: Equity fraction that constitutes ruin (default 0.5 = 50%)
        seed: Random seed for reproducibility

    Returns:
        MonteCarloResult with percentile rankings and distributions
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    trades = backtest_result.trades
    if not trades or len(trades) < 5:
        return MonteCarloResult(
            num_simulations=0,
            actual_return_percentile=50.0,
            actual_drawdown_percentile=50.0,
            ruin_probability=0.0,
            median_return_pct=0.0,
            p5_return_pct=0.0,
            p95_return_pct=0.0,
            median_max_drawdown_pct=0.0,
            p5_max_drawdown_pct=0.0,
            p95_max_drawdown_pct=0.0,
        )

    initial_cash = backtest_result.initial_cash
    ruin_threshold = initial_cash * ruin_threshold_pct

    # Extract trade P&Ls
    trade_pnls = [t.get("pnl", 0) for t in trades]

    # Run simulations
    sim_returns: list[float] = []
    sim_max_drawdowns: list[float] = []
    ruin_count = 0
    sample_curves: list[list[float]] = []

    for i in range(num_simulations):
        # Shuffle trade P&Ls
        shuffled = trade_pnls.copy()
        random.shuffle(shuffled)

        # Simulate equity curve
        equity = initial_cash
        peak = equity
        max_dd = 0.0
        ruined = False

        for pnl in shuffled:
            equity += pnl
            if equity < ruin_threshold:
                ruined = True
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        sim_return = (equity - initial_cash) / initial_cash * 100
        sim_returns.append(sim_return)
        sim_max_drawdowns.append(max_dd)
        if ruined:
            ruin_count += 1

        # Sample some equity curves for visualization
        if i < 50 or i % (num_simulations // 20) == 0:
            # Reconstruct full curve for this sim
            curve = [initial_cash]
            eq = initial_cash
            for pnl in shuffled:
                eq += pnl
                curve.append(eq)
            sample_curves.append(curve)

    # Calculate actual result's percentile
    actual_return = backtest_result.total_return_pct
    actual_dd = backtest_result.max_drawdown_pct

    sim_returns_arr = np.array(sim_returns)
    sim_dds_arr = np.array(sim_max_drawdowns)

    # Percentile: what % of simulations did the actual result beat?
    actual_return_pct = float(np.mean(sim_returns_arr <= actual_return) * 100)
    # For drawdown, lower is better, so percentile is reversed
    actual_dd_pct = float(np.mean(sim_dds_arr <= actual_dd) * 100)

    # Build equity curve samples for charting
    equity_curves = []
    for idx, curve in enumerate(sample_curves[:20]):  # Limit to 20 curves
        equity_curves.append({
            "sim": idx,
            "curve": [round(v, 2) for v in curve],
        })

    return MonteCarloResult(
        num_simulations=num_simulations,
        actual_return_percentile=actual_return_pct,
        actual_drawdown_percentile=actual_dd_pct,
        ruin_probability=ruin_count / num_simulations,
        median_return_pct=float(np.median(sim_returns_arr)),
        p5_return_pct=float(np.percentile(sim_returns_arr, 5)),
        p95_return_pct=float(np.percentile(sim_returns_arr, 95)),
        median_max_drawdown_pct=float(np.median(sim_dds_arr)),
        p5_max_drawdown_pct=float(np.percentile(sim_dds_arr, 5)),
        p95_max_drawdown_pct=float(np.percentile(sim_dds_arr, 95)),
        equity_curves=equity_curves,
    )


@dataclass
class StrategyComparison:
    """Comparison of multiple strategy backtest results."""

    strategies: list[dict[str, Any]]  # Each: {name, result, metrics}
    best_by_return: str
    best_by_sharpe: str
    best_by_drawdown: str
    best_by_win_rate: str
    best_by_profit_factor: str
    correlation_matrix: dict[str, dict[str, float]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategies": self.strategies,
            "best_by_return": self.best_by_return,
            "best_by_sharpe": self.best_by_sharpe,
            "best_by_drawdown": self.best_by_drawdown,
            "best_by_win_rate": self.best_by_win_rate,
            "best_by_profit_factor": self.best_by_profit_factor,
            "correlation_matrix": self.correlation_matrix,
        }


def compare_strategies(results: list[tuple[str, BacktestResult]]) -> StrategyComparison:
    """Compare multiple backtest results and identify the best by each metric.

    Args:
        results: List of (strategy_name, BacktestResult) tuples

    Returns:
        StrategyComparison with best strategy by each metric
    """
    if not results:
        return StrategyComparison(
            strategies=[],
            best_by_return="",
            best_by_sharpe="",
            best_by_drawdown="",
            best_by_win_rate="",
            best_by_profit_factor="",
        )

    strategies = []
    for name, result in results:
        strategies.append({
            "name": name,
            "total_return_pct": result.total_return_pct,
            "sharpe_ratio": result.sharpe_ratio,
            "max_drawdown_pct": result.max_drawdown_pct,
            "win_rate": result.win_rate,
            "profit_factor": result.profit_factor,
            "total_trades": result.total_trades,
            "alpha_pct": result.alpha_pct,
            "net_return_pct": result.net_return_pct,
        })

    # Find best by each metric
    best_return = max(results, key=lambda x: x[1].total_return_pct)
    best_sharpe = max(results, key=lambda x: x[1].sharpe_ratio)
    best_drawdown = min(results, key=lambda x: x[1].max_drawdown_pct)  # lower is better
    best_win_rate = max(results, key=lambda x: x[1].win_rate)
    best_pf = max(results, key=lambda x: x[1].profit_factor)

    # Calculate correlation between equity curves (if enough data)
    correlation_matrix = None
    if len(results) >= 2:
        try:
            curves = {}
            for name, result in results:
                if result.equity_curve:
                    curves[name] = np.array(
                        [e.get("equity", 0) for e in result.equity_curve]
                    )

            if len(curves) >= 2:
                # Align curves to min length
                min_len = min(len(c) for c in curves.values())
                aligned = {n: c[:min_len] for n, c in curves.items()}

                # Compute returns (pct change)
                returns_df = {}
                for name, curve in aligned.items():
                    rets = np.diff(curve) / curve[:-1]
                    returns_df[name] = rets

                # Correlation matrix
                names = list(returns_df.keys())
                ret_matrix = np.array([returns_df[n] for n in names])
                corr = np.corrcoef(ret_matrix)

                correlation_matrix = {}
                for i, name_i in enumerate(names):
                    correlation_matrix[name_i] = {}
                    for j, name_j in enumerate(names):
                        correlation_matrix[name_i][name_j] = round(float(corr[i][j]), 3)
        except Exception as exc:
            logger.warning("Correlation calculation failed: %s", exc)

    return StrategyComparison(
        strategies=strategies,
        best_by_return=best_return[0],
        best_by_sharpe=best_sharpe[0],
        best_by_drawdown=best_drawdown[0],
        best_by_win_rate=best_win_rate[0],
        best_by_profit_factor=best_pf[0],
        correlation_matrix=correlation_matrix,
    )
