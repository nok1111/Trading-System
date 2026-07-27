"""10 agentes especializados para análisis de inversión.

Arquitectura basada en Prompts_Arquitectura_IA_Inversion:
- 01 Orchestrator: coordina el flujo, no analiza ni ejecuta
- 02 User Profile Manager: perfil validado del usuario
- 03 Market Analyst: análisis de mercado
- 04 Risk Manager: poder de veto, protege al usuario
- 05 Portfolio Manager: asignación y rebalanceo
- 06 Execution Manager: prepara órdenes para el exchange
- 07 Advisor/Explainer: explica decisiones al usuario
- 08 Auditor/Guardian: poder de veto, detecta anomalías
- 09 News & Sentiment Analyst: opcional, noticias y sentimiento
- 10 On-chain Analyst: opcional, métricas blockchain

Orden de autoridad:
1. Restricciones legales y de seguridad
2. Preferencias del usuario
3. Risk Manager (veto)
4. Auditor/Guardian (veto)
5. Portfolio Manager
6. Market Analyst
7. Execution Manager
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    """Configuración de un agente especializado."""

    id: str
    name: str
    role: str
    system_prompt: str
    output_schema: dict
    max_tokens: int = 500
    has_veto: bool = False
    is_optional: bool = False


# --- Prompts exactos del documento ---

_ORCHESTRATOR_PROMPT = """Eres el ORQUESTADOR PRINCIPAL de una plataforma de gestión de inversiones con IA. Coordinas agentes especializados, verificas compatibilidad y decides el siguiente paso. No eres trader ni analista ni ejecutas órdenes. Si un dato crítico falta, usa REQUEST_MORE_DATA. Si el Risk Manager rechaza, no puedes aprobar. Si el Auditor detecta violación, usa EMERGENCY_HALT o NO_ACTION. Nunca aumentes riesgo para compensar pérdidas. Nunca ordenes retiros. La ausencia de operación también puede ser la mejor decisión."""

_USER_PROFILE_PROMPT = """Eres el GESTOR DE PERFIL DE INVERSIÓN del usuario. Conviertes preferencias en restricciones claras, medibles y ejecutables. No recomiendas activos ni ejecutas operaciones. Perfiles: Pasivo (preservación de capital, baja rotación, sin derivados), Intermedio (rotación moderada, riesgo controlado, derivados con consentimiento), Agresivo (mayor volatilidad, no elimina stops/límites/controles). Si faltan datos: no inventes, marca como REQUIRED y bloquea activación automática."""

_MARKET_ANALYST_PROMPT = """Eres el ANALISTA DE MERCADO de una plataforma de inversión automatizada. Interpretas datos estructurados de mercado y produces una evaluación objetiva. No decides tamaño de posición ni ejecutas. Validas calidad y actualidad de datos, identificas tendencia/rango/momentum/niveles/volatilidad/liquidez, evalúas escenarios alcista/neutral/bajista, recomiendas BULLISH_BIAS, BEARISH_BIAS, NEUTRAL, AVOID o INSUFFICIENT_DATA. Nunca inventes datos. No uses certeza absoluta. Si spread/liquidez/volatilidad anormales, incrementa riesgo."""

_RISK_MANAGER_PROMPT = """Eres el RISK MANAGER principal de una plataforma de inversión. Tu prioridad absoluta es proteger al usuario. Tu autoridad es superior a Market Analyst y Portfolio Manager. Calculas riesgo monetario máximo, tamaño máximo de posición, pérdida estimada, drawdown resultante, exposición total, concentración, correlación, riesgo de liquidación, slippage. Rechazas inmediato si: datos vencidos, operación fuera de mercados autorizados, exposición superior al límite, apalancamiento no autorizado, stop inexistente cuando obligatorio, intento de recuperar pérdidas aumentando riesgo, orden duplicada, API en estado incierto. Puedes aprobar con tamaño reducido o recomendar NO_TRADE."""

_PORTFOLIO_MANAGER_PROMPT = """Eres el PORTFOLIO MANAGER de una plataforma de inversión. Decides cómo distribuir capital respetando perfil y aprobación del Risk Manager. Propones compras/ventas/rebalanceos, mantienes diversificación, evitas concentración, mantienes porcentaje mínimo de liquidez, comparas beneficio esperado contra costos y riesgo, evitas rotación excesiva, no operas si la ventaja es insuficiente. Pasivo: baja rotación, largo plazo. Intermedio: núcleo + tácticas. Agresivo: mayor exposición dentro de límites, aceptar NO_TRADE."""

_EXECUTION_MANAGER_PROMPT = """Eres el EXECUTION MANAGER de una plataforma conectada a exchanges. Preparas y verificas órdenes. No cambias estrategia, no aumentas tamaños, no sustituyes decisiones del Risk Manager. Verificas: símbolo válido, mercado correcto, cantidad redondeada según step size, precio según tick size, notional mínimo, saldo suficiente, permisos de API, retiros deshabilitados, orden no exista, precio no desviado excesivamente, riesgo dentro de límites, no haya halt. Nunca aumentes cantidad aprobada. Nunca conviertas limit en market sin autorización. Nunca ejecutes retiros."""

_ADVISOR_PROMPT = """Eres el ASESOR EXPLICATIVO de una aplicación de inversión. Traduces decisiones técnicas a lenguaje claro, preciso y honesto. No exageras, no prometes ganancias, no ocultas riesgos. Explicas: qué se decidió, por qué, qué riesgos existen, qué podría invalidar la decisión, qué límites protegieron al usuario, qué costos se estiman. Nunca digas ganancia garantizada. Nunca uses certeza absoluta. No ocultes pérdidas o errores. Distingue hechos, estimaciones y escenarios."""

_AUDITOR_PROMPT = """Eres el AUDITOR Y GUARDIAN de una plataforma de inversión automatizada. Detectas errores, violaciones, inconsistencias, fraude, fallos de datos y comportamientos peligrosos. Tienes poder de veto. Revisas: coherencia entre perfil/análisis/riesgo/propuesta/ejecución, límites del usuario, duplicación de órdenes, cambios inesperados en cantidades, símbolos incorrectos, saldos inconsistentes, drawdown, apalancamiento, reintentos excesivos, datos vencidos, precios anómalos, API comprometida, slippage excesivo. Acciones: PASS, PASS_WITH_WARNING, BLOCK, EMERGENCY_HALT, REQUIRE_HUMAN_REVIEW. Nunca suavices una violación grave."""

_NEWS_SENTIMENT_PROMPT = """Eres el ANALISTA DE NOTICIAS Y SENTIMIENTO. Evalúas el impacto potencial de información ya recopilada por fuentes externas. No inventas noticias ni ejecutas operaciones. Evalúas: credibilidad de la fuente, si ya fue descontada por el mercado, impacto potencial, horizonte del impacto, riesgo de rumor o manipulación, contradicciones entre fuentes. Rumores no confirmados deben marcarse como tales. No uses una sola publicación social como base suficiente. No conviertas sentimiento en señal automática."""

_ONCHAIN_PROMPT = """Eres el ANALISTA ON-CHAIN. Interpretas datos blockchain y explicas posibles implicaciones. No inventas intenciones de carteras ni ejecutas operaciones. Datos: flujos hacia/desde exchanges, reservas, actividad de grandes carteras, active addresses, fees, hash rate, stablecoin flows, MVRV, distribución de holders. Un movimiento grande no equivale automáticamente a compra o venta. Diferencia transferencias internas de movimientos económicos. No uses una sola métrica para concluir."""


# --- JSON Schemas por agente ---

_ORCHESTRATOR_SCHEMA = {
    "type": "object", "required": ["status", "next_action"],
    "properties": {
        "status": {"type": "string", "enum": ["OK", "BLOCKED", "NEEDS_DATA", "NEEDS_APPROVAL"]},
        "next_action": {"type": "string", "enum": ["REQUEST_MORE_DATA", "RUN_MARKET_ANALYST", "RUN_RISK_MANAGER", "RUN_PORTFOLIO_MANAGER", "RUN_AUDITOR", "REQUEST_HUMAN_APPROVAL", "SEND_TO_EXECUTION", "NO_ACTION", "EMERGENCY_HALT"]},
        "reasoning_summary": {"type": "array", "items": {"type": "string"}},
        "blocking_issues": {"type": "array", "items": {"type": "string"}},
        "required_inputs": {"type": "array", "items": {"type": "string"}},
        "approved_proposal_id": {"type": ["string", "null"]},
        "required_human_approval": {"type": "boolean"},
        "data_timestamp": {"type": "string"},
        "data_quality": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
    },
}

_USER_PROFILE_SCHEMA = {
    "type": "object", "required": ["profile_status", "investment_style", "manual_approval_required"],
    "properties": {
        "profile_status": {"type": "string", "enum": ["COMPLETE", "INCOMPLETE", "INVALID"]},
        "investment_style": {"type": "string", "enum": ["PASSIVE", "INTERMEDIATE", "AGGRESSIVE"]},
        "base_currency": {"type": "string"}, "capital": {"type": "number"},
        "time_horizon_days": {"type": "integer"}, "primary_goal": {"type": "string"},
        "max_portfolio_drawdown_pct": {"type": "number"}, "max_risk_per_trade_pct": {"type": "number"},
        "max_asset_allocation_pct": {"type": "number"}, "max_category_allocation_pct": {"type": "number"},
        "minimum_cash_pct": {"type": "number"},
        "allowed_markets": {"type": "array", "items": {"type": "string"}},
        "allowed_assets": {"type": "array", "items": {"type": "string"}},
        "blocked_assets": {"type": "array", "items": {"type": "string"}},
        "futures_enabled": {"type": "boolean"}, "margin_enabled": {"type": "boolean"},
        "max_leverage": {"type": "integer", "minimum": 1},
        "manual_approval_required": {"type": "boolean"},
        "liquidity_requirements": {"type": "string"},
        "missing_fields": {"type": "array", "items": {"type": "string"}},
        "validation_warnings": {"type": "array", "items": {"type": "string"}},
    },
}

_MARKET_ANALYST_SCHEMA = {
    "type": "object", "required": ["analysis_status", "bias"],
    "properties": {
        "symbol": {"type": "string"}, "market": {"type": "string"},
        "analysis_status": {"type": "string", "enum": ["VALID", "INSUFFICIENT_DATA", "STALE_DATA", "INVALID"]},
        "market_regime": {"type": "string", "enum": ["TRENDING_UP", "TRENDING_DOWN", "RANGE", "HIGH_VOLATILITY", "LOW_LIQUIDITY", "UNCERTAIN"]},
        "bias": {"type": "string", "enum": ["BULLISH_BIAS", "BEARISH_BIAS", "NEUTRAL", "AVOID", "INSUFFICIENT_DATA"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "time_horizon": {"type": "string", "enum": ["INTRADAY", "SWING", "POSITION", "LONG_TERM"]},
        "key_observations": {"type": "array", "items": {"type": "string"}},
        "support_levels": {"type": "array", "items": {"type": "number"}},
        "resistance_levels": {"type": "array", "items": {"type": "number"}},
        "risk_factors": {"type": "array", "items": {"type": "string"}},
        "invalidations": {"type": "array", "items": {"type": "string"}},
        "data_timestamp": {"type": "string"},
        "data_quality": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
    },
}

_RISK_MANAGER_SCHEMA = {
    "type": "object", "required": ["risk_status"],
    "properties": {
        "risk_status": {"type": "string", "enum": ["APPROVED", "APPROVED_WITH_CHANGES", "REJECTED", "NEEDS_DATA"]},
        "proposal_id": {"type": "string"},
        "max_position_value": {"type": "number"}, "approved_position_value": {"type": "number"},
        "risk_amount": {"type": "number"}, "risk_pct_of_portfolio": {"type": "number"},
        "projected_total_exposure_pct": {"type": "number"}, "projected_drawdown_pct": {"type": "number"},
        "stop_required": {"type": "boolean"}, "approved_stop_price": {"type": ["number", "null"]},
        "max_leverage_allowed": {"type": "integer", "minimum": 1},
        "required_changes": {"type": "array", "items": {"type": "string"}},
        "rejection_reasons": {"type": "array", "items": {"type": "string"}},
        "risk_flags": {"type": "array", "items": {"type": "string"}},
        "required_human_approval": {"type": "boolean"},
        "data_timestamp": {"type": "string"},
        "data_quality": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
    },
}

_PORTFOLIO_MANAGER_SCHEMA = {
    "type": "object", "required": ["portfolio_action"],
    "properties": {
        "proposal_id": {"type": "string"},
        "portfolio_action": {"type": "string", "enum": ["BUY", "SELL", "REDUCE", "INCREASE", "REBALANCE", "HOLD", "NO_TRADE"]},
        "symbol": {"type": "string"}, "market": {"type": "string"},
        "side": {"type": "string", "enum": ["BUY", "SELL", "NONE"]},
        "order_preference": {"type": "string", "enum": ["LIMIT", "MARKET", "STOP_LIMIT", "NONE"]},
        "target_position_value": {"type": "number"}, "target_allocation_pct": {"type": "number"},
        "entry_zone": {"type": "array", "items": {"type": "number"}},
        "exit_plan": {"type": "object", "properties": {
            "stop_price": {"type": ["number", "null"]},
            "take_profit_levels": {"type": "array", "items": {"type": "number"}},
            "trailing_stop": {"type": ["number", "null"]},
        }},
        "expected_holding_period": {"type": "string"},
        "thesis": {"type": "array", "items": {"type": "string"}},
        "invalidation_conditions": {"type": "array", "items": {"type": "string"}},
        "estimated_costs": {"type": "object", "properties": {"fees": {"type": "number"}, "slippage": {"type": "number"}}},
        "risk_manager_reference": {"type": "string"},
        "required_human_approval": {"type": "boolean"},
    },
}

_EXECUTION_MANAGER_SCHEMA = {
    "type": "object", "required": ["execution_status"],
    "properties": {
        "execution_status": {"type": "string", "enum": ["READY", "BLOCKED", "NEEDS_APPROVAL", "REQUOTE_REQUIRED", "INVALID"]},
        "proposal_id": {"type": "string"}, "exchange": {"type": "string"},
        "symbol": {"type": "string"}, "market": {"type": "string"},
        "side": {"type": "string", "enum": ["BUY", "SELL"]},
        "order_type": {"type": "string", "enum": ["LIMIT", "MARKET", "STOP_LIMIT"]},
        "quantity": {"type": "number"}, "price": {"type": ["number", "null"]},
        "stop_price": {"type": ["number", "null"]},
        "time_in_force": {"type": "string", "enum": ["GTC", "IOC", "FOK", "NONE"]},
        "client_order_id": {"type": "string"}, "idempotency_key": {"type": "string"},
        "preflight_checks": {"type": "array", "items": {"type": "string"}},
        "blocking_issues": {"type": "array", "items": {"type": "string"}},
        "required_human_approval": {"type": "boolean"},
    },
}

_ADVISOR_SCHEMA = {
    "type": "object", "required": ["headline", "summary"],
    "properties": {
        "headline": {"type": "string"}, "summary": {"type": "string"},
        "what_happened": {"type": "array", "items": {"type": "string"}},
        "why": {"type": "array", "items": {"type": "string"}},
        "main_risks": {"type": "array", "items": {"type": "string"}},
        "what_would_change_the_decision": {"type": "array", "items": {"type": "string"}},
        "estimated_costs": {"type": "string"}, "user_action_required": {"type": "string"},
        "confidence_label": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
        "disclaimer": {"type": "string"},
    },
}

_AUDITOR_SCHEMA = {
    "type": "object", "required": ["audit_status"],
    "properties": {
        "audit_status": {"type": "string", "enum": ["PASS", "PASS_WITH_WARNING", "BLOCK", "EMERGENCY_HALT", "REQUIRE_HUMAN_REVIEW"]},
        "proposal_id": {"type": "string"},
        "checks_performed": {"type": "array", "items": {"type": "string"}},
        "violations": {"type": "array", "items": {"type": "string"}},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "expected_values": {"type": "object"}, "observed_values": {"type": "object"},
        "recommended_action": {"type": "string"},
        "required_human_approval": {"type": "boolean"},
        "audit_timestamp": {"type": "string"},
    },
}

_NEWS_SENTIMENT_SCHEMA = {
    "type": "object", "required": ["status", "sentiment"],
    "properties": {
        "status": {"type": "string", "enum": ["VALID", "UNCERTAIN", "INSUFFICIENT_DATA"]},
        "asset": {"type": "string"},
        "sentiment": {"type": "string", "enum": ["VERY_POSITIVE", "POSITIVE", "NEUTRAL", "NEGATIVE", "VERY_NEGATIVE"]},
        "impact_horizon": {"type": "string", "enum": ["IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM", "LONG_TERM"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "source_quality": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
        "key_events": {"type": "array", "items": {"type": "string"}},
        "contradictions": {"type": "array", "items": {"type": "string"}},
        "risk_flags": {"type": "array", "items": {"type": "string"}},
        "data_timestamp": {"type": "string"},
    },
}

_ONCHAIN_SCHEMA = {
    "type": "object", "required": ["status", "onchain_bias"],
    "properties": {
        "status": {"type": "string", "enum": ["VALID", "UNCERTAIN", "INSUFFICIENT_DATA"]},
        "asset": {"type": "string"},
        "onchain_bias": {"type": "string", "enum": ["BULLISH", "BEARISH", "NEUTRAL", "MIXED"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "observations": {"type": "array", "items": {"type": "string"}},
        "possible_interpretations": {"type": "array", "items": {"type": "string"}},
        "invalidations": {"type": "array", "items": {"type": "string"}},
        "risk_flags": {"type": "array", "items": {"type": "string"}},
        "data_timestamp": {"type": "string"},
        "data_quality": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
    },
}


# --- Registro de agentes ---

AGENTS: dict[str, AgentConfig] = {
    "orchestrator": AgentConfig(
        id="orchestrator", name="Orchestrator",
        role="Coordina el flujo, no analiza ni ejecuta",
        system_prompt=_ORCHESTRATOR_PROMPT, output_schema=_ORCHESTRATOR_SCHEMA, max_tokens=800,
    ),
    "user_profile_manager": AgentConfig(
        id="user_profile_manager", name="User Profile Manager",
        role="Convierte preferencias en restricciones ejecutables",
        system_prompt=_USER_PROFILE_PROMPT, output_schema=_USER_PROFILE_SCHEMA, max_tokens=600,
    ),
    "market_analyst": AgentConfig(
        id="market_analyst", name="Market Analyst",
        role="Interpreta datos de mercado, evaluación objetiva",
        system_prompt=_MARKET_ANALYST_PROMPT, output_schema=_MARKET_ANALYST_SCHEMA, max_tokens=600,
    ),
    "risk_manager": AgentConfig(
        id="risk_manager", name="Risk Manager",
        role="Protege al usuario, poder de veto",
        system_prompt=_RISK_MANAGER_PROMPT, output_schema=_RISK_MANAGER_SCHEMA, max_tokens=600,
        has_veto=True,
    ),
    "portfolio_manager": AgentConfig(
        id="portfolio_manager", name="Portfolio Manager",
        role="Asignación y rebalanceo respetando Risk Manager",
        system_prompt=_PORTFOLIO_MANAGER_PROMPT, output_schema=_PORTFOLIO_MANAGER_SCHEMA, max_tokens=600,
    ),
    "execution_manager": AgentConfig(
        id="execution_manager", name="Execution Manager",
        role="Prepara órdenes para el exchange",
        system_prompt=_EXECUTION_MANAGER_PROMPT, output_schema=_EXECUTION_MANAGER_SCHEMA, max_tokens=500,
    ),
    "advisor_explainer": AgentConfig(
        id="advisor_explainer", name="Advisor / Explainer",
        role="Explica decisiones en lenguaje claro",
        system_prompt=_ADVISOR_PROMPT, output_schema=_ADVISOR_SCHEMA, max_tokens=400,
    ),
    "auditor_guardian": AgentConfig(
        id="auditor_guardian", name="Auditor / Guardian",
        role="Detecta anomalías, poder de veto",
        system_prompt=_AUDITOR_PROMPT, output_schema=_AUDITOR_SCHEMA, max_tokens=500,
        has_veto=True,
    ),
    "news_sentiment_analyst": AgentConfig(
        id="news_sentiment_analyst", name="News & Sentiment Analyst",
        role="Evalúa impacto de noticias y sentimiento",
        system_prompt=_NEWS_SENTIMENT_PROMPT, output_schema=_NEWS_SENTIMENT_SCHEMA, max_tokens=400,
        is_optional=True,
    ),
    "onchain_analyst": AgentConfig(
        id="onchain_analyst", name="On-chain Analyst",
        role="Interpreta métricas blockchain",
        system_prompt=_ONCHAIN_PROMPT, output_schema=_ONCHAIN_SCHEMA, max_tokens=400,
        is_optional=True,
    ),
}


def get_agent(agent_id: str) -> AgentConfig | None:
    return AGENTS.get(agent_id)


def list_agents() -> list[dict]:
    return [
        {
            "id": a.id, "name": a.name, "role": a.role,
            "has_veto": a.has_veto, "is_optional": a.is_optional,
        }
        for a in AGENTS.values()
    ]


def get_core_agents() -> dict[str, AgentConfig]:
    """Returns only the 8 core agents (not optional)."""
    return {k: v for k, v in AGENTS.items() if not v.is_optional}


def get_optional_agents() -> dict[str, AgentConfig]:
    """Returns only the 2 optional agents."""
    return {k: v for k, v in AGENTS.items() if v.is_optional}


def get_veto_agents() -> dict[str, AgentConfig]:
    """Returns agents with veto power (Risk Manager + Auditor)."""
    return {k: v for k, v in AGENTS.items() if v.has_veto}
