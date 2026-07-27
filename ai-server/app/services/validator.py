"""Validación de salida con JSON Schema.

El ai-server valida cada respuesta del LLM contra un schema antes de devolverla
al cliente. Si no valida, se rechaza con error 422.
"""

from __future__ import annotations

from typing import Any

from jsonschema import ValidationError, validate

# JSON Schema para la respuesta de /v1/analyze
ANALYSIS_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["version", "analysis_id", "market_overview", "actions", "risk_assessment"],
    "properties": {
        "version": {"type": "string"},
        "analysis_id": {"type": "string"},
        "market_overview": {"type": "string"},
        "portfolio_status": {"type": "string"},
        "analysis": {"type": "string"},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type", "symbol", "confidence"],
                "properties": {
                    "type": {"type": "string", "enum": ["buy", "sell", "hold"]},
                    "symbol": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "stop_loss_pct": {"type": "number", "minimum": 0, "maximum": 100},
                    "take_profit_pct": {"type": "number", "minimum": 0, "maximum": 100},
                    "reason": {"type": "string"},
                },
            },
        },
        "risk_assessment": {"type": "string"},
        "next_steps": {"type": "string"},
        "tokens_used": {"type": "integer", "minimum": 0},
    },
}


def validate_analysis_response(data: dict) -> tuple[bool, str | None]:
    """Valida una respuesta de análisis contra el JSON Schema.

    Returns:
        (True, None) si valida, (False, error_message) si no.
    """
    try:
        validate(instance=data, schema=ANALYSIS_RESPONSE_SCHEMA)
        return True, None
    except ValidationError as exc:
        return False, exc.message
