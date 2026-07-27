"""Intelligence scheduler — runs news fetcher and cleanup on independent timers.

Starts automatically when the backend starts. Runs in a background thread
and does NOT depend on the AI trading agent being active.

Jobs:
  - News fetcher: every 5 minutes (configurable via INTEL_NEWS_INTERVAL_SECONDS)
  - Cleanup: every 24 hours (configurable via INTEL_CLEANUP_INTERVAL_SECONDS)

The scheduler is safe to run alongside the AI agent. If the agent is also
fetching news, the dedup-by-URL logic prevents duplicates.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# Configurable intervals (seconds) — can be overridden via env vars
DEFAULT_NEWS_INTERVAL = int(os.getenv("INTEL_NEWS_INTERVAL_SECONDS", "300"))  # 5 min
DEFAULT_CLEANUP_INTERVAL = int(os.getenv("INTEL_CLEANUP_INTERVAL_SECONDS", "86400"))  # 24h


class IntelligenceScheduler:
    """Background scheduler for intelligence jobs (news, cleanup)."""

    def __init__(
        self,
        news_interval: int = DEFAULT_NEWS_INTERVAL,
        cleanup_interval: int = DEFAULT_CLEANUP_INTERVAL,
    ) -> None:
        self._news_interval = news_interval
        self._cleanup_interval = cleanup_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False
        self._last_news_run: datetime | None = None
        self._last_cleanup_run: datetime | None = None
        self._news_count = 0  # total articles fetched
        self._cleanup_count = 0  # total records deleted
        self._errors = 0
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start the scheduler in a background thread."""
        if self._running:
            logger.warning("[IntelScheduler] Already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="intel-scheduler")
        self._thread.start()
        self._running = True
        logger.info(
            "[IntelScheduler] Started — news every %ds, cleanup every %ds",
            self._news_interval,
            self._cleanup_interval,
        )

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if not self._running:
            return
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        self._running = False
        logger.info("[IntelScheduler] Stopped")

    def _run(self) -> None:
        """Main loop — runs jobs on their intervals."""
        # Run news fetch immediately on first start
        self._run_news_fetch()
        self._run_cleanup()

        last_news = time.monotonic()
        last_cleanup = time.monotonic()

        while not self._stop_event.is_set():
            now = time.monotonic()

            if now - last_news >= self._news_interval:
                self._run_news_fetch()
                last_news = now

            if now - last_cleanup >= self._cleanup_interval:
                self._run_cleanup()
                last_cleanup = now

            # Sleep in small increments so stop() is responsive
            self._stop_event.wait(timeout=5)

    def _run_news_fetch(self) -> None:
        """Fetch and store news from RSS feeds."""
        try:
            from app.intelligence.news_fetcher import fetch_and_store_news
            count = fetch_and_store_news(max_per_feed=10, min_impact="low")
            with self._lock:
                self._news_count += count
                self._last_news_run = datetime.now(UTC)
            if count > 0:
                logger.info("[IntelScheduler] News fetch: %d new articles (total: %d)", count, self._news_count)
        except Exception as exc:
            with self._lock:
                self._errors += 1
            logger.error("[IntelScheduler] News fetch failed: %s", exc)

    def _run_cleanup(self) -> None:
        """Run cleanup of old news, analysis, and events."""
        try:
            from app.intelligence.cleanup import run_cleanup
            results = run_cleanup()
            total = sum(results.values())
            with self._lock:
                self._cleanup_count += total
                self._last_cleanup_run = datetime.now(UTC)
            logger.info("[IntelScheduler] Cleanup: %d records deleted (total: %d)", total, self._cleanup_count)
        except Exception as exc:
            with self._lock:
                self._errors += 1
            logger.error("[IntelScheduler] Cleanup failed: %s", exc)

    def get_status(self) -> dict[str, Any]:
        """Return current scheduler status."""
        with self._lock:
            return {
                "running": self._running,
                "news_interval_seconds": self._news_interval,
                "cleanup_interval_seconds": self._cleanup_interval,
                "last_news_run": self._last_news_run.isoformat() if self._last_news_run else None,
                "last_cleanup_run": self._last_cleanup_run.isoformat() if self._last_cleanup_run else None,
                "total_news_fetched": self._news_count,
                "total_records_cleaned": self._cleanup_count,
                "errors": self._errors,
            }

    def set_intervals(self, *, news_interval: int | None = None, cleanup_interval: int | None = None) -> None:
        """Update job intervals (takes effect on next cycle)."""
        if news_interval and news_interval >= 60:
            self._news_interval = news_interval
        if cleanup_interval and cleanup_interval >= 3600:
            self._cleanup_interval = cleanup_interval
        logger.info(
            "[IntelScheduler] Intervals updated — news: %ds, cleanup: %ds",
            self._news_interval,
            self._cleanup_interval,
        )


# Singleton instance
_scheduler: IntelligenceScheduler | None = None


def get_scheduler() -> IntelligenceScheduler:
    """Get or create the singleton scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = IntelligenceScheduler()
    return _scheduler


def start_scheduler() -> IntelligenceScheduler:
    """Get the scheduler and start it if not running."""
    sched = get_scheduler()
    if not sched.running:
        sched.start()
    return sched


def stop_scheduler() -> None:
    """Stop the scheduler if running."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.stop()
