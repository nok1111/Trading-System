"""Prometheus metrics for the Alvora Trading Platform.

Defines all custom metrics and helper functions for recording them.
Metrics are exposed via the /metrics endpoint (see app/api/routes/metrics.py).

Metrics:
  - alvora_orders_total (Counter, labels: broker, status)
  - alvora_order_latency_seconds (Histogram, labels: broker)
  - alvora_positions_open (Gauge, labels: broker)
  - alvora_portfolio_value_usd (Gauge)
  - alvora_ai_requests_total (Counter, labels: provider, status)
  - alvora_ai_latency_seconds (Histogram, labels: provider)
  - alvora_ws_connections (Gauge)
  - alvora_reconciler_cycles_total (Counter)
  - alvora_broker_errors_total (Counter, labels: broker, error_type)
  - alvora_http_requests_total (Counter, labels: method, path, status)
  - alvora_http_request_duration_seconds (Histogram, labels: method, path)
"""

from __future__ import annotations

import logging
from typing import Any

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

logger = logging.getLogger(__name__)

# Use a custom registry to avoid duplicate registration issues on reload
_registry = CollectorRegistry()

# ── Order metrics ───────────────────────────────────────────────────

alvora_orders_total = Counter(
    "alvora_orders_total",
    "Total number of orders placed",
    ["broker", "status"],
    registry=_registry,
)

alvora_order_latency_seconds = Histogram(
    "alvora_order_latency_seconds",
    "Order placement latency in seconds",
    ["broker"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
    registry=_registry,
)

# ── Position metrics ────────────────────────────────────────────────

alvora_positions_open = Gauge(
    "alvora_positions_open",
    "Number of open positions",
    ["broker"],
    registry=_registry,
)

alvora_portfolio_value_usd = Gauge(
    "alvora_portfolio_value_usd",
    "Total portfolio value in USD",
    registry=_registry,
)

# ── AI metrics ──────────────────────────────────────────────────────

alvora_ai_requests_total = Counter(
    "alvora_ai_requests_total",
    "Total number of AI requests",
    ["provider", "status"],
    registry=_registry,
)

alvora_ai_latency_seconds = Histogram(
    "alvora_ai_latency_seconds",
    "AI request latency in seconds",
    ["provider"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0),
    registry=_registry,
)

# ── WebSocket metrics ───────────────────────────────────────────────

alvora_ws_connections = Gauge(
    "alvora_ws_connections",
    "Number of active WebSocket connections",
    registry=_registry,
)

# ── Reconciler metrics ──────────────────────────────────────────────

alvora_reconciler_cycles_total = Counter(
    "alvora_reconciler_cycles_total",
    "Total number of reconciler cycles",
    registry=_registry,
)

# ── Broker error metrics ────────────────────────────────────────────

alvora_broker_errors_total = Counter(
    "alvora_broker_errors_total",
    "Total number of broker errors",
    ["broker", "error_type"],
    registry=_registry,
)

# ── HTTP request metrics ────────────────────────────────────────────

alvora_http_requests_total = Counter(
    "alvora_http_requests_total",
    "Total number of HTTP requests",
    ["method", "path", "status"],
    registry=_registry,
)

alvora_http_request_duration_seconds = Histogram(
    "alvora_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=_registry,
)


# ── Helper functions ────────────────────────────────────────────────


def record_order(broker: str, status: str, latency: float | None = None) -> None:
    """Record an order event.

    Args:
        broker: Broker ID (e.g. "binance", "okx").
        status: Order status (e.g. "filled", "cancelled", "error").
        latency: Order placement latency in seconds (optional).
    """
    try:
        alvora_orders_total.labels(broker=broker, status=status).inc()
        if latency is not None:
            alvora_order_latency_seconds.labels(broker=broker).observe(latency)
    except Exception as exc:
        logger.warning("record_order failed: %s", exc)


def record_ai_request(provider: str, status: str, latency: float | None = None) -> None:
    """Record an AI request event.

    Args:
        provider: AI provider (e.g. "groq", "gemini", "ollama").
        status: Request status (e.g. "success", "error", "timeout").
        latency: Request latency in seconds (optional).
    """
    try:
        alvora_ai_requests_total.labels(provider=provider, status=status).inc()
        if latency is not None:
            alvora_ai_latency_seconds.labels(provider=provider).observe(latency)
    except Exception as exc:
        logger.warning("record_ai_request failed: %s", exc)


def record_http_request(method: str, path: str, status: str, duration: float) -> None:
    """Record an HTTP request event.

    Args:
        method: HTTP method (GET, POST, etc.).
        path: Request path (normalized, e.g. "/api/portfolio/overview").
        status: HTTP status code as string (e.g. "200", "404", "500").
        duration: Request duration in seconds.
    """
    try:
        alvora_http_requests_total.labels(method=method, path=path, status=status).inc()
        alvora_http_request_duration_seconds.labels(method=method, path=path).observe(duration)
    except Exception as exc:
        logger.warning("record_http_request failed: %s", exc)


def record_broker_error(broker: str, error_type: str) -> None:
    """Record a broker error.

    Args:
        broker: Broker ID.
        error_type: Error type (e.g. "timeout", "auth", "insufficient_balance").
    """
    try:
        alvora_broker_errors_total.labels(broker=broker, error_type=error_type).inc()
    except Exception as exc:
        logger.warning("record_broker_error failed: %s", exc)


def record_reconciler_cycle() -> None:
    """Record a reconciler cycle completion."""
    try:
        alvora_reconciler_cycles_total.inc()
    except Exception as exc:
        logger.warning("record_reconciler_cycle failed: %s", exc)


def set_positions_open(broker: str, count: int) -> None:
    """Set the current number of open positions for a broker.

    Args:
        broker: Broker ID.
        count: Number of open positions.
    """
    try:
        alvora_positions_open.labels(broker=broker).set(count)
    except Exception as exc:
        logger.warning("set_positions_open failed: %s", exc)


def set_portfolio_value_usd(value: float) -> None:
    """Set the current total portfolio value in USD.

    Args:
        value: Portfolio value in USD.
    """
    try:
        alvora_portfolio_value_usd.set(value)
    except Exception as exc:
        logger.warning("set_portfolio_value_usd failed: %s", exc)


def set_ws_connections(count: int) -> None:
    """Set the current number of WebSocket connections.

    Args:
        count: Number of active WebSocket connections.
    """
    try:
        alvora_ws_connections.set(count)
    except Exception as exc:
        logger.warning("set_ws_connections failed: %s", exc)


def get_metrics() -> bytes:
    """Return metrics in Prometheus text format.

    This is the content for the /metrics endpoint that Prometheus scrapes.
    """
    return generate_latest(_registry)


def get_metrics_summary() -> dict[str, Any]:
    """Return a JSON summary of key metrics for the dashboard.

    This is NOT Prometheus format — it's a simplified JSON dict
    suitable for display in the UI.
    """
    from prometheus_client import REGISTRY

    # Collect samples from our custom registry
    summary: dict[str, Any] = {
        "orders": {},
        "ai_requests": {},
        "positions": {},
        "broker_errors": {},
        "http": {},
        "gauges": {},
    }

    try:
        for metric in _registry.collect():
            for sample in metric.samples:
                name = sample.name
                labels = sample.labels or {}
                value = sample.value

                if name.startswith("alvora_orders_total"):
                    broker = labels.get("broker", "unknown")
                    status = labels.get("status", "unknown")
                    key = f"{broker}.{status}"
                    summary["orders"][key] = int(value)
                elif name.startswith("alvora_ai_requests_total"):
                    provider = labels.get("provider", "unknown")
                    status = labels.get("status", "unknown")
                    key = f"{provider}.{status}"
                    summary["ai_requests"][key] = int(value)
                elif name.startswith("alvora_positions_open"):
                    broker = labels.get("broker", "unknown")
                    summary["positions"][broker] = int(value)
                elif name.startswith("alvora_broker_errors_total"):
                    broker = labels.get("broker", "unknown")
                    error_type = labels.get("error_type", "unknown")
                    key = f"{broker}.{error_type}"
                    summary["broker_errors"][key] = int(value)
                elif name.startswith("alvora_http_requests_total"):
                    method = labels.get("method", "")
                    path = labels.get("path", "")
                    status = labels.get("status", "")
                    key = f"{method}.{path}.{status}"
                    summary["http"][key] = int(value)
                elif name in ("alvora_portfolio_value_usd", "alvora_ws_connections"):
                    summary["gauges"][name] = value
                elif name == "alvora_reconciler_cycles_total":
                    summary["gauges"][name] = int(value)
    except Exception as exc:
        logger.warning("get_metrics_summary failed: %s", exc)

    return summary
