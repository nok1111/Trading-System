"""Rate Limiting Middleware — per-IP and per-user request throttling.

Uses a sliding window counter approach:
- Tracks request counts per key (IP or user ID) in memory
- Resets counts every window period
- Returns 429 Too Many Requests when limit exceeded

Default limits:
- Global per-IP: 100 requests / minute
- Auth endpoints: 10 requests / minute (login, register)
- Trading endpoints: 30 requests / minute (place order, cancel)
- API key validation: 5 requests / minute

Can be customized per route group.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Any, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, key: str, limit: int, window: int) -> None:
        self.key = key
        self.limit = limit
        self.window = window
        super().__init__(f"Rate limit exceeded for {key}: {limit}/{window}s")


class SlidingWindowCounter:
    """Sliding window rate limiter using two counters.

    Tracks current and previous window counts. The effective count
    is a weighted average that provides smooth transitions between windows.
    """

    def __init__(self) -> None:
        self._current: dict[str, int] = defaultdict(int)
        self._previous: dict[str, int] = defaultdict(int)
        self._window_start: float = time.time()
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window: int) -> tuple[bool, int, int]:
        """Check if a request is allowed.

        Returns:
            (allowed, current_count, retry_after_seconds)
        """
        with self._lock:
            now = time.time()
            elapsed = now - self._window_start

            # Rotate windows if current window expired
            if elapsed >= window:
                self._previous = dict(self._current)
                self._current = defaultdict(int)
                self._window_start = now
                elapsed = 0

            # Calculate weighted count (sliding window)
            # Weight of previous window decreases as current window fills
            prev_weight = max(0, 1 - elapsed / window)
            weighted_count = int(
                self._previous.get(key, 0) * prev_weight + self._current[key]
            )

            if weighted_count >= limit:
                retry_after = int(window - elapsed)
                return False, weighted_count, retry_after

            self._current[key] += 1
            return True, self._current[key], 0

    def reset(self, key: str | None = None) -> None:
        """Reset counters for a key or all keys."""
        with self._lock:
            if key:
                self._current.pop(key, None)
                self._previous.pop(key, None)
            else:
                self._current.clear()
                self._previous.clear()


# Global rate limiter instance
_limiter = SlidingWindowCounter()


# Rate limit configurations: path prefix -> (limit, window_seconds)
_RATE_LIMITS: dict[str, tuple[int, int]] = {
    # Auth endpoints — strict limit to prevent brute force
    "/api/auth/login": (10, 60),
    "/api/auth/register": (5, 60),
    "/api/auth/verify-2fa": (10, 60),
    # Trading endpoints — moderate limit
    "/api/trading/order": (30, 60),
    "/api/trading/cancel": (30, 60),
    # Broker credential validation — very strict
    "/api/brokers/validate": (5, 60),
    # Copilot — moderate limit (AI calls are expensive)
    "/api/copilot/chat": (20, 60),
    "/api/copilot/suggest": (10, 60),
    "/api/copilot/quick-action": (10, 60),
}

# Default rate limit for all other endpoints
_DEFAULT_LIMIT = (100, 60)  # 100 requests per minute


def get_rate_limit_key(request: Request) -> str:
    """Extract the rate limit key from a request.

    Uses user ID if authenticated, otherwise falls back to IP address.
    """
    # Try to get user ID from request state (set by auth middleware)
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"

    # Fall back to IP address
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"

    client = request.client
    if client:
        return f"ip:{client.host}"

    return "ip:unknown"


def get_rate_limit_for_path(path: str) -> tuple[int, int]:
    """Get the rate limit (limit, window) for a given path."""
    for prefix, (limit, window) in _RATE_LIMITS.items():
        if path.startswith(prefix):
            return limit, window
    return _DEFAULT_LIMIT


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that enforces rate limits per IP/user."""

    def __init__(self, app: ASGIApp, enabled: bool = True) -> None:
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled:
            return await call_next(request)

        # Skip rate limiting for health checks and static assets
        path = request.url.path
        if path in ("/api/health", "/api/health/live", "/api/health/ready") or path.startswith("/assets"):
            return await call_next(request)

        # Get rate limit for this path
        limit, window = get_rate_limit_for_path(path)
        key = get_rate_limit_key(request)

        # Check rate limit
        allowed, count, retry_after = _limiter.check(key, limit, window)
        if not allowed:
            logger.warning(
                "Rate limit exceeded: %s hit %d/%d for %s",
                key, count, limit, path,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": f"Rate limit exceeded. Try again in {retry_after} seconds.",
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Add rate limit headers to response
        response = await call_next(request)
        remaining = max(0, limit - count)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


def get_limiter_stats() -> dict[str, Any]:
    """Get rate limiter statistics for monitoring."""
    with _limiter._lock:
        return {
            "tracked_keys_current": len(_limiter._current),
            "tracked_keys_previous": len(_limiter._previous),
            "current_counts": dict(_limiter._current),
            "configured_limits": {
                path: {"limit": limit, "window": window}
                for path, (limit, window) in _RATE_LIMITS.items()
            },
            "default_limit": {"limit": _DEFAULT_LIMIT[0], "window": _DEFAULT_LIMIT[1]},
        }
