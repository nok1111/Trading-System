"""Caché compartida para análisis de IA.

Clave: analysis:{broker}:{market}:{symbol}:{timeframe}:{dataVersion}
TTL configurable via CACHE_TTL_SECONDS.
"""

from __future__ import annotations

import hashlib
import threading
import time
from typing import Any

from app.config import get_settings

_settings = get_settings()

_cache: dict[str, tuple[Any, float]] = {}
_cache_lock = threading.Lock()


def _make_key(
    broker: str,
    market: str,
    symbol: str,
    timeframe: str,
    data_version: str,
) -> str:
    """Genera una clave de caché determinista."""
    raw = f"{broker}:{market}:{symbol}:{timeframe}:{data_version}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get_cached_analysis(
    broker: str,
    market: str,
    symbol: str,
    timeframe: str,
    data_version: str,
) -> dict | None:
    """Recupera un análisis de caché si existe y no ha expirado."""
    key = _make_key(broker, market, symbol, timeframe, data_version)
    now = time.time()
    with _cache_lock:
        entry = _cache.get(key)
        if entry and now < entry[1]:
            return entry[0]
        if entry:
            _cache.pop(key, None)
    return None


def set_cached_analysis(
    broker: str,
    market: str,
    symbol: str,
    timeframe: str,
    data_version: str,
    analysis: dict,
) -> None:
    """Almacena un análisis en caché con TTL."""
    key = _make_key(broker, market, symbol, timeframe, data_version)
    expiry = time.time() + _settings.CACHE_TTL_SECONDS
    with _cache_lock:
        _cache[key] = (analysis, expiry)
        # Cleanup expired entries periodically
        if len(_cache) > 1000:
            current_time = time.time()
            expired = [k for k, (_, exp) in _cache.items() if current_time > exp]
            for k in expired:
                _cache.pop(k, None)


def clear_cache() -> None:
    """Limpia toda la caché."""
    with _cache_lock:
        _cache.clear()


def cache_size() -> int:
    """Devuelve el número de entradas en caché."""
    with _cache_lock:
        return len(_cache)
