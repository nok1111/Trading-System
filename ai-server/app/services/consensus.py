"""Consensus Engine — integra resultados de todos los agentes en una decisión final.

Recibe los resultados de los 8 agentes pre-consensus y llama al Consensus Agent
para producir una decisión unificada con escenarios probabilísticos.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import get_settings
from app.services.intelligence_agents import INTELLIGENCE_AGENTS
from app.services.level_router import get_model_for_plan
from app.services.validator import validate_agent_response

logger = logging.getLogger(__name__)
settings = get_settings()


def _call_llm(
    model_config: Any,
    system_prompt: str,
    user_message: str,
) -> tuple[str | None, int]:
    """Llama al LLM y devuelve (content, tokens_used)."""
    provider = model_config.provider

    if provider == "groq" and settings.GROQ_API_KEY:
        try:
            resp = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_config.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": model_config.temperature,
                    "max_tokens": model_config.max_tokens,
                    "response_format": {"type": "json_object"},
                },
                timeout=settings.AGENT_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
            return content, tokens
        except Exception as exc:  # noqa: BLE001
            logger.error("LLM call failed (groq): %s", exc)
            return None, 0

    logger.warning("No LLM provider available for %s", provider)
    return None, 0


def _parse_json(content: str | None) -> dict | None:
    if content is None:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(content[start:end])
            except json.JSONDecodeError:
                pass
    return None


def run_consensus(
    agent_results: dict[str, dict | None],
    asset: str,
    plan: str = "pro",
    user_id_hash: str = "system",
) -> dict | None:
    """Ejecuta el Consensus Agent con los resultados de los demás agentes.

    Args:
        agent_results: Resultados de los agentes pre-consensus {agent_id: result_dict | None}.
        asset: Activo objetivo del análisis.
        plan: Plan del usuario (free, pro, premium) — afecta modelo LLM.
        user_id_hash: Hash del usuario para contabilidad de tokens.

    Returns:
        dict con la decisión de consenso validada contra schema, o None si falla.
    """
    model_config = get_model_for_plan(plan)
    consensus_agent = INTELLIGENCE_AGENTS["consensus_agent"]

    # Filtrar resultados válidos
    valid_results: dict[str, dict] = {}
    for agent_id, result in agent_results.items():
        if result is not None:
            valid_results[agent_id] = result

    # Verificar mínimo de agentes
    min_agents = settings.CONSENSUS_MIN_AGENTS
    if len(valid_results) < min_agents:
        logger.warning(
            "Consensus for %s skipped: only %d agents (min %d)",
            asset, len(valid_results), min_agents,
        )
        return None

    # Construir mensaje para el Consensus Agent
    consensus_input = {
        "asset": asset,
        "agent_results": valid_results,
        "agent_count": len(valid_results),
    }

    content, tokens = _call_llm(
        model_config,
        consensus_agent.system_prompt,
        json.dumps(consensus_input, default=str),
    )

    if tokens > 0:
        from app.services.token_accounting import record_tokens
        record_tokens(user_id_hash, tokens, "consensus_agent", model_config.model)

    parsed = _parse_json(content)
    if parsed is None:
        logger.error("Consensus Agent returned unparseable response for %s", asset)
        return None

    # Validar contra schema del Consensus Agent
    valid, error = validate_agent_response("consensus_agent", parsed)
    if not valid:
        logger.warning("Consensus Agent failed schema validation for %s: %s", asset, error)
        return None

    return parsed


def compute_agreement(agent_results: dict[str, dict | None]) -> dict[str, int]:
    """Computa el acuerdo entre agentes a partir de sus resultados.

    Returns:
        dict con {positive: int, neutral: int, negative: int}.
    """
    positive = 0
    neutral = 0
    negative = 0

    bias_fields = {
        "technical_analyst": "technicalBias",
        "onchain_analyst": "onchainBias",
        "opportunity_detector": "suggestion",
        "sentiment_analyst": "sentimentScore",
    }

    for agent_id, result in agent_results.items():
        if result is None:
            continue

        field = bias_fields.get(agent_id)
        if field is None:
            continue

        value = result.get(field)
        if value is None:
            continue

        if isinstance(value, str):
            v = value.upper()
            if v in ("BUY", "BUY_ON_PULLBACK", "BULLISH", "ACCUMULATE", "BREAKOUT", "BOUNCE", "CONTINUE_TREND"):
                positive += 1
            elif v in ("SELL", "SELL_ON_RALLY", "BEARISH", "TAKE_PROFIT"):
                negative += 1
            else:
                neutral += 1
        elif isinstance(value, (int, float)):
            if value > 0.3:
                positive += 1
            elif value < -0.3:
                negative += 1
            else:
                neutral += 1

    return {"positive": positive, "neutral": neutral, "negative": negative}


def generate_default_scenarios(
    current_price: float,
    volatility: float | None = None,
) -> list[dict]:
    """Genera escenarios probabilísticos por defecto cuando el LLM no los produce.

    Args:
        current_price: Precio actual del activo.
        volatility: Volatilidad calculada (0-1).

    Returns:
        Lista de escenarios [{name, probability, range}].
    """
    vol = volatility or 0.05  # 5% default
    range_pct = vol * current_price

    return [
        {
            "name": "bullish",
            "probability": 0.25,
            "range": [current_price + range_pct * 0.5, current_price + range_pct * 2.5],
        },
        {
            "name": "base",
            "probability": 0.50,
            "range": [current_price - range_pct * 0.5, current_price + range_pct * 0.5],
        },
        {
            "name": "bearish",
            "probability": 0.25,
            "range": [current_price - range_pct * 2.5, current_price - range_pct * 0.5],
        },
    ]
