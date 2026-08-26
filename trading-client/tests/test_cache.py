"""Tests for the unified cache service."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestTTLCache:
    """Tests for TTLCache."""

    def test_set_and_get(self):
        """Should store and retrieve values."""
        from app.services.cache import TTLCache

        cache = TTLCache()
        cache.set("key1", "value1", ttl=60)
        assert cache.get("key1") == "value1"

    def test_get_missing_key(self):
        """Should return None for missing keys."""
        from app.services.cache import TTLCache

        cache = TTLCache()
        assert cache.get("nonexistent") is None

    def test_ttl_expiration(self):
        """Should expire entries after TTL."""
        from app.services.cache import TTLCache

        cache = TTLCache()
        cache.set("key1", "value1", ttl=0)  # expires immediately

        time.sleep(0.01)
        assert cache.get("key1") is None

    def test_invalidate(self):
        """Should invalidate specific keys."""
        from app.services.cache import TTLCache

        cache = TTLCache()
        cache.set("key1", "value1", ttl=60)
        assert cache.invalidate("key1") is True
        assert cache.get("key1") is None
        assert cache.invalidate("key1") is False  # already removed

    def test_invalidate_namespace(self):
        """Should invalidate all keys with a namespace prefix."""
        from app.services.cache import TTLCache

        cache = TTLCache()
        cache.set("user:1:balance", 100, ttl=60)
        cache.set("user:1:positions", [], ttl=60)
        cache.set("user:2:balance", 200, ttl=60)

        count = cache.invalidate_namespace("user:1:")
        assert count == 2
        assert cache.get("user:1:balance") is None
        assert cache.get("user:1:positions") is None
        assert cache.get("user:2:balance") == 200  # unaffected

    def test_clear(self):
        """Should clear all entries."""
        from app.services.cache import TTLCache

        cache = TTLCache()
        cache.set("key1", "value1", ttl=60)
        cache.set("key2", "value2", ttl=60)
        count = cache.clear()
        assert count == 2
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_lru_eviction(self):
        """Should evict oldest entries when max_size is reached."""
        from app.services.cache import TTLCache

        cache = TTLCache(max_size=3)
        cache.set("key1", "v1", ttl=60)
        cache.set("key2", "v2", ttl=60)
        cache.set("key3", "v3", ttl=60)

        # Access key1 to make it recently used
        cache.get("key1")

        # Add key4 — should evict key2 (least recently used)
        cache.set("key4", "v4", ttl=60)

        assert cache.get("key1") == "v1"  # still present (was accessed)
        assert cache.get("key2") is None  # evicted
        assert cache.get("key3") == "v3"
        assert cache.get("key4") == "v4"

    def test_cleanup_expired(self):
        """Should remove only expired entries."""
        from app.services.cache import TTLCache

        cache = TTLCache()
        cache.set("expired1", "v1", ttl=0)
        cache.set("expired2", "v2", ttl=0)
        cache.set("alive", "v3", ttl=60)

        time.sleep(0.01)
        removed = cache.cleanup_expired()
        assert removed == 2
        assert cache.get("alive") == "v3"

    def test_stats(self):
        """Should track cache statistics."""
        from app.services.cache import TTLCache

        cache = TTLCache()
        cache.set("key1", "value1", ttl=60)

        cache.get("key1")  # hit
        cache.get("key1")  # hit
        cache.get("missing")  # miss

        stats = cache.stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["size"] == 1
        assert stats["hit_rate"] > 0

    def test_reset_stats(self):
        """Should reset statistics counters."""
        from app.services.cache import TTLCache

        cache = TTLCache()
        cache.set("key1", "value1", ttl=60)
        cache.get("key1")

        cache.reset_stats()
        stats = cache.stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0


class TestCacheDecorator:
    """Tests for the @cached decorator."""

    def test_cached_decorator_caches_result(self):
        """Should cache the result of a decorated function."""
        from app.services.cache import cached, get_cache

        cache = get_cache()
        cache.clear()

        call_count = 0

        @cached("test_decorator:{0}", ttl=60)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call — should execute
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call with same arg — should use cache
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # not called again

        # Different arg — should execute
        result3 = expensive_function(10)
        assert result3 == 20
        assert call_count == 2


class TestCacheHelpers:
    """Tests for cache helper functions."""

    def test_invalidate_user_cache(self):
        """Should invalidate all cache entries for a user."""
        from app.services.cache import get_cache, invalidate_user_cache

        cache = get_cache()
        cache.clear()

        cache.set("user:42:balance", 1000, ttl=60)
        cache.set("user:42:positions", [], ttl=60)
        cache.set("user:99:balance", 500, ttl=60)

        count = invalidate_user_cache(42)
        assert count == 2
        assert cache.get("user:42:balance") is None
        assert cache.get("user:99:balance") == 500

    def test_invalidate_broker_cache(self):
        """Should invalidate all cache entries for a broker."""
        from app.services.cache import get_cache, invalidate_broker_cache

        cache = get_cache()
        cache.clear()

        cache.set("broker:binance:tickers", {}, ttl=60)
        cache.set("broker:binance:balance", 100, ttl=60)
        cache.set("broker:okx:balance", 200, ttl=60)

        count = invalidate_broker_cache("binance")
        assert count == 2
        assert cache.get("broker:binance:tickers") is None
        assert cache.get("broker:okx:balance") == 200
