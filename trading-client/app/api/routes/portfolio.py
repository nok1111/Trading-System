"""Unified portfolio endpoints — aggregates data across all connected brokers.

Endpoints:
  GET /api/portfolio/overview       — complete portfolio snapshot (balances + positions + exposure + concentration)
  GET /api/portfolio/balances       — unified balances from all brokers
  GET /api/portfolio/positions      — unified open positions from all brokers
  GET /api/portfolio/exposure       — net exposure per asset
  GET /api/portfolio/concentration  — concentration analysis with warnings
  POST /api/portfolio/invalidate    — invalidate cache (call after trades)
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from app.services import portfolio_aggregator as agg
from app.services.auth import LocalUser, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/overview")
def get_overview(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Complete portfolio overview — balances, positions, exposure, and concentration.

    Combines data from all connected brokers into a single unified view.
    Cached for 30 seconds for performance.
    """
    return agg.get_unified_portfolio_overview(current_user.id)


@router.get("/balances")
def get_balances(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Unified balances from all connected brokers.

    Returns total USD value, breakdown by broker, and breakdown by asset.
    """
    return agg.get_unified_balances(current_user.id)


@router.get("/positions")
def get_positions(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Unified open positions from all connected brokers.

    Includes both futures positions and spot holdings (derived from balances).
    """
    return agg.get_unified_positions(current_user.id)


@router.get("/exposure")
def get_exposure(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Net exposure per asset across all brokers.

    For example: 1 BTC long on Binance + 0.5 BTC short on Bybit = 0.5 BTC net long.
    """
    return agg.get_net_exposure(current_user.id)


@router.get("/concentration")
def get_concentration(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Portfolio concentration analysis with warnings.

    Analyzes concentration by asset, broker, and venue type (spot/futures/stablecoins).
    Returns warnings if concentration exceeds safe thresholds.
    """
    return agg.get_concentration_analysis(current_user.id)


@router.post("/invalidate")
def invalidate_cache(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Invalidate cached portfolio data. Call this after trades or balance changes."""
    agg.invalidate_cache(current_user.id)
    return {"ok": True}
