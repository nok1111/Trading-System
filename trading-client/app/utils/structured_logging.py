"""Structured logging with structlog — JSON output with request context.

Provides:
  - configure_structlog() — configure structlog with JSON rendering
  - get_logger() — returns a configured structlog logger
  - RequestContextMiddleware — injects request_id / user_id / broker_id into logs
"""

from __future__ import annotations

import logging
import sys
import uuid
from typing import Any

import structlog
from fastapi import Request
from fastapi.responses import Response

from app.config import get_settings

_CONFIGURED = False


def configure_structlog() -> None:
    """Configure structlog with JSON output, timestamps, log levels.

    Idempotent — safe to call multiple times.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Shared processors for both structlog and stdlib logging
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Bridge stdlib logging into structlog so existing logging.getLogger()
    # calls also produce structured JSON output.
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    _CONFIGURED = True


def get_logger(name: str | None = None) -> Any:
    """Return a configured structlog logger.

    Args:
        name: logger name (usually __name__). If None, returns the root logger.
    """
    if not _CONFIGURED:
        configure_structlog()
    return structlog.get_logger(name) if name else structlog.get_logger()


def bind_request_context(
    request_id: str | None = None,
    user_id: int | str | None = None,
    broker_id: str | None = None,
) -> str:
    """Bind request-scoped context vars so every log line includes them.

    Returns the request_id (generated if not provided).
    Call clear_request_context() at the end of the request.
    """
    rid = request_id or uuid.uuid4().hex
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=rid)
    if user_id is not None:
        structlog.contextvars.bind_contextvars(user_id=user_id)
    if broker_id is not None:
        structlog.contextvars.bind_contextvars(broker_id=broker_id)
    return rid


def clear_request_context() -> None:
    """Clear request-scoped context vars."""
    structlog.contextvars.clear_contextvars()


async def request_context_middleware(request: Request, call_next: Any) -> Response:
    """FastAPI/Starlette middleware that injects request_id into logs.

    Binds request_id (and user_id if available on request.state) to the
    structlog context for the duration of the request, then clears it.
    Also sets the X-Request-ID response header for client-side correlation.
    """
    # Reuse client-provided id or generate a new one
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    user_id = None
    try:
        license_info = getattr(request.state, "user", None)
        if license_info and isinstance(license_info, dict):
            user_id = license_info.get("user_id") or license_info.get("sub")
    except Exception:  # noqa: BLE001
        pass

    bind_request_context(request_id=request_id, user_id=user_id)

    logger = get_logger("app.middleware.request_context")
    logger.info(
        "request.start",
        method=request.method,
        path=request.url.path,
    )

    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request.end",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        )
        return response
    except Exception:
        logger.exception(
            "request.error",
            method=request.method,
            path=request.url.path,
        )
        raise
    finally:
        clear_request_context()
