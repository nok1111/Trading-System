"""Shared mutable state across API routers."""

import threading
import time

from app.config import get_settings

# Paper trading
paper_trading_state: dict = {"schedulers": [], "run_ids": []}

# AI Agent
ai_agent = None
ai_lock = threading.Lock()
ai_shared_broker = None
ai_shared_broker_keys: tuple | None = None
ai_allocated_capital: float = float(get_settings().AI_ALLOCATED_CAPITAL) if get_settings().AI_ALLOCATED_CAPITAL else 0.0

# ML training
ml_status: dict = {
    "is_training": False,
    "logs": [],
    "result": None,
    "error": None,
    "started_at": None,
    "finished_at": None,
    "symbol": None,
    "progress": 0,
    "continuous": False,
    "loop_count": 0,
}
ml_lock = threading.Lock()
ml_cancel = threading.Event()


def ml_log(msg: str) -> None:
    with ml_lock:
        ml_status["logs"].append(f"[{time.strftime('%H:%M:%S')}] {msg}")
        if len(ml_status["logs"]) > 200:
            ml_status["logs"] = ml_status["logs"][-200:]
