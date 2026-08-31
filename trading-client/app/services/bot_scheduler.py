"""Bot Scheduler — loop que ejecuta Grid, DCA y Scalp bots.

Mantiene una instancia singleton que corre en background thread.
Cada ciclo:
1. Carga bots activos desde DB
2. Para cada GridBot activo: llama check_and_rebalance()
3. Para cada DCABot activo: llama run_cycle()
4. Para cada ScalpBot running: llama ScalpEngine.run_cycle() (heartbeat 20s)
5. Guarda cambios en DB

Intervalo: 5s si hay scalp activo, 30s en caso contrario.
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

    def _has_active_scalp(self) -> bool:
        try:
            from app.database.session import SessionLocal
            from app.database.models.grid_bot import ScalpBot
            session = SessionLocal()
            try:
                return session.query(ScalpBot).filter(
                    ScalpBot.is_active == True,  # noqa: E712
                    ScalpBot.status == "running",
                ).count() > 0
            finally:
                session.close()
        except Exception:
            return False

    def _run_loop(self) -> None:
        """Main loop — 5s when a scalp bot is running, else 30s."""
        while not self._stop_event.is_set():
            try:
                self._run_cycle()
            except Exception as exc:
                logger.error(f"BotScheduler cycle error: {exc}")

            wait = 5 if self._has_active_scalp() else 30
            self._stop_event.wait(wait)

    def _run_cycle(self) -> None:
        """Execute one scheduler cycle."""
        self._cycle_count += 1
        self._last_cycle_at = datetime.now(tz=UTC)

        from app.database.session import SessionLocal
        from app.database.models.grid_bot import DCABot, GridBot

        session = SessionLocal()
        scalp_ids: list[int] = []
        try:
            broker = self._get_broker()

            if broker is not None:
                grid_bots = session.query(GridBot).filter(
                    GridBot.is_active == True,  # noqa: E712
                    GridBot.status == "running",
                ).all()

                for bot in grid_bots:
                    try:
                        from app.services.grid_engine import GridEngine
                        engine = GridEngine(broker, bot)

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

            from app.database.models.grid_bot import ScalpBot
            scalp_ids = [
                bot.id
                for bot in session.query(ScalpBot)
                .filter(ScalpBot.is_active == True, ScalpBot.status.in_(("running", "error")))  # noqa: E712
                .all()
            ]

            session.commit()

        except Exception as extra:
            logger.error(f"BotScheduler DB error: {extra}")
            session.rollback()
        finally:
            session.close()

        # Scalp cycles hold the HTTP calls (Binance/Ollama). Run them AFTER
        # releasing SQLite so Start/Stop API is not blocked for seconds.
        from types import SimpleNamespace
        from app.services.scalp_engine import ScalpEngine
        for bid in scalp_ids:
            try:
                result = ScalpEngine(SimpleNamespace(id=bid), None).run_cycle()
                if result.get("entered"):
                    logger.info(f"ScalpBot {bid} entered: {result}")
                elif result.get("killed") or result.get("stopped"):
                    logger.info(f"ScalpBot {bid}: {result}")
            except Exception as extra:
                logger.error(f"ScalpBot {bid} error: {extra}")

    def get_status(self) -> dict[str, Any]:
        """Get scheduler status."""
        from app.database.session import SessionLocal
        from app.database.models.grid_bot import DCABot, GridBot, ScalpBot

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
            scalp_count = session.query(ScalpBot).filter(
                ScalpBot.is_active == True,  # noqa: E712
                ScalpBot.status == "running",
            ).count()
            grid_total = session.query(GridBot).count()
            dca_total = session.query(DCABot).count()
            scalp_total = session.query(ScalpBot).count()
        finally:
            session.close()

        return {
            "is_running": self._running,
            "cycle_count": self._cycle_count,
            "last_cycle_at": self._last_cycle_at.isoformat() if self._last_cycle_at else None,
            "active_grid_bots": grid_count,
            "active_dca_bots": dca_count,
            "active_scalp_bots": scalp_count,
            "total_grid_bots": grid_total,
            "total_dca_bots": dca_total,
            "total_scalp_bots": scalp_total,
        }


# Singleton instance
_scheduler: BotScheduler | None = None


def get_bot_scheduler() -> BotScheduler:
    """Get or create the singleton BotScheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BotScheduler()
    return _scheduler
