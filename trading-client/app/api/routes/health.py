"""Health Check endpoints — liveness and readiness probes.

Endpoints:
  GET /api/health         — full health check (all dependencies)
  GET /api/health/live    — liveness probe (is the process alive?)
  GET /api/health/ready   — readiness probe (are all deps ready?)
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["health"])

# Track startup time for uptime calculation
_startup_time = time.time()


def _check_database() -> dict[str, Any]:
    """Check database connectivity."""
    try:
        from app.database.session import SessionLocal

        db = SessionLocal()
        try:
            db.execute("SELECT 1")
            return {"status": "healthy", "latency_ms": 0}
        finally:
            db.close()
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


def _check_cache() -> dict[str, Any]:
    """Check cache service."""
    try:
        from app.services.cache import get_cache

        stats = get_cache().stats()
        return {"status": "healthy", "size": stats["size"], "hit_rate": stats["hit_rate"]}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


def _check_rate_limiter() -> dict[str, Any]:
    """Check rate limiter."""
    try:
        from app.middleware.rate_limit import get_limiter_stats

        stats = get_limiter_stats()
        return {"status": "healthy", "tracked_keys": stats["tracked_keys_current"]}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


def _check_brokers() -> dict[str, Any]:
    """Check broker registry."""
    try:
        from app.brokers.registry import get_available_broker_ids

        brokers = get_available_broker_ids()
        return {"status": "healthy", "available_brokers": len(brokers)}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


@router.get("")
def health_check() -> JSONResponse:
    """Full health check — verifies all dependencies.

    Returns 200 if all healthy, 503 if any unhealthy.
    """
    checks = {
        "database": _check_database(),
        "cache": _check_cache(),
        "rate_limiter": _check_rate_limiter(),
        "brokers": _check_brokers(),
    }

    all_healthy = all(c["status"] == "healthy" for c in checks.values())
    uptime_seconds = time.time() - _startup_time

    response = {
        "status": "healthy" if all_healthy else "unhealthy",
        "uptime_seconds": round(uptime_seconds, 1),
        "version": get_settings().APP_VERSION if hasattr(get_settings(), "APP_VERSION") else "1.0.0",
        "timestamp": time.time(),
        "checks": checks,
    }

    status_code = 200 if all_healthy else 503
    return JSONResponse(content=response, status_code=status_code)


@router.get("/live")
def liveness() -> dict:
    """Liveness probe — just checks if the process is responding.

    This should always return 200 if the process is alive.
    Used by orchestrators (k8s, Docker) to know when to restart.
    """
    return {"status": "alive", "uptime_seconds": round(time.time() - _startup_time, 1)}


@router.get("/ready")
def readiness() -> JSONResponse:
    """Readiness probe — checks if the service is ready to handle requests.

    Returns 200 if database is reachable, 503 otherwise.
    Used by orchestrators to know when to route traffic.
    """
    db_check = _check_database()
    cache_check = _check_cache()

    ready = db_check["status"] == "healthy"
    status_code = 200 if ready else 503

    return JSONResponse(
        content={
            "status": "ready" if ready else "not_ready",
            "database": db_check,
            "cache": cache_check,
        },
        status_code=status_code,
    )
