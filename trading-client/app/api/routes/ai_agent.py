"""AI Agent endpoints (start, stop, execute, stats, binance balance, trading mode, kill switch)."""

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

import app.api.state as state
from app.api.helpers import (
    create_ai_snapshot,
    get_or_create_agent,
    get_shared_broker,
    resolve_binancekeys,
    resolve_broker_credentials,
)
from app.config import get_settings
from app.database.session import SessionLocal
from app.services.auth import LocalUser, get_current_user
from app.services.crypto import decrypt
from app.services.rate_limit import get_plan_limits

router = APIRouter(prefix="/api", tags=["ai-agent"])


class AIStartRequest(BaseModel):
    provider: str | None = None
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    premium_api_key: str | None = None
    premium_base_url: str | None = None
    model: str | None = None
    interval_seconds: int | None = None
    auto_trade: bool | None = None


class AIExecuteRequest(BaseModel):
    """Payload para que el agente IA ejecute una operación directamente."""
    action_type: str  # "buy" o "sell"
    symbol: str
    confidence: float = 0.7
    reason: str = ""
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None


@router.post("/ai-agent/start")
def ai_agent_start(
    request: Request,
    req: AIStartRequest = AIStartRequest(),
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Inicia el agente de IA autónomo.

    Key resolution order:
    1. User-provided keys in request body (from UI input)
    2. User's stored encrypted keys (from settings)
    3. Server .env keys (fallback for FREE users)

    Interval is enforced based on plan:
    - FREE: min 120s
    - PRO: min 15s
    - PREMIUM: min 10s
    """
    agent = get_or_create_agent()
    settings = get_settings()

    # Resolve provider
    provider = req.provider or getattr(settings, "AI_PROVIDER", "groq")
    agent.provider = provider

    # Resolve API keys: request > user stored > .env
    groq_key = req.groq_api_key
    gemini_key = req.gemini_api_key

    if not groq_key and current_user and current_user.ai_groq_key_enc:
        try:
            groq_key = decrypt(current_user.ai_groq_key_enc)
        except Exception:
            pass
    if not gemini_key and current_user and current_user.ai_gemini_key_enc:
        try:
            gemini_key = decrypt(current_user.ai_gemini_key_enc)
        except Exception:
            pass

    if not groq_key:
        groq_key = getattr(settings, "GROQ_API_KEY", None)
    if not gemini_key:
        gemini_key = getattr(settings, "GEMINI_API_KEY", None)

    if groq_key:
        agent.groq_api_key = groq_key
    if gemini_key:
        agent.gemini_api_key = gemini_key

    # Resolve model
    if req.model:
        if provider == "groq":
            agent.groq_model = req.model
        elif provider == "gemini":
            agent.gemini_model = req.model
        elif provider in ("openai", "deepseek", "mistral", "together", "perplexity", "grok"):
            agent.openai_model = req.model
        else:
            agent.ollama_model = req.model

    # Resolve premium provider key + base URL: request > user stored
    PREMIUM_BASE_URLS = {
        "openai": "https://api.openai.com/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "mistral": "https://api.mistral.ai/v1",
        "together": "https://api.together.xyz/v1",
        "perplexity": "https://api.perplexity.ai",
        "grok": "https://api.x.ai/v1",
    }
    if provider in PREMIUM_BASE_URLS:
        premium_key = req.premium_api_key
        if not premium_key and current_user and current_user.ai_premium_key_enc:
            try:
                premium_key = decrypt(current_user.ai_premium_key_enc)
            except Exception:
                pass
        if premium_key:
            agent.openai_api_key = premium_key
        base_url = req.premium_base_url or (current_user.ai_premium_base_url if current_user else None) or PREMIUM_BASE_URLS[provider]
        agent.openai_base_url = base_url
        if req.model:
            agent.openai_model = req.model
        elif current_user and current_user.ai_premium_model:
            agent.openai_model = current_user.ai_premium_model

    # Enforce plan-based interval minimum
    if current_user:
        limits = get_plan_limits(current_user.subscription)
        min_interval = limits["max_ai_interval_seconds"]
    else:
        min_interval = 10

    requested_interval = req.interval_seconds if req.interval_seconds is not None else agent.interval
    if requested_interval < min_interval:
        requested_interval = min_interval
    agent.interval = requested_interval

    if req.auto_trade is not None:
        agent.auto_trade = req.auto_trade

    # Capture JWT token for AI agent grant requests
    jwt_token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if jwt_token:
        state.ai_jwt_token = jwt_token
        agent._jwt_token = jwt_token
        settings = get_settings()
        agent._auth_server_url = settings.AUTH_SERVER_URL

    agent.start()
    # Create initial snapshot so overview tab shows data
    try:
        keys = resolve_binance_keys(current_user)
        broker = get_shared_broker(keys)
        create_ai_snapshot(broker)
    except Exception:
        pass
    return agent.get_status()


@router.post("/ai-agent/stop")
def ai_agent_stop() -> dict:
    """Detiene el agente de IA."""
    agent = get_or_create_agent()
    agent.stop()
    agent._jwt_token = None
    agent._grant_fail_streak = 0
    state.ai_jwt_token = None
    return agent.get_status()


@router.post("/ai-agent/test-key")
def ai_agent_test_key(
    req: AIStartRequest = AIStartRequest(),
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Test if the selected AI provider's API key is valid by sending a minimal request."""
    import requests as req_lib

    settings = get_settings()
    provider = req.provider or getattr(settings, "AI_PROVIDER", "groq")

    # Resolve keys: request > user stored > .env
    groq_key = req.groq_api_key
    gemini_key = req.gemini_api_key
    if not groq_key and current_user and current_user.ai_groq_key_enc:
        try:
            groq_key = decrypt(current_user.ai_groq_key_enc)
        except Exception:
            pass
    if not gemini_key and current_user and current_user.ai_gemini_key_enc:
        try:
            gemini_key = decrypt(current_user.ai_gemini_key_enc)
        except Exception:
            pass
    if not groq_key:
        groq_key = getattr(settings, "GROQ_API_KEY", None)
    if not gemini_key:
        gemini_key = getattr(settings, "GEMINI_API_KEY", None)

    model = req.model or getattr(settings, "AI_MODEL", "")

    try:
        if provider == "groq":
            if not groq_key:
                return {"ok": False, "error": "GROQ_API_KEY no configurada"}
            resp = req_lib.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                json={"model": model or "llama-3.1-8b-instant", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5},
                timeout=15,
            )
            if resp.status_code == 200:
                return {"ok": True, "provider": "Groq", "model": model or "llama-3.1-8b-instant"}
            return {"ok": False, "error": f"Groq API error {resp.status_code}: {resp.text[:200]}"}

        elif provider == "gemini":
            if not gemini_key:
                return {"ok": False, "error": "GEMINI_API_KEY no configurada"}
            gemini_model = model or "gemini-2.0-flash"
            resp = req_lib.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={gemini_key}",
                headers={"Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": "Hi"}]}], "generationConfig": {"maxOutputTokens": 5}},
                timeout=15,
            )
            if resp.status_code == 200:
                return {"ok": True, "provider": "Gemini", "model": gemini_model}
            return {"ok": False, "error": f"Gemini API error {resp.status_code}: {resp.text[:200]}"}

        elif provider == "ollama":
            ollama_url = getattr(settings, "OLLAMA_URL", "http://localhost:11434")
            ollama_model = model or getattr(settings, "OLLAMA_MODEL", "qwen2.5:14b")
            try:
                resp = req_lib.post(
                    f"{ollama_url}/api/chat",
                    json={"model": ollama_model, "messages": [{"role": "user", "content": "Hi"}], "stream": False},
                    timeout=10,
                )
                if resp.status_code == 200:
                    return {"ok": True, "provider": "Ollama", "model": ollama_model}
                return {"ok": False, "error": f"Ollama error {resp.status_code}: {resp.text[:200]}"}
            except Exception as exc:
                return {"ok": False, "error": f"Ollama no disponible: {exc}"}

        elif provider in ("openai", "deepseek", "mistral", "together", "perplexity", "grok"):
            PREMIUM_BASE_URLS = {
                "openai": "https://api.openai.com/v1",
                "deepseek": "https://api.deepseek.com/v1",
                "mistral": "https://api.mistral.ai/v1",
                "together": "https://api.together.xyz/v1",
                "perplexity": "https://api.perplexity.ai",
                "grok": "https://api.x.ai/v1",
            }
            premium_key = req.premium_api_key
            if not premium_key and current_user and current_user.ai_premium_key_enc:
                try:
                    premium_key = decrypt(current_user.ai_premium_key_enc)
                except Exception:
                    pass
            if not premium_key:
                return {"ok": False, "error": f"{provider.upper()}_API_KEY no configurada"}
            base_url = req.premium_base_url or (current_user.ai_premium_base_url if current_user else None) or PREMIUM_BASE_URLS[provider]
            resp = req_lib.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {premium_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5},
                timeout=15,
            )
            if resp.status_code == 200:
                return {"ok": True, "provider": provider, "model": model}
            return {"ok": False, "error": f"{provider} API error {resp.status_code}: {resp.text[:200]}"}

        else:
            return {"ok": False, "error": f"Provider '{provider}' no soportado"}

    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/ai-agent/status")
def ai_agent_status() -> dict:
    """Obtiene el estado del agente de IA."""
    agent = get_or_create_agent()
    return agent.get_status()


@router.get("/ai-agent/log")
def ai_agent_log(limit: int = Query(50, ge=1, le=200)) -> list[dict]:
    """Obtiene el log de decisiones del agente de IA."""
    agent = get_or_create_agent()
    return agent.get_log(limit=limit)


@router.patch("/ai-agent/interval")
def ai_agent_set_interval(interval_seconds: int = Query(30, ge=10)) -> dict:
    """Cambia el intervalo de análisis del agente de IA."""
    agent = get_or_create_agent()
    agent.set_interval(interval_seconds)
    return agent.get_status()


@router.get("/binance/balance")
def get_binance_balance(
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Consulta el saldo real de Binance en tiempo real.

    Retorna todos los activos con balance > 0, valor en USD y MXN.
    Usa las API keys del usuario logueado (o .env como fallback).
    """
    import httpx as _httpx

    settings = get_settings()
    if settings.BROKER_PROVIDER != "binance":
        return {"error": "Binance no configurado", "assets": [], "total_usd": 0, "total_mxn": 0}

    creds = resolve_broker_credentials("binance", current_user)
    if not creds:
        return {"error": "No tienes API keys de Binance configuradas. Ve a Settings para ingresarlas.", "assets": [], "total_usd": 0, "total_mxn": 0}

    from app.brokers.adapters.binance_adapter import BinanceAdapter

    adapter = BinanceAdapter(creds)

    try:
        balances = adapter.get_account_balances()
    except Exception as exc:
        return {"error": f"No se pudo conectar a Binance: {exc}", "assets": [], "total_usd": 0, "total_mxn": 0}

    assets = []
    total_usd = 0.0

    # Get MXN/USDT rate (USDTMXN exists on Binance)
    mxn_rate = 0.0
    try:
        r = _httpx.get("https://api.binance.com/api/v3/ticker/price", params={"symbol": "USDTMXN"}, timeout=5)
        if r.status_code == 200:
            mxn_rate = float(r.json()["price"])
    except Exception:
        pass
    if mxn_rate == 0:
        mxn_rate = 18.5  # fallback approximate

    for b in balances:
        free = float(b.free)
        locked = float(b.locked)
        total = free + locked
        if total <= 0:
            continue

        asset = b.asset
        usd_value = 0.0

        if asset in ("USDT", "BUSD", "USDC", "UST", "USD", "EUR"):
            usd_value = total
            if asset == "EUR":
                # EUR is ~1.08 USD, try to get exact rate
                try:
                    r = _httpx.get("https://api.binance.com/api/v3/ticker/price", params={"symbol": "EURUSDT"}, timeout=5)
                    if r.status_code == 200:
                        usd_value = total * float(r.json()["price"])
                except Exception:
                    usd_value = total * 1.08
        elif asset == "MXN":
            usd_value = total / mxn_rate
        else:
            # Try to get price in USDT
            try:
                r = _httpx.get(
                    "https://api.binance.com/api/v3/ticker/price",
                    params={"symbol": f"{asset}USDT"},
                    timeout=5,
                )
                if r.status_code == 200:
                    usd_value = total * float(r.json()["price"])
            except Exception:
                pass

        total_usd += usd_value
        assets.append({
            "asset": asset,
            "free": free,
            "locked": locked,
            "total": total,
            "usd_value": round(usd_value, 4),
        })

    # Sort by USD value descending
    assets.sort(key=lambda x: x["usd_value"], reverse=True)

    # Find USDT specifically
    usdt_asset = next((a for a in assets if a["asset"] == "USDT"), None)
    usdt_free = usdt_asset["free"] if usdt_asset else 0.0
    usdt_total = usdt_asset["total"] if usdt_asset else 0.0

    return {
        "assets": assets,
        "total_usd": round(total_usd, 2),
        "total_mxn": round(total_usd * mxn_rate, 2),
        "mxn_rate": round(mxn_rate, 4),
        "testnet": settings.BINANCE_TESTNET,
        "usdt_free": round(usdt_free, 4),
        "usdt_total": round(usdt_total, 4),
        "usdt_mxn": round(usdt_total * mxn_rate, 2),
        "usdt_usd": round(usdt_total, 2),
    }


@router.patch("/ai-agent/auto-trade")
def ai_agent_set_auto_trade(enabled: bool = Query(True)) -> dict:
    """Habilita o deshabilita la ejecución automática de trades."""
    agent = get_or_create_agent()
    agent.auto_trade = enabled
    return agent.get_status()


@router.get("/trading-mode")
def get_trading_mode(
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Retorna el modo de trading actual y configuración de safety."""
    settings = get_settings()
    is_live = settings.TRADING_MODE == "live" and settings.LIVE_TRADING_ENABLED
    keys = resolve_binance_keys(current_user)
    is_binance = settings.BROKER_PROVIDER == "binance" and bool(keys)
    # Use runtime override if set, otherwise use config value
    allocated = state.ai_allocated_capital if state.ai_allocated_capital > 0 else settings.AI_ALLOCATED_CAPITAL
    return {
        "mode": "live" if is_live else "paper",
        "broker": "binance" if is_binance else "mock",
        "testnet": settings.BINANCE_TESTNET,
        "kill_switch": settings.LIVE_KILL_SWITCH,
        "max_order_usd": settings.LIVE_MAX_ORDER_USD,
        "daily_loss_limit_usd": settings.LIVE_DAILY_LOSS_LIMIT_USD,
        "confirmation_required": settings.LIVE_CONFIRMATION_REQUIRED,
        "allocated_capital": allocated,
    }


@router.patch("/ai-agent/capital")
def set_ai_capital(amount: float = Query(0, ge=0)) -> dict:
    """Asigna cuánto capital (USD) puede usar el AI Agent para trading.

    Set 0 para usar todo el saldo disponible de la cuenta.
    Persiste el valor en .env para que sobreviva reinicios del server.
    """
    state.ai_allocated_capital = amount

    # Persist to .env file
    from pathlib import Path
    env_path = Path(".env")
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
        found = False
        new_lines = []
        for line in lines:
            if line.startswith("AI_ALLOCATED_CAPITAL="):
                new_lines.append(f"AI_ALLOCATED_CAPITAL={amount}")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"AI_ALLOCATED_CAPITAL={amount}")
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        os.environ["AI_ALLOCATED_CAPITAL"] = str(amount)
        # Clear cached settings
        get_settings.cache_clear()

    return {
        "allocated_capital": amount,
        "message": f"Capital asignado: ${amount:.2f} USD" if amount > 0 else "Usando todo el saldo disponible",
    }


@router.patch("/kill-switch")
def toggle_kill_switch(enabled: bool = Query(True)) -> dict:
    """Activa o desactiva el kill switch global para trading live."""
    os.environ["LIVE_KILL_SWITCH"] = str(enabled).lower()
    # Clear cached settings
    get_settings.cache_clear()
    settings = get_settings()
    return {
        "kill_switch": settings.LIVE_KILL_SWITCH,
        "message": "KILL SWITCH ACTIVADO - Todas las órdenes live bloqueadas" if enabled else "Kill switch desactivado",
    }


@router.post("/ai-agent/execute")
def ai_agent_execute(
    req: AIExecuteRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Ejecuta una operación de trading directamente desde el agente IA.

    No requiere paper trading activo. Usa el broker compartido y el risk manager.
    En modo live (BinanceBroker), ejecuta órdenes reales en Binance.
    """
    from app.brokers import MockBroker
    from app.execution import ExecutionEngine
    from app.models.signal import SignalCreate
    from app.risk import RiskManager

    settings = get_settings()
    symbol = req.symbol.upper()
    action = req.action_type.lower()

    # Determinar si estamos en modo live
    is_live = settings.TRADING_MODE == "live" and settings.LIVE_TRADING_ENABLED
    keys = resolve_binance_keys(current_user)
    is_binance_broker = settings.BROKER_PROVIDER == "binance" and bool(keys)

    # Safety: Kill switch (blocks buys, allows sells to close positions)
    if is_live and settings.LIVE_KILL_SWITCH and action == "buy":
        return {"status": "rejected", "action": action, "symbol": symbol, "reason": "KILL SWITCH activado. Compras bloqueadas. Sells permitidos para cerrar posiciones."}

    # Obtener o crear broker compartido
    broker = get_shared_broker(keys)

    # Safety: Check daily loss limit for live mode
    if is_live and action == "buy":
        session_check = SessionLocal()
        try:
            from app.database.models.trade import Trade
            today_start = datetime.now(tz=UTC) - timedelta(hours=24)
            recent_trades = session_check.query(Trade).filter(
                Trade.timestamp >= today_start,
                Trade.side == "SELL",
            ).all()
            daily_loss = sum(float(t.realized_pnl) for t in recent_trades if float(t.realized_pnl) < 0)
            if abs(daily_loss) >= settings.LIVE_DAILY_LOSS_LIMIT_USD:
                return {"status": "rejected", "action": action, "symbol": symbol, "reason": f"Pérdida diaria (${abs(daily_loss):.2f}) alcanzó el límite (${settings.LIVE_DAILY_LOSS_LIMIT_USD}). Trading pausado."}
        finally:
            session_check.close()

    risk_manager = RiskManager(settings)

    session = SessionLocal()
    try:
        # Get live price for the symbol - try price stream first, then Binance API directly
        from decimal import Decimal as Dec
        live_price = None
        try:
            from app.data.price_stream import get_price_stream
            stream = get_price_stream()
            if stream and stream.is_connected:
                p = stream.get_price(symbol)
                if p and p > 0:
                    live_price = Dec(str(p))
        except Exception:
            pass

        # If price stream didn't work, fetch directly from Binance API
        if not live_price or live_price <= 0:
            try:
                import httpx as _httpx
                # Try spot first
                resp = _httpx.get(
                    f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}",
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    live_price = Dec(str(resp.json()["price"]))
                else:
                    # Try futures as fallback
                    resp = _httpx.get(
                        f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}",
                        timeout=10.0,
                    )
                    if resp.status_code == 200:
                        live_price = Dec(str(resp.json()["price"]))
                    else:
                        return {"status": "error", "action": action, "symbol": symbol, "reason": f"Símbolo {symbol} no existe en Binance (spot ni futuros)"}
            except Exception as exc:
                return {"status": "error", "action": action, "symbol": symbol, "reason": f"No se pudo validar {symbol} en Binance: {exc}"}

        if not live_price or live_price <= 0:
            return {"status": "error", "action": action, "symbol": symbol, "reason": f"Precio inválido para {symbol}"}

        if action == "buy":
            # Diversification: check if symbol already has an open position
            from app.database.models.position import Position
            existing = session.query(Position).filter(
                Position.symbol == symbol,
                Position.status == "open",
            ).first()
            if existing:
                return {"status": "rejected", "action": "buy", "symbol": symbol, "reason": f"Ya hay posición abierta en {symbol}. Diversifica en otro símbolo."}

            # Get account info
            acct = broker.get_account()
            cash = acct.cash
            equity = acct.equity

            # Get real USDT balance from Binance
            usdt_balance = 0.0
            try:
                if hasattr(broker, '_signed_request'):
                    acct_data = broker._signed_request("GET", "/api/v3/account", {})
                    for bal in acct_data.get("balances", []):
                        if bal.get("asset") == "USDT":
                            usdt_balance = float(bal["free"])
                            break
            except Exception:
                pass

            # Use allocated capital if set, otherwise auto-use available USDT
            is_auto_mode = state.ai_allocated_capital <= 0
            if state.ai_allocated_capital > 0:
                allocated = state.ai_allocated_capital
                # Cap to actual USDT available
                if usdt_balance > 0 and allocated > usdt_balance:
                    allocated = usdt_balance
            else:
                # Auto mode: use all available USDT
                allocated = usdt_balance if usdt_balance > 0 else float(equity)

            # Get open positions for max position check
            open_positions = session.query(Position).filter(Position.status == "open").all()

            if is_auto_mode:
                # AUTO mode: USDT balance already reflects spent capital, use directly
                available = allocated
            else:
                # Fixed mode: subtract committed from allocated budget
                committed = sum(float(p.entry_price) * float(p.quantity) for p in open_positions)
                available = allocated - committed

            if available <= 0:
                return {"status": "rejected", "action": "buy", "symbol": symbol, "reason": f"Capital asignado (${allocated:.2f}) ya está comprometido en {len(open_positions)} posiciones."}

            # Dynamic max positions based on allocated capital
            base_max = getattr(settings, "MAX_OPEN_POSITIONS", 5)
            dynamic_max = base_max + max(0, int((allocated - 50000) / 20000))
            open_count = len(open_positions)
            if open_count >= dynamic_max:
                return {"status": "rejected", "action": "buy", "symbol": symbol, "reason": f"Máximo de {dynamic_max} posiciones abiertas alcanzado."}

            # Calculate stop-loss and take-profit from AI request or settings defaults
            sl_pct = req.stop_loss_pct if req.stop_loss_pct else float(getattr(settings, "DEFAULT_STOP_LOSS_PERCENT", 3.0))
            tp_pct = req.take_profit_pct if req.take_profit_pct else float(getattr(settings, "DEFAULT_TAKE_PROFIT_PERCENT", 6.0))
            stop_loss = live_price * (Dec(1) - Dec(str(sl_pct)) / Dec(100))
            take_profit = live_price * (Dec(1) + Dec(str(tp_pct)) / Dec(100))

            # Override account with allocated capital so risk manager uses it
            # Calculate effective position size: divide available by remaining slots
            remaining_slots = max(1, dynamic_max - open_count)
            position_budget = available / remaining_slots
            from app.database.models.account_snapshot import AccountSnapshot as AcctModel
            acct = AcctModel(
                timestamp=datetime.now(tz=UTC),
                cash=Decimal(str(position_budget)),
                equity=Decimal(str(position_budget)),
                buying_power=Decimal(str(position_budget)),
                margin_used=Decimal("0"),
                daily_pnl=Decimal("0"),
                total_pnl=Decimal("0"),
                open_positions_count=open_count,
                strategy_run_id=None,
            )

            signal = SignalCreate(
                timestamp=datetime.now(tz=UTC),
                symbol=symbol,
                signal_type="BUY",
                confidence=Decimal(str(req.confidence)),
                entry_price=live_price,
                strategy_name="AI-Agent",
                explanation=f"[AI Agent] {req.reason}",
                metadata_json={"source": "ai_agent"},
                suggested_stop_loss=stop_loss,
                suggested_take_profit=take_profit,
            )
            engine = ExecutionEngine(broker, risk_manager, session, settings)
            order = engine.process_signal(signal, account=acct)
            session.commit()

            if order:
                create_ai_snapshot(broker)
                return {
                    "status": "executed",
                    "action": "buy",
                    "symbol": symbol,
                    "order_id": order.id,
                    "side": order.side,
                    "quantity": str(order.filled_quantity),
                    "price": str(order.price) if order.price else None,
                    "order_status": order.status,
                }
            else:
                return {
                    "status": "rejected",
                    "action": "buy",
                    "symbol": symbol,
                    "reason": "Rechazado por risk manager",
                }

        elif action == "sell":
            # Buscar posición abierta
            from app.database.models.position import Position as PosModel
            pos = session.query(PosModel).filter_by(symbol=symbol, status="open").first()
            if not pos:
                return {"status": "no_position", "action": "sell", "symbol": symbol, "reason": f"No hay posición abierta en {symbol}"}

            signal = SignalCreate(
                timestamp=datetime.now(tz=UTC),
                symbol=symbol,
                signal_type="SELL",
                confidence=Decimal(str(req.confidence)),
                entry_price=live_price,
                strategy_name="AI-Agent",
                explanation=f"[AI Agent] {req.reason}",
                metadata_json={"source": "ai_agent"},
            )
            engine = ExecutionEngine(broker, risk_manager, session, settings)
            order = engine.process_signal(signal)
            session.commit()

            if order:
                create_ai_snapshot(broker)
                return {
                    "status": "executed",
                    "action": "sell",
                    "symbol": symbol,
                    "order_id": order.id,
                    "side": order.side,
                    "quantity": str(order.filled_quantity),
                    "price": str(order.price) if order.price else None,
                    "order_status": order.status,
                }
            else:
                return {
                    "status": "rejected",
                    "action": "sell",
                    "symbol": symbol,
                    "reason": "Rechazado por risk manager",
                }
        else:
            return {"status": "error", "reason": f"Tipo de acción desconocido: {action}"}

    except Exception as exc:
        session.rollback()
        return {"status": "error", "reason": str(exc)}
    finally:
        session.close()


@router.get("/ai-agent/stats")
def ai_agent_stats() -> dict:
    """Estadísticas de trading del AI Agent: trades, señales, PnL, decisiones."""
    from sqlalchemy import func

    from app.database.models.order import Order as OrderModel
    from app.database.models.position import Position as PosModel
    from app.database.models.signal import Signal as SignalModel
    from app.database.models.trade import Trade as TradeModel

    session = SessionLocal()
    try:
        # Trades del AI Agent (strategy_name = 'AI-Agent')
        ai_trades = session.query(TradeModel).filter(
            TradeModel.strategy_name == "AI-Agent"
        ).order_by(TradeModel.timestamp.desc()).limit(200).all()

        # Señales del AI Agent
        ai_signals = session.query(SignalModel).filter(
            SignalModel.strategy_name == "AI-Agent"
        ).order_by(SignalModel.timestamp.desc()).limit(200).all()

        # Posiciones abiertas del AI Agent
        ai_open_positions = session.query(PosModel).filter(
            PosModel.strategy_name == "AI-Agent",
            PosModel.status == "open"
        ).all()

        # Posiciones cerradas del AI Agent
        ai_closed_positions = session.query(PosModel).filter(
            PosModel.strategy_name == "AI-Agent",
            PosModel.status == "closed"
        ).order_by(PosModel.closed_at.desc()).limit(100).all()

        # Órdenes del AI Agent
        ai_orders = session.query(OrderModel).filter(
            OrderModel.metadata_json["source"].as_string() == "execution_engine"
        ).order_by(OrderModel.timestamp.desc()).limit(200).all()

        # Estadísticas agregadas
        total_trades = len(ai_trades)
        sell_trades = [t for t in ai_trades if t.side == "SELL"]
        wins = [t for t in sell_trades if t.realized_pnl and t.realized_pnl > 0]
        losses = [t for t in sell_trades if t.realized_pnl and t.realized_pnl < 0]
        total_pnl = sum(t.realized_pnl or 0 for t in sell_trades)
        win_rate = (len(wins) / len(sell_trades) * 100) if sell_trades else 0

        # PnL por trade
        pnl_series = [
            {
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                "symbol": t.symbol,
                "side": t.side,
                "realized_pnl": float(t.realized_pnl) if t.realized_pnl else 0,
                "price": float(t.price) if t.price else 0,
                "quantity": float(t.quantity) if t.quantity else 0,
            }
            for t in ai_trades
        ]

        # Trades por símbolo
        by_symbol: dict[str, dict] = {}
        for t in ai_trades:
            sym = t.symbol
            if sym not in by_symbol:
                by_symbol[sym] = {"trades": 0, "buys": 0, "sells": 0, "pnl": 0, "wins": 0, "losses": 0}
            by_symbol[sym]["trades"] += 1
            if t.side == "BUY":
                by_symbol[sym]["buys"] += 1
            else:
                by_symbol[sym]["sells"] += 1
                pnl = float(t.realized_pnl) if t.realized_pnl else 0
                by_symbol[sym]["pnl"] += pnl
                if pnl > 0:
                    by_symbol[sym]["wins"] += 1
                elif pnl < 0:
                    by_symbol[sym]["losses"] += 1

        # Acciones del agente (buy vs sell)
        buy_count = sum(1 for s in ai_signals if s.signal_type == "BUY")
        sell_count = sum(1 for s in ai_signals if s.signal_type == "SELL")

        # Log del agente
        agent = get_or_create_agent()
        agent_log = agent.get_log(limit=100)

        # Decisiones con acciones
        decisions_with_actions = [e for e in agent_log if e.get("phase") == "decision"]
        decisions_hold = [e for e in agent_log if e.get("phase") == "hold"]
        decisions_rejected = [e for e in agent_log if "rechazada" in e.get("message", "").lower()]

        return {
            "total_trades": total_trades,
            "total_signals": len(ai_signals),
            "open_positions": len(ai_open_positions),
            "closed_positions": len(ai_closed_positions),
            "sell_trades": len(sell_trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(win_rate, 1),
            "total_pnl": float(total_pnl),
            "buy_signals": buy_count,
            "sell_signals": sell_count,
            "pnl_series": pnl_series,
            "by_symbol": by_symbol,
            "open_positions_detail": [
                {
                    "symbol": p.symbol,
                    "side": p.side,
                    "quantity": float(p.quantity),
                    "entry_price": float(p.entry_price),
                    "stop_loss": float(p.stop_loss) if p.stop_loss else None,
                    "take_profit": float(p.take_profit) if p.take_profit else None,
                    "opened_at": p.opened_at.isoformat() if p.opened_at else None,
                }
                for p in ai_open_positions
            ],
            "agent_cycles": agent._cycle,
            "agent_running": agent.is_running,
            "decisions_total": len(decisions_with_actions) + len(decisions_hold),
            "decisions_with_actions": len(decisions_with_actions),
            "decisions_hold": len(decisions_hold),
            "decisions_rejected": len(decisions_rejected),
        }
    except Exception as exc:
        return {"error": str(exc)}
    finally:
        session.close()
