"""Event-Driven Scheduler — orquesta el pipeline 24/7 de inteligencia de mercado.

El scheduler NO ejecuta todos los agentes en cada ciclo. Usa triggers:
- No cambió nada material → No llamar IA
- Se rompió soporte → Technical + Crash + Consensus
- Noticia crítica → News + Macro + Consensus
- Movimiento de ballena → On-chain + Crash + Consensus
- Sentiment shift → Sentiment + Consensus
- Opportunity detected → Opportunity + Contrarian + Consensus

Con SCHEDULER_ENABLED=False, el sistema funciona como antes (request-response).
Con SCHEDULER_ENABLED=True, el scheduler corre 24/7 en background.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from app.config import get_settings
from app.services.consensus import (
    compute_agreement,
    generate_default_scenarios,
    run_consensus,
)
from app.services.intelligence_agents import (
    INTELLIGENCE_AGENTS,
    PRE_CONSENSUS_AGENTS,
)
from app.services.level_router import get_model_for_plan
from app.services.market_data import MarketDataEngine, get_market_data_engine
from app.services.validator import validate_agent_response

logger = logging.getLogger(__name__)
settings = get_settings()


class EventType(Enum):
    """Tipos de eventos que disparan ejecución de agentes."""

    SUPPORT_BREAK = "support_break"
    RESISTANCE_BREAK = "resistance_break"
    NEWS_CRITICAL = "news_critical"
    WHALE_MOVEMENT = "whale_movement"
    SENTIMENT_SHIFT = "sentiment_shift"
    VOLATILITY_SPIKE = "volatility_spike"
    VOLUME_SPIKE = "volume_spike"
    OPPORTUNITY_DETECTED = "opportunity_detected"
    CRASH_RISK_ELEVATED = "crash_risk_elevated"
    SCHEDULED = "scheduled"
    MANUAL = "manual"


# Qué agentes ejecutar por tipo de evento
EVENT_AGENT_MAP: dict[EventType, list[str]] = {
    EventType.SUPPORT_BREAK: ["technical_analyst", "crash_detector", "consensus_agent"],
    EventType.RESISTANCE_BREAK: ["technical_analyst", "opportunity_detector", "consensus_agent"],
    EventType.NEWS_CRITICAL: ["news_analyst", "macro_analyst", "consensus_agent"],
    EventType.WHALE_MOVEMENT: ["onchain_analyst", "crash_detector", "consensus_agent"],
    EventType.SENTIMENT_SHIFT: ["sentiment_analyst", "consensus_agent"],
    EventType.VOLATILITY_SPIKE: ["technical_analyst", "crash_detector", "consensus_agent"],
    EventType.VOLUME_SPIKE: ["technical_analyst", "opportunity_detector", "consensus_agent"],
    EventType.OPPORTUNITY_DETECTED: ["opportunity_detector", "contrarian_agent", "consensus_agent"],
    EventType.CRASH_RISK_ELEVATED: ["crash_detector", "contrarian_agent", "consensus_agent"],
    EventType.SCHEDULED: PRE_CONSENSUS_AGENTS + ["consensus_agent"],
    EventType.MANUAL: PRE_CONSENSUS_AGENTS + ["consensus_agent"],
}


@dataclass
class SchedulerEvent:
    """Evento que dispara la ejecución de agentes."""

    event_type: EventType
    asset: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class AgentExecutionResult:
    """Resultado de la ejecución de un agente."""

    agent_id: str
    success: bool
    result: dict | None = None
    tokens_used: int = 0
    error: str = ""
    duration_seconds: float = 0.0


class EventScheduler:
    """Scheduler event-driven para el pipeline de inteligencia de mercado.

    Con SCHEDULER_ENABLED=False, no hace nada (modo legacy).
    Con SCHEDULER_ENABLED=True, corre un loop en background que:
    1. Polls Market Data Engine en intervalos configurables
    2. Detecta eventos (cambio material, anomalía, noticia nueva)
    3. Dispara agentes relevantes según el evento
    4. Consensus Agent corre cuando hay nuevos inputs
    5. Guarda resultados en Market Knowledge Base
    6. Portfolio Matcher + Notification Generator generan notificaciones
    """

    def __init__(
        self,
        market_data_engine: MarketDataEngine | None = None,
        symbols: list[str] | None = None,
    ) -> None:
        self.market_data = market_data_engine or get_market_data_engine()
        self.symbols = symbols or ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_run: dict[str, float] = {}  # {agent_id: timestamp}
        self._last_indicators: dict[str, dict] = {}  # {symbol: indicator_summary}
        self._stop_event = threading.Event()

    def start(self) -> bool:
        """Inicia el scheduler en background."""
        if not settings.SCHEDULER_ENABLED:
            logger.info("Scheduler disabled (SCHEDULER_ENABLED=False)")
            return False
        if self._running:
            logger.warning("Scheduler already running")
            return False
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._running = True
        logger.info("Scheduler started — monitoring %d symbols", len(self.symbols))
        return True

    def stop(self) -> bool:
        """Detiene el scheduler."""
        if not self._running:
            return False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        self._running = False
        logger.info("Scheduler stopped")
        return True

    @property
    def is_running(self) -> bool:
        return self._running

    def status(self) -> dict[str, Any]:
        """Retorna el estado actual del scheduler."""
        return {
            "running": self._running,
            "symbols": self.symbols,
            "last_run": {
                k: datetime.fromtimestamp(v, tz=UTC).isoformat()
                for k, v in self._last_run.items()
            },
            "interval_seconds": settings.SCHEDULER_INTERVAL_SECONDS,
        }

    def process_event(self, event: SchedulerEvent) -> list[AgentExecutionResult]:
        """Procesa un evento ejecutando los agentes relevantes.

        Este método es síncrono y puede llamarse directamente (sin el loop)
        para procesar eventos manuales o de test.

        Args:
            event: Evento a procesar.

        Returns:
            Lista de resultados de ejecución por agente.
        """
        agent_ids = EVENT_AGENT_MAP.get(event.event_type, [])
        logger.info(
            "Processing event %s for %s — agents: %s",
            event.event_type.value, event.asset, agent_ids,
        )

        results: list[AgentExecutionResult] = []
        agent_results: dict[str, dict | None] = {}

        # Separar pre-consensus agents del consensus agent
        pre_consensus = [a for a in agent_ids if a != "consensus_agent"]
        needs_consensus = "consensus_agent" in agent_ids

        # Ejecutar pre-consensus agents
        for agent_id in pre_consensus:
            result = self._execute_agent(agent_id, event)
            results.append(result)
            agent_results[agent_id] = result.result
            self._last_run[agent_id] = time.time()

        # Ejecutar consensus si es necesario
        if needs_consensus:
            consensus_result = self._execute_consensus(agent_results, event)
            results.append(consensus_result)
            self._last_run["consensus_agent"] = time.time()

        return results

    def detect_events(self, symbol: str) -> list[SchedulerEvent]:
        """Detecta eventos para un símbolo comparando indicadores actuales vs anteriores.

        Args:
            symbol: Símbolo a analizar.

        Returns:
            Lista de eventos detectados.
        """
        events: list[SchedulerEvent] = []

        # Obtener indicadores actuales
        indicators = self.market_data.compute_indicators(symbol)
        anomalies = self.market_data.detect_anomalies(symbol, indicators=indicators)

        # Comparar con indicadores anteriores
        prev = self._last_indicators.get(symbol, {})
        self._last_indicators[symbol] = {
            "trend": indicators.trend,
            "rsi": indicators.rsi,
            "volatility": indicators.volatility,
            "volume_relative": indicators.volume_relative,
            "support_levels": indicators.support_levels,
            "resistance_levels": indicators.resistance_levels,
        }

        # Detectar soporte roto
        if prev and prev.get("support_levels"):
            current_price = indicators.ema_20 or 0
            if current_price and current_price < prev["support_levels"][0]:
                events.append(SchedulerEvent(
                    event_type=EventType.SUPPORT_BREAK,
                    asset=symbol,
                    data={"price": current_price, "broken_level": prev["support_levels"][0]},
                ))

        # Detectar resistencia rota
        if prev and prev.get("resistance_levels"):
            current_price = indicators.ema_20 or 0
            if current_price and current_price > prev["resistance_levels"][0]:
                events.append(SchedulerEvent(
                    event_type=EventType.RESISTANCE_BREAK,
                    asset=symbol,
                    data={"price": current_price, "broken_level": prev["resistance_levels"][0]},
                ))

        # Detectar anomalías
        for anomaly in anomalies:
            if anomaly.anomaly_type == "volatility_spike":
                events.append(SchedulerEvent(
                    event_type=EventType.VOLATILITY_SPIKE,
                    asset=symbol,
                    data={"value": anomaly.value, "severity": anomaly.severity},
                ))
            elif anomaly.anomaly_type == "volume_spike":
                events.append(SchedulerEvent(
                    event_type=EventType.VOLUME_SPIKE,
                    asset=symbol,
                    data={"value": anomaly.value, "severity": anomaly.severity},
                ))

        # Detectar RSI extreme → potential opportunity
        if indicators.rsi is not None:
            if indicators.rsi < 30:
                events.append(SchedulerEvent(
                    event_type=EventType.OPPORTUNITY_DETECTED,
                    asset=symbol,
                    data={"rsi": indicators.rsi, "type": "oversold"},
                ))
            elif indicators.rsi > 70 and prev and prev.get("rsi", 0) <= 70:
                events.append(SchedulerEvent(
                    event_type=EventType.CRASH_RISK_ELEVATED,
                    asset=symbol,
                    data={"rsi": indicators.rsi, "type": "overbought"},
                ))

        return events

    def should_run_agent(self, agent_id: str) -> bool:
        """Verifica si un agente debe ejecutarse según su intervalo."""
        agent = INTELLIGENCE_AGENTS.get(agent_id)
        if agent is None:
            return False

        last = self._last_run.get(agent_id, 0)
        elapsed = time.time() - last
        return elapsed >= agent.interval_minutes * 60

    def _run_loop(self) -> None:
        """Loop principal del scheduler — corre en background."""
        logger.info("Scheduler loop started")
        while not self._stop_event.is_set():
            try:
                for symbol in self.symbols:
                    events = self.detect_events(symbol)
                    for event in events:
                        self.process_event(event)

                    # Scheduled run if no events and enough time passed
                    if not events:
                        scheduled_agents = [
                            a for a in PRE_CONSENSUS_AGENTS
                            if self.should_run_agent(a)
                        ]
                        if scheduled_agents:
                            self.process_event(SchedulerEvent(
                                event_type=EventType.SCHEDULED,
                                asset=symbol,
                            ))

            except Exception as exc:  # noqa: BLE001
                logger.error("Scheduler loop error: %s", exc)

            self._stop_event.wait(settings.SCHEDULER_INTERVAL_SECONDS)

        logger.info("Scheduler loop ended")

    def _execute_agent(
        self,
        agent_id: str,
        event: SchedulerEvent,
    ) -> AgentExecutionResult:
        """Ejecuta un agente individual con timeout y graceful degradation."""
        agent = INTELLIGENCE_AGENTS.get(agent_id)
        if agent is None:
            return AgentExecutionResult(
                agent_id=agent_id, success=False,
                error=f"Unknown agent: {agent_id}",
            )

        start = time.time()
        model_config = get_model_for_plan("pro")

        # Construir input para el agente
        agent_input = self._build_agent_input(agent_id, event)

        from app.services.consensus import _call_llm, _parse_json

        content, tokens = _call_llm(
            model_config,
            agent.system_prompt,
            json.dumps(agent_input, default=str),
        )

        parsed = _parse_json(content)
        duration = time.time() - start

        if parsed is None:
            return AgentExecutionResult(
                agent_id=agent_id, success=False,
                tokens_used=tokens, error="LLM returned unparseable response",
                duration_seconds=duration,
            )

        # Validar contra schema
        valid, error = validate_agent_response(agent_id, parsed)
        if not valid:
            logger.warning("Agent %s failed schema validation: %s", agent_id, error)
            return AgentExecutionResult(
                agent_id=agent_id, success=False,
                tokens_used=tokens, error=f"Schema validation: {error}",
                duration_seconds=duration,
            )

        return AgentExecutionResult(
            agent_id=agent_id, success=True,
            result=parsed, tokens_used=tokens,
            duration_seconds=duration,
        )

    def _execute_consensus(
        self,
        agent_results: dict[str, dict | None],
        event: SchedulerEvent,
    ) -> AgentExecutionResult:
        """Ejecuta el Consensus Agent con los resultados de los demás agentes."""
        start = time.time()

        # Filtrar resultados válidos
        valid_results = {k: v for k, v in agent_results.items() if v is not None}

        min_agents = settings.CONSENSUS_MIN_AGENTS
        if len(valid_results) < min_agents:
            logger.warning(
                "Consensus skipped for %s: only %d agents (min %d)",
                event.asset, len(valid_results), min_agents,
            )
            return AgentExecutionResult(
                agent_id="consensus_agent", success=False,
                error=f"Insufficient agents: {len(valid_results)} < {min_agents}",
                duration_seconds=time.time() - start,
            )

        result = run_consensus(
            agent_results=valid_results,
            asset=event.asset,
            plan="pro",
        )

        duration = time.time() - start

        if result is None:
            return AgentExecutionResult(
                agent_id="consensus_agent", success=False,
                error="Consensus returned None",
                duration_seconds=duration,
            )

        # Asegurar que tiene escenarios
        if not result.get("scenarios"):
            current_price = event.data.get("price", 0)
            result["scenarios"] = generate_default_scenarios(current_price)

        # Añadir agreement si no está
        if not result.get("agreement"):
            result["agreement"] = compute_agreement(valid_results)

        return AgentExecutionResult(
            agent_id="consensus_agent", success=True,
            result=result, duration_seconds=duration,
        )

    def _build_agent_input(
        self,
        agent_id: str,
        event: SchedulerEvent,
    ) -> dict[str, Any]:
        """Construye el input para un agente según su tipo y el evento."""
        base: dict[str, Any] = {
            "asset": event.asset,
            "event_type": event.event_type.value,
            "event_data": event.data,
        }

        # Añadir indicadores técnicos si están disponibles
        if agent_id in ("technical_analyst", "crash_detector", "opportunity_detector"):
            indicators = self.market_data.compute_indicators(event.asset)
            base["indicators"] = {
                "rsi": indicators.rsi,
                "macd": indicators.macd,
                "macd_signal": indicators.macd_signal,
                "ema_20": indicators.ema_20,
                "ema_50": indicators.ema_50,
                "ema_200": indicators.ema_200,
                "atr": indicators.atr,
                "volatility": indicators.volatility,
                "volume_relative": indicators.volume_relative,
                "trend": indicators.trend,
                "support_levels": indicators.support_levels,
                "resistance_levels": indicators.resistance_levels,
            }

        # Añadir anomalías para crash detector
        if agent_id == "crash_detector":
            anomalies = self.market_data.detect_anomalies(event.asset)
            base["anomalies"] = [
                {"type": a.anomaly_type, "severity": a.severity, "value": a.value}
                for a in anomalies
            ]

        # Añadir datos del evento específicos
        if event.event_type == EventType.NEWS_CRITICAL and agent_id == "news_analyst":
            base["news"] = event.data
        elif event.event_type == EventType.WHALE_MOVEMENT and agent_id == "onchain_analyst":
            base["onchain_data"] = event.data
        elif event.event_type == EventType.SENTIMENT_SHIFT and agent_id == "sentiment_analyst":
            base["sentiment_data"] = event.data

        return base


# Singleton
_scheduler: EventScheduler | None = None
_scheduler_lock = threading.Lock()


def get_scheduler() -> EventScheduler:
    global _scheduler
    with _scheduler_lock:
        if _scheduler is None:
            _scheduler = EventScheduler()
        return _scheduler
