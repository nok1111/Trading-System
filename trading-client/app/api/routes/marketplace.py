"""Strategy Marketplace endpoints — publish, browse, subscribe, review strategies.

Endpoints:
  GET    /api/marketplace/strategies             — list with filters (type, premium, sort, page, limit)
  POST   /api/marketplace/strategies             — publish a strategy (auth)
  GET    /api/marketplace/strategies/{id}        — strategy detail with reviews
  POST   /api/marketplace/strategies/{id}/subscribe   — subscribe (auth)
  DELETE /api/marketplace/strategies/{id}/subscribe   — unsubscribe (auth)
  POST   /api/marketplace/strategies/{id}/review      — review (auth)
  GET    /api/marketplace/strategies/{id}/performance — performance metrics
  GET    /api/marketplace/trending               — trending strategies
  GET    /api/marketplace/my-strategies          — user's published strategies (auth)
  GET    /api/marketplace/my-subscriptions       — user's subscriptions (auth)
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.services import marketplace_service as svc
from app.services.auth import LocalUser, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PublishStrategyRequest(BaseModel):
    title: str
    description: str = ""
    strategy_type: str = "custom"  # grid | dca | custom | ai_generated
    config: dict[str, Any] | str = {}
    is_public: bool = True
    is_premium: bool = False
    price_monthly: float | None = None
    roi_90d: float | None = None
    max_drawdown: float | None = None
    sharpe: float | None = None
    exchange: str | None = None
    symbols: list[str] | None = None


class ReviewRequest(BaseModel):
    rating: int  # 1-5
    comment: str = ""


# ---------------------------------------------------------------------------
# List / detail
# ---------------------------------------------------------------------------

@router.get("/strategies")
def list_strategies(
    type: str | None = Query(None, description="Filter by strategy type"),
    premium: str | None = Query(None, description="Filter: 'free' or 'premium'"),
    sort: str = Query("newest", description="Sort: newest | rating | downloads | roi"),
    search: str | None = Query(None, description="Search title/description"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """List marketplace strategies with filters, sorting, and pagination."""
    return svc.list_strategies({
        "type": type,
        "premium": premium,
        "sort": sort,
        "search": search,
        "page": page,
        "limit": limit,
    })


@router.post("/strategies")
def publish_strategy(
    req: PublishStrategyRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Publish a new strategy to the marketplace."""
    try:
        return svc.publish_strategy(current_user.id, req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/strategies/{listing_id}")
def get_strategy(listing_id: int) -> dict:
    """Get strategy detail with reviews and verification."""
    try:
        return svc.get_strategy(listing_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/strategies/{listing_id}/performance")
def get_strategy_performance(listing_id: int) -> dict:
    """Get aggregated performance metrics for a strategy."""
    try:
        return svc.get_strategy_performance(listing_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ---------------------------------------------------------------------------
# Subscribe / unsubscribe
# ---------------------------------------------------------------------------

@router.post("/strategies/{listing_id}/subscribe")
def subscribe_strategy(
    listing_id: int,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Subscribe to a strategy. Free = instant; premium = requires paid subscription."""
    # Premium strategies require a paid subscription tier
    listing = svc.get_strategy(listing_id)
    if listing.get("is_premium") and current_user.subscription == "free":
        raise HTTPException(
            status_code=403,
            detail="Premium strategy requires a paid subscription",
        )
    try:
        return svc.subscribe_strategy(current_user.id, listing_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/strategies/{listing_id}/subscribe")
def unsubscribe_strategy(
    listing_id: int,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Unsubscribe from a strategy."""
    try:
        return svc.unsubscribe_strategy(current_user.id, listing_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

@router.post("/strategies/{listing_id}/review")
def review_strategy(
    listing_id: int,
    req: ReviewRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Add or update a review for a strategy."""
    try:
        return svc.review_strategy(current_user.id, listing_id, req.rating, req.comment)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Trending
# ---------------------------------------------------------------------------

@router.get("/trending")
def get_trending(
    limit: int = Query(10, ge=1, le=50),
) -> list[dict]:
    """Get trending strategies (top by downloads + rating in last 7 days)."""
    return svc.get_trending_strategies(limit)


# ---------------------------------------------------------------------------
# My strategies / My subscriptions
# ---------------------------------------------------------------------------

@router.get("/my-strategies")
def get_my_strategies(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> list[dict]:
    """Get strategies published by the current user."""
    return svc.get_my_strategies(current_user.id)


@router.get("/my-subscriptions")
def get_my_subscriptions(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> list[dict]:
    """Get the current user's subscriptions."""
    return svc.get_my_subscriptions(current_user.id)
