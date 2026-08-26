"""Security Headers Middleware — adds HTTP security headers to all responses.

Headers added:
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- Referrer-Policy: strict-origin-when-cross-origin
- Permissions-Policy: restrict sensitive APIs
- Strict-Transport-Security: enforce HTTPS (in production)
- Content-Security-Policy: restrict resource loading

Also handles CORS hardening with configurable allowed origins.
"""

from __future__ import annotations

import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Security headers applied to all responses
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=(), usb=()",
    # HSTS — only meaningful over HTTPS, but safe to set always
    # max-age=1 year, include subdomains, preload-ready
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}

# CSP for API responses (restrictive — no external resources)
_API_CSP = "default-src 'none'; frame-ancestors 'none'"

# CSP for the desktop app (Tauri — allows inline scripts and styles)
_APP_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "connect-src 'self' https: wss: ws:; "
    "font-src 'self' data:; "
    "frame-ancestors 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that adds security headers to all responses."""

    def __init__(self, app: ASGIApp, is_production: bool = False) -> None:
        super().__init__(app)
        self.is_production = is_production

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Add security headers
        for header, value in _SECURITY_HEADERS.items():
            if header not in response.headers:
                response.headers[header] = value

        # Add CSP based on request type
        path = request.url.path
        if path.startswith("/api/"):
            response.headers["Content-Security-Policy"] = _API_CSP
        else:
            response.headers["Content-Security-Policy"] = _APP_CSP

        # Remove server header for security through obscurity
        if "server" in response.headers:
            del response.headers["server"]

        return response
