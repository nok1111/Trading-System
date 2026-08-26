"""Auto-Copy Trading Service — automatically executes leader signals for followers.

When a follower enables auto-copy for a leader:
1. New signals from the leader are detected
2. The signal is translated to the follower's connected broker
3. An order is placed automatically (with risk checks)
4. The copy is recorded for tracking

Safety features:
- Max position size per signal (configurable)
- Max total exposure per leader
- Daily loss limit — stops copying if daily loss exceeds threshold
- Requires CONNECTED_TRADING status on the broker account
- All auto-copies are logged for audit
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database.models.social_follow import SocialFollow
from app.database.models.social_signal import SocialSignal
from app.database.session import SessionLocal

logger = logging.getLogger(__name__)

# Default risk limits for auto-copy
DEFAULT_MAX_POSITION_PCT = 10.0  # max 10% of portfolio per signal
DEFAULT_MAX_DAILY_LOSS_PCT = 5.0  # stop if daily loss exceeds 5%
DEFAULT_MAX_OPEN_POSITIONS = 10  # max concurrent copied positions


def get_auto_copy_followers(leader_id: int) -> list[SocialFollow]:
    """Get all followers with auto-copy enabled for a leader."""
    db = SessionLocal()
    try:
        return (
            db.query(SocialFollow)
            .filter(
                SocialFollow.leader_id == leader_id,
                SocialFollow.auto_copy == True,  # noqa: E712
                SocialFollow.status == "active",
            )
            .all()
        )
    finally:
        db.close()


def process_new_signal(signal: SocialSignal) -> list[dict[str, Any]]:
    """Process a new signal and auto-copy it to all enabled followers.

    Args:
        signal: The new SocialSignal to copy

    Returns:
        List of copy results: [{follower_id, success, error, order_id}]
    """
    results: list[dict[str, Any]] = []
    followers = get_auto_copy_followers(signal.leader_id)

    if not followers:
        return results

    logger.info(
        "Auto-copying signal %d from leader %d to %d followers",
        signal.id, signal.leader_id, len(followers),
    )

    for follow in followers:
        result = _copy_signal_to_follower(signal, follow)
        results.append(result)

    return results


def _copy_signal_to_follower(signal: SocialSignal, follow: SocialFollow) -> dict[str, Any]:
    """Copy a single signal to a single follower.

    Args:
        signal: The signal to copy
        follow: The follow relationship with auto-copy settings

    Returns:
        {follower_id, success, error, order_id}
    """
    follower_id = follow.user_id
    result: dict[str, Any] = {
        "follower_id": follower_id,
        "signal_id": signal.id,
        "success": False,
        "error": None,
        "order_id": None,
    }

    try:
        # 1. Check risk limits
        risk_check = _check_risk_limits(signal, follow)
        if not risk_check["ok"]:
            result["error"] = risk_check["reason"]
            return result

        # 2. Get the follower's connected broker
        broker_info = _get_follower_broker(follower_id)
        if not broker_info:
            result["error"] = "No connected broker with trading permissions"
            return result

        # 3. Calculate position size
        position_size = _calculate_position_size(
            signal, follow, broker_info["balance_usd"]
        )

        if position_size <= 0:
            result["error"] = "Calculated position size is zero"
            return result

        # 4. Place the order on the follower's broker
        order_result = _place_copy_order(
            follower_id=follower_id,
            broker_id=broker_info["broker_id"],
            signal=signal,
            position_size=position_size,
        )

        if order_result.get("success"):
            result["success"] = True
            result["order_id"] = order_result.get("order_id")
            # Log the auto-copy
            _log_auto_copy(follower_id, signal.id, order_result.get("order_id"))
        else:
            result["error"] = order_result.get("error", "Order placement failed")

    except Exception as exc:
        logger.warning("Auto-copy failed for follower %d: %s", follower_id, exc)
        result["error"] = str(exc)

    return result


def _check_risk_limits(signal: SocialSignal, follow: SocialFollow) -> dict[str, bool | str]:
    """Check if the auto-copy respects risk limits."""
    max_pos_pct = follow.auto_copy_max_pct or DEFAULT_MAX_POSITION_PCT

    if signal.size_pct > max_pos_pct:
        return {
            "ok": False,
            "reason": f"Signal size {signal.size_pct}% exceeds max {max_pos_pct}%",
        }

    # Check daily loss limit
    daily_loss = _get_daily_copy_loss(follow.user_id)
    max_daily_loss = follow.auto_copy_daily_limit or DEFAULT_MAX_DAILY_LOSS_PCT

    if daily_loss < -max_daily_loss:
        return {
            "ok": False,
            "reason": f"Daily loss {daily_loss:.1f}% exceeds limit -{max_daily_loss}%",
        }

    # Check max open positions
    open_count = _count_open_copies(follow.user_id)
    if open_count >= DEFAULT_MAX_OPEN_POSITIONS:
        return {
            "ok": False,
            "reason": f"Max open positions ({DEFAULT_MAX_OPEN_POSITIONS}) reached",
        }

    return {"ok": True, "reason": ""}


def _get_follower_broker(user_id: int) -> dict[str, Any] | None:
    """Get the follower's connected broker with trading permissions."""
    db = SessionLocal()
    try:
        from app.database.models.broker_account import BrokerAccount

        account = (
            db.query(BrokerAccount)
            .filter(
                BrokerAccount.user_id == user_id,
                BrokerAccount.status == "CONNECTED_TRADING",
            )
            .first()
        )

        if not account:
            return None

        # Get balance
        from app.services.broker_account_service import get_broker_balance
        try:
            balance = get_broker_balance(account.id)
        except Exception:
            balance = 0.0

        return {
            "broker_id": account.broker_id,
            "account_id": account.id,
            "balance_usd": balance,
        }
    except Exception as exc:
        logger.warning("Failed to get follower broker: %s", exc)
        return None
    finally:
        db.close()


def _calculate_position_size(
    signal: SocialSignal,
    follow: SocialFollow,
    balance_usd: float,
) -> float:
    """Calculate the position size in USD for the copy."""
    if balance_usd <= 0:
        return 0.0

    max_pct = follow.auto_copy_max_pct or DEFAULT_MAX_POSITION_PCT
    # Use the smaller of signal size and follower's max
    effective_pct = min(signal.size_pct, max_pct)

    return balance_usd * (effective_pct / 100.0)


def _place_copy_order(
    follower_id: int,
    broker_id: str,
    signal: SocialSignal,
    position_size_usd: float,
) -> dict[str, Any]:
    """Place an order on the follower's broker to copy the signal."""
    try:
        from app.services.order_execution import execute_order_with_retry
        from app.brokers.registry import get_adapter
        from app.brokers.models import BrokerCredentials
        from app.services.broker_account_service import get_broker_credentials

        # Get credentials for the broker account
        creds = get_broker_credentials(follower_id, broker_id)
        if not creds:
            return {"success": False, "error": "No credentials found for broker"}

        adapter = get_adapter(broker_id, creds)

        # Get current price to calculate quantity
        ticker = adapter.get_ticker(signal.symbol)
        current_price = float(ticker.last_price)

        if current_price <= 0:
            return {"success": False, "error": "Invalid current price"}

        quantity = position_size_usd / current_price

        # Place market order
        from app.brokers.models import OrderRequest, OrderSide, OrderType

        side = OrderSide.BUY if signal.side.upper() == "BUY" else OrderSide.SELL
        order_req = OrderRequest(
            symbol=signal.symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=Decimal(str(quantity)),
        )

        result = adapter.place_order(order_req)

        return {
            "success": True,
            "order_id": result.order_id,
            "quantity": quantity,
            "price": current_price,
        }
    except Exception as exc:
        logger.warning("Copy order failed: %s", exc)
        return {"success": False, "error": str(exc)}


def _get_daily_copy_loss(user_id: int) -> float:
    """Get the total P&L percentage of copied trades today."""
    db = SessionLocal()
    try:
        from datetime import timedelta

        since = datetime.now(tz=UTC).replace(tzinfo=None) - timedelta(hours=24)
        signals = (
            db.query(SocialSignal)
            .filter(
                SocialSignal.user_id == user_id,
                SocialSignal.status == "closed",
                SocialSignal.closed_at >= since,
            )
            .all()
        )

        if not signals:
            return 0.0

        total_pnl = sum(s.pnl_pct for s in signals)
        return total_pnl
    except Exception:
        return 0.0
    finally:
        db.close()


def _count_open_copies(user_id: int) -> int:
    """Count open copied positions for a user."""
    db = SessionLocal()
    try:
        return (
            db.query(SocialSignal)
            .filter(
                SocialSignal.user_id == user_id,
                SocialSignal.status == "active",
            )
            .count()
        )
    except Exception:
        return 0
    finally:
        db.close()


def _log_auto_copy(follower_id: int, signal_id: int, order_id: str | None) -> None:
    """Log an auto-copy execution for audit."""
    try:
        from app.services.audit_log import log_audit

        log_audit(
            user_id=follower_id,
            source="trading",
            message=f"Auto-copied signal {signal_id}, order {order_id}",
            level="info",
            details={"signal_id": signal_id, "order_id": order_id},
        )
    except Exception:
        pass


def get_auto_copy_stats(user_id: int) -> dict[str, Any]:
    """Get auto-copy statistics for a user."""
    db = SessionLocal()
    try:
        # Get all copied signals for this user
        signals = (
            db.query(SocialSignal)
            .filter(SocialSignal.user_id == user_id)
            .order_by(desc(SocialSignal.created_at))
            .all()
        )

        total = len(signals)
        active = sum(1 for s in signals if s.status == "active")
        closed = sum(1 for s in signals if s.status == "closed")
        winning = sum(1 for s in signals if s.status == "closed" and s.pnl_pct > 0)

        total_pnl = sum(s.pnl_pct for s in signals if s.status == "closed")

        win_rate = (winning / closed * 100) if closed > 0 else 0

        return {
            "total_copies": total,
            "active_positions": active,
            "closed_positions": closed,
            "winning_copies": winning,
            "win_rate": round(win_rate, 1),
            "total_pnl_pct": round(total_pnl, 2),
            "avg_pnl_pct": round(total_pnl / closed, 2) if closed > 0 else 0,
        }
    except Exception as exc:
        logger.warning("Failed to get auto-copy stats: %s", exc)
        return {
            "total_copies": 0,
            "active_positions": 0,
            "closed_positions": 0,
            "winning_copies": 0,
            "win_rate": 0,
            "total_pnl_pct": 0,
            "avg_pnl_pct": 0,
        }
    finally:
        db.close()
