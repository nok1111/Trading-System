"""Broker management endpoints — list supported brokers and capabilities."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services.auth import LocalUser, get_current_user
from app.services.broker_account_service import get_supported_brokers

router = APIRouter(prefix="/api/brokers", tags=["brokers"])


@router.get("")
def list_brokers(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> list[dict]:
    """List all supported brokers with capabilities and metadata."""
    return get_supported_brokers()


@router.get("/capabilities")
def get_capabilities(
    broker_id: str,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Get capabilities for a specific broker."""
    from app.brokers.registry import get_capabilities as _get_caps

    caps = _get_caps(broker_id)
    return {
        "spot": caps.spot,
        "margin": caps.margin,
        "futures": caps.futures,
        "staking": caps.staking,
        "earn": caps.earn,
        "websocket": caps.websocket,
        "marketOrders": caps.market_orders,
        "limitOrders": caps.limit_orders,
        "stopOrders": caps.stop_orders,
        "withdrawals": caps.withdrawals,
    }
