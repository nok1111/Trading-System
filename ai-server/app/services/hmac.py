"""HMAC service-to-service authentication + nonce + timestamp validation.

Security model:
- Every request to /v1/* must include X-HMAC-Signature, X-HMAC-Timestamp, X-HMAC-Nonce headers.
- The signature is HMAC-SHA256 of "{timestamp}\n{nonce}\n{body}" using a shared secret.
- Timestamp must be within HMAC_TIMESTAMP_WINDOW_SECONDS of server time.
- Nonce must be unique within the timestamp window (in-memory store, anti-replay).
- JWT is validated separately against the Auth Server.
"""

from __future__ import annotations

import hashlib
import hmac
import threading
import time
from collections.abc import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.config import get_settings

_settings = get_settings()

# In-memory nonce store: nonce -> expiry timestamp
_nonce_store: dict[str, float] = {}
_nonce_lock = threading.Lock()


def _cleanup_nonces() -> None:
    now = time.time()
    with _nonce_lock:
        expired = [n for n, exp in _nonce_store.items() if now > exp]
        for n in expired:
            _nonce_store.pop(n, None)


def compute_signature(timestamp: str, nonce: str, body: str, secret: str) -> str:
    """Compute HMAC-SHA256 signature for the given payload."""
    payload = f"{timestamp}\n{nonce}\n{body}"
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def verify_signature(
    timestamp: str,
    nonce: str,
    body: str,
    signature: str,
    secret: str,
) -> bool:
    """Verify HMAC-SHA256 signature."""
    expected = compute_signature(timestamp, nonce, body, secret)
    return hmac.compare_digest(expected, signature)


def verify_timestamp(timestamp: str, window_seconds: int) -> bool:
    """Verify timestamp is within the allowed window."""
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    now = int(time.time())
    return abs(now - ts) <= window_seconds


def verify_nonce(nonce: str, window_seconds: int) -> bool:
    """Verify nonce is unique within the window. Returns True if accepted."""
    _cleanup_nonces()
    with _nonce_lock:
        if nonce in _nonce_store:
            return False
        _nonce_store[nonce] = time.time() + window_seconds
        return True


async def hmac_middleware(request: Request, call_next: Callable) -> Response:
    """FastAPI middleware that validates HMAC on /v1/ routes."""
    path = request.url.path
    if not path.startswith("/v1/"):
        return await call_next(request)

    signature = request.headers.get("X-HMAC-Signature", "")
    timestamp = request.headers.get("X-HMAC-Timestamp", "")
    nonce = request.headers.get("X-HMAC-Nonce", "")

    if not signature or not timestamp or not nonce:
        return JSONResponse(
            status_code=401,
            content={"detail": "Missing HMAC headers"},
        )

    if not verify_timestamp(timestamp, _settings.HMAC_TIMESTAMP_WINDOW_SECONDS):
        return JSONResponse(
            status_code=401,
            content={"detail": "Timestamp outside allowed window"},
        )

    body = (await request.body()).decode() if await request.body() else ""
    # Re-read body since we consumed it
    request._body = body.encode()

    if not verify_signature(timestamp, nonce, body, signature, _settings.HMAC_SECRET):
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid HMAC signature"},
        )

    if not verify_nonce(nonce, _settings.HMAC_TIMESTAMP_WINDOW_SECONDS):
        return JSONResponse(
            status_code=401,
            content={"detail": "Nonce already used (replay detected)"},
        )

    return await call_next(request)
