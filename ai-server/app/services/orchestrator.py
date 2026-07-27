"""Orquestador de agentes — combina los 10 agentes en un análisis unificado.

Flujo del documento (01_ORCHESTRATOR):
1. Orchestrator decide qué agentes ejecutar
2. Market Analyst analiza mercado
3. Risk Manager evalúa riesgo (poder de veto)
4. Portfolio Manager propone asignación
5. Auditor/Guardian revisa consistencia (poder de veto)
6. Execution Manager prepara orden (si aprobada)
7. Advisor/Explainer explica al usuario

Selección de modelo según plan del usuario.
Validación contra JSON Schema por agente y del envelope.
Registro de tokens consumidos.
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
from app.services.validator import validate_agent_response, validate_analysis_response

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


# Flujo por plan: qué agentes ejecutar
_PLAN_AGENTS: dict[str, list[str]] = {
    "free": ["market_analyst", "risk_manager", "advisor_explainer"],
    "pro": [
        "market_analyst", "risk_manager", "portfolio_manager",
        "auditor_guardian", "advisor_explainer",
    ],
    "premium": list(AGENTS.keys()),
}


def orchestrate_analysis(
    context: dict[str, Any],
    plan: str,
    user_id_hash: str,
) -> dict | None:
    """Ejecuta el pipeline de agentes y devuelve el análisis unificado.

    Args:
        context: Contexto de mercado comprimido (sin claves ni datos sensibles).
        plan: Plan del usuario (free, pro, premium).
        user_id_hash: Hash del user_id para contabilidad de tokens.

    Returns:
        dict con la respuesta validada contra JSON Schema, o None si falla.
    """
    model_config = get_model_for_plan(plan)
    context_str = json.dumps(context, default=str)

    agent_ids = _PLAN_AGENTS.get(plan, _PLAN_AGENTS["free"])

    total_tokens = 0
    agent_results: dict[str, dict | None] = {}
    veto_triggered = False
    veto_reason = ""

    for agent_id in agent_ids:
        agent: AgentConfig = AGENTS[agent_id]
        content, tokens = _call_llm(model_config, agent.system_prompt, context_str)
        total_tokens += tokens
        parsed = _parse_json(content)
        agent_results[agent_id] = parsed

        if tokens > 0:
            record_tokens(user_id_hash, tokens, agent_id, model_config.model)

        # Validar respuesta contra schema del agente
        if parsed:
            valid, error = validate_agent_response(agent_id, parsed)
            if not valid:
                logger.warning(f"Agent {agent_id} failed schema validation: {error}")
                agent_results[agent_id] = None
                parsed = None

        # Check veto power (Risk Manager + Auditor)
        if parsed and agent.has_veto:
            if agent_id == "risk_manager":
                risk_status = parsed.get("risk_status", "")
                if risk_status in ("REJECTED", "NEEDS_DATA"):
                    veto_triggered = True
                    veto_reason = f"Risk Manager: {risk_status} - {parsed.get('rejection_reasons', [])}"
            elif agent_id == "auditor_guardian":
                audit_status = parsed.get("audit_status", "")
                if audit_status in ("BLOCK", "EMERGENCY_HALT"):
                    veto_triggered = True
                    veto_reason = f"Auditor: {audit_status} - {parsed.get('violations', [])}"

    # Construir respuesta unificada
    market_result = agent_results.get("market_analyst") or {}
    risk_result = agent_results.get("risk_manager") or {}
    portfolio_result = agent_results.get("portfolio_manager") or {}
    advisor_result = agent_results.get("advisor_explainer") or {}
    auditor_result = agent_results.get("auditor_guardian") or {}
    sentiment_result = agent_results.get("news_sentiment_analyst") or {}

    # Market overview from market_analyst
    market_overview = market_result.get("bias", "N/A")
    if market_result.get("market_regime"):
        market_overview += f" | Regime: {market_result['market_regime']}"
    if sentiment_result.get("sentiment"):
        market_overview += f" | Sentiment: {sentiment_result['sentiment']}"

    # Actions from portfolio_manager
    actions: list[dict] = []
    if portfolio_result and portfolio_result.get("portfolio_action") in ("BUY", "SELL", "REBALANCE"):
        pm_side = portfolio_result.get("side", "BUY").lower()
        actions.append({
            "type": pm_side if pm_side in ("buy", "sell") else "hold",
            "symbol": portfolio_result.get("symbol", ""),
            "confidence": portfolio_result.get("target_allocation_pct", 0) / 100 if portfolio_result.get("target_allocation_pct") else 0.5,
            "stop_loss_pct": 0,
            "take_profit_pct": 0,
            "reason": "; ".join(portfolio_result.get("thesis", []))[:200],
        })

    # If veto triggered, override actions
    if veto_triggered:
        actions = []
        market_overview = f"BLOQUEADO: {veto_reason}"

    # Risk assessment from risk_manager
    risk_assessment = risk_result.get("risk_status", "N/A")
    if risk_result.get("risk_flags"):
        risk_assessment += f" | Flags: {', '.join(risk_result['risk_flags'][:3])}"

    # Portfolio status from portfolio_manager
    portfolio_status = portfolio_result.get("portfolio_action", "N/A")
    if portfolio_result.get("target_allocation_pct"):
        portfolio_status += f" | Target: {portfolio_result['target_allocation_pct']}%"

    # Next steps from advisor or auditor
    next_steps = "Continuar monitoreo"
    if advisor_result.get("summary"):
        next_steps = advisor_result["summary"][:300]
    elif auditor_result.get("recommended_action"):
        next_steps = auditor_result["recommended_action"][:300]

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

    valid, error = validate_analysis_response(analysis)
    if not valid:
        logger.error(f"Analysis failed JSON Schema validation: {error}")
        return None

    return analysis
