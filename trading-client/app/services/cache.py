"""Unified cache service — TTL-based in-memory cache with LRU eviction.

Provides a simple, thread-safe cache that can be used across the app:
- Portfolio data (balances, positions) — 30s TTL
- Market data (tickers, orderbook) — 10s TTL
- Intelligence data (Fear & Greed, dominance) — 300s TTL
- Static data (broker info, market info) — 3600s TTL

Features:
- TTL-based expiration
- LRU eviction when max size is reached
- Thread-safe (uses threading.Lock)
- Per-user namespacing
- Cache invalidation by namespace or key
- Cache statistics for monitoring
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from typing import Any

logger = logging.getLogger(__name__)

# Default TTLs (in seconds)
TTL_SHORT = 10  # market data (tickers, prices)
TTL_MEDIUM = 30  # portfolio data (balances, positions)
TTL_LONG = 300  # intelligence data (Fear & Greed, dominance)
TTL_STATIC = 3600  # static data (broker info, market info)


class TTLCache:
    """Thread-safe TTL cache with LRU eviction."""

    def __init__(self, max_size: int = 1000) -> None:
        self._data: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._max_size = max_size
        # Stats
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str) -> Any | None:
        """Get a value from the cache. Returns None if not found or expired."""
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry["expires"] < time.time():
                del self._data[key]
                self._misses += 1
                return None
            # Move to end (most recently used)
            self._data.move_to_end(key)
            self._hits += 1
            return entry["data"]

    def set(self, key: str, data: Any, ttl: int = TTL_MEDIUM) -> None:
        """Set a value in the cache with TTL."""
        with self._lock:
            # Evict oldest if at max size
            while len(self._data) >= self._max_size:
                self._data.popitem(last=False)  # Remove oldest (LRU)
                self._evictions += 1

            self._data[key] = {
                "data": data,
                "expires": time.time() + ttl,
            }
            self._data.move_to_end(key)

    def invalidate(self, key: str) -> bool:
        """Invalidate a specific key. Returns True if key existed."""
        with self._lock:
            if key in self._data:
                del self._data[key]
                return True
            return False

    def invalidate_namespace(self, namespace: str) -> int:
        """Invalidate all keys starting with namespace. Returns count invalidated."""
        with self._lock:
            keys_to_remove = [k for k in self._data if k.startswith(namespace)]
            for k in keys_to_remove:
                del self._data[k]
            return len(keys_to_remove)

    def clear(self) -> int:
        """Clear all cache entries. Returns count cleared."""
        with self._lock:
            count = len(self._data)
            self._data.clear()
            return count

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        with self._lock:
            now = time.time()
            expired = [k for k, v in self._data.items() if v["expires"] < now]
            for k in expired:
                del self._data[k]
            return len(expired)

    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            return {
                "size": len(self._data),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "hit_rate": round(hit_rate, 2),
            }

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        with self._lock:
            self._hits = 0
            self._misses = 0
            self._evictions = 0


# Global cache instance
_cache = TTLCache(max_size=2000)


def get_cache() -> TTLCache:
    """Get the global cache instance."""
    return _cache


def cached(key: str, ttl: int = TTL_MEDIUM):
    """Decorator that caches the result of a function.

    Usage:
        @cached("my_function:{arg}", ttl=30)
        def my_function(arg):
            return expensive_operation(arg)

    The key can contain format placeholders that will be filled
    from the function's arguments.
    """
    def decorator(fn):
        def wrapper(*args, **kwargs):
            # Build cache key from format string + args
            try:
                cache_key = key.format(*args, **kwargs)
            except (KeyError, IndexError):
                cache_key = key

            # Try cache first
            result = _cache.get(cache_key)
            if result is not None:
                return result

            # Call function and cache result
            result = fn(*args, **kwargs)
            if result is not None:
                _cache.set(cache_key, result, ttl)
            return result
        wrapper.__name__ = fn.__name__
        wrapper.__doc__ = fn.__doc__
        return wrapper
    return decorator


def invalidate_user_cache(user_id: int) -> int:
    """Invalidate all cache entries for a user."""
    return _cache.invalidate_namespace(f"user:{user_id}:")


def invalidate_broker_cache(broker_id: str) -> int:
    """Invalidate all cache entries for a broker."""
    return _cache.invalidate_namespace(f"broker:{broker_id}:")


# Periodic cleanup task (runs in background)
_cleanup_thread: threading.Thread | None = None
_cleanup_stop = threading.Event()


def start_cleanup_task(interval: int = 300) -> None:
    """Start a background thread that periodically cleans up expired entries.

    Args:
        interval: Cleanup interval in seconds (default: 5 minutes)
    """
    global _cleanup_thread, _cleanup_stop

    if _cleanup_thread and _cleanup_thread.is_alive():
        return

    _cleanup_stop.clear()

    def _cleanup_loop():
        while not _cleanup_stop.is_set():
            try:
                removed = _cache.cleanup_expired()
                if removed > 0:
                    logger.debug("Cache cleanup: removed %d expired entries", removed)
            except Exception as exc:
                logger.warning("Cache cleanup error: %s", exc)
            _cleanup_stop.wait(interval)

    _cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True)
    _cleanup_thread.start()
    logger.info("Cache cleanup task started (interval=%ds)", interval)


def stop_cleanup_task() -> None:
    """Stop the background cleanup task."""
    global _cleanup_stop
    _cleanup_stop.set()
