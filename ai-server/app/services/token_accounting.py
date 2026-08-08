"""Contabilidad de tokens por usuario.

Registra tokens consumidos por usuario para facturación y cuota.
In-memory store para desarrollo; en producción usar Redis o PostgreSQL.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from datetime import UTC, datetime, date
from typing import Any

_token_usage: dict[str, list[dict[str, Any]]] = defaultdict(list)
_usage_lock = threading.Lock()

# Daily token limits per plan
_DAILY_TOKEN_LIMITS: dict[str, int] = {
    "free": 50_000,
    "pro": 500_000,
    "premium": 2_000_000,
}


def _get_today_entries(user_id_hash: str) -> list[dict[str, Any]]:
    """Get today's token entries for a user."""
    today = datetime.now(UTC).date().isoformat()
    return [e for e in _token_usage.get(user_id_hash, []) if e["timestamp"].startswith(today)]


def check_quota(user_id_hash: str, plan: str = "free") -> tuple[bool, int, int]:
    """Check if user has remaining token quota for today.

    Returns (allowed, used_today, limit).
    """
    limit = _DAILY_TOKEN_LIMITS.get(plan, _DAILY_TOKEN_LIMITS["free"])
    with _usage_lock:
        entries = _get_today_entries(user_id_hash)
        used = sum(e["tokens"] for e in entries)
    return (used < limit, used, limit)


def record_tokens(user_id_hash: str, tokens: int, agent: str, model: str, plan: str = "free") -> bool:
    """Registra el consumo de tokens de un usuario.

    Returns True if recorded, False if quota exceeded.
    """
    allowed, used, limit = check_quota(user_id_hash, plan)
    if not allowed:
        return False

    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "tokens": tokens,
        "agent": agent,
        "model": model,
    }
    with _usage_lock:
        _token_usage[user_id_hash].append(entry)
    return True


def get_user_usage(user_id_hash: str) -> dict:
    """Devuelve el uso total de tokens de un usuario."""
    with _usage_lock:
        entries = _token_usage.get(user_id_hash, [])
        total = sum(e["tokens"] for e in entries)
        return {
            "user_id_hash": user_id_hash,
            "total_tokens": total,
            "request_count": len(entries),
            "recent": entries[-10:],
        }


def get_all_usage() -> dict:
    """Devuelve el uso de todos los usuarios (admin endpoint)."""
    with _usage_lock:
        result = {}
        for uid, entries in _token_usage.items():
            total = sum(e["tokens"] for e in entries)
            result[uid] = {
                "total_tokens": total,
                "request_count": len(entries),
            }
        return result
