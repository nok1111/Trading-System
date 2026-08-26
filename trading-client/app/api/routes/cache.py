"""Cache management endpoints — monitor and control the unified cache.

Endpoints:
  GET  /api/cache/stats          — get cache statistics
  POST /api/cache/invalidate     — invalidate cache entries
  POST /api/cache/cleanup        — force cleanup of expired entries
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.services.auth import LocalUser, get_current_user
from app.services.cache import get_cache, invalidate_user_cache

router = APIRouter(prefix="/api/cache", tags=["cache"])


class InvalidateRequest(BaseModel):
    namespace: str | None = None
    user_id: int | None = None


@router.get("/stats")
def get_stats(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Get cache statistics (size, hit rate, evictions)."""
    cache = get_cache()
    return cache.stats()


@router.post("/invalidate")
def invalidate(
    req: InvalidateRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Invalidate cache entries by namespace or user_id."""
    cache = get_cache()

    if req.user_id:
        count = invalidate_user_cache(req.user_id)
        return {"ok": True, "invalidated": count, "scope": f"user:{req.user_id}"}

    if req.namespace:
        count = cache.invalidate_namespace(req.namespace)
        return {"ok": True, "invalidated": count, "scope": req.namespace}

    # Invalidate all
    count = cache.clear()
    return {"ok": True, "invalidated": count, "scope": "all"}


@router.post("/cleanup")
def cleanup(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Force cleanup of expired entries."""
    cache = get_cache()
    removed = cache.cleanup_expired()
    return {"ok": True, "removed": removed}
