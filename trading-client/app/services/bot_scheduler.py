"""Bot Scheduler — loop que ejecuta Grid y DCA bots cada 30 segundos.

Mantiene una instancia singleton que corre en background thread.
Cada ciclo:
1. Carga bots activos desde DB
2. Para cada GridBot activo: llama check_and_rebalance()
3. Para cada DCABot activo: llama run_cycle()
4. Guarda cambios en DB
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class BotScheduler:
    """Scheduler que corre grid y DCA bots en background."""

    def __init__(self, broker_factory=None) -> None:
        self._broker_factory = broker_factory
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._running = False
        self._cycle_count = 0
        self._last_cycle_at: datetime | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def last_cycle_at(self) -> datetime | None:
        return self._last_cycle_at

    def start(self) -> None:
        """Start the scheduler in a background thread."""
        if self._running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="BotScheduler")
        self._thread.start()
        self._running = True
        logger.info("BotScheduler started")

    def stop(self) -> None:
        """Stop the scheduler."""
        self._stop_event.set()
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("BotScheduler stopped")

    def _get_broker(self):
        """Get broker instance."""
        if self._broker_factory:
            return self._broker_factory()
        # Default: use shared broker from API state
        try:
            from app.api.helpers import get_shared_broker
            return get_shared_broker()
        except Exception:
            return None

    def _run_loop(self) -> None:
        """Main loop — runs every 30 seconds."""
        while not self._stop_event.is_set():
            try:
                self._run_cycle()
            except Exception as exc:
                logger.error(f"BotScheduler cycle error: {exc}")

            self._stop_event.wait(30)  # 30 second interval

    def _run_cycle(self) -> None:
        """Execute one scheduler cycle."""
        self._cycle_count += 1
        self._last_cycle_at = datetime.now(tz=UTC)

        from app.database.session import SessionLocal
        from app.database.models.grid_bot import DCABot, GridBot

        session = SessionLocal()
        try:
            broker = self._get_broker()
            if broker is None:
                return

            # Process Grid bots
            grid_bots = session.query(GridBot).filter(
                GridBot.is_active == True,  # noqa: E712
                GridBot.status == "running",
            ).all()

            for bot in grid_bots:
                try:
                    from app.services.grid_engine import GridEngine
                    engine = GridEngine(broker, bot)

                    # Initialize grid if first run
                    if not bot.grid_state:
                        result = engine.initialize_grid()
                        logger.info(f"GridBot {bot.name} initialized: {result}")
                    else:
                        result = engine.check_and_rebalance()
                        if result.get("fills_detected", 0) > 0:
                            logger.info(f"GridBot {bot.name}: {result}")

                except Exception as exc:
                    logger.error(f"GridBot {bot.name} error: {exc}")
                    bot.status = "error"

            # Process DCA bots
            dca_bots = session.query(DCABot).filter(
                DCABot.is_active == True,  # noqa: E712
                DCABot.status == "running",
            ).all()

            for bot in dca_bots:
                try:
                    from app.services.dca_engine import DCAEngine
                    engine = DCAEngine(broker, bot)
                    result = engine.run_cycle()
                    if result.get("buy", {}).get("executed"):
                        logger.info(f"DCABot {bot.name} buy executed: {result['buy']}")
                    elif result.get("take_profit", {}).get("take_profit"):
                        logger.info(f"DCABot {bot.name} TP hit: {result['take_profit']}")
                except Exception as exc:
                    logger.error(f"DCABot {bot.name} error: {exc}")
                    bot.status = "error"

            session.commit()

        except Exception as exc:
            logger.error(f"BotScheduler DB error: {exc}")
            session.rollback()
        finally:
            session.close()

    def get_status(self) -> dict[str, Any]:
        """Get scheduler status."""
        from app.database.session import SessionLocal
        from app.database.models.grid_bot import DCABot, GridBot

        session = SessionLocal()
        try:
            grid_count = session.query(GridBot).filter(
                GridBot.is_active == True,  # noqa: E712
                GridBot.status == "running",
            ).count()
            dca_count = session.query(DCABot).filter(
                DCABot.is_active == True,  # noqa: E712
                DCABot.status == "running",
            ).count()
            grid_total = session.query(GridBot).count()
            dca_total = session.query(DCABot).count()
        finally:
            session.close()

        return {
            "is_running": self._running,
            "cycle_count": self._cycle_count,
            "last_cycle_at": self._last_cycle_at.isoformat() if self._last_cycle_at else None,
            "active_grid_bots": grid_count,
            "active_dca_bots": dca_count,
            "total_grid_bots": grid_total,
            "total_dca_bots": dca_total,
        }


# Singleton instance
_scheduler: BotScheduler | None = None


def get_bot_scheduler() -> BotScheduler:
    """Get or create the singleton BotScheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BotScheduler()
    return _scheduler
