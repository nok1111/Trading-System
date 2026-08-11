"""Broker leaderboard service — calculates real performance stats from broker accounts.

Reads AccountSnapshot data for each leader's connected broker account to compute
real ROI, win rate, drawdown, etc. Works with any broker (Binance, Bybit, Kraken,
OKX, etc.) — no broker-specific logic.

The leaderboard merges:
  - Internal leaders (SocialLeader records with broker accounts)
  - Their real trading stats from AccountSnapshot history

This is NOT a Binance-specific leaderboard. It works with whatever broker
the leader has connected.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.database.models.account_snapshot import AccountSnapshot
from app.database.models.broker_account import BrokerAccount
from app.database.models.social_leader import SocialLeader
from app.database.models.social_signal import SocialSignal

logger = logging.getLogger(__name__)


def _safe_float(val: Decimal | float | None) -> float:
    if val is None:
        return 0.0
    return float(val)


def _compute_roi_from_snapshots(
    snapshots: list[AccountSnapshot],
    since: datetime,
) -> float:
    """Compute ROI % from account snapshots since a given date.

    ROI = (latest_equity - earliest_equity) / earliest_equity * 100
    Falls back to using total_pnl if equity history is too short.
    """
    if not snapshots:
        return 0.0

    sorted_snaps = sorted(snapshots, key=lambda s: s.timestamp)
    earliest = sorted_snaps[0]
    latest = sorted_snaps[-1]

    if earliest.equity and earliest.equity > 0:
        roi = (float(latest.equity) - float(earliest.equity)) / float(earliest.equity) * 100
        return round(roi, 2)

    # Fallback: use total_pnl delta
    pnl_delta = float(latest.total_pnl) - float(earliest.total_pnl)
    if earliest.equity and earliest.equity > 0:
        return round(pnl_delta / float(earliest.equity) * 100, 2)
    return 0.0


def _compute_max_drawdown(snapshots: list[AccountSnapshot]) -> float:
    """Compute max drawdown % from equity curve."""
    if len(snapshots) < 2:
        return 0.0

    sorted_snaps = sorted(snapshots, key=lambda s: s.timestamp)
    peak = float(sorted_snaps[0].equity)
    max_dd = 0.0

    for snap in sorted_snaps:
        equity = float(snap.equity)
        if equity > peak:
            peak = equity
        if peak > 0:
            dd = (peak - equity) / peak * 100
            if dd > max_dd:
                max_dd = dd

    return round(max_dd, 2)


def _compute_sharpe(snapshots: list[AccountSnapshot]) -> float:
    """Compute simplified Sharpe ratio from daily PnL."""
    if len(snapshots) < 3:
        return 0.0

    # Group by day and sum daily_pnl
    daily_pnls: dict[str, float] = {}
    for snap in sorted(snapshots, key=lambda s: s.timestamp):
        day_key = snap.timestamp.strftime("%Y-%m-%d")
        daily_pnls[day_key] = daily_pnls.get(day_key, 0.0) + float(snap.daily_pnl)

    pnl_values = list(daily_pnls.values())
    if len(pnl_values) < 2:
        return 0.0

    avg_pnl = sum(pnl_values) / len(pnl_values)
    variance = sum((p - avg_pnl) ** 2 for p in pnl_values) / len(pnl_values)
    std_pnl = variance ** 0.5

    if std_pnl == 0:
        return 0.0

    # Annualized: sqrt(365) ~ 19.1
    sharpe = (avg_pnl / std_pnl) * (365 ** 0.5)
    return round(sharpe, 2)


def get_leaderboard(
    db: Session,
    broker_id: str | None = None,
    limit: int = 50,
    sort: str = "roi_30d",
) -> list[dict[str, Any]]:
    """Get the broker leaderboard with real performance stats.

    Args:
        db: Database session
        broker_id: Optional broker filter (e.g. "binance", "bybit"). None = all brokers.
        limit: Max results
        sort: Sort field (roi_30d, roi_90d, roi_all, win_rate, total_followers, total_trades)

    Returns:
        List of leader dicts with real stats from their broker accounts.
    """
    # Base query: public leaders
    stmt = select(SocialLeader).where(SocialLeader.is_public == True)  # noqa: E712

    if broker_id:
        stmt = stmt.where(SocialLeader.broker_id == broker_id)

    sort_column = getattr(SocialLeader, sort, SocialLeader.roi_30d)
    stmt = stmt.order_by(desc(sort_column)).limit(limit)
    leaders = db.execute(stmt).scalars().all()

    now = datetime.now(UTC)
    since_30d = now - timedelta(days=30)
    since_90d = now - timedelta(days=90)

    result: list[dict[str, Any]] = []

    for leader in leaders:
        # Get broker accounts for this leader's user_id
        accounts = db.execute(
            select(BrokerAccount).where(
                BrokerAccount.user_id == leader.user_id,
                BrokerAccount.status == "active",
            )
        ).scalars().all()

        # Get snapshots for this leader (from all their broker accounts)
        account_ids = [a.id for a in accounts]
        if account_ids:
            # AccountSnapshot doesn't have broker_account_id FK directly,
            # use user_id + broker_id to filter
            snap_stmt = select(AccountSnapshot).where(
                AccountSnapshot.user_id == leader.user_id,
                AccountSnapshot.broker_id == leader.broker_id,
            ).order_by(AccountSnapshot.timestamp.desc()).limit(500)

            all_snaps = db.execute(snap_stmt).scalars().all()
        else:
            all_snaps = []

        # Split by time period
        snaps_30d = [s for s in all_snaps if s.timestamp >= since_30d]
        snaps_90d = [s for s in all_snaps if s.timestamp >= since_90d]

        # Compute real ROI from snapshots
        real_roi_30d = _compute_roi_from_snapshots(snaps_30d, since_30d)
        real_roi_90d = _compute_roi_from_snapshots(snaps_90d, since_90d)
        real_roi_all = _compute_roi_from_snapshots(all_snaps, datetime(2020, 1, 1, tzinfo=UTC))
        real_max_dd = _compute_max_drawdown(all_snaps)
        real_sharpe = _compute_sharpe(all_snaps)

        # Get signal-based win rate (from closed signals)
        closed_signals = db.execute(
            select(SocialSignal).where(
                SocialSignal.leader_id == leader.id,
                SocialSignal.status == "closed",
            )
        ).scalars().all()

        total_closed = len(closed_signals)
        wins = sum(1 for s in closed_signals if s.pnl_pct > 0)
        real_win_rate = (wins / total_closed * 100) if total_closed > 0 else 0.0

        # Count active signals (open positions)
        active_count = db.execute(
            select(func.count(SocialSignal.id)).where(
                SocialSignal.leader_id == leader.id,
                SocialSignal.status == "active",
            )
        ).scalar() or 0

        # Count followers
        from app.database.models.social_follow import SocialFollow
        follower_count = db.execute(
            select(func.count(SocialFollow.id)).where(
                SocialFollow.leader_id == leader.id,
                SocialFollow.active == True,  # noqa: E712
            )
        ).scalar() or 0

        # Get latest equity from most recent snapshot
        latest_equity = float(all_snaps[0].equity) if all_snaps else 0.0
        latest_pnl = float(all_snaps[0].total_pnl) if all_snaps else 0.0

        # Use real stats if available, fall back to cached stats
        roi_30d = real_roi_30d if snaps_30d else leader.roi_30d
        roi_90d = real_roi_90d if snaps_90d else leader.roi_90d
        roi_all = real_roi_all if all_snaps else leader.roi_all
        max_dd = real_max_dd if all_snaps else leader.max_drawdown
        sharpe = real_sharpe if len(all_snaps) >= 3 else leader.sharpe_ratio
        win_rate = real_win_rate if total_closed > 0 else leader.win_rate
        open_positions = active_count if active_count else leader.open_positions
        total_followers = follower_count if follower_count else leader.total_followers

        result.append({
            "id": leader.id,
            "user_id": leader.user_id,
            "display_name": leader.display_name,
            "bio": leader.bio,
            "avatar_url": leader.avatar_url,
            "broker_id": leader.broker_id,
            "is_public": leader.is_public,
            "fee_percent": leader.fee_percent,
            "min_copy_amount_usd": leader.min_copy_amount_usd,
            "roi_30d": round(roi_30d, 2),
            "roi_90d": round(roi_90d, 2),
            "roi_all": round(roi_all, 2),
            "win_rate": round(win_rate, 2),
            "total_trades": max(total_closed, leader.total_trades),
            "total_followers": total_followers,
            "max_drawdown": round(max_dd, 2),
            "sharpe_ratio": round(sharpe, 2),
            "open_positions": open_positions,
            "latest_equity_usd": round(latest_equity, 2),
            "total_pnl_usd": round(latest_pnl, 2),
            "has_broker_account": len(accounts) > 0,
            "broker_account_ids": [a.id for a in accounts],
            "broker_display_name": leader.broker_id.title(),
            "created_at": leader.created_at.isoformat() if leader.created_at else None,
            "stats_updated_at": leader.stats_updated_at.isoformat() if leader.stats_updated_at else None,
        })

    # Re-sort by requested field (since real stats may differ from cached)
    sort_key = sort
    reverse_sort = sort_key in ("roi_30d", "roi_90d", "roi_all", "win_rate", "total_followers", "total_trades", "sharpe_ratio")
    result.sort(
        key=lambda x: x.get(sort_key, 0) if x.get(sort_key) is not None else 0,
        reverse=reverse_sort,
    )

    return result[:limit]


def get_available_brokers(db: Session) -> list[dict[str, Any]]:
    """Get list of brokers that have at least one public leader.

    Returns brokers that are actually used by leaders, not a hardcoded list.
    """
    stmt = (
        select(SocialLeader.broker_id, func.count(SocialLeader.id).label("leader_count"))
        .where(SocialLeader.is_public == True)  # noqa: E712
        .group_by(SocialLeader.broker_id)
        .order_by(desc("leader_count"))
    )
    rows = db.execute(stmt).all()

    return [
        {
            "broker_id": row.broker_id,
            "display_name": row.broker_id.title(),
            "leader_count": row.leader_count,
        }
        for row in rows
    ]
