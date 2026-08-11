"""Social trading scheduler — auto-copy engine and leader stats calculator.

Runs in a background thread with independent timers:
  - Auto-copy: checks for new active signals and executes them for followers
    with auto_copy=True. Runs every 15 seconds.
  - Stats calculator: updates leader ROI, win rate, drawdown, etc.
    Runs every 5 minutes.

The scheduler is safe to run alongside other schedulers. It uses its own
DB session and handles errors gracefully.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import desc, select

logger = logging.getLogger(__name__)

DEFAULT_COPY_INTERVAL = int(os.getenv("SOCIAL_COPY_INTERVAL_SECONDS", "15"))  # 15s
DEFAULT_STATS_INTERVAL = int(os.getenv("SOCIAL_STATS_INTERVAL_SECONDS", "300"))  # 5min


class SocialScheduler:
    """Background scheduler for social trading (auto-copy + stats)."""

    def __init__(
        self,
        copy_interval: int = DEFAULT_COPY_INTERVAL,
        stats_interval: int = DEFAULT_STATS_INTERVAL,
    ) -> None:
        self._copy_interval = copy_interval
        self._stats_interval = stats_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False
        self._last_copy_run: datetime | None = None
        self._last_stats_run: datetime | None = None
        self._copies_executed = 0
        self._copies_failed = 0
        self._stats_updated = 0
        self._errors = 0
        self._lock = threading.Lock()
        # Track which signals we've already processed for auto-copy
        self._processed_signal_ids: set[int] = set()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def last_copy_run(self) -> datetime | None:
        return self._last_copy_run

    @property
    def last_stats_run(self) -> datetime | None:
        return self._last_stats_run

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "copy_interval": self._copy_interval,
            "stats_interval": self._stats_interval,
            "last_copy_run": self._last_copy_run.isoformat() if self._last_copy_run else None,
            "last_stats_run": self._last_stats_run.isoformat() if self._last_stats_run else None,
            "copies_executed": self._copies_executed,
            "copies_failed": self._copies_failed,
            "stats_updated": self._stats_updated,
            "errors": self._errors,
            "pending_signals": len(self._processed_signal_ids),
        }

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._running = True
        logger.info("SocialScheduler started (copy=%ds, stats=%ds)", self._copy_interval, self._stats_interval)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        self._running = False
        logger.info("SocialScheduler stopped")

    def _run_loop(self) -> None:
        last_stats = 0.0
        while not self._stop_event.is_set():
            try:
                # Auto-copy check
                self._run_auto_copy()
                self._last_copy_run = datetime.now(UTC)

                # Stats check (less frequent)
                now = time.time()
                if now - last_stats >= self._stats_interval:
                    self._run_stats_update()
                    self._last_stats_run = datetime.now(UTC)
                    last_stats = now

            except Exception as exc:
                self._errors += 1
                logger.error("SocialScheduler error: %s", exc, exc_info=True)

            # Wait for next interval
            self._stop_event.wait(self._copy_interval)

    def _run_auto_copy(self) -> None:
        """Check for new active signals and auto-copy them for eligible followers."""
        from app.database.models.social_follow import SocialCopyTrade, SocialFollow
        from app.database.models.social_leader import SocialLeader
        from app.database.models.social_signal import SocialSignal
        from app.database.session import SessionLocal

        db = SessionLocal()
        try:
            # Find active signals that we haven't processed yet
            active_signals = db.execute(
                select(SocialSignal)
                .where(SocialSignal.status == "active")
                .order_by(desc(SocialSignal.created_at))
                .limit(50)
            ).scalars().all()

            new_signals = [s for s in active_signals if s.id not in self._processed_signal_ids]

            if not new_signals:
                return

            for signal in new_signals:
                self._processed_signal_ids.add(signal.id)
                # Prune old IDs to prevent unbounded growth
                if len(self._processed_signal_ids) > 500:
                    self._processed_signal_ids = set(list(self._processed_signal_ids)[-300:])

                # Find all followers with auto_copy=True for this leader
                follows = db.execute(
                    select(SocialFollow).where(
                        SocialFollow.leader_id == signal.leader_id,
                        SocialFollow.auto_copy == True,  # noqa: E712
                        SocialFollow.active == True,  # noqa: E712
                    )
                ).scalars().all()

                for follow in follows:
                    # Check symbol filter
                    if follow.symbol_filter:
                        allowed = [s.strip().upper() for s in follow.symbol_filter.split(",")]
                        base_asset = signal.symbol.replace("USDT", "").replace("USDC", "").replace("USD", "")
                        if base_asset not in allowed:
                            continue

                    # Check max positions
                    existing_copies = db.execute(
                        select(SocialCopyTrade).where(
                            SocialCopyTrade.follower_id == follow.follower_id,
                            SocialCopyTrade.leader_id == signal.leader_id,
                            SocialCopyTrade.status.in_(["executed", "pending"]),
                        )
                    ).scalars().all()
                    if len(existing_copies) >= follow.max_positions:
                        continue

                    # Execute auto-copy
                    try:
                        self._execute_auto_copy(db, signal, follow)
                        self._copies_executed += 1
                    except Exception as exc:
                        self._copies_failed += 1
                        logger.warning("Auto-copy failed for follower %d, signal %d: %s", follow.follower_id, signal.id, exc)

        finally:
            db.close()

    def _execute_auto_copy(self, db, signal, follow) -> None:
        """Execute an auto-copy trade for a follower."""
        from app.brokers.models import BrokerCredentials, OrderRequest, OrderSide, OrderType
        from app.brokers.registry import get_adapter
        from app.services.crypto import decrypt
        from app.database.models.social_copy_trade import SocialCopyTrade as _CT
        from app.database.models.broker_account import BrokerAccount as BrokerAccountModel
        from app.services.signal_normalizer import calculate_quantity, check_slippage, normalize_symbol

        # Get follower's broker account (query model directly for encrypted credentials)
        broker_account = db.execute(
            select(BrokerAccountModel).where(
                BrokerAccountModel.user_id == follow.follower_id,
                BrokerAccountModel.status == "CONNECTED_TRADING",
            )
        ).scalars().first()
        if not broker_account:
            raise ValueError(f"Follower {follow.follower_id} has no connected broker accounts")

        broker_id = broker_account.broker_id

        # Decrypt credentials
        creds = BrokerCredentials(
            broker_id=broker_id,
            api_key=decrypt(broker_account.api_key_enc),
            api_secret=decrypt(broker_account.api_secret_enc),
            passphrase=decrypt(broker_account.passphrase_enc) if broker_account.passphrase_enc else None,
            testnet=broker_account.environment == "testnet",
        )

        # Normalize symbol
        target_symbol = normalize_symbol(signal.symbol, broker_id)

        # Get current price
        adapter = get_adapter(broker_id, creds)
        ticker = adapter.get_ticker(target_symbol)
        current_price = Decimal(str(ticker.price))

        # Check slippage
        if not check_slippage(signal.entry_price, current_price, max_slippage_pct=5.0):
            raise ValueError(f"Slippage too high for {target_symbol}")

        # Calculate size
        try:
            portfolio = adapter.get_portfolio()
            follower_portfolio = float(portfolio.total_usd)
        except Exception:
            follower_portfolio = 1000.0

        size_usd = Decimal(str(
            follower_portfolio * (follow.copy_pct / 100.0) * (signal.size_pct / 100.0)
        ))

        if size_usd <= 0:
            raise ValueError("Calculated size is 0")

        quantity = calculate_quantity(size_usd, current_price)
        if quantity <= 0:
            raise ValueError("Calculated quantity is 0")

        # Execute order
        side = OrderSide.BUY if signal.side in ("BUY", "CLOSE") else OrderSide.SELL
        order_req = OrderRequest(
            symbol=target_symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
        )

        result = adapter.place_order(order_req)

        # Record copy trade
        copy_trade = _CT(
            follow_id=follow.id,
            signal_id=signal.id,
            follower_id=follow.follower_id,
            leader_id=signal.leader_id,
            symbol=target_symbol,
            side=signal.side,
            size_usd=size_usd,
            entry_price=current_price,
            broker_id=broker_id,
            broker_order_id=result.order.broker_order_id if result.order else None,
            status="executed" if result.success else "failed",
            error=result.error if not result.success else None,
        )
        db.add(copy_trade)
        db.commit()

        if not result.success:
            raise ValueError(f"Order failed: {result.error}")

    def _run_stats_update(self) -> None:
        """Update leader stats (ROI, win rate, drawdown) from closed signals."""
        from app.database.models.social_leader import SocialLeader
        from app.database.models.social_signal import SocialSignal
        from app.database.session import SessionLocal

        db = SessionLocal()
        try:
            leaders = db.execute(
                select(SocialLeader).where(SocialLeader.is_public == True)  # noqa: E712
            ).scalars().all()

            for leader in leaders:
                try:
                    self._update_leader_stats(db, leader)
                    self._stats_updated += 1
                except Exception as exc:
                    logger.warning("Failed to update stats for leader %d: %s", leader.id, exc)

        finally:
            db.close()

    def _update_leader_stats(self, db, leader: SocialLeader) -> None:
        """Calculate and update stats for a single leader."""
        from app.database.models.social_signal import SocialSignal

        # Get all closed signals for this leader
        signals = db.execute(
            select(SocialSignal).where(
                SocialSignal.leader_id == leader.id,
                SocialSignal.status == "closed",
            )
        ).scalars().all()

        if not signals:
            return

        total_trades = len(signals)
        wins = sum(1 for s in signals if s.pnl_pct > 0)
        losses = sum(1 for s in signals if s.pnl_pct < 0)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

        # Calculate cumulative ROI
        cumulative_pnl = sum(s.pnl_pct for s in signals)
        roi_all = cumulative_pnl

        # ROI 30d
        cutoff_30d = datetime.utcnow().timestamp() - (30 * 86400)
        recent_30d = [s for s in signals if s.closed_at and s.closed_at.timestamp() > cutoff_30d]
        roi_30d = sum(s.pnl_pct for s in recent_30d) if recent_30d else 0

        # ROI 90d
        cutoff_90d = datetime.utcnow().timestamp() - (90 * 86400)
        recent_90d = [s for s in signals if s.closed_at and s.closed_at.timestamp() > cutoff_90d]
        roi_90d = sum(s.pnl_pct for s in recent_90d) if recent_90d else 0

        # Max drawdown (simplified: worst single trade)
        max_drawdown = min((s.pnl_pct for s in signals), default=0)
        if max_drawdown > 0:
            max_drawdown = 0

        # Sharpe ratio (simplified: avg_pnl / std_pnl)
        import statistics
        pnl_values = [s.pnl_pct for s in signals]
        if len(pnl_values) > 1:
            avg_pnl = statistics.mean(pnl_values)
            std_pnl = statistics.stdev(pnl_values)
            sharpe = (avg_pnl / std_pnl) if std_pnl > 0 else 0
        else:
            sharpe = 0

        # Count open positions
        open_count = db.execute(
            select(SocialSignal).where(
                SocialSignal.leader_id == leader.id,
                SocialSignal.status == "active",
            )
        ).scalars().all()
        open_positions = len(open_count)

        # Update leader
        leader.total_trades = total_trades
        leader.win_rate = round(win_rate, 2)
        leader.roi_30d = round(roi_30d, 2)
        leader.roi_90d = round(roi_90d, 2)
        leader.roi_all = round(roi_all, 2)
        leader.max_drawdown = round(abs(max_drawdown), 2)
        leader.sharpe_ratio = round(sharpe, 2)
        leader.open_positions = open_positions
        leader.stats_updated_at = datetime.utcnow()
        db.commit()


# Singleton
_social_scheduler: SocialScheduler | None = None


def get_social_scheduler() -> SocialScheduler | None:
    return _social_scheduler


def start_social_scheduler() -> SocialScheduler:
    global _social_scheduler
    if _social_scheduler and _social_scheduler.is_running:
        return _social_scheduler
    _social_scheduler = SocialScheduler()
    _social_scheduler.start()
    return _social_scheduler


def stop_social_scheduler() -> None:
    global _social_scheduler
    if _social_scheduler:
        _social_scheduler.stop()
        _social_scheduler = None
