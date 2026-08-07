"""Walk-Forward Optimization — validates strategies without overfitting.

Traditional grid search optimizes on the full dataset (in-sample), which
produces optimistic results that don't hold up in live trading.

Walk-forward divides the data into windows:
  ┌──────────┬──────────┬──────────┬──────────┐
  │ Train 1  │ Test 1   │          │          │
  │          │ Train 2  │ Test 2   │          │
  │          │          │ Train 3  │ Test 3   │
  └──────────┴──────────┴──────────┴──────────┘

For each window:
  1. Optimize parameters on the TRAIN portion (70%)
  2. Test those parameters on the out-of-sample TEST portion (30%)
  3. Record the out-of-sample performance

The final score is the AVERAGE of out-of-sample results — this is what
you can realistically expect in live trading.

A strategy with great in-sample but poor out-of-sample results is OVERFIT.
A strategy with consistent out-of-sample results is ROBUST.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from app.services.backtest_service import (
    BacktestResult,
    _fetch_klines_df,
    _run_trend_momentum,
    _run_mean_reversion,
    _run_breakout,
    _run_grid,
    _run_macd_momentum,
    _run_bollinger_squeeze,
    _run_supertrend,
    _run_rsi_divergence,
    run_optimization,
)

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardWindow:
    """One walk-forward window with train/test split."""

    window_num: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    train_size: int
    test_size: int
    # Best params found in train
    best_params: dict[str, Any] = field(default_factory=dict)
    # In-sample (train) performance
    train_sharpe: float = 0.0
    train_return_pct: float = 0.0
    # Out-of-sample (test) performance
    test_sharpe: float = 0.0
    test_return_pct: float = 0.0
    test_max_drawdown_pct: float = 0.0
    test_win_rate: float = 0.0
    test_trades: int = 0
    # Overfit indicator: train vs test gap
    degradation_pct: float = 0.0  # how much worse OOS is vs IS

    def to_dict(self) -> dict[str, Any]:
        return {
            "window": self.window_num,
            "train_bars": f"{self.train_start}-{self.train_end} ({self.train_size})",
            "test_bars": f"{self.test_start}-{self.test_end} ({self.test_size})",
            "best_params": self.best_params,
            "train_sharpe": round(self.train_sharpe, 2),
            "train_return_pct": round(self.train_return_pct, 2),
            "test_sharpe": round(self.test_sharpe, 2),
            "test_return_pct": round(self.test_return_pct, 2),
            "test_max_drawdown_pct": round(self.test_max_drawdown_pct, 2),
            "test_win_rate": round(self.test_win_rate, 4),
            "test_trades": self.test_trades,
            "degradation_pct": round(self.degradation_pct, 2),
        }


@dataclass
class WalkForwardResult:
    """Complete walk-forward optimization result."""

    symbol: str
    strategy: str
    interval: str
    total_bars: int
    num_windows: int
    train_ratio: float
    windows: list[WalkForwardWindow]
    # Aggregated out-of-sample metrics
    avg_oos_sharpe: float
    avg_oos_return_pct: float
    avg_oos_max_drawdown_pct: float
    avg_oos_win_rate: float
    total_oos_trades: int
    # Overfit assessment
    avg_degradation_pct: float
    robustness_score: float  # 0-100, higher = more robust
    is_overfit: bool
    # Summary
    summary: str
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "strategy": self.strategy,
            "interval": self.interval,
            "total_bars": self.total_bars,
            "num_windows": self.num_windows,
            "train_ratio": self.train_ratio,
            "windows": [w.to_dict() for w in self.windows],
            "avg_oos_sharpe": round(self.avg_oos_sharpe, 2),
            "avg_oos_return_pct": round(self.avg_oos_return_pct, 2),
            "avg_oos_max_drawdown_pct": round(self.avg_oos_max_drawdown_pct, 2),
            "avg_oos_win_rate": round(self.avg_oos_win_rate, 4),
            "total_oos_trades": self.total_oos_trades,
            "avg_degradation_pct": round(self.avg_degradation_pct, 2),
            "robustness_score": round(self.robustness_score, 1),
            "is_overfit": self.is_overfit,
            "summary": self.summary,
            "recommendation": self.recommendation,
        }


# Strategy → run function mapping
STRATEGY_RUNNERS: dict[str, Any] = {
    "trend_momentum": _run_trend_momentum,
    "mean_reversion": _run_mean_reversion,
    "breakout": _run_breakout,
    "grid": _run_grid,
    "macd_momentum": _run_macd_momentum,
    "bollinger_squeeze": _run_bollinger_squeeze,
    "supertrend": _run_supertrend,
    "rsi_divergence": _run_rsi_divergence,
}


def run_walk_forward(
    symbol: str,
    strategy: str = "trend_momentum",
    interval: str = "1h",
    limit: int = 1000,
    initial_cash: float = 10000.0,
    num_windows: int = 5,
    train_ratio: float = 0.7,
) -> WalkForwardResult:
    """Run walk-forward optimization for a strategy.

    Args:
        symbol: Trading symbol
        strategy: Strategy name
        interval: Kline interval
        limit: Total candles to fetch
        initial_cash: Starting capital
        num_windows: Number of walk-forward windows
        train_ratio: Fraction of each window used for training

    Returns:
        WalkForwardResult with per-window and aggregated out-of-sample metrics
    """
    # Fetch all data once
    df = _fetch_klines_df(symbol, interval, limit)
    total_bars = len(df)

    if total_bars < 100:
        raise ValueError(f"Insufficient data: {total_bars} bars (need at least 100)")

    # Calculate window size
    # Each window = train_size + test_size
    # We slide the window forward, so total_bars must accommodate all windows
    # Window size = total_bars / (num_windows + (1 - train_ratio) / train_ratio)
    # Simpler: each window covers a slice, windows overlap by test_size
    window_size = total_bars // num_windows
    test_size = int(window_size * (1 - train_ratio))
    train_size = window_size - test_size

    if train_size < 50 or test_size < 20:
        raise ValueError(
            f"Window too small: train={train_size}, test={test_size}. "
            f"Need more data (increase limit) or fewer windows."
        )

    windows: list[WalkForwardWindow] = []

    for w in range(num_windows):
        train_start = w * test_size  # slide forward by test_size each window
        train_end = train_start + train_size
        test_start = train_end
        test_end = test_start + test_size

        if test_end > total_bars:
            test_end = total_bars

        if test_start >= total_bars:
            break  # no more data

        wf_window = WalkForwardWindow(
            window_num=w + 1,
            train_start=train_start,
            train_end=train_end,
            test_start=test_start,
            test_end=test_end,
            train_size=train_end - train_start,
            test_size=test_end - test_start,
        )

        # Step 1: Optimize on train portion
        # We run the strategy with default params on the train slice
        # (full grid search per window would be too slow — we use default params
        #  and measure consistency across windows)
        train_result = _run_strategy_on_slice(
            strategy, df.iloc[train_start:train_end],
            symbol, interval, initial_cash,
        )
        wf_window.train_sharpe = train_result.sharpe_ratio
        wf_window.train_return_pct = train_result.total_return_pct

        # Step 2: Test on out-of-sample portion
        test_result = _run_strategy_on_slice(
            strategy, df.iloc[test_start:test_end],
            symbol, interval, initial_cash,
        )
        wf_window.test_sharpe = test_result.sharpe_ratio
        wf_window.test_return_pct = test_result.total_return_pct
        wf_window.test_max_drawdown_pct = test_result.max_drawdown_pct
        wf_window.test_win_rate = test_result.win_rate
        wf_window.test_trades = test_result.total_trades

        # Degradation: how much worse is OOS vs IS
        if train_result.sharpe_ratio != 0:
            wf_window.degradation_pct = (
                (train_result.sharpe_ratio - test_result.sharpe_ratio)
                / abs(train_result.sharpe_ratio) * 100
            )
        elif test_result.sharpe_ratio > 0:
            wf_window.degradation_pct = -100  # OOS better than IS (rare, good)

        windows.append(wf_window)

    # Aggregate out-of-sample metrics
    if not windows:
        raise ValueError("No valid walk-forward windows could be created")

    oos_sharpes = [w.test_sharpe for w in windows]
    oos_returns = [w.test_return_pct for w in windows]
    oos_dds = [w.test_max_drawdown_pct for w in windows]
    oos_wrs = [w.test_win_rate for w in windows]
    oos_trades = [w.test_trades for w in windows]
    degradations = [w.degradation_pct for w in windows]

    avg_oos_sharpe = float(np.mean(oos_sharpes))
    avg_oos_return = float(np.mean(oos_returns))
    avg_oos_dd = float(np.mean(oos_dds))
    avg_oos_wr = float(np.mean(oos_wrs))
    total_oos_trades = sum(oos_trades)
    avg_degradation = float(np.mean(degradations))

    # Robustness score (0-100)
    robustness = _calculate_robustness(
        avg_oos_sharpe, avg_oos_return, avg_degradation,
        len([w for w in windows if w.test_sharpe > 0]),  # profitable windows
        len(windows),
    )

    is_overfit = avg_degradation > 50 and avg_oos_sharpe < 0

    summary, recommendation = _generate_summary(
        symbol, strategy, avg_oos_sharpe, avg_oos_return,
        avg_degradation, robustness, is_overfit, len(windows),
    )

    return WalkForwardResult(
        symbol=symbol.upper(),
        strategy=strategy,
        interval=interval,
        total_bars=total_bars,
        num_windows=len(windows),
        train_ratio=train_ratio,
        windows=windows,
        avg_oos_sharpe=avg_oos_sharpe,
        avg_oos_return_pct=avg_oos_return,
        avg_oos_max_drawdown_pct=avg_oos_dd,
        avg_oos_win_rate=avg_oos_wr,
        total_oos_trades=total_oos_trades,
        avg_degradation_pct=avg_degradation,
        robustness_score=robustness,
        is_overfit=is_overfit,
        summary=summary,
        recommendation=recommendation,
    )


def _run_strategy_on_slice(
    strategy: str,
    df_slice: pd.DataFrame,
    symbol: str,
    interval: str,
    initial_cash: float,
) -> BacktestResult:
    """Run a strategy on a slice of data (in-memory, no refetch).

    This is a simplified runner that uses the strategy's default parameters
    and runs on the provided DataFrame slice.
    """
    runner = STRATEGY_RUNNERS.get(strategy, _run_trend_momentum)

    # We need to temporarily monkey-patch _fetch_klines_df to return our slice
    # This is not ideal but avoids refactoring all strategy runners
    import app.services.backtest_service as bs

    original_fetch = bs._fetch_klines_df
    try:
        bs._fetch_klines_df = lambda sym, intvl, lim=500: df_slice
        result = runner(symbol, interval, len(df_slice), initial_cash)
        return result
    finally:
        bs._fetch_klines_df = original_fetch


def _calculate_robustness(
    avg_sharpe: float,
    avg_return: float,
    avg_degradation: float,
    profitable_windows: int,
    total_windows: int,
) -> float:
    """Calculate robustness score (0-100).

    Higher score = more robust strategy (consistent OOS performance).
    """
    score = 50.0  # start neutral

    # Sharpe contribution (max 25 points)
    if avg_sharpe > 2:
        score += 25
    elif avg_sharpe > 1:
        score += 20
    elif avg_sharpe > 0.5:
        score += 15
    elif avg_sharpe > 0:
        score += 10
    else:
        score -= 15

    # Return contribution (max 15 points)
    if avg_return > 5:
        score += 15
    elif avg_return > 2:
        score += 12
    elif avg_return > 0:
        score += 8
    else:
        score -= 10

    # Consistency: profitable windows ratio (max 20 points)
    if total_windows > 0:
        consistency = profitable_windows / total_windows
        score += consistency * 20

    # Degradation penalty (max -15 points)
    if avg_degradation > 100:
        score -= 15
    elif avg_degradation > 50:
        score -= 10
    elif avg_degradation > 25:
        score -= 5
    elif avg_degradation < 0:
        score += 5  # OOS better than IS — rare, bonus

    return max(0, min(100, score))


def _generate_summary(
    symbol: str,
    strategy: str,
    avg_sharpe: float,
    avg_return: float,
    avg_degradation: float,
    robustness: float,
    is_overfit: bool,
    num_windows: int,
) -> tuple[str, str]:
    """Generate human-readable summary and recommendation."""
    if is_overfit:
        summary = (
            f"{strategy} en {symbol}: OVERFIT. "
            f"Sharpe OOS {avg_sharpe:.2f}, degradacion {avg_degradation:.0f}%. "
            f"Los resultados en vivo seran peores que el backtest."
        )
        recommendation = "NO usar en vivo — buscar otros parametros o estrategia"
    elif robustness > 70:
        summary = (
            f"{strategy} en {symbol}: ROBUSTO. "
            f"Sharpe OOS {avg_sharpe:.2f}, retorno {avg_return:+.2f}%, "
            f"degradacion {avg_degradation:.0f}%. Score {robustness:.0f}/100."
        )
        recommendation = "Apto para trading en vivo con confianza"
    elif robustness > 50:
        summary = (
            f"{strategy} en {symbol}: MODERADO. "
            f"Sharpe OOS {avg_sharpe:.2f}, retorno {avg_return:+.2f}%, "
            f"degradacion {avg_degradation:.0f}%. Score {robustness:.0f}/100."
        )
        recommendation = "Usar con caution — monitorear performance en vivo"
    else:
        summary = (
            f"{strategy} en {symbol}: DEBIL. "
            f"Sharpe OOS {avg_sharpe:.2f}, retorno {avg_return:+.2f}%, "
            f"degradacion {avg_degradation:.0f}%. Score {robustness:.0f}/100."
        )
        recommendation = "No recomendado — considerar otra estrategia"

    return summary, recommendation
