"""Contabilidad de tokens por usuario.

Registra tokens consumidos por usuario para facturación y cuota.
In-memory store para desarrollo; en producción usar Redis o PostgreSQL.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

_token_usage: dict[str, list[dict[str, Any]]] = defaultdict(list)
_usage_lock = threading.Lock()


def record_tokens(user_id_hash: str, tokens: int, agent: str, model: str) -> None:
    """Registra el consumo de tokens de un usuario."""
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "tokens": tokens,
        "agent": agent,
        "model": model,
    }
    with _usage_lock:
        _token_usage[user_id_hash].append(entry)


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
