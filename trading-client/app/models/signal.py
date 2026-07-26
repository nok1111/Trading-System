"""Modelos Pydantic para señales de trading."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class SignalCreate(BaseModel):
    """Datos necesarios para crear una señal en base de datos."""

    timestamp: datetime
    symbol: str = Field(..., min_length=1, max_length=16)
    signal_type: Literal["BUY", "SELL", "HOLD"]
    confidence: Decimal = Field(..., ge=0, le=1)
    entry_price: Decimal | None = None
    suggested_stop_loss: Decimal | None = None
    suggested_take_profit: Decimal | None = None
    strategy_name: str = Field(..., min_length=1, max_length=50)
    explanation: str = ""
    metadata_json: dict = Field(default_factory=dict)
