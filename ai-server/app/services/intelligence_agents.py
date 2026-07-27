"""9 agentes IA para la Plataforma de Inteligencia de Mercado Autónoma.

Arquitectura nueva (Fase B):
1. Technical Market Analyst — interpreta indicadores por timeframe
2. News Analyst — evalúa impacto de noticias
3. Sentiment Analyst — analiza sentimiento de redes sociales
4. On-chain Analyst — interpreta métricas blockchain
5. Macro Analyst — analiza entorno macroeconómico
6. Crash Risk Detector — detecta riesgo de caída con reglas numéricas
7. Opportunity Detector — busca oportunidades de trading
8. Contrarian Agent — intenta refutar señales de otros agentes
9. Consensus Agent — integra todos los agentes en una decisión final

Los agentes NO conocen al usuario. El análisis es global y compartido.
La personalización por usuario es determinista (Portfolio Matcher, Fase D).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntelligenceAgentConfig:
    """Configuración de un agente de inteligencia de mercado."""

    id: str
    name: str
    role: str
    system_prompt: str
    output_schema: dict
    max_tokens: int = 500
    interval_minutes: int = 15
    is_optional: bool = False
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None


# --- Prompts ---

_TECHNICAL_PROMPT = """Eres el ANALISTA TÉCNICO de una plataforma de inteligencia de mercado. Interpretas los indicadores técnicos de cada activo. No conoces al usuario. Recibes datos estructurados (RSI, MACD, EMA, ATR, volatilidad, volumen, soportes, resistencias) y produces una evaluación objetiva. Determinas bias técnico (BULLISH, BEARISH, NEUTRAL), fuerza de tendencia, zonas de soporte y resistencia, y recomendación técnica. Nunca inventes datos. No uses certeza absoluta."""

_NEWS_PROMPT = """Eres el ANALISTA DE NOTICIAS. Lees noticias nuevas y determinas: activos afectados, gravedad, si es rumor o hecho confirmado, horizonte del impacto, posible efecto positivo o negativo, y si ya está reflejado en el precio. No inventas noticias. Rumores no confirmados deben marcarse como tales. No conviertes una sola publicación social en señal automática."""

_SENTIMENT_PROMPT = """Eres el ANALISTA DE SENTIMIENTO. Analizas redes sociales, menciones, cambios de narrativa, euforia excesiva, miedo excesivo, y posibles campañas coordinadas. Detectas situaciones como: precio subiendo + sentimiento eufórico + volumen perdiendo fuerza = riesgo de distribución. No usas una sola fuente como base suficiente."""

_ONCHAIN_PROMPT = """Eres el ANALISTA ON-CHAIN. Interpretas datos blockchain: entradas/salidas de exchanges, movimientos de ballenas, reservas, stablecoins, actividad de carteras, concentración, flujos entre cadenas. Un movimiento grande no equivale automáticamente a compra o venta. Diferencia transferencias internas de movimientos económicos. No uses una sola métrica para concluir."""

_MACRO_PROMPT = """Eres el ANALISTA MACRO. Analizas tasas de interés, inflación, decisiones de bancos centrales, dólar, bonos, oro, petróleo, mercado accionario y eventos geopolíticos. Determinas el entorno general (risk_on, risk_off, neutral) y su impacto en cripto. Tu función es establecer el contexto macro, no predecir precios."""

_CRASH_PROMPT = """Eres el DETECTOR DE RIESGO DE CAÍDA. Complementas reglas numéricas con análisis IA. Revisas: volatilidad repentina, rupturas de soporte, cascadas de liquidaciones, funding extremo, open interest excesivo, caída de liquidez, grandes entradas a exchanges, noticias críticas, correlaciones entre mercados, divergencias. Produces niveles de riesgo (0-1), no afirmaciones absolutas."""

_OPPORTUNITY_PROMPT = """Eres el DETECTOR DE OPORTUNIDADES. Buscas posibles oportunidades de compra, venta, toma de ganancias, acumulación, ruptura, rebote, reversión y continuación de tendencia. Generas candidatos con zonas de entrada, invalidación, objetivos y horizonte temporal. No generas órdenes directas. Cada oportunidad debe incluir condiciones de invalidación."""

_CONTRARIAN_PROMPT = """Eres el AGENTE CONTRARIANO. Tu trabajo es intentar demostrar que la señal es incorrecta. Si el Opportunity Detector dice comprar, buscas: divergencias negativas, mala liquidez, noticias no consideradas, señales de distribución, debilidad macro, correlaciones peligrosas, manipulación de mercado. Evitas que todos los agentes se confirmen mutuamente sin cuestionarse."""

_CONSENSUS_PROMPT = """Eres el AGENTE DE CONSENSO. Recibes los resultados de todos los agentes (Technical, News, Sentiment, On-chain, Macro, Crash, Opportunity, Contrarian). Decides: comprar, vender, mantener, tomar ganancias, evitar, esperar confirmación, o sin acción. Calculas confianza (0-1), acuerdo entre agentes, razones principales, riesgos principales, y escenarios probabilísticos (alcista, base, bajista con rangos). No inventas datos que no estén en los inputs.

Tu output debe incluir OBLIGATORIAMENTE:
- riskLevel: LOW, MEDIUM o HIGH
- agentVotes: voto de cada agente (technical, news, sentiment, onchain, macro, crash, opportunity, contrarian)
- validFrom y expiresAt: ventana de validez ISO 8601
- entryZone: {min, max} — zona de entrada sugerida como strings
- invalidation: {type: PRICE_BELOW|PRICE_ABOVE|TIME_EXPIRED|EVENT_TRIGGERED, value}
- targets: [{price, probability}] — objetivos de precio con probabilidad
- requiresConfirmation: true si requiere confirmación humana para ejecutar

Ejemplo de output:
{
  "asset": "BTCUSDT",
  "decision": "BUY_ON_PULLBACK",
  "confidence": 0.78,
  "riskLevel": "MEDIUM",
  "validFrom": "2026-07-27T15:00:00Z",
  "expiresAt": "2026-07-27T19:00:00Z",
  "entryZone": {"min": "102400", "max": "103800"},
  "invalidation": {"type": "PRICE_BELOW", "value": "100900"},
  "targets": [{"price": "106500", "probability": 0.57}, {"price": "109200", "probability": 0.31}],
  "agentVotes": {"technical": "BUY", "news": "NEUTRAL", "sentiment": "BUY", "onchain": "BUY", "macro": "NEUTRAL", "crash": "LOW_RISK", "opportunity": "BUY", "contrarian": "CAUTION"},
  "mainReasons": [],
  "mainRisks": [],
  "requiresConfirmation": true
}"""


# --- JSON Schemas ---

_TECHNICAL_SCHEMA = {
    "type": "object",
    "required": ["asset", "technicalBias", "confidence"],
    "properties": {
        "asset": {"type": "string"},
        "timeframes": {"type": "object"},
        "trendStrength": {"type": "number", "minimum": 0, "maximum": 1},
        "volatility": {"type": "string", "enum": ["low", "medium", "high"]},
        "supportZones": {"type": "array", "items": {"type": "number"}},
        "resistanceZones": {"type": "array", "items": {"type": "number"}},
        "technicalBias": {"type": "string", "enum": ["BUY", "SELL", "BUY_ON_PULLBACK", "SELL_ON_RALLY", "NEUTRAL", "AVOID"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}

_NEWS_SCHEMA = {
    "type": "object",
    "required": ["headline", "affectedAssets", "impact", "confidence"],
    "properties": {
        "headline": {"type": "string"},
        "affectedAssets": {"type": "array", "items": {"type": "string"}},
        "impact": {"type": "string", "enum": ["positive", "negative", "neutral"]},
        "severity": {"type": "string", "enum": ["low", "medium", "high"]},
        "timeHorizon": {"type": "string", "enum": ["immediate", "short_term", "medium_term", "long_term"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "isRumor": {"type": "boolean"},
        "pricedIn": {"type": "boolean"},
    },
}

_SENTIMENT_SCHEMA = {
    "type": "object",
    "required": ["asset", "sentimentScore", "confidence"],
    "properties": {
        "asset": {"type": "string"},
        "sentimentScore": {"type": "number", "minimum": -1, "maximum": 1},
        "narrative": {"type": "string"},
        "euphoria": {"type": "boolean"},
        "fear": {"type": "boolean"},
        "coordinated": {"type": "boolean"},
        "riskFlags": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}

_ONCHAIN_SCHEMA = {
    "type": "object",
    "required": ["asset", "onchainBias", "confidence"],
    "properties": {
        "asset": {"type": "string"},
        "exchangeFlows": {"type": "object"},
        "whaleMovements": {"type": "array", "items": {"type": "object"}},
        "onchainBias": {"type": "string", "enum": ["BULLISH", "BEARISH", "NEUTRAL", "MIXED"]},
        "observations": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}

_MACRO_SCHEMA = {
    "type": "object",
    "required": ["macroRegime", "cryptoImpact"],
    "properties": {
        "macroRegime": {"type": "string", "enum": ["risk_on", "risk_off", "neutral"]},
        "cryptoImpact": {"type": "string", "enum": ["positive", "negative", "neutral"]},
        "equityImpact": {"type": "string", "enum": ["positive", "negative", "neutral"]},
        "usdImpact": {"type": "string", "enum": ["positive", "negative", "neutral"]},
        "durationEstimate": {"type": "string", "enum": ["hours", "days_to_weeks", "weeks_to_months"]},
        "keyEvents": {"type": "array", "items": {"type": "string"}},
    },
}

_CRASH_SCHEMA = {
    "type": "object",
    "required": ["asset", "crashRisk", "riskLevel"],
    "properties": {
        "asset": {"type": "string"},
        "crashRisk": {"type": "number", "minimum": 0, "maximum": 1},
        "riskLevel": {"type": "string", "enum": ["low", "medium", "high"]},
        "horizon": {"type": "string"},
        "reasons": {"type": "array", "items": {"type": "string"}},
    },
}

_OPPORTUNITY_SCHEMA = {
    "type": "object",
    "required": ["asset", "suggestion", "confidence"],
    "properties": {
        "asset": {"type": "string"},
        "suggestion": {"type": "string", "enum": ["BUY", "SELL", "TAKE_PROFIT", "ACCUMULATE", "BREAKOUT", "BOUNCE", "REVERSAL", "CONTINUE_TREND"]},
        "entryZone": {"type": "array", "items": {"type": "number"}},
        "invalidatedBelow": {"type": "number"},
        "invalidatedAbove": {"type": "number"},
        "targets": {"type": "array", "items": {"type": "number"}},
        "timeHorizon": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}

_CONTRARIAN_SCHEMA = {
    "type": "object",
    "required": ["targetSignal", "counterArguments", "recommendation"],
    "properties": {
        "targetSignal": {"type": "string"},
        "counterArguments": {"type": "array", "items": {"type": "string"}},
        "divergence": {"type": "boolean"},
        "manipulationRisk": {"type": "boolean"},
        "recommendation": {"type": "string", "enum": ["PROCEED", "PROCEED_WITH_CAUTION", "WAIT", "ABORT"]},
    },
}

_CONSENSUS_SCHEMA = {
    "type": "object",
    "required": ["asset", "decision", "confidence", "riskLevel", "agentVotes"],
    "properties": {
        "asset": {"type": "string"},
        "decision": {"type": "string", "enum": ["BUY", "SELL", "BUY_ON_PULLBACK", "SELL_ON_RALLY", "HOLD", "TAKE_PROFIT", "AVOID", "WAIT_CONFIRMATION", "NO_ACTION"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "riskLevel": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
        "validFrom": {"type": "string"},
        "expiresAt": {"type": "string"},
        "entryZone": {
            "type": "object",
            "properties": {
                "min": {"type": "string"},
                "max": {"type": "string"},
            },
        },
        "invalidation": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["PRICE_BELOW", "PRICE_ABOVE", "TIME_EXPIRED", "EVENT_TRIGGERED"]},
                "value": {"type": "string"},
            },
        },
        "targets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "price": {"type": "string"},
                    "probability": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        },
        "agentVotes": {
            "type": "object",
            "properties": {
                "technical": {"type": "string"},
                "news": {"type": "string"},
                "sentiment": {"type": "string"},
                "onchain": {"type": "string"},
                "macro": {"type": "string"},
                "crash": {"type": "string"},
                "opportunity": {"type": "string"},
                "contrarian": {"type": "string"},
            },
        },
        "agreement": {
            "type": "object",
            "properties": {
                "positive": {"type": "integer"},
                "neutral": {"type": "integer"},
                "negative": {"type": "integer"},
            },
        },
        "mainReasons": {"type": "array", "items": {"type": "string"}},
        "mainRisks": {"type": "array", "items": {"type": "string"}},
        "scenarios": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "probability": {"type": "number", "minimum": 0, "maximum": 1},
                    "range": {"type": "array", "items": {"type": "number"}},
                },
            },
        },
        "requiresConfirmation": {"type": "boolean"},
    },
}


# --- Registro de agentes ---

INTELLIGENCE_AGENTS: dict[str, IntelligenceAgentConfig] = {
    "technical_analyst": IntelligenceAgentConfig(
        id="technical_analyst", name="Technical Market Analyst",
        role="Interpreta indicadores técnicos por timeframe",
        system_prompt=_TECHNICAL_PROMPT, output_schema=_TECHNICAL_SCHEMA,
        max_tokens=600, interval_minutes=15,
    ),
    "news_analyst": IntelligenceAgentConfig(
        id="news_analyst", name="News Analyst",
        role="Evalúa impacto de noticias",
        system_prompt=_NEWS_PROMPT, output_schema=_NEWS_SCHEMA,
        max_tokens=500, interval_minutes=30, is_optional=True,
    ),
    "sentiment_analyst": IntelligenceAgentConfig(
        id="sentiment_analyst", name="Sentiment Analyst",
        role="Analiza sentimiento de redes sociales",
        system_prompt=_SENTIMENT_PROMPT, output_schema=_SENTIMENT_SCHEMA,
        max_tokens=500, interval_minutes=30, is_optional=True,
    ),
    "onchain_analyst": IntelligenceAgentConfig(
        id="onchain_analyst", name="On-chain Analyst",
        role="Interpreta métricas blockchain",
        system_prompt=_ONCHAIN_PROMPT, output_schema=_ONCHAIN_SCHEMA,
        max_tokens=500, interval_minutes=60, is_optional=True,
    ),
    "macro_analyst": IntelligenceAgentConfig(
        id="macro_analyst", name="Macro Analyst",
        role="Analiza entorno macroeconómico",
        system_prompt=_MACRO_PROMPT, output_schema=_MACRO_SCHEMA,
        max_tokens=500, interval_minutes=60, is_optional=True,
    ),
    "crash_detector": IntelligenceAgentConfig(
        id="crash_detector", name="Crash Risk Detector",
        role="Detecta riesgo de caída con reglas numéricas",
        system_prompt=_CRASH_PROMPT, output_schema=_CRASH_SCHEMA,
        max_tokens=400, interval_minutes=5,
    ),
    "opportunity_detector": IntelligenceAgentConfig(
        id="opportunity_detector", name="Opportunity Detector",
        role="Busca oportunidades de trading",
        system_prompt=_OPPORTUNITY_PROMPT, output_schema=_OPPORTUNITY_SCHEMA,
        max_tokens=500, interval_minutes=15,
    ),
    "contrarian_agent": IntelligenceAgentConfig(
        id="contrarian_agent", name="Contrarian Agent",
        role="Intenta refutar señales de otros agentes",
        system_prompt=_CONTRARIAN_PROMPT, output_schema=_CONTRARIAN_SCHEMA,
        max_tokens=400, interval_minutes=15,
    ),
    "consensus_agent": IntelligenceAgentConfig(
        id="consensus_agent", name="Consensus Agent",
        role="Integra todos los agentes en una decisión final",
        system_prompt=_CONSENSUS_PROMPT, output_schema=_CONSENSUS_SCHEMA,
        max_tokens=800, interval_minutes=15,
    ),
}


# Agentes que se ejecutan antes del Consensus (en orden)
PRE_CONSENSUS_AGENTS = [
    "technical_analyst",
    "news_analyst",
    "sentiment_analyst",
    "onchain_analyst",
    "macro_analyst",
    "crash_detector",
    "opportunity_detector",
    "contrarian_agent",
]


def get_intelligence_agent(agent_id: str) -> IntelligenceAgentConfig | None:
    return INTELLIGENCE_AGENTS.get(agent_id)


def list_intelligence_agents() -> list[dict]:
    return [
        {
            "id": a.id, "name": a.name, "role": a.role,
            "interval_minutes": a.interval_minutes,
            "is_optional": a.is_optional,
        }
        for a in INTELLIGENCE_AGENTS.values()
    ]


def get_core_intelligence_agents() -> dict[str, IntelligenceAgentConfig]:
    """Returns only the core agents (not optional)."""
    return {k: v for k, v in INTELLIGENCE_AGENTS.items() if not v.is_optional}


def get_optional_intelligence_agents() -> dict[str, IntelligenceAgentConfig]:
    """Returns only the optional agents."""
    return {k: v for k, v in INTELLIGENCE_AGENTS.items() if v.is_optional}
