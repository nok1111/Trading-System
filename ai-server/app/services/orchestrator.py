"""Orquestador de agentes — combina los 8 agentes en un análisis unificado.

Flujo:
1. Selecciona modelo según plan del usuario
2. Ejecuta los agentes relevantes (paralelo en producción)
3. Combina las respuestas en un JSON final
4. Valida contra JSON Schema
5. Registra tokens consumidos
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

import httpx

from app.config import get_settings
from app.services.agents import AGENTS, AgentConfig
from app.services.level_router import ModelConfig, get_model_for_plan
from app.services.token_accounting import record_tokens
from app.services.validator import validate_analysis_response

logger = logging.getLogger(__name__)


def _call_llm(
    model_config: ModelConfig,
    system_prompt: str,
    user_message: str,
) -> tuple[str | None, int]:
    """Llama al LLM y devuelve (content, tokens_used).

    Usa el mismo proveedor que el trading-client (Groq/Gemini/Ollama/OpenAI-compat).
    """
    settings = get_settings()
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
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
            return content, tokens
        except Exception as exc:
            logger.error(f"LLM call failed (groq): {exc}")
            return None, 0

    # Fallback: return None (no LLM available)
    logger.warning(f"No LLM provider available for {provider}")
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


def orchestrate_analysis(
    context: dict[str, Any],
    plan: str,
    user_id_hash: str,
) -> dict | None:
    """Ejecuta el pipeline de 8 agentes y devuelve el análisis unificado.

    Args:
        context: Contexto de mercado comprimido (sin claves ni datos sensibles).
        plan: Plan del usuario (free, pro, premium).
        user_id_hash: Hash del user_id para contabilidad de tokens.

    Returns:
        dict con la respuesta validada contra JSON Schema, o None si falla.
    """
    model_config = get_model_for_plan(plan)
    context_str = json.dumps(context, default=str)

    # Agentes a ejecutar (todos para premium, subset para planes menores)
    agent_ids = list(AGENTS.keys())
    if plan == "free":
        agent_ids = ["market_analyst", "entry_strategist", "risk_analyst"]
    elif plan == "pro":
        agent_ids = [
            "market_analyst", "risk_analyst", "strategy_selector",
            "entry_strategist", "portfolio_manager",
        ]

    total_tokens = 0
    agent_results: dict[str, dict | None] = {}

    for agent_id in agent_ids:
        agent: AgentConfig = AGENTS[agent_id]
        content, tokens = _call_llm(model_config, agent.system_prompt, context_str)
        total_tokens += tokens
        agent_results[agent_id] = _parse_json(content)
        if tokens > 0:
            record_tokens(user_id_hash, tokens, agent_id, model_config.model)

    # Combinar resultados en un JSON unificado
    market_result = agent_results.get("market_analyst") or {}
    risk_result = agent_results.get("risk_analyst") or {}
    entry_result = agent_results.get("entry_strategist") or {}
    strategy_result = agent_results.get("strategy_selector") or {}
    portfolio_result = agent_results.get("portfolio_manager") or {}
    sentiment_result = agent_results.get("sentiment_analyst") or {}
    performance_result = agent_results.get("performance_monitor") or {}

    # Construir market_overview
    market_overview = market_result.get("trend", "N/A")
    if market_result.get("momentum"):
        market_overview += f" | Momentum: {market_result['momentum']}"
    if sentiment_result.get("sentiment"):
        market_overview += f" | Sentiment: {sentiment_result['sentiment']}"

    # Construir actions desde entry_strategist
    actions = entry_result.get("entries", [])
    # Enriquecer con strategy defaults
    default_sl = strategy_result.get("default_sl_pct", 3)
    default_tp = strategy_result.get("default_tp_pct", 8)
    for action in actions:
        action.setdefault("stop_loss_pct", default_sl)
        action.setdefault("take_profit_pct", default_tp)
        action.setdefault("type", "buy")

    # Construir risk_assessment
    risk_assessment = str(risk_result.get("overall_risk", "N/A"))
    if risk_result.get("concentration"):
        risk_assessment += f" | Concentración: {risk_result['concentration']}"

    # Construir portfolio_status
    portfolio_status = str(portfolio_result.get("diversification_score", "N/A"))
    if portfolio_result.get("capital_allocation"):
        portfolio_status += f" | Allocation: {portfolio_result['capital_allocation']}"

    # Construir next_steps
    next_steps_parts = []
    if performance_result.get("suggestions"):
        next_steps_parts.extend(performance_result["suggestions"][:3])
    if risk_result.get("recommendations"):
        next_steps_parts.extend(risk_result["recommendations"][:2])
    next_steps = "; ".join(next_steps_parts) if next_steps_parts else "Continuar monitoreo"

    analysis = {
        "version": "1",
        "analysis_id": str(uuid4()),
        "market_overview": market_overview,
        "portfolio_status": str(portfolio_status),
        "analysis": json.dumps(agent_results, default=str)[:2000],
        "actions": actions,
        "risk_assessment": str(risk_assessment),
        "next_steps": next_steps,
        "tokens_used": total_tokens,
    }

    # Validar contra JSON Schema
    valid, error = validate_analysis_response(analysis)
    if not valid:
        logger.error(f"Analysis failed JSON Schema validation: {error}")
        return None

    return analysis
