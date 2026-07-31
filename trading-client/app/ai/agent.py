"""Agente de IA autónomo para trading.

Funciona automáticamente: lee señales, analiza mercado, ejecuta trades.
Soporta Groq (cloud, gratis) y Ollama (local).

Configuración (.env):
    AI_PROVIDER=groq          # 'groq' o 'ollama'
    GROQ_API_KEY=gsk_xxx      # Obtener en console.groq.com (gratis)
    OLLAMA_URL=http://localhost:11434
    OLLAMA_MODEL=qwen2.5:14b
    AI_INTERVAL_SECONDS=30    # Intervalo de análisis
    AI_AUTO_TRADE=true        # Ejecutar trades automáticamente
"""

import json
import logging
import time
from datetime import UTC, datetime
from decimal import Decimal
from threading import Event, Thread
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.ai.intelligence_provider import IntelligenceProvider, create_intelligence_provider
from app.ai.local_provider import LocalAIProvider
from app.ai.provider import AIProvider, AIProviderConfig, AIResponse
from app.ai.remote_provider import RemoteAIProvider
from app.risk.engine import RiskEngine

logger = logging.getLogger(__name__)

# ─── Single source of truth for profile → risk limits ─────────────────────────
PROFILE_RISK_LIMITS: dict[str, dict[str, Any]] = {
    "conservative": {"sl_range": (2.0, 3.0), "tp_range": (4.0, 8.0),  "min_confidence": 0.7, "max_positions": 3},
    "moderate":     {"sl_range": (3.0, 4.0), "tp_range": (6.0, 10.0), "min_confidence": 0.6, "max_positions": 5},
    "aggressive":   {"sl_range": (4.0, 5.0), "tp_range": (8.0, 15.0), "min_confidence": 0.5, "max_positions": 7},
}

# Models that benefit from few-shot examples in the prompt
LIGHTWEIGHT_MODELS: frozenset[str] = frozenset({
    "llama-3.1-8b-instant",
    "llama3.2:3b",
    "qwen2.5:7b",
    "qwen2.5:14b",
    "gemini-flash-lite-latest",
    "gpt-4o-mini",
})

# ─── Pydantic schemas for LLM output validation ───────────────────────────────

class TradeAction(BaseModel):
    type: Literal["buy"]
    symbol: str
    confidence: float = Field(ge=0, le=1)
    stop_loss_pct: float
    take_profit_pct: float
    reason: str = ""

class AgentDecision(BaseModel):
    market_overview: str = ""
    portfolio_status: str = ""
    analysis: str = ""
    actions: list[TradeAction] = []
    risk_assessment: str = ""
    next_steps: str = ""


class PositionSuggestion(BaseModel):
    symbol: str
    position_id: int = 0
    suggested_stop_loss: float | None = None
    suggested_take_profit: float | None = None
    time_horizon: str = ""
    confidence: float = Field(ge=0, le=1, default=0.5)
    reason: str = ""
    detailed_analysis: str = ""


class PositionAnalysisDecision(BaseModel):
    market_overview: str = ""
    analysis: str = ""
    suggestions: list[PositionSuggestion] = []
    risk_assessment: str = ""
    next_steps: str = ""


POSITION_ANALYSIS_PROMPT = """Eres un analista de trading experto de élite. El usuario tiene posiciones ABIERTAS y necesita un análisis PROFUNDO y EXHAUSTIVO para optimizarlas.

⚠️ MÁXIMA PRIORIDAD Y ESFUERZO: Esta es la tarea más importante del momento. Dedica tu MÁXIMA CAPACIDAD DE ANÁLISIS a cada posición. No te apresures. Analiza cada posición con el mismo rigor que un analista profesional aplicaría en un informe detallado.

Devuelves SOLO JSON con este schema exacto:
{"market_overview":"...","analysis":"...","suggestions":[{"symbol":"BTCUSDT","position_id":123,"side":"long","suggested_stop_loss":58000,"suggested_take_profit":68000,"time_horizon":"4h-8h","confidence":0.8,"reason":"...","detailed_analysis":"..."}],"risk_assessment":"...","next_steps":"..."}

Recibes posiciones abiertas con: symbol, side, entry_price, current_price, stop_loss, take_profit, quantity, unrealized_pnl.
El campo "side" indica la dirección de la posición: "long" (compra) o "short" (venta).

REGLA CRÍTICA DE SL/TP SEGÚN EL SIDE:
- LONG (compra): el SL debe estar DEBAJO del precio actual, el TP debe estar ARRIBA del precio actual.
  SL < current_price < TP
- SHORT (venta): el SL debe estar ARRIBA del precio actual, el TP debe estar DEBAJO del precio actual.
  TP < current_price < SL

NUNCA sugieras un SL arriba del precio actual para una posición LONG.
NUNCA sugieras un TP abajo del precio actual para una posición LONG.
NUNCA sugieras un SL abajo del precio actual para una posición SHORT.
NUNCA sugieras un TP arriba del precio actual para una posición SHORT.
También recibes datos técnicos del mercado (RSI, MACD, EMA, ATR, volumen) para los símbolos de las posiciones.
También recibes el perfil del usuario (risk_tolerance, experience_level, preferred_strategies, trading_goal).

Para CADA posición, realiza un ANÁLISIS EXHAUSTIVO:

1. ANÁLISIS DE TENDENCIA Y MOMENTUM (profundo):
   - Evalúa la tendencia general del activo (alcista, bajista, lateral)
   - Analiza el momentum con MACD (cruces, divergencias, histograma)
   - Identifica si el precio está en zona de expansión o contracción
   - Considera la estructura de mercado (máximos/mínimos crecientes o decrecientes)

2. ANÁLISIS DE VOLATILIDAD Y RIESGO (detallado):
   - Calcula el ATR actual y compáralo con el histórico para evaluar volatilidad
   - ¿Está el SL bien colocado o debería ajustarse según volatilidad actual (ATR)?
   - Evalúa el ratio riesgo/recompensa actual de la posición
   - Considera el tamaño de la posición relativo al capital

3. ANÁLISIS DE NIVELES Y OBJETIVOS (preciso):
   - ¿Está el TP bien colocado o hay más potencial alcista?
   - Identifica soportes y resistencias clave cercanos
   - Evalúa si el precio actual está cerca de zonas de reversión
   - Proyecta objetivos realistas basados en volatilidad y momentum

4. ANÁLISIS DE MOMENTUM DEL MERCADO (contextual):
   - ¿El momentum del mercado favorece mantener, reducir, o cerrar la posición?
   - Considera el volumen relativo para validar movimientos
   - Evalúa señales de divergencia entre precio y osciladores

5. HORIZONTE DE TIEMPO Y ESTRATEGIA (claro):
   - Horizonte de tiempo sugerido para mantener la posición
   - Escenarios optimista, neutral y pesimista
   - Condiciones específicas que activarían un cierre anticipado

SUGERENCIAS CONCRETAS por cada posición:
- suggested_stop_loss: nuevo precio de SL (puede ser igual al actual si está bien)
- suggested_take_profit: nuevo precio de TP
- time_horizon: string como "2h-4h", "4h-8h", "1d-3d"
- confidence: 0-1 de qué tan seguro estás de la sugerencia
- reason: explicación técnica concreta referenciando RSI, MACD, ATR, volumen, y el perfil del usuario
- detailed_analysis: análisis profundo y completo de esta posición (mínimo 3 párrafos cubriendo tendencia, volatilidad, niveles, momentum y estrategia)

PERFIL: Usa el perfil del usuario para calibrar las sugerencias.
- conservative: SL más ajustados, TP más conservadores
- moderate: balance entre riesgo y recompensa
- aggressive: SL más amplios, TP más ambiciosos

DATOS TÉCNICOS: El contexto incluye "technical" con análisis real (RSI, MACD, EMA, ATR, Bollinger, volumen). USA estos datos:
- RSI > 70 = sobrecomprado, considera ajustar SL hacia arriba para proteger profit
- RSI < 30 = sobrevendido, posible rebote, mantén SL actual
- MACD bearish + precio cayendo = considera SL más ajustado
- ATR_pct alto = mayor volatilidad, SL más amplio justificado
- volume_relative > 1.5 = movimiento confirmado, TP puede ser más ambicioso

⚠️ ENFOQUE TOTAL: Tómate tu tiempo. Cada posición merece un análisis completo y detallado. No escatimes en profundidad. El usuario depende de tu análisis para tomar decisiones financieras importantes. Sé meticuloso, preciso y exhaustivo.

SOLO devuelve sugerencias para las posiciones recibidas. NO sugieras nuevas compras."""

SYSTEM_PROMPT = """Eres un agente de trading PROACTIVO que SOLO COMPRA. Devuelves SOLO JSON con este schema exacto:
{"market_overview":"...","portfolio_status":"...","analysis":"...","actions":[{"type":"buy","symbol":"BTCUSDT","confidence":0.8,"stop_loss_pct":3,"take_profit_pct":8,"reason":"..."}],"risk_assessment":"...","next_steps":"..."}

SEÑALES REMOTAS: El contexto puede incluir "remote_signals" con señales de la Intelligence Platform (AI Server). USA estas señales COMO INPUT ADICIONAL:
- Si una señal remota dice "BUY" o "STRONG_BUY" y tu análisis técnico local lo confirma → COMPRA con confianza alta
- Si una señal remota dice "BUY" pero tu análisis técnico local dice "SELL" → NO compres, menciona la discrepancia en "analysis"
- Si no hay señales remotas (remote_signals=[]) pero tu análisis técnico local encuentra oportunidad → COMPRA basado en tu criterio
- Las señales remotas tienen "reasons" — úsalas para enriquecer tu "reason" en las acciones
- Si hay "remote_alerts" en el contexto, considéralas en tu "risk_assessment"

SOLO COMPRAS. Las ventas son automáticas con trailing stop y take-profit. NO incluyas "sell".

FRENO DE EMERGENCIA: actions=[] SOLO si: cash < $100, TODAS las señales son SELL/STRONG_SELL, o ya tienes el máximo de posiciones de tu perfil. En cualquier otro caso, BUSCA oportunidades.

PRIORIDAD DE COMPRA (compra el mejor candidato del ciclo):
1. Technical signal BUY o STRONG_BUY → compra INMEDIATAMENTE
2. Remote signal BUY/STRONG_BUY confirmado por technical → compra INMEDIATAMENTE (alta confianza)
3. RSI < 40 + trend bullish → compra (rebote inminente)
4. Gainer con volume_relative > 1.2 + cambio > 2% → compra (momentum)
5. Precio cerca de soporte (Bollinger lower band) → compra
6. Si hay cash > $1000 y 0 posiciones → compra el MEJOR candidato disponible

DATOS TÉCNICOS: El contexto incluye "technical" con análisis real (RSI, MACD, EMA, ATR, Bollinger, volumen). USA estos datos:
- signal "STRONG_BUY" o "BUY" = oportunidad alcista confirmada → COMPRA
- RSI < 40 = oversold (posible rebote) → COMPRA con SL ajustado
- RSI < 30 = oversold extremo → COMPRA con confianza alta
- EMA trend bullish = momentum positivo → COMPRA
- volume_relative > 1.2 = volumen confirmado → refuerza la compra
- ATR_pct = volatilidad, úsalo para ajustar stop_loss_pct (mayor ATR = mayor SL)
- NO compres símbolos con signal "SELL" o "STRONG_SELL"
- Si no hay technical data, usa gainers con momentum del spot/futures

CADA COMPRA debe incluir:
- stop_loss_pct: % de pérdida máxima (según ATR_pct y perfil del usuario)
- take_profit_pct: % de ganancia objetivo (según potencial y perfil del usuario)
- reason: explicación técnica concreta que referencia el perfil (ej: "RSI 32 + volume 2.1x + EMA bullish — adecuado para tu perfil moderate")

DIVERSIFICACIÓN: Compra símbolos DIFERENTES cada ciclo. NO compres un símbolo que ya está en positions. Si tienes 0 posiciones y cash > $500, COMPRA algo — no quedes en HOLD con el capital parado.

BUY_CANDIDATES: El contexto incluye "buy_candidates" con los mejores símbolos rankeados por score técnico. USA esta lista como prioridad de compra. El primer candidato con score más alto = mejor oportunidad.

SOLO usa símbolos de spot.up, spot.dn, futures.up, futures.dn, positions o technical. confidence entre 0 y 1."""

FEW_SHOT_EXAMPLE = """
EJEMPLO de respuesta válida:
{"market_overview":"BTC en rango 60k-65k, volumen estable. ETH con momentum alcista.","portfolio_status":"2 posiciones abiertas (SOL, ADA), cash $3200","analysis":"ETH muestra RSI 35 + volume_relative 1.8 + EMA bullish. Alineado con perfil moderate.","actions":[{"type":"buy","symbol":"ETHUSDT","confidence":0.75,"stop_loss_pct":3.5,"take_profit_pct":8,"reason":"RSI 35 (oversold) + volume 1.8x + EMA bullish — adecuado para perfil moderate"}],"risk_assessment":"Riesgo moderado. SL 3.5% protege contra caída brusca. ATR_pct 2.1% justifica el SL elegido.","next_steps":"Monitorear ETH. Si sube 4%, trailing stop activará."}"""


class AITradingAgent:
    """Agente de IA que analiza el mercado y ejecuta trades automáticamente."""

    def __init__(
        self,
        provider: str = "groq",
        groq_api_key: str | None = None,
        groq_model: str = "llama-3.1-8b-instant",
        gemini_api_key: str | None = None,
        gemini_model: str = "gemini-2.0-flash",
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen2.5:14b",
        openai_api_key: str | None = None,
        openai_base_url: str = "https://api.openai.com/v1",
        openai_model: str = "gpt-4o-mini",
        api_base: str = "http://127.0.0.1:8080",
        interval_seconds: int = 30,
        auto_trade: bool = True,
        jwt_token: str | None = None,
        auth_server_url: str | None = None,
        ai_provider: AIProvider | None = None,
        user_id: int = 0,
    ) -> None:
        self.provider = provider
        self.groq_api_key = groq_api_key
        self.groq_model = groq_model
        self.gemini_api_key = gemini_api_key
        self.gemini_model = gemini_model
        self.ollama_url = ollama_url.rstrip("/")
        self.ollama_model = ollama_model
        self.openai_api_key = openai_api_key
        self.openai_base_url = openai_base_url.rstrip("/")
        self.openai_model = openai_model
        self.api_base = api_base
        self.interval = interval_seconds
        self.auto_trade = auto_trade
        self._thread: Thread | None = None
        self._auto_close_thread: Thread | None = None
        self._stop_event = Event()
        self._log: list[dict] = []
        self._cycle = 0
        self._hold_streak = 0
        self._last_context_hash = ""
        self._base_interval = interval_seconds
        self._current_interval = interval_seconds
        self._position_peaks: dict[str, float] = {}  # symbol -> highest price seen (legacy)
        self._risk_engine = RiskEngine()  # Deterministic risk engine with trailing stop
        self._jwt_token = jwt_token
        self._user_id = user_id
        self._auth_server_url = auth_server_url
        self._grant_fail_streak = 0  # consecutive grant failures
        self._intelligence_provider: IntelligenceProvider | None = None
        self._last_signals_snapshot: dict[str, str] = {}  # asset -> decision (for consensus change detection)

        # AI provider: use injected or build from config
        if ai_provider is not None:
            self._ai_provider = ai_provider
        else:
            provider_config = AIProviderConfig(
                provider=provider,
                groq_api_key=groq_api_key,
                groq_model=groq_model,
                gemini_api_key=gemini_api_key,
                gemini_model=gemini_model,
                ollama_url=ollama_url,
                ollama_model=ollama_model,
                openai_api_key=openai_api_key,
                openai_base_url=openai_base_url,
                openai_model=openai_model,
            )
            try:
                from app.config import get_settings
                settings = get_settings()

                # Intelligence Platform mode (new architecture)
                if settings.USE_INTELLIGENCE_API:
                    self._intelligence_provider = create_intelligence_provider(settings)
                    if self._intelligence_provider:
                        prof = self._get_user_profile()
                        if prof:
                            r_label = {"conservative": "conservador", "moderate": "moderado", "aggressive": "agresivo"}.get(prof.get("risk_tolerance", ""), prof.get("risk_tolerance", ""))
                            exp = prof.get("experience_level", "intermediate")
                            strats = prof.get("preferred_strategies", [])
                            goal = prof.get("trading_goal", "growth")
                            self._add_log("info", f"Intelligence Platform activada — operando bajo tu perfil {r_label} (experiencia: {exp}, estrategia: {', '.join(strats) or 'swing'}, objetivo: {goal})")
                        else:
                            self._add_log("info", "Intelligence Platform mode enabled — using /v1/intelligence endpoints")

                if settings.USE_REMOTE_AI and settings.REMOTE_AI_URL:
                    provider_config = AIProviderConfig(
                        provider=provider,
                        groq_api_key=groq_api_key,
                        groq_model=groq_model,
                        gemini_api_key=gemini_api_key,
                        gemini_model=gemini_model,
                        ollama_url=ollama_url,
                        ollama_model=ollama_model,
                        openai_api_key=openai_api_key,
                        openai_base_url=openai_base_url,
                        openai_model=openai_model,
                        remote_ai_url=settings.REMOTE_AI_URL,
                        remote_ai_token=settings.REMOTE_AI_TOKEN,
                    )
                    self._ai_provider = RemoteAIProvider(provider_config)
                else:
                    self._ai_provider = LocalAIProvider(provider_config)
            except Exception:
                self._ai_provider = LocalAIProvider(provider_config)

    def _rebuild_provider(self) -> None:
        """Reconstruct the AI provider from current agent settings.

        Called after the /start endpoint updates provider, keys, and model
        so the agent uses the user's selected configuration, not the .env defaults.
        """
        provider_config = AIProviderConfig(
            provider=self.provider,
            groq_api_key=self.groq_api_key,
            groq_model=self.groq_model,
            gemini_api_key=self.gemini_api_key,
            gemini_model=self.gemini_model,
            ollama_url=self.ollama_url,
            ollama_model=self.ollama_model,
            openai_api_key=self.openai_api_key,
            openai_base_url=self.openai_base_url,
            openai_model=self.openai_model,
        )
        try:
            from app.config import get_settings
            settings = get_settings()

            if settings.USE_REMOTE_AI and settings.REMOTE_AI_URL:
                provider_config = AIProviderConfig(
                    provider=self.provider,
                    groq_api_key=self.groq_api_key,
                    groq_model=self.groq_model,
                    gemini_api_key=self.gemini_api_key,
                    gemini_model=self.gemini_model,
                    ollama_url=self.ollama_url,
                    ollama_model=self.ollama_model,
                    openai_api_key=self.openai_api_key,
                    openai_base_url=self.openai_base_url,
                    openai_model=self.openai_model,
                    remote_ai_url=settings.REMOTE_AI_URL,
                    remote_ai_token=settings.REMOTE_AI_TOKEN,
                )
                self._ai_provider = RemoteAIProvider(provider_config)
            else:
                self._ai_provider = LocalAIProvider(provider_config)
        except Exception:
            self._ai_provider = LocalAIProvider(provider_config)

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def get_log(self, limit: int = 50) -> list[dict]:
        # Try DB first, fallback to in-memory
        try:
            from app.database.session import SessionLocal
            from app.database.models.agent_log import AgentLog
            db = SessionLocal()
            logs = db.query(AgentLog).filter(
                AgentLog.user_id == self._user_id
            ).order_by(AgentLog.id.desc()).limit(limit).all()
            db.close()
            if logs:
                return [{
                    "timestamp": log.timestamp.isoformat() if log.timestamp else "",
                    "level": log.level,
                    "message": log.message,
                    "cycle": log.cycle,
                    **(log.metadata_json or {}),
                } for log in logs]
        except Exception:
            pass
        return list(reversed(self._log[-limit:]))

    def get_status(self) -> dict:
        return {
            "is_running": self.is_running,
            "provider": self.provider,
            "model": self.groq_model if self.provider == "groq" else (self.gemini_model if self.provider == "gemini" else (self.openai_model if self.provider in ("openai","deepseek","mistral","together","perplexity","grok") else self.ollama_model)),
            "interval_seconds": self.interval,
            "current_interval": self._current_interval,
            "hold_streak": self._hold_streak,
            "auto_trade": self.auto_trade,
            "cycles": self._cycle,
            "last_log_count": len(self._log),
            "grant_authorized": self._jwt_token is not None,
            "intelligence_mode": self._intelligence_provider is not None,
        }

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._auto_close_thread = Thread(target=self._auto_close_loop, daemon=True)
        self._auto_close_thread.start()
        self._add_log("info", "Agente IA iniciado (modo solo compra + auto stop-loss/take-profit)")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        if self._auto_close_thread:
            self._auto_close_thread.join(timeout=5)
            self._auto_close_thread = None
        self._add_log("info", "Agente IA detenido")

    def set_interval(self, seconds: int) -> None:
        if seconds >= 10:
            self.interval = seconds

    def _add_log(self, level: str, message: str, extra: dict | None = None) -> None:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": level,
            "message": message,
        }
        if extra:
            entry.update(extra)
        self._log.append(entry)
        if len(self._log) > 500:
            self._log = self._log[-500:]
        if level == "error":
            logger.error(f"[AI Agent] {message}")
        else:
            logger.info(f"[AI Agent] {message}")

        # Persist to DB
        try:
            from app.database.session import SessionLocal
            from app.database.models.agent_log import AgentLog
            db = SessionLocal()
            db.add(AgentLog(
                user_id=self._user_id,
                level=level,
                message=message,
                cycle=self._cycle if hasattr(self, "_cycle") else None,
                metadata_json=extra or {},
            ))
            db.commit()
            # Cleanup old logs (keep last 500 per user)
            db.query(AgentLog).filter(
                AgentLog.user_id == self._user_id,
                AgentLog.id.notin_(
                    db.query(AgentLog.id)
                    .filter(AgentLog.user_id == self._user_id)
                    .order_by(AgentLog.id.desc())
                    .limit(500)
                )
            ).delete(synchronize_session=False)
            db.commit()
            db.close()
        except Exception:
            pass

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._cycle += 1

                # Request authorization grant from Auth Server before each cycle
                grant = self._request_grant()
                if not grant:
                    self._grant_fail_streak += 1
                    if self._grant_fail_streak >= 5:
                        self._add_log("error", "Grant rechazado 5 veces consecutivas. Deteniendo agente.")
                        self._stop_event.set()
                        break
                    # Wait longer before retrying
                    self._stop_event.wait(min(self._current_interval * 2, 120))
                    continue

                self._grant_fail_streak = 0
                self._add_log("info", f"Grant autorizado (cuota: {grant.get('quota_used', '?')}/{grant.get('quota_limit', '?')})", {
                    "cycle": self._cycle, "phase": "grant_authorized",
                    "quota_remaining": grant.get("quota_remaining"),
                })

                # Run the tick
                cycle_success = False
                try:
                    self._tick()
                    cycle_success = True
                finally:
                    # Report usage back to Auth Server
                    self._report_usage(grant, cycle_success)

            except Exception as exc:
                self._add_log("error", f"Error en ciclo: {exc}")
            self._stop_event.wait(self._current_interval)

    def _auto_close_loop(self) -> None:
        """Monitors open positions every 5s and auto-sells when stop-loss or take-profit is hit."""
        while not self._stop_event.is_set():
            try:
                self._check_auto_close()
            except Exception as exc:
                logger.error(f"[AI Agent] Auto-close error: {exc}")
            self._stop_event.wait(5)

    def _check_auto_close(self) -> None:
        """Check open positions with trailing stop logic via RiskEngine.

        Uses RiskEngine.evaluate_trailing_stop (Decimal-based, deterministic).
        Falls back to legacy float logic if RiskEngine unavailable.
        """
        try:
            positions = self._api_get("/api/positions?status=open&limit=50")
            if not isinstance(positions, list) or not positions:
                return

            for pos in positions:
                symbol = pos.get("symbol", "")
                stop_loss = pos.get("stop_loss")
                take_profit = pos.get("take_profit")
                entry_price = pos.get("entry_price")
                auto_sell = pos.get("auto_sell_enabled", True)

                if not symbol or not entry_price:
                    continue

                # Skip positions where user disabled auto-sell
                if not auto_sell:
                    continue

                if not stop_loss or not take_profit:
                    continue

                # Get current price from Binance (spot first, then futures)
                try:
                    resp = httpx.get(
                        f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}",
                        timeout=5.0,
                    )
                    if resp.status_code == 200:
                        current_price = float(resp.json()["price"])
                    else:
                        resp = httpx.get(
                            f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}",
                            timeout=5.0,
                        )
                        if resp.status_code == 200:
                            current_price = float(resp.json()["price"])
                        else:
                            continue
                except Exception:
                    continue

                # Use RiskEngine for trailing stop evaluation (Decimal-based)
                result = self._risk_engine.evaluate_trailing_stop(
                    symbol=symbol,
                    entry_price=Decimal(str(entry_price)),
                    stop_loss=Decimal(str(stop_loss)),
                    take_profit=Decimal(str(take_profit)),
                    current_price=Decimal(str(current_price)),
                )

                if result.should_close:
                    entry = float(entry_price)
                    peak = float(result.peak)

                    if result.close_type == "breakeven":
                        self._add_log("warn", f"BREAKEVEN STOP {symbol}: precio ${current_price:.4f} bajó hacia entry ${entry:.4f}. Vendiendo para proteger capital.", {
                            "phase": "auto_breakeven", "symbol": symbol, "price": current_price, "entry": entry, "peak": peak,
                        })
                        reason = f"Auto breakeven-stop: protegía profit, precio volvió a ${current_price}"
                        self._create_notif("stop_loss_hit", f"Breakeven stop: {symbol}", f"Precio volvió a entry. Vendiendo para proteger capital.", severity="warning", asset=symbol.replace("USDT", ""))
                    elif result.close_type == "trailing":
                        self._add_log("info", f"TRAILING STOP {symbol}: precio ${current_price:.4f} bajó del peak ${peak:.4f}. Vendiendo con profit asegurado.", {
                            "phase": "auto_trailing", "symbol": symbol, "price": current_price, "entry": entry, "peak": peak,
                        })
                        reason = f"Auto trailing-stop: peak fue ${peak:.4f}, vendiendo a ${current_price}"
                        self._create_notif("trailing_stop_update", f"Trailing stop: {symbol}", f"Peak fue ${peak:.4f}, vendiendo a ${current_price:.4f}", severity="info", asset=symbol.replace("USDT", ""))
                    elif result.close_type == "take_profit":
                        self._add_log("info", f"TAKE-PROFIT {symbol}: precio ${current_price:.4f} >= TP ${float(take_profit):.4f}. Vendiendo.", {
                            "phase": "auto_take_profit", "symbol": symbol, "price": current_price, "take_profit": float(take_profit),
                        })
                        reason = f"Auto take-profit: precio subió a ${current_price}"
                        self._create_notif("take_profit_hit", f"Take-profit: {symbol}", f"Precio alcanzó TP. Vendiendo con profit.", severity="info", asset=symbol.replace("USDT", ""))
                    else:
                        self._add_log("warn", f"STOP-LOSS {symbol}: precio ${current_price:.4f} <= SL ${float(result.effective_sl):.4f}. Vendiendo.", {
                            "phase": "auto_stop_loss", "symbol": symbol, "price": current_price, "stop_loss": float(result.effective_sl),
                        })
                        reason = f"Auto stop-loss: precio bajó a ${current_price}"
                        self._create_notif("stop_loss_hit", f"Stop-loss: {symbol}", f"Precio bajó a ${current_price:.4f} (SL: ${float(result.effective_sl):.4f})", severity="critical", asset=symbol.replace("USDT", ""))

                    sell_result = self._api_post("/api/ai-agent/execute", {
                        "action_type": "sell",
                        "symbol": symbol,
                        "confidence": 1.0,
                        "reason": reason,
                    })
                    if sell_result and sell_result.get("status") == "executed":
                        pnl_pct = ((current_price - entry) / entry) * 100
                        emoji = "🎉" if current_price > entry else "🛡️" if current_price >= entry * 0.999 else "⚠️"
                        self._add_log("info", f"{emoji} Venta {symbol} ejecutada @ ${current_price:.4f} (PnL: {pnl_pct:+.2f}%)")
                        self._risk_engine.clear_position_peak(symbol)
                        self._position_peaks.pop(symbol, None)
                    else:
                        self._add_log("error", f"Auto-sell falló para {symbol}: {sell_result}")
                else:
                    # Position still open - log trailing status occasionally
                    peak = float(result.peak)
                    if peak > entry * 1.01:
                        trail_sl = float(result.effective_sl)
                        profit_pct = ((current_price - entry) / entry) * 100
                        if peak == current_price and profit_pct > 2:
                            self._add_log("info", f"📈 {symbol} subiendo: ${current_price:.4f} (PnL: {profit_pct:+.2f}%, peak: ${peak:.4f}, trailing SL: ${trail_sl:.4f})", {
                                "phase": "trailing_update", "symbol": symbol, "price": current_price, "peak": peak, "trailing_sl": trail_sl,
                            })

                    # Technical exit checks (RSI, MACD, time, volume)
                    try:
                        from app.risk.engine import AutoSellConfig
                        tech_config = self._get_auto_sell_config()
                        opened_at = pos.get("opened_at")
                        if opened_at:
                            from datetime import datetime as _dt
                            if isinstance(opened_at, str):
                                opened_at = _dt.fromisoformat(opened_at.replace("Z", "+00:00"))
                            tech_result = self._risk_engine.evaluate_technical_exit(
                                symbol=symbol,
                                entry_price=Decimal(str(entry_price)),
                                current_price=Decimal(str(current_price)),
                                opened_at=opened_at,
                                config=tech_config,
                            )
                            if tech_result.should_close:
                                self._add_log("warn", f"TECHNICAL EXIT {symbol}: {tech_result.reason}", {
                                    "phase": "auto_technical", "symbol": symbol,
                                    "indicator": tech_result.indicator, "value": tech_result.value,
                                    "price": current_price,
                                })
                                reason = f"Auto technical exit ({tech_result.indicator}): {tech_result.reason}"
                                self._create_notif(
                                    "technical_exit",
                                    f"Venta técnica: {symbol} ({tech_result.indicator})",
                                    tech_result.reason,
                                    severity="warning",
                                    asset=symbol.replace("USDT", ""),
                                )
                                sell_result = self._api_post("/api/ai-agent/execute", {
                                    "action_type": "sell",
                                    "symbol": symbol,
                                    "confidence": 1.0,
                                    "reason": reason,
                                })
                                if sell_result and sell_result.get("status") == "executed":
                                    pnl_pct = ((current_price - entry) / entry) * 100
                                    self._add_log("info", f"📊 Venta técnica {symbol} ejecutada @ ${current_price:.4f} (PnL: {pnl_pct:+.2f}%) — {tech_result.indicator}")
                                    self._risk_engine.clear_position_peak(symbol)
                                    self._position_peaks.pop(symbol, None)
                                else:
                                    self._add_log("error", f"Technical sell falló para {symbol}: {sell_result}")
                    except Exception as tech_err:
                        logger.debug(f"[AI Agent] Technical exit check error for {symbol}: {tech_err}")

        except Exception as exc:
            logger.error(f"[AI Agent] Error en auto-close: {exc}")

    def _get_auto_sell_config(self):
        """Fetch auto-sell config from the risk config endpoint, or use defaults."""
        from app.risk.engine import AutoSellConfig
        try:
            cfg = self._api_get("/api/intelligence/risk/config")
            if isinstance(cfg, dict):
                return AutoSellConfig(
                    rsi_overbought=float(cfg.get("auto_sell_rsi_overbought", 70.0)),
                    max_position_hours=float(cfg.get("auto_sell_max_position_hours", 24.0)),
                    min_volume_relative=float(cfg.get("auto_sell_min_volume_relative", 0.5)),
                    macd_bearish_enabled=bool(cfg.get("auto_sell_macd_bearish", True)),
                    rsi_enabled=bool(cfg.get("auto_sell_rsi_enabled", True)),
                    time_enabled=bool(cfg.get("auto_sell_time_enabled", True)),
                    volume_enabled=bool(cfg.get("auto_sell_volume_enabled", True)),
                )
        except Exception:
            pass
        return AutoSellConfig()

    def _request_grant(self) -> dict | None:
        """Request a signed grant from the Auth Server before each AI cycle.

        Returns the grant dict if authorized, None if denied or unreachable.
        The AI agent will not proceed without a valid grant.
        """
        if not self._jwt_token:
            self._add_log("error", "No hay JWT token configurado. No se puede solicitar grant.")
            return None

        try:
            from app.services.license import request_ai_grant
            grant = request_ai_grant(self._jwt_token)
            if grant and grant.get("granted"):
                return grant
            self._add_log("warn", "Grant rechazado por el Auth Server (cuota agotada o suscripción inactiva)")
            return None
        except Exception as exc:
            self._add_log("error", f"Error solicitando grant: {exc}")
            return None

    def _report_usage(self, grant: dict, success: bool = True) -> None:
        """Report AI cycle completion to the Auth Server to consume the grant."""
        if not self._jwt_token:
            return
        grant_id = grant.get("grant_id")
        grant_token = grant.get("grant_token")
        if not grant_id or not grant_token:
            return
        try:
            from app.services.license import report_ai_usage
            result = report_ai_usage(self._jwt_token, grant_id, grant_token, success)
            if result and result.get("reported"):
                self._add_log("info", f"Uso reportado (cuota: {result.get('quota_used', '?')}/{result.get('quota_limit', '?')})", {
                    "phase": "usage_reported",
                    "quota_remaining": result.get("quota_remaining"),
                })
            elif result:
                self._add_log("warn", "Uso reportado pero no contabilizado (ciclo fallido)")
            else:
                self._add_log("warn", "No se pudo reportar uso al Auth Server")
        except Exception as exc:
            self._add_log("error", f"Error reportando uso: {exc}")

    def _tick(self) -> None:
        self._add_log("info", f"--- Ciclo {self._cycle} iniciado ---", {"cycle": self._cycle, "phase": "start"})

        # Route to intelligence platform mode if enabled
        if self._intelligence_provider is not None:
            self._tick_intelligence()
            return

        # Legacy mode: gather context → ask LLM → execute
        self._add_log("info", "Recopilando datos del sistema...", {"cycle": self._cycle, "phase": "gathering"})
        context = self._gather_context()
        if not context:
            self._add_log("warn", "No se pudo obtener contexto del sistema", {"cycle": self._cycle, "phase": "error"})
            return

        # Skip cycle if context hasn't changed (save tokens)
        import hashlib
        context_str = json.dumps(context, sort_keys=True, default=str)
        context_hash = hashlib.md5(context_str.encode()).hexdigest()
        if context_hash == self._last_context_hash and self._hold_streak >= 2:
            self._add_log("info", "Sin cambios en el mercado, saltando ciclo (ahorro de tokens)", {"cycle": self._cycle, "phase": "skip"})
            self._hold_streak += 1
            self._adjust_interval()
            return
        self._last_context_hash = context_hash

        # Log what we're seeing
        self._log_context_summary(context)

        # 2. Ask the LLM to analyze and decide
        self._add_log("info", "Enviando datos al LLM para análisis...", {"cycle": self._cycle, "phase": "analyzing"})
        decision = self._ask_llm(context)
        if not decision:
            self._add_log("warn", "El LLM no respondió", {"cycle": self._cycle, "phase": "error"})
            self._handle_llm_failure()
            return

        # Log the full decision with all fields
        self._add_log("info", "Análisis completado", {
            "cycle": self._cycle,
            "phase": "decision",
            "market_overview": decision.get("market_overview", ""),
            "portfolio_status": decision.get("portfolio_status", ""),
            "analysis": decision.get("analysis", ""),
            "risk_assessment": decision.get("risk_assessment", ""),
            "next_steps": decision.get("next_steps", ""),
            "actions_count": len(decision.get("actions", [])),
            "actions": decision.get("actions", []),
        })

        # 3. Execute actions (limit buys to 1 per cycle for small capital)
        actions = decision.get("actions", [])
        if not actions:
            self._add_log("info", "Sin acciones a ejecutar este ciclo - manteniendo posiciones", {"cycle": self._cycle, "phase": "hold"})
            self._hold_streak += 1
            self._adjust_interval()
            return

        # Has actions - reset hold streak and interval
        self._hold_streak = 0
        self._current_interval = self._base_interval

        # Save recommendations to Reports tab (always, so users can review what the AI proposed)
        self._save_recommendations(actions, [])

        if not self.auto_trade:
            self._add_log("info", f"Auto-trade deshabilitado. {len(actions)} acciones propuestas pero no ejecutadas", {"cycle": self._cycle, "phase": "proposed"})
            return

        # Execute sells first (close positions), then buys (up to MAX_OPEN_POSITIONS)
        buy_actions = [a for a in actions if a.get("type", "").lower() == "buy"]
        sell_actions = [a for a in actions if a.get("type", "").lower() == "sell"]

        # Execute sells first (close positions)
        for action in sell_actions:
            self._execute_action(action)
        # Execute buys (allow multiple up to max positions)
        for action in buy_actions:
            self._execute_action(action)

        self._add_log("info", f"--- Ciclo {self._cycle} completado ---", {"cycle": self._cycle, "phase": "end"})

    def _tick_intelligence(self) -> None:
        """Intelligence Platform mode: combine remote signals + local technical analysis + LLM.

        Flow:
        1. Get active signals from /v1/intelligence/signals
        2. Get active alerts from /v1/intelligence/alerts
        3. Gather local technical context (movers, RSI, MACD, etc.)
        4. Send combined data (signals + local context) to LLM for decision
        5. Execute actions from LLM decision (which may differ from raw signals)
        6. Log alerts as warnings
        """
        provider = self._intelligence_provider
        assert provider is not None

        # Load user profile for profile-aware messaging
        profile = self._get_user_profile()
        risk_tol = profile.get("risk_tolerance") if profile else "moderate"
        experience = profile.get("experience_level") if profile else "intermediate"
        strategies = profile.get("preferred_strategies", []) if profile else []
        goal = profile.get("trading_goal") if profile else "growth"
        profile_label = {"conservative": "conservador", "moderate": "moderado", "aggressive": "agresivo"}.get(risk_tol, risk_tol)

        self._add_log("info", f"Consultando Intelligence Platform... (perfil: {profile_label}, experiencia: {experience}, estrategia: {', '.join(strategies) or 'swing'}, objetivo: {goal})", {"cycle": self._cycle, "phase": "intelligence_fetch"})

        # 1. Get active alerts (always fetch, even if no signals)
        alerts = provider.get_alerts(limit=5)
        for alert in alerts:
            self._add_log("warn", f"Alerta {alert.asset}: {alert.message} (severity={alert.severity})", {
                "cycle": self._cycle, "phase": "alert", "alert_type": alert.alert_type,
            })
            sev = "critical" if alert.severity in ("critical", "high") else "warning" if alert.severity == "medium" else "info"
            self._create_notif("news_high_impact", f"Alerta: {alert.asset}", alert.message, severity=sev, asset=alert.asset)

        # 2. Get global signals
        signals = provider.get_signals(limit=10)

        # 2.5. Record events to journal for multi-user dashboard
        self._record_events_to_journal(signals, alerts)

        # 3. Gather local technical context (movers, RSI, MACD, positions, etc.)
        local_context = self._gather_context()

        # 4. Build combined context for LLM: remote signals + local technical data
        combined_context: dict[str, Any] = dict(local_context)  # Start with local context (acc, positions, spot, futures, technical, etc.)

        # Add remote signals to context so LLM can use them
        if signals:
            combined_context["remote_signals"] = [
                {
                    "asset": s.asset,
                    "decision": s.decision,
                    "confidence": s.confidence,
                    "entry_zone": getattr(s, "entry_zone", None),
                    "targets": getattr(s, "targets", None),
                    "invalidation": getattr(s, "invalidation", None),
                    "reasons": getattr(s, "reasons", None) or getattr(s, "main_reasons", None),
                }
                for s in signals
            ]
        else:
            combined_context["remote_signals"] = []

        # Add alerts to context
        if alerts:
            combined_context["remote_alerts"] = [
                {"asset": a.asset, "type": a.alert_type, "severity": a.severity, "message": a.message}
                for a in alerts
            ]

        # 5. Send combined context to LLM for analysis and decision
        # The LLM receives BOTH remote signals AND local technical data
        # It can confirm, override, or find new opportunities the remote signals missed
        self._add_log("info", f"Enviando contexto combinado al LLM ({len(signals)} señales remotas + datos técnicos locales)...", {
            "cycle": self._cycle, "phase": "llm_analysis",
            "remote_signals_count": len(signals),
            "has_technical": "technical" in combined_context,
            "has_buy_candidates": "buy_candidates" in combined_context,
        })

        decision = self._ask_llm(combined_context)
        if not decision:
            # LLM failed — check if it's a critical error (quota/auth) before falling back
            if self._handle_llm_failure():
                return
            # Non-critical error — fall back to signal-based execution
            self._add_log("warn", "LLM no respondió, usando señales remotas directamente", {"cycle": self._cycle, "phase": "llm_fallback"})
            if not signals:
                self._add_log("info", f"No hay señales activas ni LLM — manteniendo posiciones según tu perfil {profile_label}", {"cycle": self._cycle, "phase": "no_signals"})
                self._hold_streak += 1
                self._adjust_interval()
                return
            # Use legacy signal-based flow as fallback
            actions = self._signals_to_actions(signals, provider, profile_label)
        else:
            # LLM responded — use its decision (combines remote + local)
            self._add_log("info", "Análisis LLM completado (señales remotas + técnico local)", {
                "cycle": self._cycle,
                "phase": "decision",
                "market_overview": decision.get("market_overview", ""),
                "analysis": decision.get("analysis", ""),
                "risk_assessment": decision.get("risk_assessment", ""),
                "actions_count": len(decision.get("actions", [])),
                "actions": decision.get("actions", []),
            })
            actions = decision.get("actions", [])

        # 6. Execute actions
        if not actions:
            self._add_log("info", f"Sin acciones tras análisis combinado — tu perfil {profile_label} filtra oportunidades de mayor riesgo", {"cycle": self._cycle, "phase": "no_actions"})
            self._hold_streak += 1
            self._adjust_interval()
            return

        self._hold_streak = 0
        self._current_interval = self._base_interval

        # Save recommendations to Reports tab (always, so users can review what the AI proposed)
        self._save_recommendations(actions, signals)

        if not self.auto_trade:
            self._add_log("info", f"Auto-trade deshabilitado. {len(actions)} acciones propuestas", {"cycle": self._cycle, "phase": "proposed"})
            return

        for action in actions:
            self._execute_action(action)

        self._add_log("info", f"--- Ciclo {self._cycle} completado (intelligence + LLM mode) ---", {"cycle": self._cycle, "phase": "end"})

    def _signals_to_actions(self, signals: list, provider: Any, profile_label: str) -> list[dict]:
        """Fallback: convert remote signals to actions without LLM (used when LLM fails)."""
        actions: list[dict] = []
        positions = self._api_get("/api/positions?status=open&limit=20")
        portfolio_data = self._build_portfolio_for_match(positions)
        for signal in signals:
            signal_dict = {
                "asset": signal.asset,
                "decision": signal.decision,
                "confidence": signal.confidence,
            }
            recommendation = provider.portfolio_match(
                user_id_hash=self._get_user_hash(),
                signal=signal_dict,
                portfolio=portfolio_data,
            )
            if recommendation is None:
                continue
            self._add_log("info", f"Signal {signal.asset}: market={recommendation.market_decision} → personal={recommendation.personal_recommendation} ({recommendation.reason}) — basado en tu perfil {profile_label}", {
                "cycle": self._cycle, "phase": "portfolio_match",
                "asset": signal.asset, "recommendation": recommendation.personal_recommendation,
                "confidence": recommendation.confidence,
            })
            action = self._recommendation_to_action(recommendation)
            if action:
                actions.append(action)
        return actions

    def _record_events_to_journal(
        self,
        signals: list,
        alerts: list,
    ) -> None:
        """Write signals and alerts to the Event Journal for multi-user dashboard.

        Detects consensus changes by comparing current signal decisions with
        the previous cycle's snapshot. New signals, invalidated signals, and
        consensus changes are recorded as events.
        """
        try:
            from app.database.session import SessionLocal
            from app.intelligence.event_journal import EventJournal

            session = SessionLocal()
            try:
                journal = EventJournal(session)

                # 1. Record alerts as news_high_impact or whale_move events
                for alert in alerts:
                    event_type = "news_high_impact"
                    if alert.alert_type in ("whale", "whale_move", "large_transfer"):
                        event_type = "whale_move"
                    elif alert.alert_type in ("funding", "funding_shift"):
                        event_type = "funding_shift"
                    elif alert.alert_type in ("macro", "economic_event"):
                        event_type = "macro_event"

                    severity = "critical" if alert.severity in ("critical", "high") else "info"
                    scope = "global" if severity == "critical" else "asset"

                    journal.record(
                        event_type=event_type,
                        asset=alert.asset,
                        title=alert.message[:200],
                        detail=alert.message,
                        severity=severity,
                        scope=scope,
                        agent_source="News",
                        metadata={"alert_type": alert.alert_type, "alert_id": alert.id},
                    )

                # 2. Detect consensus changes and new/invalidated signals
                current_snapshot: dict[str, str] = {}
                for signal in signals:
                    asset = signal.asset
                    decision = signal.decision
                    current_snapshot[asset] = decision

                    prev_decision = self._last_signals_snapshot.get(asset)

                    if prev_decision is None:
                        # New signal for this asset
                        journal.record(
                            event_type="new_opportunity",
                            asset=asset,
                            title=f"Nueva señal: {asset} → {decision}",
                            detail=f"Confianza: {signal.confidence:.0%}. Motivos: {', '.join(signal.main_reasons[:3])}",
                            severity="info",
                            scope="asset",
                            agent_source="Consensus",
                            metadata={
                                "decision": decision,
                                "confidence": signal.confidence,
                                "reasons": signal.main_reasons,
                                "risks": signal.main_risks,
                                "signal_id": signal.id,
                            },
                        )
                    elif prev_decision != decision:
                        # Consensus changed
                        journal.record(
                            event_type="consensus_change",
                            asset=asset,
                            title=f"{asset} cambió de {prev_decision} → {decision}",
                            detail=f"Confianza: {signal.confidence:.0%}. Motivos: {', '.join(signal.main_reasons[:3])}",
                            severity="warning",
                            scope="asset",
                            agent_source="Consensus",
                            metadata={
                                "prev_decision": prev_decision,
                                "new_decision": decision,
                                "confidence": signal.confidence,
                                "reasons": signal.main_reasons,
                                "signal_id": signal.id,
                            },
                        )

                # 3. Detect invalidated signals (assets that were in snapshot but no longer in current)
                for asset, prev_decision in self._last_signals_snapshot.items():
                    if asset not in current_snapshot:
                        journal.record(
                            event_type="invalidated",
                            asset=asset,
                            title=f"Señal de {asset} invalidada",
                            detail=f"Ya no hay señal activa para {asset} (era {prev_decision})",
                            severity="info",
                            scope="asset",
                            agent_source="Consensus",
                            metadata={"prev_decision": prev_decision},
                        )

                # 4. Update snapshot for next cycle
                self._last_signals_snapshot = current_snapshot

                # 5. Save analysis snapshots to analysis storage (like klines for AI)
                from app.intelligence.analysis_storage import AnalysisStorage
                storage = AnalysisStorage(session)
                for signal in signals:
                    storage.save(
                        asset=signal.asset,
                        decision=signal.decision,
                        confidence=signal.confidence,
                        risk_level="medium",
                        reasons={"main_reasons": signal.main_reasons},
                        risks={"main_risks": signal.main_risks},
                        metrics={"agreement": signal.agreement} if hasattr(signal, "agreement") else {},
                        agent_votes=signal.agreement if hasattr(signal, "agreement") else {},
                    )

            finally:
                session.close()
        except Exception as exc:
            logger.warning("[AI Agent] Failed to record events to journal: %s", exc)

    def _save_recommendations(self, actions: list[dict], signals: list) -> None:
        """Save proposed actions as recommendations in the DB for the Reports tab."""
        try:
            from app.database.session import SessionLocal
            from app.database.models.ai_recommendation import AIRecommendation
            from app.config import get_settings

            settings = get_settings()
            trading_mode = settings.TRADING_MODE
            broker_name = settings.BROKER_PROVIDER

            self._add_log("info", f"Guardando {len(actions)} recomendaciones en DB...", {
                "cycle": self._cycle, "phase": "saving_recommendations",
                "actions": [{"type": a.get("type"), "symbol": a.get("symbol"), "confidence": a.get("confidence")} for a in actions],
            })

            session = SessionLocal()
            try:
                # Build a lookup of signal data by asset
                signal_map = {}
                for sig in signals:
                    asset_key = sig.asset.upper().replace("USDT", "").replace("USDC", "")
                    signal_map[asset_key] = sig

                saved_count = 0
                for action in actions:
                    symbol = action.get("symbol", "").upper()
                    asset = symbol.replace("USDT", "").replace("USDC", "")
                    sig = signal_map.get(asset)

                    # Normalize confidence: LLM may send 90 (percent) or 0.9 (decimal)
                    raw_conf = action.get("confidence", 0)
                    conf_val = float(raw_conf)
                    # If confidence > 1, treat as percentage and convert to decimal
                    if conf_val > 1:
                        conf_val = conf_val / 100.0

                    rec = AIRecommendation(
                        user_id=self._user_id,
                        asset=asset,
                        action_type=action.get("type", "HOLD").upper(),
                        confidence=conf_val,
                        reason=action.get("reason", ""),
                        stop_loss_pct=action.get("stop_loss_pct"),
                        take_profit_pct=action.get("take_profit_pct"),
                        market_decision=sig.decision if sig else None,
                        personal_recommendation=action.get("type", "").upper(),
                        status="pending",
                        trading_mode=trading_mode,
                        broker_name=broker_name if trading_mode == "live" else None,
                        metadata_json={
                            "cycle": self._cycle,
                            "signal_id": sig.id if sig else None,
                            "main_reasons": sig.main_reasons if sig else [],
                            "main_risks": sig.main_risks if sig else [],
                        },
                    )
                    session.add(rec)
                    saved_count += 1

                session.commit()
                self._add_log("info", f"{saved_count} recomendaciones guardadas en Reportes", {
                    "cycle": self._cycle, "phase": "recommendations_saved",
                })
            finally:
                session.close()
        except Exception as exc:
            logger.warning("[AI Agent] Failed to save recommendations: %s", exc)
            self._add_log("error", f"Error guardando recomendaciones en DB: {exc}", {"phase": "save_recommendations_error"})

    def _fetch_news(self) -> None:
        """Fetch and store important crypto news (runs every few cycles)."""
        try:
            from app.intelligence.news_fetcher import fetch_and_store_news
            count = fetch_and_store_news(max_per_feed=10, min_impact="medium")
            if count > 0:
                self._add_log("info", f"News fetcher: {count} new articles stored", {
                    "cycle": self._cycle, "phase": "news_fetch",
                })
        except Exception as exc:
            logger.warning("[AI Agent] News fetch failed: %s", exc)

    def _get_user_profile(self) -> dict | None:
        """Fetch the user's onboarding profile from local DB."""
        try:
            from app.database.session import SessionLocal
            from app.database.models.user_profile import UserProfile
            session = SessionLocal()
            try:
                profile = session.query(UserProfile).filter(UserProfile.user_id == 0).first()
                if profile:
                    return profile.to_dict()
                return None
            finally:
                session.close()
        except Exception:
            return None

    def _risk_tolerance_to_profile(self, risk_tolerance: str | None) -> str:
        """Map onboarding risk_tolerance to ai-server risk_profile."""
        if risk_tolerance == "conservative":
            return "passive"
        elif risk_tolerance == "aggressive":
            return "aggressive"
        return "intermediate"

    def _build_portfolio_for_match(self, positions: list | None) -> dict:
        """Build portfolio dict for the Portfolio Matcher from open positions."""
        if not isinstance(positions, list):
            positions = []

        # Fetch user profile to get real risk tolerance
        profile = self._get_user_profile()
        risk_profile = self._risk_tolerance_to_profile(profile.get("risk_tolerance") if profile else None)

        total_value = 0.0
        position_list = []
        for p in positions:
            symbol = p.get("symbol", "")
            qty = float(p.get("quantity", 0))
            entry = float(p.get("entry_price", 0))
            current = float(p.get("current_price", entry))
            value = qty * current
            total_value += value
            position_list.append({
                "symbol": symbol,
                "quantity": qty,
                "entry_price": entry,
                "current_price": current,
                "value": value,
                "allocation_pct": 0,  # calculated below
            })

        # Calculate allocation percentages
        if total_value > 0:
            for pos in position_list:
                pos["allocation_pct"] = (pos["value"] / total_value) * 100

        # Get account snapshot for total portfolio value
        snapshots = self._api_get("/api/snapshots?limit=1")
        total_portfolio = total_value
        cash_pct = 100.0
        if isinstance(snapshots, list) and snapshots:
            snap = snapshots[0]
            equity = float(snap.get("equity", 0))
            cash = float(snap.get("cash", 0))
            if equity > 0:
                total_portfolio = equity
                cash_pct = (cash / equity) * 100

        result = {
            "broker": "binance",
            "risk_profile": risk_profile,
            "positions": position_list,
            "total_portfolio_value": total_portfolio,
            "cash_pct": cash_pct,
        }
        # Include profile data for the ai-server to use
        if profile:
            result["user_profile"] = {
                "experience_level": profile.get("experience_level"),
                "risk_tolerance": profile.get("risk_tolerance"),
                "preferred_strategies": profile.get("preferred_strategies", []),
                "trading_goal": profile.get("trading_goal"),
                "capital_range": profile.get("capital_range"),
            }
        return result

    def _get_user_hash(self) -> str:
        """Get a hash identifying the current user for personalization."""
        if self._jwt_token:
            import hashlib as _hashlib
            return _hashlib.sha256(self._jwt_token.encode()).hexdigest()[:32]
        return "anonymous_user_hash_000000"

    def _recommendation_to_action(self, rec: Any) -> dict | None:
        """Convert a PersonalRecommendation to an action dict for execution."""
        rec_type = rec.personal_recommendation
        asset = rec.asset

        # Map asset to trading symbol (add USDT suffix if needed)
        symbol = asset.upper()
        if not symbol.endswith("USDT"):
            symbol = symbol + "USDT"

        # Get risk parameters from PROFILE_RISK_LIMITS (single source of truth)
        profile = self._get_user_profile()
        risk_tol = profile.get("risk_tolerance") if profile else "moderate"
        limits = PROFILE_RISK_LIMITS.get(risk_tol, PROFILE_RISK_LIMITS["moderate"])
        sl_pct = limits["sl_range"][0]
        tp_pct = limits["tp_range"][1]

        if rec_type == "BUY":
            return {
                "type": "buy",
                "symbol": symbol,
                "confidence": rec.confidence,
                "stop_loss_pct": sl_pct,
                "take_profit_pct": tp_pct,
                "reason": rec.reason,
            }
        elif rec_type in ("TAKE_PARTIAL_PROFIT", "SELL_FULL"):
            return {
                "type": "sell",
                "symbol": symbol,
                "confidence": rec.confidence,
                "reason": rec.reason,
            }
        # HOLD, AVOID, WAIT → no action
        return None

    def _adjust_interval(self) -> None:
        """Adjust interval based on hold streak to save tokens."""
        if self._hold_streak >= 5:
            self._current_interval = min(self._base_interval * 10, 300)  # max 5 min
        elif self._hold_streak >= 3:
            self._current_interval = min(self._base_interval * 4, 120)   # max 2 min
        elif self._hold_streak >= 2:
            self._current_interval = min(self._base_interval * 2, 60)    # max 1 min
        else:
            self._current_interval = self._base_interval

    def _log_context_summary(self, context: dict) -> None:
        """Registra un resumen de lo que el agente está viendo."""
        parts = []

        acct = context.get("acc")
        if acct:
            parts.append(f"Cash: ${acct.get('cash', 'N/A')}, Equity: ${acct.get('eq', 'N/A')}, Posiciones: {acct.get('pos', 0)}")

        positions = context.get("positions", [])
        if positions:
            pos_summary = ", ".join(f"{p['s']} ({p.get('pnl', 'N/A')})" for p in positions[:5])
            parts.append(f"Posiciones: {pos_summary}")
        else:
            parts.append("Sin posiciones abiertas")

        spot = context.get("spot", {})
        spot_up = spot.get("up", [])
        if spot_up:
            parts.append(f"Spot top: {spot_up[0].get('s', '?')} +{spot_up[0].get('chg', '?')}%")

        fut = context.get("futures", {})
        fut_up = fut.get("up", [])
        if fut_up:
            parts.append(f"Futures top: {fut_up[0].get('s', '?')} +{fut_up[0].get('chg', '?')}%")

        rejections = context.get("rejections", [])
        if rejections:
            parts.append(f"Rechazos: {len(rejections)}")

        prices = context.get("prices", {})
        if prices:
            parts.append(f"Precios: {len(prices)} símbolos")

        self._add_log("info", " | ".join(parts), {
            "cycle": self._cycle,
            "phase": "context",
            "cash": acct.get("cash") if acct else None,
            "equity": acct.get("eq") if acct else None,
            "positions_count": len(positions),
            "spot_gainers": spot_up[:3] if spot_up else [],
            "futures_gainers": fut_up[:3] if fut_up else [],
            "rejections_count": len(rejections),
            "live_prices_count": len(prices),
        })

    def _gather_context(self) -> dict[str, Any]:
        """Recopila datos del sistema para enviar al LLM (comprimido para ahorrar tokens)."""
        try:
            ctx: dict[str, Any] = {}

            # User profile (so the LLM knows who it's trading for)
            profile = self._get_user_profile()
            if profile:
                ctx["user_profile"] = {
                    "experience": profile.get("experience_level"),
                    "risk_tolerance": profile.get("risk_tolerance"),
                    "strategies": profile.get("preferred_strategies", []),
                    "goal": profile.get("trading_goal"),
                    "capital_range": profile.get("capital_range"),
                }

            # Account (minimal fields)
            snapshots = self._api_get("/api/snapshots?limit=1")
            if isinstance(snapshots, list) and snapshots:
                snap = snapshots[0]
                ctx["acc"] = {
                    "cash": snap.get("cash"),
                    "eq": snap.get("equity"),
                    "pnl": snap.get("total_pnl"),
                    "pos": snap.get("open_positions_count"),
                }

            # Open positions (compact)
            positions = self._api_get("/api/positions?status=open&limit=10")
            if isinstance(positions, list):
                ctx["positions"] = [
                    {"s": p.get("symbol"), "qty": p.get("quantity"), "entry": p.get("entry_price"),
                     "cur": p.get("current_price"), "pnl": p.get("unrealized_pnl")}
                    for p in positions
                ]

            # Market movers - spot (top gainers/losers from Binance, filtered)
            movers_spot = self._api_get("/api/market/movers?market=spot&limit=50")
            movers_futures = self._api_get("/api/market/movers?market=futures&limit=50")
            if isinstance(movers_spot, dict):
                spot_up = [g for g in movers_spot.get("gainers", []) if self._is_tradeable(g.get("symbol", ""))][:20]
                spot_dn = [l for l in movers_spot.get("losers", []) if self._is_tradeable(l.get("symbol", ""))][:10]
                ctx["spot"] = {
                    "up": [{"s": g.get("symbol"), "p": g.get("price"), "chg": g.get("price_change_percent"), "vol": g.get("volume")} for g in spot_up],
                    "dn": [{"s": l.get("symbol"), "p": l.get("price"), "chg": l.get("price_change_percent")} for l in spot_dn],
                }
            if isinstance(movers_futures, dict):
                fut_up = [g for g in movers_futures.get("gainers", []) if self._is_tradeable(g.get("symbol", ""))][:20]
                fut_dn = [l for l in movers_futures.get("losers", []) if self._is_tradeable(l.get("symbol", ""))][:10]
                ctx["futures"] = {
                    "up": [{"s": g.get("symbol"), "p": g.get("price"), "chg": g.get("price_change_percent"), "vol": g.get("volume")} for g in fut_up],
                    "dn": [{"s": l.get("symbol"), "p": l.get("price"), "chg": l.get("price_change_percent")} for l in fut_dn],
                }

            # Live prices (only symbols we track)
            prices = self._api_get("/api/prices/live")
            if isinstance(prices, dict) and prices.get("prices"):
                ctx["prices"] = dict(list(prices.get("prices", {}).items())[:10])

            # Recent rejections (compact)
            risk_events = self._api_get("/api/risk-events?limit=3")
            if isinstance(risk_events, list) and risk_events:
                ctx["rejections"] = [{"s": e.get("symbol"), "r": e.get("reason")} for e in risk_events[:3]]

            # Technical analysis for tracked symbols + top movers
            try:
                from app.services.technical_analysis import analyze_symbol
                from app.config import get_settings
                settings = get_settings()
                tech_data = []

                # Start with tracked symbols from config
                tracked = list(settings.symbols_list[:10])

                # Also analyze ALL top spot gainers (more opportunities for the LLM)
                spot = ctx.get("spot", {})
                for g in spot.get("up", [])[:15]:
                    sym = g.get("s", "")
                    if sym and sym not in tracked:
                        tracked.append(sym)
                fut = ctx.get("futures", {})
                for g in fut.get("up", [])[:10]:
                    sym = g.get("s", "")
                    if sym and sym not in tracked:
                        tracked.append(sym)

                for sym in tracked[:30]:
                    try:
                        ta = analyze_symbol(sym, interval="1h")
                        tech_data.append({
                            "s": sym,
                            "sig": ta.signal,
                            "trend": ta.trend,
                            "rsi": ta.rsi,
                            "macd": ta.macd_signal,
                            "atr_pct": ta.atr_pct,
                            "vol_rel": ta.volume_relative,
                            "sl": ta.stop_loss,
                            "tp": ta.take_profit,
                            "reasons": ta.signal_reasons[:3],
                        })
                    except Exception:
                        continue
                if tech_data:
                    ctx["technical"] = tech_data

                    # Build ranked buy candidates for the LLM
                    buy_candidates = []
                    for t in tech_data:
                        sig = t.get("sig", "")
                        rsi = t.get("rsi", 50)
                        vol_rel = t.get("vol_rel", 1)
                        score = 0
                        if sig == "STRONG_BUY": score += 3
                        elif sig == "BUY": score += 2
                        if rsi < 30: score += 2
                        elif rsi < 40: score += 1
                        if vol_rel > 1.5: score += 1
                        if score > 0:
                            buy_candidates.append({"s": t["s"], "score": score, "sig": sig, "rsi": rsi, "vol_rel": vol_rel})
                    buy_candidates.sort(key=lambda x: x["score"], reverse=True)
                    ctx["buy_candidates"] = buy_candidates[:5]
            except Exception:
                pass

            return ctx

        except Exception as exc:
            self._add_log("error", f"Error recopilando contexto: {exc}")
            return {}

    # Cached set of valid Binance spot symbols
    _valid_symbols_cache: set[str] | None = None
    _valid_symbols_cache_time: float = 0
    # Allowed symbols loaded from config (DEFAULT_SYMBOLS)
    _allowed_symbols: set[str] | None = None

    def _get_allowed_symbols(self) -> set[str]:
        """Load allowed symbols from config DEFAULT_SYMBOLS.

        Returns empty set if no restriction is configured (allow all tradeable USDT pairs).
        """
        if self._allowed_symbols is None:
            try:
                from app.config import get_settings
                settings = get_settings()
                self._allowed_symbols = {s.strip().upper() for s in settings.DEFAULT_SYMBOLS.split(",") if s.strip()}
            except Exception:
                self._allowed_symbols = set()
        return self._allowed_symbols

    def _is_tradeable(self, symbol: str) -> bool:
        """Filter out leveraged tokens and non-USDT pairs.

        Does NOT restrict to DEFAULT_SYMBOLS — the agent can trade any
        valid USDT pair available on the broker.
        """
        s = symbol.upper().strip()
        if not s or not s.endswith("USDT"):
            return False
        # Filter out leveraged tokens
        for suffix in ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT"):
            if s.endswith(suffix):
                return False
        # Filter out obvious non-tradeable patterns
        if "UP" in s and s.endswith("UPUSDT") and not s.startswith("UP"):
            return False
        return True

    def _handle_llm_failure(self) -> bool:
        """Check if the LLM failure is critical (quota/auth/no-key) and stop the agent.

        Returns True if the agent was stopped (critical error), False if it can continue.
        """
        if not isinstance(self._ai_provider, LocalAIProvider):
            return False
        http_err = self._ai_provider.get_last_http_error()
        if not http_err:
            return False
        err_lower = http_err.lower()
        is_quota = "429" in err_lower or "rate limit" in err_lower or "quota" in err_lower
        is_auth = "401" in err_lower or "403" in err_lower or "invalid api key" in err_lower or "unauthorized" in err_lower
        is_no_key = "no hay" in err_lower and "api key" in err_lower
        if is_quota or is_auth or is_no_key:
            if is_quota:
                reason = f"Cuota agotada del proveedor {self.provider} (rate limit 429)"
            elif is_auth:
                reason = f"API Key inválida o no autorizada para {self.provider} (401/403)"
            else:
                reason = f"No hay API key configurada para {self.provider}"
            self._add_log("error", f"🛑 Agente detenido — {reason}. Detalle: {http_err}", {"phase": "llm_critical_error"})
            self._create_notif(
                "system_event",
                "AI Agent detenido",
                f"{reason}. Ve a Config e ingresa una API key válida para {self.provider}.",
                severity="critical",
            )
            self._stop_event.set()
            return True
        return False

    def _ask_llm(self, context: dict) -> dict | None:
        """Envía el contexto al proveedor de IA y recibe la decisión validada."""
        # Build dynamic prompt with profile block + optional few-shot
        prompt = self._build_system_prompt()

        user_msg = f"Datos:{json.dumps(context, default=str)}\nAnaliza y decide. SOLO JSON."
        decision = self._ask_and_validate(prompt, user_msg)
        if decision is None:
            repair_msg = user_msg + "\n\nTu respuesta anterior no cumplió el schema. Responde SOLO con el JSON corregido."
            decision = self._ask_and_validate(prompt, repair_msg)
        return decision

    def _build_system_prompt(self) -> str:
        """Build the system prompt with dynamic profile block and optional few-shot example."""
        prompt = SYSTEM_PROMPT

        # Add profile-specific rules block
        profile = self._get_user_profile()
        prompt += self._build_profile_prompt_block(profile)

        # Add few-shot example for lightweight models
        active_model = self._get_active_model()
        if active_model in LIGHTWEIGHT_MODELS:
            prompt += FEW_SHOT_EXAMPLE

        return prompt

    def _get_active_model(self) -> str:
        """Return the currently active model name for the selected provider."""
        if self.provider == "groq":
            return self.groq_model
        elif self.provider == "gemini":
            return self.gemini_model
        elif self.provider == "ollama":
            return self.ollama_model
        elif self.provider in ("openai", "deepseek", "mistral", "together", "perplexity", "grok"):
            return self.openai_model
        return ""

    def _build_profile_prompt_block(self, profile: dict | None) -> str:
        """Build a profile-specific rules block appended to the system prompt."""
        limits = PROFILE_RISK_LIMITS.get(
            (profile or {}).get("risk_tolerance", "moderate"),
            PROFILE_RISK_LIMITS["moderate"],
        )
        sl_lo, sl_hi = limits["sl_range"]
        tp_lo, tp_hi = limits["tp_range"]
        risk_tol = (profile or {}).get("risk_tolerance", "moderate")
        return (
            f"\n\nPERFIL ACTIVO: {risk_tol}. confianza mínima {limits['min_confidence']}, "
            f"stop_loss_pct entre {sl_lo}% y {sl_hi}%, take_profit_pct entre {tp_lo}% y {tp_hi}%, "
            f"máximo {limits['max_positions']} posiciones abiertas. El sistema ajustará estos valores "
            "si te sales de rango, así que respétalos desde el inicio. "
            "Referencia el perfil del usuario en analysis, risk_assessment y reason de cada acción."
        )

    def _ask_and_validate(self, system_prompt: str, user_msg: str) -> dict | None:
        """Send message to provider and validate response against AgentDecision schema."""
        response: AIResponse = self._ai_provider.ask(system_prompt, user_msg)
        if not response.success:
            self._log_provider_error(response)
            return None
        if isinstance(self._ai_provider, LocalAIProvider):
            for log_entry in self._ai_provider.get_logs():
                self._add_log("warn", log_entry)
        try:
            validated = AgentDecision.model_validate(response.decision)
            return validated.model_dump()
        except ValidationError as exc:
            self._add_log("warn", f"JSON del LLM no cumple el schema: {exc}")
            return None

    def _log_provider_error(self, response: AIResponse) -> None:
        """Log provider errors with differentiated messages."""
        err = response.error or "El proveedor de IA no respondió"
        err_lower = err.lower()
        if "429" in err_lower or "rate limit" in err_lower or "quota" in err_lower:
            self._add_log("error", f"Cuota agotada (429): {err}")
        elif "401" in err_lower or "403" in err_lower or "invalid api key" in err_lower or "unauthorized" in err_lower:
            self._add_log("error", f"API Key inválida o no autorizada: {err}")
        elif "timeout" in err_lower or "timed out" in err_lower:
            self._add_log("error", f"Timeout del proveedor: {err}")
        elif "connection" in err_lower or "refused" in err_lower or "unreachable" in err_lower:
            self._add_log("error", f"Error de conexión: {err}")
        else:
            self._add_log("error", err)

    def _apply_profile_guardrails(self, action: dict, open_positions: list | None = None) -> dict | None:
        """Valida y ajusta una acción de compra contra los límites duros del perfil.
        None = se descarta (HOLD). Modifica action in-place con SL/TP clampados."""
        profile = self._get_user_profile() or {}
        limits = PROFILE_RISK_LIMITS.get(
            profile.get("risk_tolerance", "moderate"),
            PROFILE_RISK_LIMITS["moderate"],
        )

        confidence = float(action.get("confidence", 0))
        if confidence < limits["min_confidence"]:
            self._add_log("info", f"{action.get('symbol')}: confianza {confidence} < mínimo {limits['min_confidence']} de tu perfil — descartada")
            return None

        # Count open positions (use provided list or fetch)
        if open_positions is not None:
            open_count = len(open_positions)
        else:
            positions = self._api_get("/api/positions?status=open&limit=20")
            open_count = len(positions) if isinstance(positions, list) else 0
        if open_count >= limits["max_positions"]:
            self._add_log("info", f"Máximo de posiciones para tu perfil ({limits['max_positions']}) alcanzado — no se compra {action.get('symbol')}")
            return None

        # Clamp SL/TP to profile range
        sl_lo, sl_hi = limits["sl_range"]
        tp_lo, tp_hi = limits["tp_range"]
        action["confidence"] = confidence
        action["stop_loss_pct"] = min(max(float(action.get("stop_loss_pct", sl_lo)), sl_lo), sl_hi)
        action["take_profit_pct"] = min(max(float(action.get("take_profit_pct", tp_lo)), tp_lo), tp_hi)
        return action

    def _execute_action(self, action: dict) -> None:
        """Ejecuta una acción de trading directamente via execution engine."""
        action_type = action.get("type", "").lower()
        symbol = action.get("symbol", "").upper()
        reason = action.get("reason", "")

        if not symbol:
            self._add_log("warn", f"Acción sin símbolo: {action}")
            return

        # Block trades for symbols outside allowed list
        if not self._is_tradeable(symbol):
            self._add_log("warn", f"Símbolo {symbol} no permitido. Solo se opera: {', '.join(sorted(self._get_allowed_symbols()))}")
            return

        if action_type == "buy":
            action = self._apply_profile_guardrails(action)
            if action is None:
                return
            confidence = action["confidence"]
            sl_pct = action["stop_loss_pct"]
            tp_pct = action["take_profit_pct"]
            self._add_log("info", f"Comprando {symbol} (confianza: {confidence}, SL: {sl_pct}%, TP: {tp_pct}%): {reason}")
            result = self._api_post("/api/ai-agent/execute", {
                "action_type": "buy",
                "symbol": symbol,
                "confidence": confidence,
                "reason": reason,
                "stop_loss_pct": sl_pct,
                "take_profit_pct": tp_pct,
            })
            if isinstance(result, dict) and result.get("status") == "executed":
                self._add_log("info", f"Compra {symbol} ejecutada: {result.get('quantity')} @ ${result.get('price')}")
                self._notify_telegram("buy", symbol, result.get("quantity", 0), result.get("price", 0), reason)
                self._create_notif("trade_executed", f"Compra ejecutada: {symbol}", f"Qty: {result.get('quantity')} @ ${result.get('price')} — {reason}", severity="info", asset=symbol.replace("USDT", ""))
            elif isinstance(result, dict) and result.get("status") == "rejected":
                self._add_log("warn", f"Compra {symbol} rechazada: {result.get('reason', 'risk manager')}")
                self._create_notif("risk_warning", f"Compra rechazada: {symbol}", result.get("reason", "Risk manager"), severity="warning", asset=symbol.replace("USDT", ""))
            elif isinstance(result, dict) and result.get("status") == "error":
                self._add_log("error", f"Error comprando {symbol}: {result.get('reason')}")
                self._create_notif("system_event", f"Error en compra: {symbol}", result.get("reason", "Error desconocido"), severity="critical", asset=symbol.replace("USDT", ""))
            else:
                self._add_log("warn", f"Respuesta inesperada: {result}")

        elif action_type == "sell":
            self._add_log("warn", f"IA intentó vender {symbol} pero las ventas son automáticas (stop-loss/take-profit). Ignorado.")

        else:
            self._add_log("warn", f"Tipo de acción desconocido: {action_type}")

    def _notify_telegram(self, action: str, symbol: str, quantity: float, price: float, reason: str = "") -> None:
        """Send Telegram notification to all users with alerts enabled."""
        try:
            from sqlalchemy import select

            from app.database.models.user import User
            from app.database.session import SessionLocal
            from app.services.telegram import notify_trade

            db = SessionLocal()
            try:
                users = db.execute(
                    select(User).where(User.telegram_alerts, User.telegram_chat_id.isnot(None))
                ).scalars().all()
                for user in users:
                    notify_trade(user.telegram_chat_id, action, symbol, float(quantity), float(price), reason)
            finally:
                db.close()
        except Exception:
            pass

    def _create_notif(self, type: str, title: str, message: str, severity: str = "info", asset: str | None = None, action_url: str | None = None) -> None:
        """Create a user notification in the DB."""
        try:
            from app.database.session import SessionLocal
            from app.services.notification_service import create_notification

            session = SessionLocal()
            try:
                create_notification(session, type=type, title=title, message=message, severity=severity, asset=asset, action_url=action_url)
            finally:
                session.close()
        except Exception:
            pass

    def analyze_positions(self, positions_data: list[dict], broker: str = "paper") -> None:
        """Run a one-shot analysis cycle for specific open positions.

        Gathers market context for the position symbols, sends to LLM with
        POSITION_ANALYSIS_PROMPT, and saves suggestions as AIRecommendation
        records with action_type='position_analysis'.
        """
        try:
            symbols = [p.get("symbol", "") for p in positions_data if p.get("symbol")]
            self._add_log("info", f"Análisis de posiciones iniciado para {len(positions_data)} posiciones: {', '.join(symbols)}", {
                "phase": "position_analysis_start", "positions": positions_data,
            })
            self._create_notif(
                "position_analysis_started",
                "Análisis de posiciones iniciado",
                f"Analizando {len(positions_data)} posiciones con IA. Te notificaremos al terminar.",
                severity="info",
            )

            # 1. Build context: user profile + positions + technical analysis
            ctx: dict[str, Any] = {}

            profile = self._get_user_profile()
            if profile:
                ctx["user_profile"] = {
                    "experience": profile.get("experience_level"),
                    "risk_tolerance": profile.get("risk_tolerance"),
                    "strategies": profile.get("preferred_strategies", []),
                    "goal": profile.get("trading_goal"),
                    "capital_range": profile.get("capital_range"),
                }

            ctx["open_positions"] = positions_data

            # 2. Gather technical analysis for each position's symbol (multi-timeframe)
            try:
                from app.services.technical_analysis import analyze_symbol
                tech_data = []
                for p in positions_data:
                    sym = p.get("symbol", "")
                    if not sym:
                        continue
                    try:
                        ta_1h = analyze_symbol(sym, interval="1h")
                        entry = {
                            "s": sym,
                            "sig": ta_1h.signal,
                            "trend": ta_1h.trend,
                            "rsi": ta_1h.rsi,
                            "macd": ta_1h.macd_signal,
                            "atr_pct": ta_1h.atr_pct,
                            "vol_rel": ta_1h.volume_relative,
                            "sl": ta_1h.stop_loss,
                            "tp": ta_1h.take_profit,
                            "reasons": ta_1h.signal_reasons[:3],
                        }
                        # Add 4h timeframe for deeper analysis
                        try:
                            ta_4h = analyze_symbol(sym, interval="4h")
                            entry["trend_4h"] = ta_4h.trend
                            entry["rsi_4h"] = ta_4h.rsi
                            entry["macd_4h"] = ta_4h.macd_signal
                            entry["atr_pct_4h"] = ta_4h.atr_pct
                        except Exception:
                            pass
                        tech_data.append(entry)
                    except Exception:
                        continue
                if tech_data:
                    ctx["technical"] = tech_data
            except Exception:
                pass

            # 3. Ask LLM with position analysis prompt — per position for deeper analysis
            self._add_log("info", f"Iniciando análisis profundo por posición ({len(positions_data)} posiciones)...", {
                "phase": "position_analysis_llm",
            })

            all_suggestions: list[dict] = []
            market_overview = ""
            risk_assessment = ""
            next_steps = ""

            for idx, pos in enumerate(positions_data):
                sym = pos.get("symbol", f"pos_{idx}")
                pos_start = time.monotonic()
                self._add_log("info", f"Analizando posición {idx+1}/{len(positions_data)}: {sym}...", {
                    "phase": "position_analysis_per_pos", "symbol": sym,
                })

                # Build per-position context
                pos_ctx: dict[str, Any] = {}
                if profile:
                    pos_ctx["user_profile"] = ctx.get("user_profile", {})
                pos_ctx["open_positions"] = [pos]
                # Include only this position's technical data
                pos_tech = [t for t in tech_data if t.get("s", "").upper() == sym.upper()]
                if pos_tech:
                    pos_ctx["technical"] = pos_tech

                pos_decision = self._ask_position_analysis_llm(pos_ctx)
                pos_elapsed = time.monotonic() - pos_start
                if pos_decision:
                    if not market_overview and pos_decision.get("market_overview"):
                        market_overview = pos_decision["market_overview"]
                    if not risk_assessment and pos_decision.get("risk_assessment"):
                        risk_assessment = pos_decision["risk_assessment"]
                    if not next_steps and pos_decision.get("next_steps"):
                        next_steps = pos_decision["next_steps"]
                    all_suggestions.extend(pos_decision.get("suggestions", []))
                    self._add_log("info", f"Análisis de {sym} completado en {pos_elapsed:.1f}s", {
                        "phase": "position_analysis_per_pos_done", "symbol": sym,
                        "suggestions": len(pos_decision.get("suggestions", [])),
                        "elapsed_seconds": round(pos_elapsed, 1),
                    })
                else:
                    self._add_log("warn", f"El LLM no respondió para {sym} tras {pos_elapsed:.1f}s", {
                        "phase": "position_analysis_per_pos_failed", "symbol": sym,
                        "elapsed_seconds": round(pos_elapsed, 1),
                    })

            if not all_suggestions:
                self._add_log("error", "El LLM no respondió al análisis de posiciones", {"phase": "position_analysis_error"})
                self._create_notif(
                    "position_analysis_error",
                    "Error en análisis de posiciones",
                    "La IA no respondió. Verifica tu configuración de AI Agent.",
                    severity="critical",
                )
                return

            # 4. Log the decision
            self._add_log("info", "Análisis de posiciones completado", {
                "phase": "position_analysis_decision",
                "market_overview": market_overview,
                "suggestions_count": len(all_suggestions),
                "risk_assessment": risk_assessment,
                "next_steps": next_steps,
            })

            # 5. Save suggestions as AIRecommendation records
            saved = self._save_position_analysis(all_suggestions, positions_data, broker)

            self._add_log("info", f"Análisis completado. {saved} sugerencias guardadas en Reportes.", {
                "phase": "position_analysis_done", "saved_count": saved,
            })
            self._create_notif(
                "position_analysis_completed",
                "Análisis de posiciones completado",
                f"{saved} sugerencias generadas. Revisa las sugerencias en Reportes.",
                severity="info",
                action_url="/reports",
            )

        except Exception as exc:
            self._add_log("error", f"Error en análisis de posiciones: {exc}", {"phase": "position_analysis_error"})
            self._create_notif(
                "position_analysis_error",
                "Error en análisis de posiciones",
                f"Error: {exc}",
                severity="critical",
            )

    def _ask_position_analysis_llm(self, context: dict) -> dict | None:
        """Send position context to LLM with POSITION_ANALYSIS_PROMPT and validate."""
        prompt = POSITION_ANALYSIS_PROMPT

        # Add profile-specific rules
        profile = self._get_user_profile()
        prompt += self._build_profile_prompt_block(profile)

        user_msg = f"Datos:{json.dumps(context, default=str)}\nAnaliza las posiciones y sugiere ajustes. SOLO JSON.\n\n⚠️ MÁXIMA PRIORIDAD: Dedica tu máximo esfuerzo y enfoque a este análisis. Sé exhaustivo, meticuloso y detallado para cada posición."
        try:
            response: AIResponse = self._ai_provider.ask(prompt, user_msg, deep=True)
        except TypeError:
            response: AIResponse = self._ai_provider.ask(prompt, user_msg)
        if not response.success:
            self._log_provider_error(response)
            return None
        if isinstance(self._ai_provider, LocalAIProvider):
            for log_entry in self._ai_provider.get_logs():
                self._add_log("warn", log_entry)
        try:
            validated = PositionAnalysisDecision.model_validate(response.decision)
            return validated.model_dump()
        except ValidationError as exc:
            self._add_log("warn", f"JSON del LLM no cumple schema de análisis de posiciones: {exc}")
            # Try repair
            repair_msg = user_msg + "\n\nTu respuesta anterior no cumplió el schema. Responde SOLO con el JSON corregido."
            try:
                response2: AIResponse = self._ai_provider.ask(prompt, repair_msg, deep=True)
            except TypeError:
                response2: AIResponse = self._ai_provider.ask(prompt, repair_msg)
            if not response2.success:
                self._log_provider_error(response2)
                return None
            try:
                validated = PositionAnalysisDecision.model_validate(response2.decision)
                return validated.model_dump()
            except ValidationError:
                return None

    def _save_position_analysis(self, suggestions: list[dict], positions_data: list[dict], broker: str) -> int:
        """Save position analysis suggestions as AIRecommendation records."""
        from app.database.session import SessionLocal
        from app.database.models.ai_recommendation import AIRecommendation

        # Build lookup of position data by symbol
        pos_map: dict[str, dict] = {}
        for p in positions_data:
            sym = p.get("symbol", "").upper()
            pos_map[sym] = p

        session = SessionLocal()
        try:
            saved_count = 0
            for sug in suggestions:
                symbol = sug.get("symbol", "").upper()
                asset = symbol.replace("USDT", "").replace("USDC", "")
                pos_data = pos_map.get(symbol, {})

                # Normalize confidence
                raw_conf = sug.get("confidence", 0)
                conf_val = float(raw_conf)
                if conf_val > 1:
                    conf_val = conf_val / 100.0

                current_sl = pos_data.get("stop_loss")
                current_tp = pos_data.get("take_profit")

                suggested_sl = sug.get("suggested_stop_loss")
                suggested_tp = sug.get("suggested_take_profit")
                pos_side = (pos_data.get("side") or sug.get("side") or "long").lower()
                current_price = pos_data.get("current_price")

                # Validate and fix SL/TP direction based on side
                if suggested_sl and suggested_tp and current_price:
                    try:
                        sl_f = float(suggested_sl)
                        tp_f = float(suggested_tp)
                        cp_f = float(current_price)
                        if pos_side in ("long", "buy"):
                            if sl_f > cp_f and tp_f < cp_f:
                                # SL above and TP below for LONG — inverted, swap them
                                suggested_sl, suggested_tp = suggested_tp, suggested_sl
                                self._add_log("warn", f"SL/TP invertidos para {symbol} LONG — corregido: SL={suggested_sl}, TP={suggested_tp}")
                            elif sl_f > cp_f:
                                # SL above current price for LONG — move below
                                suggested_sl = cp_f * 0.97
                                self._add_log("warn", f"SL arriba del precio para {symbol} LONG — ajustado a {suggested_sl}")
                            elif tp_f < cp_f:
                                # TP below current price for LONG — move above
                                suggested_tp = cp_f * 1.03
                                self._add_log("warn", f"TP abajo del precio para {symbol} LONG — ajustado a {suggested_tp}")
                        elif pos_side in ("short", "sell"):
                            if sl_f < cp_f and tp_f > cp_f:
                                # SL below and TP above for SHORT — inverted, swap them
                                suggested_sl, suggested_tp = suggested_tp, suggested_sl
                                self._add_log("warn", f"SL/TP invertidos para {symbol} SHORT — corregido: SL={suggested_sl}, TP={suggested_tp}")
                            elif sl_f < cp_f:
                                suggested_sl = cp_f * 1.03
                                self._add_log("warn", f"SL abajo del precio para {symbol} SHORT — ajustado a {suggested_sl}")
                            elif tp_f > cp_f:
                                suggested_tp = cp_f * 0.97
                                self._add_log("warn", f"TP arriba del precio para {symbol} SHORT — ajustado a {suggested_tp}")
                    except (ValueError, TypeError):
                        pass

                rec = AIRecommendation(
                    user_id=self._user_id,
                    asset=asset,
                    action_type="position_analysis",
                    confidence=conf_val,
                    reason=sug.get("reason", ""),
                    stop_loss_pct=None,
                    take_profit_pct=None,
                    status="pending",
                    trading_mode="live",
                    broker_name=broker,
                    metadata_json={
                        "position_id": sug.get("position_id") or pos_data.get("id"),
                        "symbol": symbol,
                        "side": pos_side,
                        "current_sl": current_sl,
                        "current_tp": current_tp,
                        "suggested_sl": suggested_sl,
                        "suggested_tp": suggested_tp,
                        "time_horizon": sug.get("time_horizon", ""),
                        "entry_price": pos_data.get("entry_price"),
                        "current_price": pos_data.get("current_price"),
                        "quantity": pos_data.get("quantity"),
                        "unrealized_pnl": pos_data.get("unrealized_pnl"),
                        "detailed_analysis": sug.get("detailed_analysis", ""),
                    },
                )
                session.add(rec)
                saved_count += 1

            session.commit()

            # Clear reports cache
            try:
                from app.api.routes.intelligence import _clear_cache
                _clear_cache("reports_")
            except Exception:
                pass

            return saved_count
        except Exception as exc:
            session.rollback()
            self._add_log("error", f"Error guardando sugerencias: {exc}")
            return 0
        finally:
            session.close()

    def _api_get(self, path: str) -> Any:
        try:
            resp = httpx.get(f"{self.api_base}{path}", timeout=15.0)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def _api_post(self, path: str, json_body: dict) -> Any:
        try:
            resp = httpx.post(f"{self.api_base}{path}", json=json_body, timeout=15.0)
            if resp.status_code < 400:
                return resp.json()
            return {"error": f"HTTP {resp.status_code}", "detail": resp.text}
        except Exception as exc:
            return {"error": str(exc)}
