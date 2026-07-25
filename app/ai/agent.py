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
from threading import Event, Thread
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres un agente de trading que SOLO COMPRA. Devuelves SOLO JSON:
{"market_overview":"...","portfolio_status":"...","analysis":"...","actions":[{"type":"buy","symbol":"BTCUSDT","confidence":0.8,"stop_loss_pct":3,"take_profit_pct":8,"reason":"..."}],"risk_assessment":"...","next_steps":"..."}

SOLO COMPRAS. Las ventas son automáticas con trailing stop (protege profit, nunca deja volver a loss) y take-profit. NO incluyas "sell".

Reglas: actions=[] si no hay oportunidad clara. confidence 0-1. Cash>$5000=suficiente. SOLO usa símbolos de spot.up, spot.dn, futures.up, futures.dn o positions.

CADA COMPRA debe incluir:
- stop_loss_pct: % de pérdida máxima (2-5% según volatilidad)
- take_profit_pct: % de ganancia objetivo (5-15% según potencial)

DIVERSIFICACIÓN: Compra símbolos DIFERENTES cada ciclo. NO compres un símbolo que ya está en positions. Busca ALTO POTENCIAL a corto plazo: gainers con momentum positivo y volumen alto."""


class AITradingAgent:
    """Agente de IA que analiza el mercado y ejecuta trades automáticamente."""

    def __init__(
        self,
        provider: str = "groq",
        groq_api_key: str | None = None,
        groq_model: str = "llama-3.1-8b-instant",
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen2.5:14b",
        api_base: str = "http://127.0.0.1:8080",
        interval_seconds: int = 30,
        auto_trade: bool = True,
    ) -> None:
        self.provider = provider
        self.groq_api_key = groq_api_key
        self.groq_model = groq_model
        self.ollama_url = ollama_url.rstrip("/")
        self.ollama_model = ollama_model
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
        self._position_peaks: dict[str, float] = {}  # symbol -> highest price seen

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def get_log(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._log[-limit:]))

    def get_status(self) -> dict:
        return {
            "is_running": self.is_running,
            "provider": self.provider,
            "model": self.groq_model if self.provider == "groq" else self.ollama_model,
            "interval_seconds": self.interval,
            "current_interval": self._current_interval,
            "hold_streak": self._hold_streak,
            "auto_trade": self.auto_trade,
            "cycles": self._cycle,
            "last_log_count": len(self._log),
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

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._cycle += 1
                self._tick()
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
        """Check open positions with trailing stop logic.
        
        Phases:
        1. Below entry: use original stop-loss
        2. Above entry (in profit): stop moves to breakeven (entry price)
        3. Peak tracking: stop trails at 2% below the highest price seen
        4. Never lets a profitable position go back to loss
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

                if not symbol or not stop_loss or not take_profit or not entry_price:
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

                entry = float(entry_price)
                original_sl = float(stop_loss)
                tp = float(take_profit)

                # Track peak price for this position
                peak = self._position_peaks.get(symbol, entry)
                if current_price > peak:
                    peak = current_price
                    self._position_peaks[symbol] = peak

                # Determine the effective stop-loss based on trailing logic
                if current_price <= entry:
                    # Below or at entry: use original stop-loss
                    effective_sl = original_sl
                elif current_price > entry and peak <= entry * 1.02:
                    # Just barely in profit (< 2% up): stop at breakeven
                    effective_sl = entry
                else:
                    # Clearly in profit: trail at 2% below peak, but never below entry
                    trailing_sl = peak * 0.98
                    effective_sl = max(entry, trailing_sl)

                # Check if we should sell
                if current_price <= effective_sl:
                    if effective_sl == entry and current_price < entry:
                        # Selling at breakeven to avoid loss
                        self._add_log("warn", f"BREAKEVEN STOP {symbol}: precio ${current_price:.4f} bajó hacia entry ${entry:.4f}. Vendiendo para proteger capital.", {
                            "phase": "auto_breakeven", "symbol": symbol, "price": current_price, "entry": entry, "peak": peak,
                        })
                        reason = f"Auto breakeven-stop: protegía profit, precio volvió a ${current_price}"
                    elif effective_sl > entry:
                        # Trailing stop hit - we had a good run
                        self._add_log("info", f"TRAILING STOP {symbol}: precio ${current_price:.4f} bajó del peak ${peak:.4f}. Vendiendo con profit asegurado.", {
                            "phase": "auto_trailing", "symbol": symbol, "price": current_price, "entry": entry, "peak": peak,
                        })
                        reason = f"Auto trailing-stop: peak fue ${peak:.4f}, vendiendo a ${current_price}"
                    else:
                        # Original stop-loss
                        self._add_log("warn", f"STOP-LOSS {symbol}: precio ${current_price:.4f} <= SL ${effective_sl:.4f}. Vendiendo.", {
                            "phase": "auto_stop_loss", "symbol": symbol, "price": current_price, "stop_loss": effective_sl,
                        })
                        reason = f"Auto stop-loss: precio bajó a ${current_price}"

                    result = self._api_post("/api/ai-agent/execute", {
                        "action_type": "sell",
                        "symbol": symbol,
                        "confidence": 1.0,
                        "reason": reason,
                    })
                    if result and result.get("status") == "executed":
                        pnl_pct = ((current_price - entry) / entry) * 100
                        emoji = "🎉" if current_price > entry else "🛡️" if current_price >= entry * 0.999 else "⚠️"
                        self._add_log("info", f"{emoji} Venta {symbol} ejecutada @ ${current_price:.4f} (PnL: {pnl_pct:+.2f}%)")
                        # Clean up peak tracking
                        self._position_peaks.pop(symbol, None)
                    else:
                        self._add_log("error", f"Auto-sell falló para {symbol}: {result}")

                elif current_price >= tp:
                    # Take-profit hit
                    self._add_log("info", f"TAKE-PROFIT {symbol}: precio ${current_price:.4f} >= TP ${tp:.4f}. Vendiendo.", {
                        "phase": "auto_take_profit", "symbol": symbol, "price": current_price, "take_profit": tp,
                    })
                    result = self._api_post("/api/ai-agent/execute", {
                        "action_type": "sell",
                        "symbol": symbol,
                        "confidence": 1.0,
                        "reason": f"Auto take-profit: precio subió a ${current_price}",
                    })
                    if result and result.get("status") == "executed":
                        pnl_pct = ((current_price - entry) / entry) * 100
                        self._add_log("info", f"🎉 Take-profit {symbol} ejecutado @ ${current_price:.4f} (PnL: {pnl_pct:+.2f}%)")
                        self._position_peaks.pop(symbol, None)
                    else:
                        self._add_log("error", f"Take-profit falló para {symbol}: {result}")
                else:
                    # Position still open - log trailing status occasionally
                    if peak > entry * 1.01:
                        # Only log if in profit > 1%
                        trail_sl = max(entry, peak * 0.98)
                        profit_pct = ((current_price - entry) / entry) * 100
                        # Log every significant peak update
                        if peak == current_price and profit_pct > 2:
                            self._add_log("info", f"📈 {symbol} subiendo: ${current_price:.4f} (PnL: {profit_pct:+.2f}%, peak: ${peak:.4f}, trailing SL: ${trail_sl:.4f})", {
                                "phase": "trailing_update", "symbol": symbol, "price": current_price, "peak": peak, "trailing_sl": trail_sl,
                            })

        except Exception as exc:
            logger.error(f"[AI Agent] Error en auto-close: {exc}")

    def _tick(self) -> None:
        self._add_log("info", f"--- Ciclo {self._cycle} iniciado ---", {"cycle": self._cycle, "phase": "start"})

        # 1. Gather context from the trading system
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
            return

        # Log the full decision with all fields
        self._add_log("info", f"Análisis completado", {
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
            movers_spot = self._api_get("/api/market/movers?market=spot&limit=20")
            movers_futures = self._api_get("/api/market/movers?market=futures&limit=20")
            if isinstance(movers_spot, dict):
                spot_up = [g for g in movers_spot.get("gainers", []) if self._is_tradeable(g.get("symbol", ""))][:10]
                spot_dn = [l for l in movers_spot.get("losers", []) if self._is_tradeable(l.get("symbol", ""))][:5]
                ctx["spot"] = {
                    "up": [{"s": g.get("symbol"), "p": g.get("price"), "chg": g.get("price_change_percent"), "vol": g.get("volume")} for g in spot_up],
                    "dn": [{"s": l.get("symbol"), "p": l.get("price"), "chg": l.get("price_change_percent")} for l in spot_dn],
                }
            if isinstance(movers_futures, dict):
                fut_up = [g for g in movers_futures.get("gainers", []) if self._is_tradeable(g.get("symbol", ""))][:10]
                fut_dn = [l for l in movers_futures.get("losers", []) if self._is_tradeable(l.get("symbol", ""))][:5]
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
        """Load allowed symbols from config DEFAULT_SYMBOLS."""
        if self._allowed_symbols is None:
            try:
                from app.config import get_settings
                settings = get_settings()
                self._allowed_symbols = {s.strip().upper() for s in settings.DEFAULT_SYMBOLS.split(",") if s.strip()}
            except Exception:
                # Fallback: allow all tradeable USDT pairs
                self._allowed_symbols = set()
        return self._allowed_symbols

    def _is_tradeable(self, symbol: str) -> bool:
        """Filter out leveraged tokens and validate symbol exists on Binance.

        If DEFAULT_SYMBOLS is configured, only allow those symbols.
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
        # If we have an allowed symbols list, enforce it
        allowed = self._get_allowed_symbols()
        if allowed and s not in allowed:
            return False
        return True

    def _ask_llm(self, context: dict) -> dict | None:
        """Envía el contexto al LLM y recibe la decisión."""
        user_msg = f"Datos:{json.dumps(context,default=str)}\nAnaliza y decide. SOLO JSON."

        if self.provider == "groq":
            result = self._ask_groq(user_msg)
            if result is None:
                self._add_log("warn", "Groq no disponible, intentando con Ollama local...")
                result = self._ask_ollama(user_msg)
                if result is None:
                    self._add_log("error", "Ni Groq ni Ollama disponibles. Revisa tu conexión o API key.")
                else:
                    self._add_log("info", "Ollama respondió correctamente (fallback exitoso)")
            return result
        elif self.provider == "ollama":
            return self._ask_ollama(user_msg)
        else:
            self._add_log("error", f"Provider desconocido: {self.provider}")
            return None

    def _ask_groq(self, user_msg: str) -> dict | None:
        """Consulta a Groq API (gratis, rápido)."""
        if not self.groq_api_key:
            self._add_log("error", "GROQ_API_KEY no configurada")
            return None
        try:
            resp = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.groq_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.groq_model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1000,
                    "response_format": {"type": "json_object"},
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return self._parse_response(content)
        except httpx.HTTPStatusError as exc:
            self._add_log("error", f"Groq API error {exc.response.status_code}: {exc.response.text[:200]}")
            return None
        except Exception as exc:
            self._add_log("error", f"Error consultando Groq: {exc}")
            return None

    def _ask_ollama(self, user_msg: str) -> dict | None:
        """Consulta a Ollama local."""
        try:
            resp = httpx.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.ollama_model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.3},
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            content = resp.json()["message"]["content"]
            return self._parse_response(content)
        except Exception as exc:
            self._add_log("error", f"Error consultando Ollama: {exc}")
            return None

    def _parse_response(self, content: str) -> dict | None:
        """Parsea la respuesta del LLM como JSON."""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Intentar extraer JSON de la respuesta
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(content[start:end])
                except json.JSONDecodeError:
                    pass
            self._add_log("error", f"Respuesta no es JSON válido: {content[:200]}")
            return None

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
            confidence = action.get("confidence", 0.7)
            sl_pct = action.get("stop_loss_pct", 3)
            tp_pct = action.get("take_profit_pct", 8)
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
            elif isinstance(result, dict) and result.get("status") == "rejected":
                self._add_log("warn", f"Compra {symbol} rechazada: {result.get('reason', 'risk manager')}")
            elif isinstance(result, dict) and result.get("status") == "error":
                self._add_log("error", f"Error comprando {symbol}: {result.get('reason')}")
            else:
                self._add_log("warn", f"Respuesta inesperada: {result}")

        elif action_type == "sell":
            self._add_log("warn", f"IA intentó vender {symbol} pero las ventas son automáticas (stop-loss/take-profit). Ignorado.")

        else:
            self._add_log("warn", f"Tipo de acción desconocido: {action_type}")

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
