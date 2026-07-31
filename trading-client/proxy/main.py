"""Binance VPS Proxy — forwards pre-signed requests to Binance API.

The client signs requests locally (HMAC-SHA256) and sends them here.
This proxy only validates the bearer token and forwards the request.
API keys never touch this server.
"""

import logging
import time
from collections import defaultdict
from typing import Any

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import os

PROXY_TOKEN = os.environ.get("PROXY_TOKEN", "")
if not PROXY_TOKEN:
    raise RuntimeError("PROXY_TOKEN environment variable must be set")

BINANCE_MAINNET = "https://api.binance.com"
BINANCE_TESTNET = "https://testnet.binance.vision"

# Rate limiting: 1200 requests per minute per token
RATE_LIMIT = 1200
RATE_WINDOW = 60  # seconds
_rate_counter: dict[str, list[float]] = defaultdict(list)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("binance-proxy")

app = FastAPI(title="Binance VPS Proxy", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)


class ProxyRequest(BaseModel):
    method: str  # GET, POST, DELETE
    path: str  # e.g. /api/v3/account
    params: dict[str, Any]  # query params (already includes timestamp + signature)
    api_key_header: str  # the X-MBX-APIKEY value
    testnet: bool = False


def verify_token(authorization: str = Header(...)) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if token != PROXY_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid proxy token")
    return token


def check_rate_limit(token: str) -> None:
    now = time.time()
    requests = _rate_counter[token]
    # Remove old entries
    _rate_counter[token] = [t for t in requests if now - t < RATE_WINDOW]
    if len(_rate_counter[token]) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    _rate_counter[token].append(now)


@app.get("/health")
def health():
    return {"status": "ok", "service": "binance-proxy"}


@app.post("/proxy")
async def proxy_request(
    req: ProxyRequest,
    token: str = Depends(verify_token),
):
    check_rate_limit(token)

    base_url = BINANCE_TESTNET if req.testnet else BINANCE_MAINNET
    url = f"{base_url}{req.path}"
    headers = {"X-MBX-APIKEY": req.api_key_header}

    method = req.method.upper()
    logger.info("%s %s (testnet=%s)", method, req.path, req.testnet)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                resp = await client.get(url, params=req.params, headers=headers)
            elif method == "POST":
                resp = await client.post(url, params=req.params, headers=headers)
            elif method == "DELETE":
                resp = await client.delete(url, params=req.params, headers=headers)
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported method: {method}")
    except httpx.HTTPError as exc:
        logger.error("Connection error: %s", exc)
        raise HTTPException(status_code=502, detail=f"Failed to reach Binance: {exc}")

    # Return Binance response as-is
    try:
        data = resp.json()
    except Exception:
        data = resp.text

    return JSONResponse(
        status_code=resp.status_code,
        content=data if isinstance(data, (dict, list)) else {"raw": data},
    )
