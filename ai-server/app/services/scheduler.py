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
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.models import MarketAlert, MarketReport, MarketScenario, MarketSignal
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
    EventType.SUPPORT_BREAK: ["technical_analyst", "crash_detector", "liquidity_analyst", "regime_analyst", "consensus_agent"],
    EventType.RESISTANCE_BREAK: ["technical_analyst", "opportunity_detector", "liquidity_analyst", "regime_analyst", "consensus_agent"],
    EventType.NEWS_CRITICAL: ["news_analyst", "macro_analyst", "sentiment_analyst", "consensus_agent"],
    EventType.WHALE_MOVEMENT: ["onchain_analyst", "crash_detector", "correlation_analyst", "consensus_agent"],
    EventType.SENTIMENT_SHIFT: ["sentiment_analyst", "consensus_agent"],
    EventType.VOLATILITY_SPIKE: ["technical_analyst", "crash_detector", "regime_analyst", "consensus_agent"],
    EventType.VOLUME_SPIKE: ["technical_analyst", "opportunity_detector", "liquidity_analyst", "consensus_agent"],
    EventType.OPPORTUNITY_DETECTED: ["opportunity_detector", "liquidity_analyst", "contrarian_agent", "consensus_agent"],
    EventType.CRASH_RISK_ELEVATED: ["crash_detector", "contrarian_agent", "regime_analyst", "consensus_agent"],
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
        self._last_agent_results: dict[str, dict[str, dict | None]] = {}  # {symbol: {agent_id: result}}
        self._last_consensus: dict[str, dict | None] = {}  # {symbol: last consensus result}
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

    def process_event(
        self,
        event: SchedulerEvent,
        session: Session | None = None,
    ) -> list[AgentExecutionResult]:
        """Procesa un evento ejecutando los agentes relevantes.

        Este método es síncrono y puede llamarse directamente (sin el loop)
        para procesar eventos manuales o de test.

        Args:
            event: Evento a procesar.
            session: SQLAlchemy session opcional para persistir resultados.
                Si es None, no se persiste en BD.

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

            # Small delay between agents to avoid rate limiting
            time.sleep(2)

            # Persistir alerta si crash_detector tiene riesgo elevado
            if (
                session is not None
                and agent_id == "crash_detector"
                and result.success
                and result.result
                and result.result.get("riskLevel") in ("medium", "high")
            ):
                self._persist_alert(session, result.result)

        # Guardar resultados de agentes para comparación futura
        symbol = event.asset
        prev_results = self._last_agent_results.get(symbol, {})
        # Merge: actualizar solo los agentes que se ejecutaron
        merged_results = {**prev_results, **agent_results}
        self._last_agent_results[symbol] = merged_results

        # Ejecutar consensus solo si hay cambio material o evento explícito
        if needs_consensus:
            force_consensus = event.event_type in (
                EventType.SCHEDULED,
                EventType.MANUAL,
                EventType.NEWS_CRITICAL,
                EventType.SUPPORT_BREAK,
                EventType.RESISTANCE_BREAK,
            )

            if force_consensus or self._has_material_change(symbol, merged_results):
                logger.info(
                    "Consensus triggered for %s (force=%s, material_change=%s)",
                    symbol, force_consensus,
                    not force_consensus,
                )
                consensus_result = self._execute_consensus(merged_results, event)
                results.append(consensus_result)
                self._last_run["consensus_agent"] = time.time()

                # Persistir señal si consensus fue exitoso
                if (
                    session is not None
                    and consensus_result.success
                    and consensus_result.result
                ):
                    self._persist_signal(
                        session,
                        consensus_result.result,
                        merged_results,
                    )
                    # Persistir escenarios del consensus
                    self._persist_scenario(session, consensus_result.result, event)
                    # Persistir reporte periódico
                    self._persist_report(session, consensus_result.result, merged_results, event)
                    self._last_consensus[symbol] = consensus_result.result
            else:
                logger.info("Consensus skipped for %s — no material change", symbol)
                results.append(AgentExecutionResult(
                    agent_id="consensus_agent", success=False,
                    error="Skipped — no material change",
                ))

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
        from app.database.session import SessionLocal

        logger.info("Scheduler loop started")
        while not self._stop_event.is_set():
            session = None
            try:
                session = SessionLocal()
                for symbol in self.symbols:
                    events = self.detect_events(symbol)
                    for event in events:
                        self.process_event(event, session=session)

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
                            ), session=session)

                # Expire stale signals and notifications each cycle
                self._expire_stale(session)

            except Exception as exc:  # noqa: BLE001
                logger.error("Scheduler loop error: %s", exc)
                if session:
                    session.rollback()
            finally:
                if session:
                    session.close()

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

        # Include schema in user message so LLM knows required fields
        schema_hint = json.dumps(agent.output_schema, default=str)
        user_msg = json.dumps(agent_input, default=str) + f"\n\nYour output must match this JSON schema (return ONLY valid JSON):\n{schema_hint}"

        content, tokens = _call_llm(
            model_config,
            agent.system_prompt,
            user_msg,
            agent_config=agent,
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

    def _persist_signal(
        self,
        session: Session,
        consensus_result: dict[str, Any],
        agent_results: dict[str, dict | None],
    ) -> MarketSignal | None:
        """Persiste el resultado del Consensus Agent como MarketSignal en BD."""
        try:
            asset = consensus_result.get("asset", "")
            decision = consensus_result.get("decision", "NO_ACTION")
            confidence = consensus_result.get("confidence", 0.0)
            agreement = consensus_result.get("agreement", {})
            reasons = consensus_result.get("mainReasons", consensus_result.get("main_reasons", []))
            risks = consensus_result.get("mainRisks", consensus_result.get("main_risks", []))

            # Mapear decision a signal_type
            signal_type = decision if decision in ("BUY", "SELL", "HOLD", "TAKE_PROFIT", "AVOID") else "HOLD"

            # Marcar señales anteriores del mismo asset como SUPERSEDED
            old_signals = session.execute(
                select(MarketSignal)
                .where(MarketSignal.asset == asset, MarketSignal.status == "ACTIVE")
            ).scalars().all()
            for old in old_signals:
                old.status = "SUPERSEDED"

            signal = MarketSignal(
                asset=asset,
                signal_type=signal_type,
                decision=decision,
                confidence=confidence,
                agreement_positive=agreement.get("positive", 0) if isinstance(agreement, dict) else 0,
                agreement_neutral=agreement.get("neutral", 0) if isinstance(agreement, dict) else 0,
                agreement_negative=agreement.get("negative", 0) if isinstance(agreement, dict) else 0,
                main_reasons=reasons,
                main_risks=risks,
                consensus_data=consensus_result,
                status="ACTIVE",
                expires_at=datetime.now(UTC) + timedelta(hours=24),
            )
            session.add(signal)
            session.commit()
            session.refresh(signal)
            logger.info("Persisted signal %d for %s — decision=%s", signal.id, asset, decision)

            # Generate pending notifications for subscribed users
            self._generate_notifications_for_signal(session, signal)

            return signal
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to persist signal: %s", exc)
            session.rollback()
            return None

    def _persist_scenario(
        self,
        session: Session,
        consensus_result: dict[str, Any],
        event: SchedulerEvent,
    ) -> MarketScenario | None:
        """Persiste los escenarios probabilísticos del Consensus en BD."""
        try:
            asset = consensus_result.get("asset", event.asset)
            scenarios = consensus_result.get("scenarios", [])
            if not scenarios:
                return None

            current_price = event.data.get("price", 0)
            invalidation = consensus_result.get("invalidation", {})

            scenario = MarketScenario(
                asset=asset,
                horizon="1d",
                current_price=current_price,
                scenarios=scenarios,
                invalidation_conditions=[invalidation] if invalidation else [],
                expires_at=datetime.now(UTC) + timedelta(hours=24),
            )
            session.add(scenario)
            session.commit()
            session.refresh(scenario)
            logger.info("Persisted scenario %d for %s — %d scenarios", scenario.id, asset, len(scenarios))
            return scenario
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to persist scenario: %s", exc)
            session.rollback()
            return None

    def _persist_report(
        self,
        session: Session,
        consensus_result: dict[str, Any],
        agent_results: dict[str, dict | None],
        event: SchedulerEvent,
    ) -> MarketReport | None:
        """Persiste un reporte periódico con el consensus + resultados de agentes."""
        try:
            asset = consensus_result.get("asset", event.asset)
            now = datetime.now(UTC)

            # Determinar tipo de reporte y período
            if now.hour < 1:
                report_type = "daily"
                period = now.strftime("%Y-%m-%d")
            else:
                report_type = "event"
                period = now.strftime("%Y-%m-%d %H:00")

            report = MarketReport(
                asset=asset,
                report_type=report_type,
                content={
                    "consensus": consensus_result,
                    "agent_results": {
                        k: v for k, v in agent_results.items() if v is not None
                    },
                    "event_type": event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
                    "price": event.data.get("price", 0),
                },
                period=period,
            )
            session.add(report)
            session.commit()
            session.refresh(report)
            logger.info("Persisted report %d for %s — type=%s", report.id, asset, report_type)
            return report
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to persist report: %s", exc)
            session.rollback()
            return None

    def _persist_alert(
        self,
        session: Session,
        crash_result: dict[str, Any],
    ) -> MarketAlert | None:
        """Persiste el resultado del Crash Detector como MarketAlert en BD."""
        try:
            asset = crash_result.get("asset", "")
            risk_level = crash_result.get("riskLevel", "medium")
            crash_risk = crash_result.get("crashRisk", 0.5)
            reasons = crash_result.get("reasons", [])

            alert = MarketAlert(
                asset=asset,
                alert_type="crash_risk",
                severity=risk_level,
                message="; ".join(reasons[:3]) if reasons else f"Crash risk elevated ({crash_risk:.0%})",
                details=crash_result,
                status="ACTIVE",
                expires_at=datetime.now(UTC) + timedelta(hours=12),
            )
            session.add(alert)
            session.commit()
            session.refresh(alert)
            logger.info("Persisted alert %d for %s — severity=%s", alert.id, asset, risk_level)
            return alert
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to persist alert: %s", exc)
            session.rollback()
            return None

    def _generate_notifications_for_signal(
        self,
        session: Session,
        signal: MarketSignal,
    ) -> None:
        """Genera PendingNotifications for a new signal for all subscribed users.

        In the current architecture, the ai-server doesn't store user portfolios.
        Instead, it creates a generic 'signal' notification that the trading-client
        will personalize via /portfolio-match when the user polls /pending.

        Future: if user subscriptions are stored server-side, this method
        will iterate over subscribed users and create personalized notifications.
        """
        try:
            from app.database.models import PendingNotification

            # Create a generic signal notification for the "broadcast" user
            # Trading-client users will see this and personalize via portfolio-match
            notif = PendingNotification(
                user_id_hash="broadcast",
                notification_type="signal",
                asset=signal.asset,
                content={
                    "signal_id": signal.id,
                    "decision": signal.decision,
                    "confidence": signal.confidence,
                    "main_reasons": signal.main_reasons,
                    "main_risks": signal.main_risks,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                status="PENDING",
                expires_at=signal.expires_at,
            )
            session.add(notif)
            session.commit()
            logger.info(
                "Generated pending notification for signal %d (%s)",
                signal.id, signal.asset,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to generate notifications: %s", exc)
            session.rollback()

    def _expire_stale(self, session: Session) -> None:
        """#5: Mark expired signals and notifications as EXPIRED.

        Called every scheduler cycle to clean up stale data.
        """
        try:
            now = datetime.now(UTC)

            # Expire stale signals
            stale_signals = session.execute(
                select(MarketSignal)
                .where(MarketSignal.status == "ACTIVE")
                .where(MarketSignal.expires_at < now)
            ).scalars().all()
            for sig in stale_signals:
                sig.status = "EXPIRED"
            if stale_signals:
                logger.info("Expired %d stale signals", len(stale_signals))

            # Expire stale alerts
            stale_alerts = session.execute(
                select(MarketAlert)
                .where(MarketAlert.status == "ACTIVE")
                .where(MarketAlert.expires_at < now)
            ).scalars().all()
            for alert in stale_alerts:
                alert.status = "EXPIRED"
            if stale_alerts:
                logger.info("Expired %d stale alerts", len(stale_alerts))

            # Expire stale pending notifications
            from app.database.models import PendingNotification
            stale_notifs = session.execute(
                select(PendingNotification)
                .where(PendingNotification.status == "PENDING")
                .where(PendingNotification.expires_at < now)
            ).scalars().all()
            for notif in stale_notifs:
                notif.status = "EXPIRED"
            if stale_notifs:
                logger.info("Expired %d stale notifications", len(stale_notifs))

            if stale_signals or stale_alerts or stale_notifs:
                session.commit()
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to expire stale items: %s", exc)
            session.rollback()

    def _has_material_change(
        self,
        symbol: str,
        agent_results: dict[str, dict | None],
    ) -> bool:
        """Detecta si hubo un cambio material que justifique ejecutar Consensus.

        Consensus se ejecuta cuando:
        - Un agente cambió su bias/decision (BUY→SELL, NEUTRAL→BUY, etc.)
        - Crash risk aumentó significativamente (>15% delta)
        - No hay resultados previos (primer run)
        - No hay consensus previo para este símbolo
        """
        if symbol not in self._last_consensus:
            return True

        prev = self._last_agent_results.get(symbol, {})
        if not prev:
            return True

        # Campos clave a comparar por agente
        bias_fields = {
            "technical_analyst": "technicalBias",
            "onchain_analyst": "onchainBias",
            "opportunity_detector": "suggestion",
            "sentiment_analyst": "sentimentScore",
            "contrarian_agent": "recommendation",
            "news_analyst": "impact",
            "macro_analyst": "cryptoImpact",
            "liquidity_analyst": "liquidityRating",
            "correlation_analyst": "marketDriver",
            "regime_analyst": "regime",
        }

        for agent_id, result in agent_results.items():
            old_result = prev.get(agent_id)
            if old_result is None and result is not None:
                return True
            if old_result is not None and result is None:
                return True
            if old_result is None or result is None:
                continue

            field = bias_fields.get(agent_id)
            if field:
                old_val = old_result.get(field)
                new_val = result.get(field)
                if old_val != new_val:
                    return True

            # Crash detector: delta significativo
            if agent_id == "crash_detector":
                old_risk = old_result.get("crashRisk", 0)
                new_risk = result.get("crashRisk", 0)
                if abs(new_risk - old_risk) > 0.15:
                    return True
                old_level = old_result.get("riskLevel", "low")
                new_level = result.get("riskLevel", "low")
                if old_level != new_level:
                    return True

        return False

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
        if agent_id in ("technical_analyst", "crash_detector", "opportunity_detector", "liquidity_analyst", "regime_analyst"):
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

        # Añadir anomalías para crash detector y regime analyst
        if agent_id in ("crash_detector", "regime_analyst"):
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
