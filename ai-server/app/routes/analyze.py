"""Endpoint /v1/analyze — contrato versionado para análisis de IA.

Request:
    POST /v1/analyze
    Headers: X-HMAC-Signature, X-HMAC-Timestamp, X-HMAC-Nonce, Authorization: Bearer <jwt>
    Body: {"version": "1", "user_id_hash": "...", "plan": "free|pro|premium", "context": {...}}

Response (validado con JSON Schema):
    {"version": "1", "analysis_id": "...", "market_overview": "...", "actions": [...], ...}
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services.cache import get_cached_analysis, set_cached_analysis
from app.services.orchestrator import orchestrate_analysis
from app.services.token_accounting import get_all_usage, get_user_usage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["ai-analysis"])
settings = get_settings()


# --- Models ---

class AnalysisRequest(BaseModel):
    version: str = Field(pattern=r"^1$")
    user_id_hash: str = Field(min_length=8, max_length=128)
    plan: str = Field(pattern=r"^(free|pro|premium)$")
    broker: str = Field(default="binance", max_length=32)
    market: str = Field(default="spot", pattern=r"^(spot|futures)$")
    symbol: str = Field(default="ALL", max_length=32)
    timeframe: str = Field(default="1m", max_length=8)
    data_version: str = Field(default="", max_length=128)
    context: dict[str, Any] = Field(default_factory=dict)


class AnalysisResponse(BaseModel):
    version: str = "1"
    analysis_id: str
    market_overview: str
    portfolio_status: str = ""
    analysis: str = ""
    actions: list[dict[str, Any]] = Field(default_factory=list)
    risk_assessment: str
    next_steps: str = ""
    tokens_used: int = 0


# --- JWT Validation ---

def _validate_jwt(jwt_token: str) -> dict | None:
    """Validate JWT against the Auth Server."""
    try:
        resp = httpx.post(
            f"{settings.AUTH_SERVER_URL}/api/license/validate",
            headers={"Authorization": f"Bearer {jwt_token}"},
            timeout=10.0,
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as exc:
        logger.error(f"JWT validation failed: {exc}")
        return None


# --- Dependencies ---

async def verify_jwt(authorization: Annotated[str | None, Header()] = None) -> dict:
    """Verify JWT token from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    token = authorization.removeprefix("Bearer ")
    payload = _validate_jwt(token)
    if not payload or not payload.get("valid"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT invalid or expired",
        )
    return payload


# --- Endpoints ---

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze(
    req: AnalysisRequest,
    user: Annotated[dict, Depends(verify_jwt)],
) -> AnalysisResponse:
    """Analyze market context and return AI-powered trading decisions.

    The request must include HMAC headers (validated by middleware) and a valid JWT.
    The context must NOT contain broker API keys or sensitive user data.
    """
    # Check cache first
    cached = get_cached_analysis(
        broker=req.broker,
        market=req.market,
        symbol=req.symbol,
        timeframe=req.timeframe,
        data_version=req.data_version,
    )
    if cached:
        logger.info(f"Cache hit for {req.broker}:{req.market}:{req.symbol}")
        return AnalysisResponse(**cached)

    # Run orchestration
    result = orchestrate_analysis(
        context=req.context,
        plan=req.plan,
        user_id_hash=req.user_id_hash,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI analysis failed — LLM unavailable or output invalid",
        )

    # Cache the result
    set_cached_analysis(
        broker=req.broker,
        market=req.market,
        symbol=req.symbol,
        timeframe=req.timeframe,
        data_version=req.data_version,
        analysis=result,
    )

    return AnalysisResponse(**result)


@router.get("/agents")
async def list_agents() -> dict:
    """List available specialized agents."""
    from app.services.agents import list_agents
    return {"agents": list_agents()}


@router.get("/usage/{user_id_hash}")
async def get_usage(
    user_id_hash: str,
    user: Annotated[dict, Depends(verify_jwt)],
) -> dict:
    """Get token usage for a user."""
    return get_user_usage(user_id_hash)


@router.get("/usage")
async def get_all_usage_endpoint(
    user: Annotated[dict, Depends(verify_jwt)],
) -> dict:
    """Get token usage for all users (admin only)."""
    if user.get("subscription") != "premium":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return get_all_usage()
