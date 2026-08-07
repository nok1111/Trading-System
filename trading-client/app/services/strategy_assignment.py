"""Auto-assign best strategy per symbol based on backtest performance.

Runs all 4 strategies (trend_momentum, mean_reversion, breakout, grid) on each
symbol, picks the best by Sharpe ratio, and stores the assignment. Supports
periodic re-evaluation to rotate strategies when market conditions change.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.services.backtest_service import run_backtest

logger = logging.getLogger(__name__)

STRATEGIES = ["trend_momentum", "mean_reversion", "breakout", "grid"]


@dataclass
class StrategyAssignment:
    """Best strategy assignment for a symbol."""

    symbol: str
    best_strategy: str
    best_sharpe: float
    best_return_pct: float
    best_alpha_pct: float
    best_win_rate: float
    best_max_drawdown: float
    all_results: list[dict[str, Any]]
    interval: str
    limit: int
    assigned_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "best_strategy": self.best_strategy,
            "best_sharpe": round(self.best_sharpe, 2),
            "best_return_pct": round(self.best_return_pct, 2),
            "best_alpha_pct": round(self.best_alpha_pct, 2),
            "best_win_rate": round(self.best_win_rate * 100, 1),
            "best_max_drawdown": round(self.best_max_drawdown, 2),
            "all_results": self.all_results,
            "interval": self.interval,
            "limit": self.limit,
            "assigned_at": self.assigned_at,
        }


@dataclass
class AutoAssignmentResult:
    """Result of running auto-assignment across multiple symbols."""

    assignments: list[StrategyAssignment]
    total_symbols: int
    evaluated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "assignments": [a.to_dict() for a in self.assignments],
            "total_symbols": self.total_symbols,
            "evaluated_at": self.evaluated_at,
            # Summary by strategy
            "strategy_distribution": self._strategy_distribution(),
        }

    def _strategy_distribution(self) -> dict[str, int]:
        dist: dict[str, int] = {}
        for a in self.assignments:
            dist[a.best_strategy] = dist.get(a.best_strategy, 0) + 1
        return dist


def evaluate_symbol(
    symbol: str,
    interval: str = "1h",
    limit: int = 500,
    initial_cash: float = 10000.0,
) -> StrategyAssignment:
    """Run all 4 strategies on a symbol and pick the best by Sharpe ratio.

    Args:
        symbol: Trading symbol (e.g. "BTCUSDT")
        interval: Kline interval
        limit: Number of candles
        initial_cash: Starting capital for backtest

    Returns:
        StrategyAssignment with the best strategy and all results
    """
    all_results: list[dict[str, Any]] = []
    best_sharpe = -999.0
    best_result = None

    for strategy_name in STRATEGIES:
        try:
            result = run_backtest(
                symbol=symbol,
                strategy=strategy_name,
                interval=interval,
                limit=limit,
                initial_cash=initial_cash,
            )

            entry = {
                "strategy": strategy_name,
                "sharpe": round(result.sharpe_ratio, 2),
                "total_return_pct": round(result.total_return_pct, 2),
                "alpha_pct": round(result.alpha_pct, 2),
                "win_rate": round(result.win_rate * 100, 1),
                "max_drawdown_pct": round(result.max_drawdown_pct, 2),
                "total_trades": result.total_trades,
                "total_fees": round(result.total_fees, 2),
                "buy_hold_return_pct": round(result.buy_hold_return_pct, 2),
            }
            all_results.append(entry)

            # Pick best by Sharpe (must have at least 1 trade)
            if result.total_trades > 0 and result.sharpe_ratio > best_sharpe:
                best_sharpe = result.sharpe_ratio
                best_result = result

        except Exception as exc:
            logger.warning("Strategy %s failed for %s: %s", strategy_name, symbol, exc)
            all_results.append({
                "strategy": strategy_name,
                "sharpe": 0,
                "total_return_pct": 0,
                "alpha_pct": 0,
                "win_rate": 0,
                "max_drawdown_pct": 0,
                "total_trades": 0,
                "total_fees": 0,
                "buy_hold_return_pct": 0,
                "error": str(exc),
            })

    # Sort by Sharpe descending
    all_results.sort(key=lambda x: x.get("sharpe", 0), reverse=True)

    if best_result is None:
        # No strategy generated trades — pick the one with best return
        best_entry = all_results[0] if all_results else None
        if best_entry:
            return StrategyAssignment(
                symbol=symbol,
                best_strategy=best_entry["strategy"],
                best_sharpe=best_entry.get("sharpe", 0),
                best_return_pct=best_entry.get("total_return_pct", 0),
                best_alpha_pct=best_entry.get("alpha_pct", 0),
                best_win_rate=best_entry.get("win_rate", 0) / 100,
                best_max_drawdown=best_entry.get("max_drawdown_pct", 0),
                all_results=all_results,
                interval=interval,
                limit=limit,
            )
        # Fallback
        return StrategyAssignment(
            symbol=symbol,
            best_strategy="trend_momentum",
            best_sharpe=0,
            best_return_pct=0,
            best_alpha_pct=0,
            best_win_rate=0,
            best_max_drawdown=0,
            all_results=all_results,
            interval=interval,
            limit=limit,
        )

    return StrategyAssignment(
        symbol=symbol,
        best_strategy=best_result.strategy,
        best_sharpe=best_result.sharpe_ratio,
        best_return_pct=best_result.total_return_pct,
        best_alpha_pct=best_result.alpha_pct,
        best_win_rate=best_result.win_rate,
        best_max_drawdown=best_result.max_drawdown_pct,
        all_results=all_results,
        interval=interval,
        limit=limit,
    )


def auto_assign_strategies(
    symbols: list[str],
    interval: str = "1h",
    limit: int = 500,
    initial_cash: float = 10000.0,
) -> AutoAssignmentResult:
    """Run auto-assignment for multiple symbols.

    Args:
        symbols: List of symbols to evaluate
        interval: Kline interval
        limit: Number of candles
        initial_cash: Starting capital

    Returns:
        AutoAssignmentResult with all assignments
    """
    assignments: list[StrategyAssignment] = []

    for symbol in symbols:
        try:
            assignment = evaluate_symbol(symbol, interval, limit, initial_cash)
            assignments.append(assignment)
            logger.info(
                "%s -> %s (Sharpe %.2f, return %+.2f%%, alpha %+.2f%%)",
                symbol, assignment.best_strategy, assignment.best_sharpe,
                assignment.best_return_pct, assignment.best_alpha_pct,
            )
        except Exception as exc:
            logger.error("Failed to evaluate %s: %s", symbol, exc)

    return AutoAssignmentResult(assignments=assignments, total_symbols=len(assignments))


# ─── In-memory cache for assignments ──────────────────────────────────────────

_assignment_cache: dict[str, StrategyAssignment] = {}
_last_full_evaluation: datetime | None = None


def get_cached_assignment(symbol: str) -> StrategyAssignment | None:
    """Get cached strategy assignment for a symbol."""
    return _assignment_cache.get(symbol.upper())


def update_assignment_cache(assignment: StrategyAssignment) -> None:
    """Update the cache with a new assignment."""
    _assignment_cache[assignment.symbol.upper()] = assignment


def get_all_cached_assignments() -> dict[str, StrategyAssignment]:
    """Get all cached assignments."""
    return _assignment_cache


def get_last_evaluation_time() -> datetime | None:
    """Get the last full evaluation timestamp."""
    return _last_full_evaluation
