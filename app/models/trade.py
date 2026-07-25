"""Modelos Pydantic para trades."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class TradeSummary(BaseModel):
    """Resumen de un trade ejecutado."""

    symbol: str = Field(..., min_length=1, max_length=16)
    side: Literal["BUY", "SELL"]
    quantity: Decimal = Field(..., gt=0)
    price: Decimal = Field(..., gt=0)
    commission: Decimal = Field(default=Decimal("0"), ge=0)
    slippage: Decimal = Field(default=Decimal("0"), ge=0)
    realized_pnl: Decimal = Field(default=Decimal("0"))
