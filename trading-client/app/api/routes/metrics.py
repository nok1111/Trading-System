"""Prometheus metrics endpoints.

Endpoints:
  GET /metrics               — Prometheus text format (no auth, for Prometheus scraper)
  GET /api/metrics/summary   — JSON summary for dashboard (auth)
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.services.auth import LocalUser, get_current_user
from app.utils.metrics import get_metrics, get_metrics_summary

logger = logging.getLogger(__name__)
router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics() -> PlainTextResponse:
    """Prometheus metrics endpoint — no auth, for Prometheus scraper.

    Returns metrics in Prometheus text exposition format.
    This endpoint should be scraped by Prometheus (or Grafana Agent).
    """
    data = get_metrics()
    return PlainTextResponse(
        content=data.decode("utf-8") if isinstance(data, bytes) else str(data),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/api/metrics/summary")
def metrics_summary(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """JSON summary of key metrics for the observability dashboard.

    Returns a simplified JSON view of the Prometheus metrics,
    suitable for display in the UI.
    """
    return get_metrics_summary()
