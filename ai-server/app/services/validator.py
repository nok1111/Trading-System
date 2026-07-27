"""Validación de salida con JSON Schema.

El ai-server valida cada respuesta del LLM contra un schema antes de devolverla
al cliente. Si no valida, se rechaza con error 422.

Cada agente tiene su propio schema definido en agents.py.
El envelope estándar valida la estructura externa de cada mensaje.
"""

from __future__ import annotations

from typing import Any

from jsonschema import ValidationError, validate

from app.services.agents import AGENTS
from app.services.intelligence_agents import INTELLIGENCE_AGENTS

# Envelope estándar para mensajes entre agentes (del documento 11_JSON_CONTRACT_EXAMPLE)
ENVELOPE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["agent", "version", "request_id", "timestamp", "status", "payload"],
    "properties": {
        "agent": {"type": "string"},
        "version": {"type": "string"},
        "request_id": {"type": "string"},
        "user_id_hash": {"type": "string"},
        "proposal_id": {"type": ["string", "null"]},
        "timestamp": {"type": "string"},
        "data_timestamp": {"type": "string"},
        "status": {"type": "string"},
        "payload": {"type": "object"},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "errors": {"type": "array", "items": {"type": "string"}},
        "requires_human_approval": {"type": "boolean"},
    },
}

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


def validate_agent_response(agent_id: str, data: dict) -> tuple[bool, str | None]:
    """Valida la respuesta de un agente específico contra su JSON Schema.

    Soporta tanto los agentes legacy (agents.py) como los nuevos agentes
    de inteligencia (intelligence_agents.py).

    Returns:
        (True, None) si valida, (False, error_message) si no.
    """
    # Try legacy agents first
    agent = AGENTS.get(agent_id)
    if agent is not None:
        try:
            validate(instance=data, schema=agent.output_schema)
            return True, None
        except ValidationError as exc:
            return False, exc.message

    # Try intelligence agents
    intel_agent = INTELLIGENCE_AGENTS.get(agent_id)
    if intel_agent is not None:
        try:
            validate(instance=data, schema=intel_agent.output_schema)
            return True, None
        except ValidationError as exc:
            return False, exc.message

    return False, f"Agente desconocido: {agent_id}"


def validate_envelope(data: dict) -> tuple[bool, str | None]:
    """Valida que un mensaje cumpla con el envelope estándar.

    Returns:
        (True, None) si valida, (False, error_message) si no.
    """
    try:
        validate(instance=data, schema=ENVELOPE_SCHEMA)
        return True, None
    except ValidationError as exc:
        return False, exc.message
