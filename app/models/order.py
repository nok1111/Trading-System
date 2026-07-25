"""Modelos Pydantic para órdenes."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class OrderRequest(BaseModel):
    """Solicitud de envío de orden."""

    symbol: str = Field(..., min_length=1, max_length=16)
    side: Literal["BUY", "SELL"]
    order_type: Literal["market", "limit", "stop", "stop_limit"] = "market"
    quantity: Decimal = Field(..., gt=0)
    price: Decimal | None = None
    signal_id: int | None = None
