"""8 agentes especializados para análisis de trading.

Cada agente tiene un prompt especializado y devuelve una parte del análisis.
El orquestador combina las respuestas en un JSON final validado.

Agentes:
1. Market Analyst — analiza mercado general
2. Risk Analyst — evalúa riesgo de portfolio
3. Strategy Selector — elige estrategia por condición
4. Entry Strategist — identifica puntos de entrada
5. Exit Strategist — identifica puntos de salida
6. Portfolio Manager — balance y diversificación
7. Sentiment Analyst — noticias y sentimiento
8. Performance Monitor — métricas y ajustes
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    """Configuración de un agente especializado."""

    name: str
    role: str
    system_prompt: str
    max_tokens: int = 500


# --- Prompts especializados ---

_MARKET_ANALYST_PROMPT = """Eres un analista de mercado cripto. Analiza:
- Tendencia general (bull/bear/range)
- Momentum de gainers y losers
- Volumen y liquidez
- Correlaciones entre spot y futures
Devuelve JSON: {"trend": "...", "momentum": "...", "volume_assessment": "...", "key_levels": [...]}"""

_RISK_ANALYST_PROMPT = """Eres un analista de riesgo. Evalúa:
- Exposición del portfolio
- Concentración por símbolo
- Risk/reward ratio de posiciones abiertas
- Nivel de riesgo overall (1-10)
Devuelve JSON: {"overall_risk": N, "concentration": "...", "exposure": "...", "recommendations": [...]}"""

_STRATEGY_SELECTOR_PROMPT = """Eres un selector de estrategia. Dado el contexto de mercado:
- Identifica la estrategia óptima (scalp, swing, hold)
- Justifica la elección
- Define parámetros (timeframe, stop-loss %, take-profit %)
Devuelve JSON: {"strategy": "...", "timeframe": "...", "reason": "...", "default_sl_pct": N, "default_tp_pct": N}"""

_ENTRY_STRATEGIST_PROMPT = """Eres un estratega de entrada. Identifica:
- Mejores oportunidades de compra
- Puntos de entrada precisos
- Confidence score (0-1) por oportunidad
- Stop-loss y take-profit por oportunidad
Devuelve JSON: {"entries": [{"symbol": "...", "confidence": N, "sl_pct": N, "tp_pct": N, "reason": "..."}]}"""

_EXIT_STRATEGIST_PROMPT = """Eres un estratega de salida. Para posiciones abiertas:
- Evalúa si mantener o cerrar
- Ajusta trailing stops
- Identifica niveles de take-profit
Devuelve JSON: {"exits": [{"symbol": "...", "action": "hold|close", "reason": "...", "new_sl": N}]}"""

_PORTFOLIO_MANAGER_PROMPT = """Eres un gestor de portfolio. Evalúa:
- Diversificación
- Asignación de capital
- Balance entre spot y futures
- Recomendaciones de rebalanceo
Devuelve JSON: {"diversification_score": N, "capital_allocation": "...", "rebalance": [...]}"""

_SENTIMENT_ANALYST_PROMPT = """Eres un analista de sentimiento. Basado en price action:
- Sentimiento de mercado (fear/greed)
- Señales de momentum
- Posible impacto de noticias
Devuelve JSON: {"sentiment": "...", "fear_greed_index": N, "signals": [...]}"""

_PERFORMANCE_MONITOR_PROMPT = """Eres un monitor de rendimiento. Analiza:
- PnL de posiciones abiertas
- Tendencia del equity
- Eficiencia de entradas previas
- Sugerencias de optimización
Devuelve JSON: {"pnl_trend": "...", "efficiency": "...", "suggestions": [...]}"""


# --- Registro de agentes ---

AGENTS: dict[str, AgentConfig] = {
    "market_analyst": AgentConfig(
        name="Market Analyst",
        role="Analiza mercado general",
        system_prompt=_MARKET_ANALYST_PROMPT,
    ),
    "risk_analyst": AgentConfig(
        name="Risk Analyst",
        role="Evalúa riesgo de portfolio",
        system_prompt=_RISK_ANALYST_PROMPT,
    ),
    "strategy_selector": AgentConfig(
        name="Strategy Selector",
        role="Elige estrategia por condición",
        system_prompt=_STRATEGY_SELECTOR_PROMPT,
    ),
    "entry_strategist": AgentConfig(
        name="Entry Strategist",
        role="Identifica puntos de entrada",
        system_prompt=_ENTRY_STRATEGIST_PROMPT,
    ),
    "exit_strategist": AgentConfig(
        name="Exit Strategist",
        role="Identifica puntos de salida",
        system_prompt=_EXIT_STRATEGIST_PROMPT,
    ),
    "portfolio_manager": AgentConfig(
        name="Portfolio Manager",
        role="Balance y diversificación",
        system_prompt=_PORTFOLIO_MANAGER_PROMPT,
    ),
    "sentiment_analyst": AgentConfig(
        name="Sentiment Analyst",
        role="Noticias y sentimiento",
        system_prompt=_SENTIMENT_ANALYST_PROMPT,
    ),
    "performance_monitor": AgentConfig(
        name="Performance Monitor",
        role="Métricas y ajustes",
        system_prompt=_PERFORMANCE_MONITOR_PROMPT,
    ),
}


def get_agent(agent_id: str) -> AgentConfig | None:
    return AGENTS.get(agent_id)


def list_agents() -> list[dict]:
    return [
        {"id": aid, "name": a.name, "role": a.role}
        for aid, a in AGENTS.items()
    ]
