"""DCA Bot endpoints — manage Dollar Cost Averaging bots.

Endpoints:
  GET    /api/dca/bots           — list user's DCA bots
  POST   /api/dca/bots           — create a new DCA bot
  GET    /api/dca/bots/{id}      — get a specific DCA bot
  POST   /api/dca/bots/{id}/stop — stop a DCA bot
  DELETE /api/dca/bots/{id}      — delete a DCA bot
  GET    /api/dca/stats          — get DCA statistics
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.services.auth import LocalUser, get_current_user
from app.services.dca_bot_service import (
    create_dca_bot,
    delete_dca_bot,
    get_dca_bot,
    list_dca_bots,
    stop_dca_bot,
)

router = APIRouter(prefix="/api/dca", tags=["dca-bots"])


class CreateDCABotRequest(BaseModel):
    name: str
    broker_id: str = "binance"
    symbol: str
    investment_usd: float
    interval_hours: int = 24
    max_investments: int = 0
    max_buy_price: float | None = None
    min_buy_price: float | None = None
    market_type: str = "spot"


@router.get("/bots")
def list_bots(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> list[dict]:
    """List all DCA bots for the current user."""
    return list_dca_bots(current_user.id)


@router.post("/bots")
def create_bot(
    req: CreateDCABotRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Create a new DCA bot."""
    return create_dca_bot(
        user_id=current_user.id,
        name=req.name,
        broker_id=req.broker_id,
        symbol=req.symbol,
        investment_usd=req.investment_usd,
        interval_hours=req.interval_hours,
        max_investments=req.max_investments,
        max_buy_price=req.max_buy_price,
        min_buy_price=req.min_buy_price,
        market_type=req.market_type,
    )


@router.get("/bots/{bot_id}")
def get_bot(
    bot_id: int,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Get a specific DCA bot."""
    bot = get_dca_bot(current_user.id, bot_id)
    if not bot:
        return {"error": "Bot not found"}
    return bot


@router.post("/bots/{bot_id}/stop")
def stop_bot(
    bot_id: int,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Stop a DCA bot."""
    return stop_dca_bot(current_user.id, bot_id)


@router.delete("/bots/{bot_id}")
def delete_bot(
    bot_id: int,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Delete a DCA bot."""
    return delete_dca_bot(current_user.id, bot_id)
