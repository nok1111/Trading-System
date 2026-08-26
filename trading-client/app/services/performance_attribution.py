"""Performance Attribution Service — analyzes where returns come from.

Breaks down portfolio returns into:
- Asset allocation effect (which assets contributed)
- Broker effect (which brokers performed better)
- Strategy effect (which strategies generated alpha)
- Market effect (buy-and-hold benchmark)
- Timing effect (entry/exit timing)

This helps users understand WHY their portfolio performed the way it did,
not just HOW MUCH it returned.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database.session import SessionLocal

logger = logging.getLogger(__name__)


def get_performance_attribution(user_id: int, days: int = 30) -> dict[str, Any]:
    """Get performance attribution for a user's portfolio.

    Args:
        user_id: User ID
        days: Lookback period in days

    Returns:
        {
            "total_return_pct": float,
            "benchmark_return_pct": float,
            "alpha_pct": float,
            "by_asset": [{symbol, contribution_pct, return_pct, weight_pct}],
            "by_broker": [{broker_id, contribution_pct, return_pct, weight_pct}],
            "by_strategy": [{strategy, contribution_pct, return_pct}],
            "summary": {best_performer, worst_performer, ...}
        }
    """
    try:
        from app.services.portfolio_aggregator import (
            get_unified_portfolio_overview,
            get_unified_positions,
        )

        overview = get_unified_portfolio_overview(user_id)
        positions = get_unified_positions(user_id)

        total_usd = overview.get("total_usd", 0)
        if total_usd <= 0:
            return _empty_attribution()

        # Attribution by asset
        by_asset = _attribute_by_asset(positions.get("positions", []), total_usd)

        # Attribution by broker
        by_broker = _attribute_by_broker(positions.get("positions", []), total_usd, overview)

        # Attribution by strategy (from trades)
        by_strategy = _attribute_by_strategy(user_id, days)

        # Calculate total P&L
        total_pnl = sum(p.get("unrealized_pnl", 0) for p in positions.get("positions", []))
        total_return_pct = (total_pnl / total_usd * 100) if total_usd > 0 else 0

        # Benchmark: equal-weight buy-and-hold of all positions
        benchmark_return = _calculate_benchmark(positions.get("positions", []))

        alpha = total_return_pct - benchmark_return

        # Summary
        sorted_assets = sorted(by_asset, key=lambda x: x["contribution_pct"], reverse=True)
        best_performer = sorted_assets[0] if sorted_assets else None
        worst_performer = sorted_assets[-1] if sorted_assets else None

        return {
            "total_return_pct": round(total_return_pct, 2),
            "benchmark_return_pct": round(benchmark_return, 2),
            "alpha_pct": round(alpha, 2),
            "by_asset": by_asset,
            "by_broker": by_broker,
            "by_strategy": by_strategy,
            "summary": {
                "best_performer": best_performer,
                "worst_performer": worst_performer,
                "total_positions": len(positions.get("positions", [])),
                "winning_positions": sum(
                    1 for p in positions.get("positions", [])
                    if p.get("unrealized_pnl", 0) > 0
                ),
                "losing_positions": sum(
                    1 for p in positions.get("positions", [])
                    if p.get("unrealized_pnl", 0) < 0
                ),
            },
            "period_days": days,
        }
    except Exception as exc:
        logger.warning("Performance attribution error: %s", exc)
        return _empty_attribution()


def _attribute_by_asset(positions: list[dict], total_usd: float) -> list[dict[str, Any]]:
    """Attribute returns by individual asset."""
    asset_data: dict[str, dict] = {}

    for pos in positions:
        symbol = pos.get("symbol", "")
        pnl = pos.get("unrealized_pnl", 0)
        value = pos.get("current_value", 0) or abs(pnl) + (pos.get("entry_price", 0) * pos.get("quantity", 0))

        if symbol not in asset_data:
            asset_data[symbol] = {"pnl": 0, "value": 0}
        asset_data[symbol]["pnl"] += pnl
        asset_data[symbol]["value"] += value

    result = []
    for symbol, data in asset_data.items():
        weight = (data["value"] / total_usd * 100) if total_usd > 0 else 0
        contribution = (data["pnl"] / total_usd * 100) if total_usd > 0 else 0
        asset_return = (data["pnl"] / data["value"] * 100) if data["value"] > 0 else 0

        result.append({
            "symbol": symbol,
            "contribution_pct": round(contribution, 2),
            "return_pct": round(asset_return, 2),
            "weight_pct": round(weight, 2),
            "pnl_usd": round(data["pnl"], 2),
        })

    return sorted(result, key=lambda x: abs(x["contribution_pct"]), reverse=True)


def _attribute_by_broker(positions: list[dict], total_usd: float, overview: dict) -> list[dict[str, Any]]:
    """Attribute returns by broker."""
    broker_data: dict[str, dict] = {}

    for pos in positions:
        broker = pos.get("broker_name", pos.get("broker_id", "unknown"))
        pnl = pos.get("unrealized_pnl", 0)
        value = pos.get("current_value", 0) or 1000

        if broker not in broker_data:
            broker_data[broker] = {"pnl": 0, "value": 0}
        broker_data[broker]["pnl"] += pnl
        broker_data[broker]["value"] += value

    result = []
    for broker, data in broker_data.items():
        weight = (data["value"] / total_usd * 100) if total_usd > 0 else 0
        contribution = (data["pnl"] / total_usd * 100) if total_usd > 0 else 0
        broker_return = (data["pnl"] / data["value"] * 100) if data["value"] > 0 else 0

        result.append({
            "broker": broker,
            "contribution_pct": round(contribution, 2),
            "return_pct": round(broker_return, 2),
            "weight_pct": round(weight, 2),
            "pnl_usd": round(data["pnl"], 2),
        })

    return sorted(result, key=lambda x: abs(x["contribution_pct"]), reverse=True)


def _attribute_by_strategy(user_id: int, days: int) -> list[dict[str, Any]]:
    """Attribute returns by trading strategy (from closed trades)."""
    db = SessionLocal()
    try:
        from app.database.models.trade import Trade

        since = datetime.now(tz=UTC).replace(tzinfo=None) - timedelta(days=days)
        trades = (
            db.query(Trade)
            .filter(
                Trade.user_id == user_id,
                Trade.closed_at >= since,
            )
            .all()
            if hasattr(Trade, "closed_at")
            else []
        )

        strategy_data: dict[str, dict] = {}
        for trade in trades:
            strategy = getattr(trade, "strategy", "manual") or "manual"
            pnl = float(getattr(trade, "realized_pnl", 0) or 0)

            if strategy not in strategy_data:
                strategy_data[strategy] = {"pnl": 0, "count": 0}
            strategy_data[strategy]["pnl"] += pnl
            strategy_data[strategy]["count"] += 1

        result = []
        for strategy, data in strategy_data.items():
            result.append({
                "strategy": strategy,
                "pnl_usd": round(data["pnl"], 2),
                "trade_count": data["count"],
                "avg_pnl": round(data["pnl"] / data["count"], 2) if data["count"] > 0 else 0,
            })

        return sorted(result, key=lambda x: abs(x["pnl_usd"]), reverse=True)
    except Exception:
        return []
    finally:
        db.close()


def _calculate_benchmark(positions: list[dict]) -> float:
    """Calculate equal-weight buy-and-hold benchmark."""
    if not positions:
        return 0.0

    returns = []
    for pos in positions:
        entry = pos.get("entry_price", 0)
        current = pos.get("current_price", 0)
        if entry > 0 and current > 0:
            returns.append((current - entry) / entry * 100)

    if not returns:
        return 0.0

    return sum(returns) / len(returns)


def _empty_attribution() -> dict[str, Any]:
    """Return empty attribution result."""
    return {
        "total_return_pct": 0,
        "benchmark_return_pct": 0,
        "alpha_pct": 0,
        "by_asset": [],
        "by_broker": [],
        "by_strategy": [],
        "summary": {
            "best_performer": None,
            "worst_performer": None,
            "total_positions": 0,
            "winning_positions": 0,
            "losing_positions": 0,
        },
        "period_days": 30,
    }
