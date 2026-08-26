"""Alvora Copilot endpoints — unified AI interface.

Endpoints:
  POST /api/copilot/chat              — conversational chat with AI
  GET  /api/copilot/suggest           — proactive portfolio suggestions
  POST /api/copilot/analyze-position  — deep analysis of a single position
  POST /api/copilot/quick-action      — one-click AI actions (rebalance, risk check, etc.)
  GET  /api/copilot/context           — get the current AI context (for transparency)
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.ai.copilot import (
    copilot_analyze_position,
    copilot_chat,
    copilot_quick_action,
    copilot_suggest,
)
from app.services.auth import LocalUser, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/copilot", tags=["copilot"])


class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None


class QuickActionRequest(BaseModel):
    action: str  # "rebalance" | "risk_check" | "opportunity_scan" | "close_all_review"


class AnalyzePositionRequest(BaseModel):
    symbol: str
    broker_id: str | None = None


@router.post("/chat")
def chat(
    req: ChatRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Conversational chat with the AI Copilot.

    Returns reply text, optional actions, and conversation metadata.
    """
    return copilot_chat(current_user.id, req.message, req.conversation_id)


@router.get("/suggest")
def suggest(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Get proactive AI suggestions based on the unified portfolio.

    Returns a prioritized list of suggestions (risk warnings, opportunities,
    position adjustments) generated from portfolio analysis.
    """
    return copilot_suggest(current_user.id)


@router.post("/analyze-position")
def analyze_position(
    req: AnalyzePositionRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Deep AI analysis of a single position.

    Returns market overview, analysis, and recommendation (hold/close/adjust).
    """
    return copilot_analyze_position(current_user.id, req.symbol, req.broker_id)


@router.post("/quick-action")
def quick_action(
    req: QuickActionRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Execute a one-click AI action.

    Available actions:
    - "rebalance" — suggest portfolio rebalancing
    - "risk_check" — full risk assessment
    - "opportunity_scan" — scan for trading opportunities
    - "close_all_review" — review all positions for potential closure
    """
    return copilot_quick_action(current_user.id, req.action)


@router.get("/context")
def get_context(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Get the current AI context (for the transparency panel).

    Shows what data the AI can see about the user.
    """
    from app.ai.alvora_context import build_alvora_context

    context = build_alvora_context(current_user.id)
    return {
        "context": context,
        "context_length": len(context),
    }
