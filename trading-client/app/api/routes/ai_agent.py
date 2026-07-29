"""AI Agent endpoints (start, stop, execute, stats, binance balance, trading mode, kill switch)."""

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select

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
from app.database.models.user_settings import UserSettings
from app.services.auth import LocalUser, get_current_user
from app.services.crypto import decrypt
from app.services.rate_limit import get_plan_limits, has_feature

PREMIUM_PROVIDERS = {"openai", "deepseek", "mistral", "together", "perplexity", "grok"}


def _load_user_keys(user_id: int) -> dict:
    """Load user's stored AI keys from DB, decrypted."""
    db = SessionLocal()
    try:
        s = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        if not s:
            return {}
        keys = {}
        if s.ai_groq_key_enc:
            try:
                keys["groq"] = decrypt(s.ai_groq_key_enc)
            except Exception:
                pass
        if s.ai_gemini_key_enc:
            try:
                keys["gemini"] = decrypt(s.ai_gemini_key_enc)
            except Exception:
                pass
        if s.ai_premium_key_enc:
            try:
                keys["premium"] = decrypt(s.ai_premium_key_enc)
            except Exception:
                pass
        if s.ai_premium_provider:
            keys["premium_provider"] = s.ai_premium_provider
        if s.ai_premium_base_url:
            keys["premium_base_url"] = s.ai_premium_base_url
        if s.ai_premium_model:
            keys["premium_model"] = s.ai_premium_model
        return keys
    finally:
        db.close()

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

    Key resolution & plan enforcement:
    - FREE: Must bring own API key (BYOK). Server keys NOT used.
    - PRO/PREMIUM: Can use server keys (included in subscription) or BYOK.
    - Premium providers (OpenAI, DeepSeek, Mistral, etc.) require PRO/PREMIUM.

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

    # Plan info
    subscription = current_user.subscription if current_user else "free"
    is_free = subscription == "free"
    is_paid = subscription in ("pro", "premium")

    # Block premium providers for FREE users
    if provider in PREMIUM_PROVIDERS and is_free:
        raise HTTPException(
            status_code=403,
            detail=f"El proveedor '{provider}' requiere suscripción PRO o PREMIUM. "
                   f"Usuarios FREE pueden usar Groq o Gemini (gratis) con su propia API key.",
        )

    # Load user's stored keys from DB
    user_keys = _load_user_keys(current_user.id) if current_user else {}

    # Resolve API keys: request body > user DB > server .env (only for paid)
    groq_key = (req.groq_api_key or user_keys.get("groq") or "").strip() or None
    gemini_key = (req.gemini_api_key or user_keys.get("gemini") or "").strip() or None

    # FREE users: must have their own key — no server fallback
    if is_free:
        if provider == "groq" and not groq_key:
            raise HTTPException(
                status_code=403,
                detail="Usuarios FREE deben ingresar su propia Groq API key. "
                       "Obtén una gratis en console.groq.com",
            )
        if provider == "gemini" and not gemini_key:
            raise HTTPException(
                status_code=403,
                detail="Usuarios FREE deben ingresar su propia Gemini API key. "
                       "Obtén una gratis en aistudio.google.com",
            )
    else:
        # Paid users: fallback to server keys
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
        premium_key = req.premium_api_key or user_keys.get("premium")
        if premium_key:
            agent.openai_api_key = premium_key
        base_url = req.premium_base_url or user_keys.get("premium_base_url") or PREMIUM_BASE_URLS[provider]
        agent.openai_base_url = base_url
        if req.model:
            agent.openai_model = req.model
        elif user_keys.get("premium_model"):
            agent.openai_model = user_keys["premium_model"]

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

    # Load user's stored keys from DB
    user_keys = _load_user_keys(current_user.id) if current_user else {}

    # Resolve keys: request body > user DB > .env (test-key always allows .env fallback for convenience)
    groq_key = (req.groq_api_key or user_keys.get("groq") or "").strip() or None
    gemini_key = (req.gemini_api_key or user_keys.get("gemini") or "").strip() or None
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
            gemini_model = model or "gemini-flash-latest"
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


@router.get("/ai-agent/plan")
def ai_agent_plan(
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Returns user's plan info, features, and BYOK status for the frontend."""
    subscription = current_user.subscription if current_user else "free"
    limits = get_plan_limits(subscription)
    user_keys = _load_user_keys(current_user.id) if current_user else {}

    return {
        "subscription": subscription,
        "is_free": subscription == "free",
        "is_paid": subscription in ("pro", "premium"),
        "max_ai_requests_per_day": limits["max_ai_requests_per_day"],
        "min_interval_seconds": limits["max_ai_interval_seconds"],
        "features": limits["features"],
        "has_groq_key": bool(user_keys.get("groq")),
        "has_gemini_key": bool(user_keys.get("gemini")),
        "has_premium_key": bool(user_keys.get("premium")),
        "premium_provider": user_keys.get("premium_provider"),
        "premium_model": user_keys.get("premium_model"),
        "free_providers": ["groq", "gemini", "ollama"],
        "premium_providers": list(PREMIUM_PROVIDERS),
        "get_keys_links": {
            "groq": "https://console.groq.com/keys",
            "gemini": "https://aistudio.google.com/apikey",
        },
    }


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
        return {"error": "No tienes API keys de Binance configuradas. Conecta tu broker desde Conexiones.", "assets": [], "total_usd": 0, "total_mxn": 0}

    from app.brokers.adapters.binance_adapter import BinanceAdapter

    adapter = BinanceAdapter(creds)

    try:
        balances = adapter.get_account_balances()
    except Exception as exc:
        err_msg = str(exc)
        if "401" in err_msg or "-2015" in err_msg:
            err_msg = "Binance rechazó las credenciales. Verifica que tu API key tenga permisos de lectura y que tu IP esté autorizada en Binance."
        return {"error": f"No se pudo conectar a Binance: {err_msg}", "assets": [], "total_usd": 0, "total_mxn": 0}

    # Batch-fetch all ticker prices in one call
    price_map: dict[str, float] = {}
    try:
        tickers = _httpx.get("https://api.binance.com/api/v3/ticker/price", timeout=10).json()
        for t in tickers:
            price_map[t["symbol"]] = float(t["price"])
    except Exception:
        pass

    # Get MXN/USDT rate
    mxn_rate = price_map.get("USDTMXN", 0.0)
    if mxn_rate == 0:
        mxn_rate = 18.5  # fallback approximate

    assets = []
    total_usd = 0.0

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
                usd_value = total * price_map.get("EURUSDT", 1.08)
        elif asset == "MXN":
            usd_value = total / mxn_rate
        else:
            usd_value = total * price_map.get(f"{asset}USDT", 0.0)

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


@router.get("/binance/open-orders")
def get_binance_open_orders(
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Consulta las órdenes abiertas reales en Binance en tiempo real."""
    settings = get_settings()
    if settings.BROKER_PROVIDER != "binance":
        return {"error": "Binance no configurado", "orders": []}

    creds = resolve_broker_credentials("binance", current_user)
    if not creds:
        return {"error": "No tienes API keys de Binance configuradas. Conecta tu broker desde Conexiones.", "orders": []}

    from app.brokers.adapters.binance_adapter import BinanceAdapter

    adapter = BinanceAdapter(creds)

    try:
        resp = adapter._broker._signed_request("GET", "/api/v3/openOrders", {})
    except Exception as exc:
        return {"error": f"No se pudo consultar órdenes abiertas: {exc}", "orders": []}

    orders = []
    for o in resp:
        orders.append({
            "orderId": str(o.get("orderId", "")),
            "clientOrderId": o.get("clientOrderId", ""),
            "symbol": o.get("symbol", ""),
            "side": o.get("side", ""),
            "type": o.get("type", ""),
            "status": o.get("status", ""),
            "quantity": float(o.get("origQty", "0")),
            "filled_quantity": float(o.get("executedQty", "0")),
            "price": float(o.get("price", "0")) if o.get("price") and o.get("price") != "0" else None,
            "stop_price": float(o.get("stopPrice", "0")) if o.get("stopPrice") and o.get("stopPrice") != "0" else None,
            "time": o.get("time", 0),
            "updateTime": o.get("updateTime", 0),
        })

    return {"orders": orders, "count": len(orders)}


@router.get("/binance/all-orders")
def get_binance_all_orders(
    limit: int = 50,
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Consulta el historial completo de órdenes desde Binance en tiempo real.

    Binance /api/v3/allOrders requires a symbol parameter, so we first get
    the user's balances to find which symbols they trade, then query orders
    for each. Also fetches open orders (which don't require symbol).
    """
    creds = resolve_broker_credentials("binance", current_user)
    if not creds:
        return {"error": "No tienes API keys de Binance configuradas. Conecta tu broker desde Conexiones.", "orders": [], "active": [], "filled": []}

    from app.brokers.adapters.binance_adapter import BinanceAdapter

    adapter = BinanceAdapter(creds)

    # 1. Get open orders (no symbol required)
    try:
        open_resp = adapter._broker._signed_request("GET", "/api/v3/openOrders", {})
    except Exception as exc:
        err_msg = str(exc)
        if "401" in err_msg or "-2015" in err_msg:
            err_msg = "Binance rechazó las credenciales. Verifica permisos de lectura e IP autorizada."
        return {"error": f"No se pudo consultar órdenes: {err_msg}", "orders": [], "active": [], "filled": []}

    # 2. Get symbols from balance to query historical orders
    symbols_to_query = set()
    try:
        balances = adapter.get_account_balances()
        for b in balances:
            if b.free > 0 or b.locked > 0:
                if b.asset not in ("USDT", "BUSD", "USDC", "EUR", "MXN", "BNB"):
                    symbols_to_query.add(f"{b.asset}USDT")
    except Exception:
        pass

    # Always include common symbols
    symbols_to_query.update({"BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"})

    # 3. Query all orders per symbol in parallel
    import concurrent.futures

    def fetch_symbol_orders(sym: str):
        try:
            return adapter._broker._signed_request("GET", "/api/v3/allOrders", {"symbol": sym, "limit": limit})
        except Exception:
            return []

    all_orders = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_symbol_orders, sym): sym for sym in symbols_to_query}
        for future in concurrent.futures.as_completed(futures):
            all_orders.extend(future.result())

    # 4. Merge open orders + historical, deduplicate by orderId
    seen_ids = set()
    orders = []

    for o in open_resp:
        oid = str(o.get("orderId", ""))
        if oid in seen_ids:
            continue
        seen_ids.add(oid)
        orders.append({
            "orderId": oid,
            "clientOrderId": o.get("clientOrderId", ""),
            "symbol": o.get("symbol", ""),
            "side": o.get("side", ""),
            "type": o.get("type", ""),
            "status": o.get("status", ""),
            "is_active": True,
            "quantity": float(o.get("origQty", "0")),
            "filled_quantity": float(o.get("executedQty", "0")),
            "price": float(o.get("price", "0")) if o.get("price") and o.get("price") != "0" else None,
            "avg_price": float(o.get("avgPrice", "0")) if o.get("avgPrice") and o.get("avgPrice") != "0" else None,
            "stop_price": float(o.get("stopPrice", "0")) if o.get("stopPrice") and o.get("stopPrice") != "0" else None,
            "time": o.get("time", 0),
            "updateTime": o.get("updateTime", 0),
        })

    for o in all_orders:
        oid = str(o.get("orderId", ""))
        if oid in seen_ids:
            continue
        seen_ids.add(oid)
        status = o.get("status", "")
        is_active = status in ("NEW", "PARTIALLY_FILLED", "PENDING_NEW", "PENDING_CANCEL")
        orders.append({
            "orderId": oid,
            "clientOrderId": o.get("clientOrderId", ""),
            "symbol": o.get("symbol", ""),
            "side": o.get("side", ""),
            "type": o.get("type", ""),
            "status": status,
            "is_active": is_active,
            "quantity": float(o.get("origQty", "0")),
            "filled_quantity": float(o.get("executedQty", "0")),
            "price": float(o.get("price", "0")) if o.get("price") and o.get("price") != "0" else None,
            "avg_price": float(o.get("avgPrice", "0")) if o.get("avgPrice") and o.get("avgPrice") != "0" else None,
            "stop_price": float(o.get("stopPrice", "0")) if o.get("stopPrice") and o.get("stopPrice") != "0" else None,
            "time": o.get("time", 0),
            "updateTime": o.get("updateTime", 0),
        })

    # Sort by time descending
    orders.sort(key=lambda x: x.get("time", 0), reverse=True)

    active = [o for o in orders if o["is_active"]]
    filled = [o for o in orders if not o["is_active"]]

    return {
        "orders": orders,
        "active": active,
        "filled": filled,
        "count": len(orders),
        "active_count": len(active),
    }


@router.get("/binance/account")
def get_binance_account(
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Consulta la info de la cuenta de Binance (permisos, comisiones, etc)."""
    creds = resolve_broker_credentials("binance", current_user)
    if not creds:
        return {"error": "No tienes API keys de Binance configuradas. Conecta tu broker desde Conexiones."}

    from app.brokers.adapters.binance_adapter import BinanceAdapter

    adapter = BinanceAdapter(creds)

    try:
        resp = adapter._broker._signed_request("GET", "/api/v3/account", {})
    except Exception as exc:
        return {"error": f"No se pudo conectar a Binance: {exc}"}

    return {
        "accountType": resp.get("accountType", ""),
        "canTrade": resp.get("canTrade", False),
        "canWithdraw": resp.get("canWithdraw", False),
        "canDeposit": resp.get("canDeposit", False),
        "permissions": resp.get("permissions", []),
        "makerCommission": resp.get("makerCommission", 0),
        "takerCommission": resp.get("takerCommission", 0),
        "updateTime": resp.get("updateTime", 0),
    }


class ManualOrderRequest(BaseModel):
    symbol: str
    side: str  # "BUY" or "SELL"
    order_type: str = "MARKET"  # "MARKET" or "LIMIT"
    quantity: float | None = None
    quote_order_qty: float | None = None  # amount in USDT for market buys
    price: float | None = None  # required for LIMIT
    stop_loss_price: float | None = None  # optional stop-loss
    take_profit_price: float | None = None  # optional take-profit


@router.post("/binance/manual-order")
def place_binance_manual_order(
    req: ManualOrderRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Place a manual order on Binance (buy/sell, market/limit)."""
    settings = get_settings()
    if settings.BROKER_PROVIDER != "binance":
        return {"error": "Binance no configurado"}

    creds = resolve_broker_credentials("binance", current_user)
    if not creds:
        return {"error": "No tienes API keys de Binance configuradas. Conecta tu broker desde Conexiones."}

    from app.brokers.adapters.binance_adapter import BinanceAdapter
    adapter = BinanceAdapter(creds)

    symbol = req.symbol.upper()
    side = req.side.upper()
    order_type = req.order_type.upper()

    if side not in ("BUY", "SELL"):
        return {"error": "Side debe ser BUY o SELL"}
    if order_type not in ("MARKET", "LIMIT"):
        return {"error": "Order type debe ser MARKET o LIMIT"}
    if order_type == "LIMIT" and not req.price:
        return {"error": "LIMIT requiere price"}
    if not req.quantity and not req.quote_order_qty:
        return {"error": "Requiere quantity o quote_order_qty"}

    params: dict = {
        "symbol": symbol,
        "side": side,
        "type": order_type,
    }

    if order_type == "LIMIT":
        params["timeInForce"] = "GTC"
        params["price"] = f"{req.price:.8f}".rstrip("0").rstrip(".")

    if req.quantity:
        params["quantity"] = f"{req.quantity:.8f}".rstrip("0").rstrip(".")
    elif req.quote_order_qty and order_type == "MARKET":
        params["quoteOrderQty"] = f"{req.quote_order_qty:.8f}".rstrip("0").rstrip(".")

    try:
        resp = adapter._broker._signed_request("POST", "/api/v3/order", params)
        result = {
            "status": "ok",
            "orderId": str(resp.get("orderId", "")),
            "symbol": resp.get("symbol", symbol),
            "side": resp.get("side", side),
            "type": resp.get("type", order_type),
            "quantity": resp.get("origQty", ""),
            "price": resp.get("price", ""),
            "executedQty": resp.get("executedQty", ""),
            "status": resp.get("status", ""),
            "transactTime": resp.get("transactTime", ""),
        }

        # Place stop-loss and take-profit as OCO order if provided and BUY
        if side == "BUY" and req.stop_loss_price and req.take_profit_price:
            executed_qty = resp.get("origQty", "")
            if not executed_qty:
                # For market orders, fetch executed qty
                executed_qty = resp.get("executedQty", "")
            if executed_qty and float(executed_qty) > 0:
                try:
                    oco_params = {
                        "symbol": symbol,
                        "side": "SELL",
                        "quantity": executed_qty,
                        "price": f"{req.take_profit_price:.8f}".rstrip("0").rstrip("."),
                        "stopPrice": f"{req.stop_loss_price:.8f}".rstrip("0").rstrip("."),
                        "stopLimitPrice": f"{req.stop_loss_price:.8f}".rstrip("0").rstrip("."),
                        "stopLimitTimeInForce": "GTC",
                    }
                    oco_resp = adapter._broker._signed_request("POST", "/api/v3/order/oco", oco_params)
                    result["ocoOrderId"] = str(oco_resp.get("orderListId", ""))
                    result["stopLoss"] = req.stop_loss_price
                    result["takeProfit"] = req.take_profit_price
                except Exception as oco_exc:
                    result["ocoError"] = str(oco_exc)

        return result
    except Exception as exc:
        err_msg = str(exc)
        if "401" in err_msg or "-2015" in err_msg:
            err_msg = "Binance rechazó las credenciales. Verifica que tu API key tenga permisos de trading y que tu IP esté autorizada en Binance."
        return {"status": "error", "error": err_msg}


@router.get("/binance/price")
def get_binance_price(symbol: str = Query(...)) -> dict:
    """Get current price for a symbol from Binance."""
    import httpx as _httpx
    try:
        resp = _httpx.get(
            f"https://api.binance.com/api/v3/ticker/price?symbol={symbol.upper()}",
            timeout=10.0,
        )
        if resp.status_code == 200:
            return {"symbol": symbol.upper(), "price": float(resp.json()["price"])}
        return {"error": f"Binance respondió {resp.status_code}"}
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/binance/positions")
def get_binance_positions(
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Consulta posiciones abiertas desde la DB con precios en vivo de Binance."""
    from app.database.session import SessionLocal
    from app.database.models.position import Position
    from app.brokers.adapters.binance_adapter import BinanceAdapter
    from app.brokers.models import BrokerCredentials, normalize_symbol
    from decimal import Decimal as Dec

    creds = resolve_broker_credentials("binance", current_user)
    if not creds:
        return {"error": "No tienes API keys de Binance configuradas. Conecta tu broker desde Conexiones.", "positions": []}

    db = SessionLocal()
    try:
        positions = db.query(Position).filter(
            Position.status == "open",
            Position.user_id == current_user.id,
        ).all()
        if not positions:
            return {"positions": [], "count": 0}

        # Batch-fetch all ticker prices in one call
        import httpx as _httpx
        price_map: dict[str, float] = {}
        try:
            tickers = _httpx.get("https://api.binance.com/api/v3/ticker/price", timeout=10).json()
            for t in tickers:
                price_map[t["symbol"]] = float(t["price"])
        except Exception:
            pass

        result = []
        for p in positions:
            current_price = None
            unrealized = 0.0
            broker_sym = p.symbol.upper().replace("/", "").replace("-", "").replace("_", "")
            if broker_sym in price_map:
                current_price = price_map[broker_sym]
                unrealized = (current_price - float(p.entry_price)) * float(p.quantity)

            if current_price:
                p.current_price = Dec(str(current_price))
                p.unrealized_pnl = Dec(str(unrealized))
            result.append({
                "id": p.id,
                "symbol": p.symbol,
                "side": p.side,
                "quantity": float(p.quantity),
                "entry_price": float(p.entry_price),
                "current_price": current_price,
                "unrealized_pnl": round(unrealized, 4),
                "stop_loss": float(p.stop_loss) if p.stop_loss else None,
                "take_profit": float(p.take_profit) if p.take_profit else None,
                "status": p.status,
                "strategy_name": p.strategy_name,
                "opened_at": p.opened_at.isoformat() if p.opened_at else None,
            })
        db.commit()
        return {"positions": result, "count": len(result)}
    finally:
        db.close()


@router.get("/binance/resumen")
def get_binance_resumen(
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Resumen completo del portfolio: balance, posiciones abiertas, PnL y distribución."""
    import httpx as _httpx

    creds = resolve_broker_credentials("binance", current_user)
    if not creds:
        return {"error": "No tienes API keys de Binance configuradas.", "balance_usd": 0, "positions": [], "total_pnl": 0}

    from app.brokers.adapters.binance_adapter import BinanceAdapter
    from app.database.session import SessionLocal
    from app.database.models.position import Position as PositionModel

    adapter = BinanceAdapter(creds)
    broker = adapter._broker

    # Batch fetch prices
    price_map: dict[str, float] = {}
    try:
        tickers = _httpx.get("https://api.binance.com/api/v3/ticker/price", timeout=10).json()
        for t in tickers:
            price_map[t["symbol"]] = float(t["price"])
    except Exception:
        pass

    # 1) Spot balances
    spot_assets = []
    balance_usd = 0.0
    try:
        account = broker._signed_request("GET", "/api/v3/account", {})
        balances = account.get("balances", [])
        stablecoins = {"USDT", "BUSD", "USDC", "UST", "TUSD", "FDUSD"}
        for b in balances:
            asset = b["asset"]
            free = float(b["free"])
            locked = float(b["locked"])
            total = free + locked
            if total <= 0:
                continue
            if asset in stablecoins:
                usd = total
            else:
                usd = total * price_map.get(f"{asset}USDT", 0.0)
            balance_usd += usd
            spot_assets.append({"asset": asset, "free": free, "locked": locked, "total": total, "usd_value": round(usd, 2)})
    except Exception:
        pass

    # 2) Open positions from DB with live prices
    db = SessionLocal()
    positions_list = []
    total_pnl = 0.0
    try:
        positions = db.query(PositionModel).filter(
            PositionModel.status == "open",
            PositionModel.user_id == current_user.id,
        ).all()
        for p in positions:
            broker_sym = p.symbol.upper().replace("/", "").replace("-", "").replace("_", "")
            current = price_map.get(broker_sym, float(p.current_price or p.entry_price or 0))
            entry = float(p.entry_price or 0)
            qty = float(p.quantity or 0)
            if p.side == "long":
                pnl = (current - entry) * qty
            else:
                pnl = (entry - current) * qty
            total_pnl += pnl
            pnl_pct = ((current - entry) / entry * 100) if entry > 0 else 0
            positions_list.append({
                "symbol": p.symbol,
                "side": p.side,
                "quantity": qty,
                "entry_price": entry,
                "current_price": current,
                "usd_value": round(qty * current, 2),
                "unrealized_pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "strategy_name": p.strategy_name,
                "opened_at": p.opened_at.isoformat() if p.opened_at else None,
            })
            # Update DB with live price
            p.current_price = Decimal(str(current))
            p.unrealized_pnl = Decimal(str(pnl))
        db.commit()
    finally:
        db.close()

    # 3) Distribution
    all_assets = {}
    for a in spot_assets:
        if a["usd_value"] > 0:
            all_assets[a["asset"]] = all_assets.get(a["asset"], 0) + a["usd_value"]
    for p in positions_list:
        asset = p["symbol"].replace("USDT", "").replace("USD", "")
        if p["usd_value"] > 0:
            all_assets[asset] = all_assets.get(asset, 0) + p["usd_value"]

    distribution = [
        {"asset": k, "usd": v, "pct": round(v / (balance_usd + sum(p["usd_value"] for p in positions_list)) * 100, 1) if (balance_usd + sum(p["usd_value"] for p in positions_list)) > 0 else 0}
        for k, v in sorted(all_assets.items(), key=lambda x: -x[1])
    ]

    return {
        "balance_usd": round(balance_usd, 2),
        "positions": positions_list,
        "positions_count": len(positions_list),
        "total_pnl": round(total_pnl, 2),
        "total_value": round(balance_usd + sum(p["usd_value"] for p in positions_list), 2),
        "spot_assets": spot_assets,
        "distribution": distribution,
    }


@router.post("/binance/import-positions")
def import_binance_positions(
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Importa posiciones reales de Binance (spot + futures) a la DB local."""
    creds = resolve_broker_credentials("binance", current_user)
    if not creds:
        return {"error": "No tienes API keys de Binance configuradas. Conecta tu broker desde Conexiones."}

    from app.brokers.adapters.binance_adapter import BinanceAdapter
    from app.database.session import SessionLocal
    from app.database.models.position import Position as PositionModel

    adapter = BinanceAdapter(creds)
    broker = adapter._broker
    db = SessionLocal()
    imported = []
    skipped = 0

    try:
        # 1) Spot holdings from /api/v3/account
        try:
            account = broker._signed_request("GET", "/api/v3/account", {})
            balances = account.get("balances", [])
        except Exception as exc:
            return {"error": f"No se pudo conectar a Binance: {exc}"}

        # Batch fetch prices
        import httpx as _httpx
        price_map: dict[str, float] = {}
        try:
            tickers = _httpx.get("https://api.binance.com/api/v3/ticker/price", timeout=10).json()
            for t in tickers:
                price_map[t["symbol"]] = float(t["price"])
        except Exception:
            pass

        stablecoins = {"USDT", "BUSD", "USDC", "UST", "TUSD", "FDUSD"}

        for b in balances:
            asset = b["asset"]
            free = float(b["free"])
            locked = float(b["locked"])
            total = free + locked
            if total <= 0 or asset in stablecoins:
                continue

            symbol = f"{asset}USDT"
            price = price_map.get(symbol, 0.0)
            if price <= 0:
                continue

            # Check if already exists as open position
            existing = db.query(PositionModel).filter(
                PositionModel.symbol == symbol,
                PositionModel.status == "open",
                PositionModel.user_id == current_user.id,
            ).first()
            if existing:
                existing.current_price = Decimal(str(price))
                existing.unrealized_pnl = (Decimal(str(price)) - existing.entry_price) * existing.quantity
                skipped += 1
                continue

            pos = PositionModel(
                user_id=current_user.id,
                symbol=symbol,
                opened_at=datetime.now(tz=UTC),
                side="long",
                quantity=Decimal(str(total)),
                entry_price=Decimal(str(price)),
                current_price=Decimal(str(price)),
                unrealized_pnl=Decimal("0"),
                status="open",
                strategy_name="imported_binance",
                metadata_json={"source": "binance_spot_import", "asset": asset},
            )
            db.add(pos)
            imported.append({"symbol": symbol, "quantity": total, "entry_price": price})

        # 2) Futures positions from /fapi/v2/positionRisk
        try:
            fapi_resp = broker._signed_request("GET", "/fapi/v2/positionRisk", {})
            for p in fapi_resp:
                amt = float(p.get("positionAmt", 0))
                if amt == 0:
                    continue
                symbol = p.get("symbol", "")
                entry = float(p.get("entryPrice", 0))
                mark = float(p.get("markPrice", 0))
                side = "long" if amt > 0 else "short"
                qty = abs(amt)

                existing = db.query(PositionModel).filter(
                    PositionModel.symbol == symbol,
                    PositionModel.status == "open",
                    PositionModel.user_id == current_user.id,
                ).first()
                if existing:
                    existing.current_price = Decimal(str(mark))
                    existing.unrealized_pnl = (Decimal(str(mark)) - existing.entry_price) * existing.quantity
                    skipped += 1
                    continue

                pos = PositionModel(
                    user_id=current_user.id,
                    symbol=symbol,
                    opened_at=datetime.now(tz=UTC),
                    side=side,
                    quantity=Decimal(str(qty)),
                    entry_price=Decimal(str(entry)),
                    current_price=Decimal(str(mark)),
                    unrealized_pnl=Decimal(str((mark - entry) * qty if side == "long" else (entry - mark) * qty)),
                    status="open",
                    strategy_name="imported_binance",
                    metadata_json={"source": "binance_futures_import"},
                )
                db.add(pos)
                imported.append({"symbol": symbol, "quantity": qty, "entry_price": entry, "side": side})
        except Exception:
            pass  # Futures might not be enabled

        db.commit()
        return {
            "imported": imported,
            "imported_count": len(imported),
            "skipped": skipped,
            "message": f"Se importaron {len(imported)} posiciones. {skipped} ya existían.",
        }
    except Exception as exc:
        db.rollback()
        return {"error": f"Error importando posiciones: {exc}"}
    finally:
        db.close()


@router.patch("/ai-agent/auto-trade")
def ai_agent_set_auto_trade(enabled: bool = Query(True)) -> dict:
    """Habilita o deshabilita la ejecución automática de trades."""
    agent = get_or_create_agent()
    agent.auto_trade = enabled
    return agent.get_status()


@router.get("/ai-agent/brokers")
def get_ai_agent_brokers(
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Lista los brokers disponibles para el AI Agent, incluyendo los conectados por el usuario."""
    from app.brokers.registry import list_brokers, is_implemented, get_capabilities as _get_caps
    from app.services.broker_account_service import list_accounts

    # Get all supported brokers
    all_brokers = list_brokers()

    # Get user's connected broker accounts
    connected_brokers: set[str] = set()
    if current_user:
        db = SessionLocal()
        try:
            accounts = list_accounts(db, current_user.id)
            for acc in accounts:
                connected_brokers.add(acc.get("broker_id", ""))
        finally:
            db.close()

    brokers_list = []
    for b in all_brokers:
        broker_id = b.broker_id
        try:
            caps = _get_caps(broker_id)
            cap_spot = caps.spot
            cap_futures = caps.futures
        except Exception:
            cap_spot = True
            cap_futures = False
        brokers_list.append({
            "id": broker_id,
            "name": b.display_name,
            "implemented": is_implemented(broker_id),
            "connected": broker_id in connected_brokers,
            "logo": b.logo_url,
            "capabilities": {
                "spot": cap_spot,
                "futures": cap_futures,
            },
        })

    # Always include "paper" as an option
    brokers_list.insert(0, {
        "id": "paper",
        "name": "Paper Trading (Simulado)",
        "implemented": True,
        "connected": True,
        "logo": None,
        "capabilities": {"spot": True, "futures": False},
    })

    # Current selected broker
    current_broker = getattr(state, "ai_selected_broker", "paper")

    return {
        "brokers": brokers_list,
        "current": current_broker,
    }


@router.patch("/ai-agent/broker")
def set_ai_agent_broker(
    broker_id: str = Query(...),
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Set the broker where the AI Agent executes trades."""
    from app.brokers.registry import is_implemented

    broker_id = broker_id.lower().strip()

    # Validate broker
    if broker_id != "paper" and not is_implemented(broker_id):
        return {"status": "error", "reason": f"Broker '{broker_id}' no implementado"}

    # If selecting a real broker, check user has connected it
    if broker_id != "paper" and current_user:
        from app.services.broker_account_service import list_accounts
        from app.database.session import SessionLocal

        db = SessionLocal()
        try:
            accounts = list_accounts(db, current_user.id)
            connected = any(a.get("broker_id") == broker_id for a in accounts)
            if not connected:
                return {"status": "error", "reason": f"No tienes {broker_id} conectado. Ve a Conexiones."}
        finally:
            db.close()

    state.ai_selected_broker = broker_id

    # Update .env for persistence
    from pathlib import Path
    env_path = Path(".env")
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
        found = False
        new_lines = []
        for line in lines:
            if line.startswith("AI_SELECTED_BROKER="):
                new_lines.append(f"AI_SELECTED_BROKER={broker_id}")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"AI_SELECTED_BROKER={broker_id}")
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        os.environ["AI_SELECTED_BROKER"] = broker_id

    return {
        "status": "ok",
        "broker": broker_id,
        "message": f"AI Agent usará {broker_id} para ejecutar trades",
    }


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
                Position.user_id == current_user.id,
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
            open_positions = session.query(Position).filter(
                Position.status == "open",
                Position.user_id == current_user.id,
            ).all()

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
            engine = ExecutionEngine(broker, risk_manager, session, settings, user_id=current_user.id)
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
            pos = session.query(PosModel).filter_by(symbol=symbol, status="open", user_id=current_user.id).first()
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
            engine = ExecutionEngine(broker, risk_manager, session, settings, user_id=current_user.id)
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


# ---------------------------------------------------------------------------
# Intelligence Dashboard Endpoints (Phase 1: Event Journal + Personalization)
# ---------------------------------------------------------------------------

@router.get("/intelligence/changes-since-last-login")
def get_changes_since_last_login(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Returns changes since the user's last login.

    Combines Event Journal entries with portfolio changes to build
    the 'Since Last Visit' section of the dashboard.
    """
    from app.intelligence.personalizer import get_changes_since_last_login as _get_changes

    session = SessionLocal()
    try:
        return _get_changes(session, user_id=current_user.id)
    except Exception as exc:
        return {
            "lastLogin": datetime.now(UTC).isoformat(),
            "hoursSinceLogin": 24,
            "greeting": "Hola",
            "changes": [],
            "toReview": [],
            "portfolio": {"totalPnl": 0, "positionsCount": 0, "totalValue": 0, "bestPerformer": None, "worstPerformer": None},
            "movers": [],
            "buyRecommendations": [],
            "highImpactNews": [],
            "error": str(exc),
        }
    finally:
        session.close()


@router.get("/intelligence/today-priorities")
def get_today_priorities(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Returns prioritized assets for the user to review today.

    Based on open positions and recent signals, ranked by confidence.
    """
    from app.intelligence.personalizer import get_today_priorities as _get_priorities

    session = SessionLocal()
    try:
        return _get_priorities(session, user_id=current_user.id)
    except Exception as exc:
        return {"priorities": [], "error": str(exc)}
    finally:
        session.close()


@router.get("/intelligence/activity")
def get_intelligence_activity(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """Returns the AI activity timeline (chronological agent decisions).

    Reads from the Event Journal, falling back to AI agent logs if empty.
    """
    from app.intelligence.personalizer import get_activity as _get_activity

    session = SessionLocal()
    try:
        return _get_activity(session, hours=24, limit=limit, user_id=current_user.id)
    except Exception as exc:
        return {"entries": [], "error": str(exc)}
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Intelligence News Endpoints
# ---------------------------------------------------------------------------

@router.get("/intelligence/news")
def get_intelligence_news(
    hours: int = Query(24, ge=1, le=168),
    impact: str | None = Query(None),
    asset: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    """Returns stored news articles, filtered by time/impact/asset."""
    from app.intelligence.news_fetcher import get_news

    try:
        news = get_news(hours=hours, impact=impact, asset=asset, limit=limit, offset=offset)
        return {"news": news, "count": len(news)}
    except Exception as exc:
        return {"news": [], "count": 0, "error": str(exc)}


@router.post("/intelligence/news/fetch")
def trigger_news_fetch(
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Manually trigger a news fetch cycle (normally runs on scheduler)."""
    from app.intelligence.news_fetcher import fetch_and_store_news

    try:
        count = fetch_and_store_news(max_per_feed=10, min_impact="medium")
        return {"fetched": count, "status": "ok"}
    except Exception as exc:
        return {"fetched": 0, "error": str(exc)}


# ---------------------------------------------------------------------------
# Intelligence Analysis Endpoints (historical AI analysis per asset)
# ---------------------------------------------------------------------------

@router.get("/intelligence/analysis/{asset}")
def get_analysis_history(
    asset: str,
    hours: int = Query(168, ge=1, le=2160),  # up to 90 days
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """Returns historical AI analysis for a specific asset."""
    from app.intelligence.analysis_storage import get_analysis_history as _get_history

    try:
        history = _get_history(asset, hours=hours, limit=limit)
        return {"asset": asset.upper(), "history": history, "count": len(history)}
    except Exception as exc:
        return {"asset": asset.upper(), "history": [], "count": 0, "error": str(exc)}


@router.get("/intelligence/analysis/{asset}/trend")
def get_analysis_trend(
    asset: str,
    hours: int = Query(168, ge=1, le=2160),
) -> dict:
    """Returns trend analysis for an asset (how decision/confidence evolved)."""
    from app.intelligence.analysis_storage import get_analysis_trend as _get_trend

    try:
        return _get_trend(asset, hours=hours)
    except Exception as exc:
        return {"asset": asset.upper(), "trend": "error", "error": str(exc)}


@router.get("/intelligence/analysis")
def get_all_latest_analyses(
    assets: str | None = Query(None),  # comma-separated: BTC,ETH,SOL
) -> dict:
    """Returns the latest analysis for all assets (or specified ones)."""
    from app.intelligence.analysis_storage import get_all_latest_analyses as _get_all

    try:
        asset_list = assets.split(",") if assets else None
        analyses = _get_all(asset_list)
        return {"analyses": analyses, "count": len(analyses)}
    except Exception as exc:
        return {"analyses": [], "count": 0, "error": str(exc)}


# ---------------------------------------------------------------------------
# Intelligence Cleanup Endpoint
# ---------------------------------------------------------------------------

@router.post("/intelligence/cleanup")
def trigger_cleanup(
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Manually trigger cleanup of old news, analysis, and events."""
    from app.intelligence.cleanup import run_cleanup

    try:
        return run_cleanup()
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Market Sources Endpoints
# ---------------------------------------------------------------------------

@router.get("/intelligence/sources")
def get_market_sources(
    category: str | None = Query(None),
    asset_type: str | None = Query(None),
) -> dict:
    """Returns configured market data sources, optionally filtered."""
    from app.intelligence.market_sources import MARKET_SOURCES, SOURCE_CATEGORIES

    sources = MARKET_SOURCES
    if category:
        sources = [s for s in sources if s.category == category]
    if asset_type:
        sources = [s for s in sources if s.asset_type == asset_type or s.asset_type == "general"]

    return {
        "sources": [
            {
                "name": s.name,
                "url": s.url,
                "category": s.category,
                "asset_type": s.asset_type,
                "priority": s.priority,
                "requires_auth": s.requires_auth,
                "notes": s.notes,
            }
            for s in sorted(sources, key=lambda x: x.priority)
        ],
        "count": len(sources),
        "categories": SOURCE_CATEGORIES,
    }


@router.get("/intelligence/sources/context")
def get_sources_for_agent(
    asset: str | None = Query(None),
    include_crypto: bool = Query(True),
    include_stocks: bool = Query(True),
    include_macro: bool = Query(True),
) -> dict:
    """Returns a context string of available sources for AI agent prompts."""
    from app.intelligence.market_sources import get_sources_for_agent_context

    context = get_sources_for_agent_context(
        asset=asset,
        include_crypto=include_crypto,
        include_stocks=include_stocks,
        include_macro=include_macro,
    )
    return {"context": context}


# ---------------------------------------------------------------------------
# Intelligence Scheduler Endpoints
# ---------------------------------------------------------------------------

@router.get("/intelligence/scheduler/status")
def get_scheduler_status() -> dict:
    """Returns the current intelligence scheduler status."""
    from app.intelligence.scheduler import get_scheduler
    return get_scheduler().get_status()


@router.post("/intelligence/scheduler/start")
def start_intel_scheduler() -> dict:
    """Start the intelligence scheduler (news + cleanup)."""
    from app.intelligence.scheduler import start_scheduler as _start
    sched = _start()
    return sched.get_status()


@router.post("/intelligence/scheduler/stop")
def stop_intel_scheduler() -> dict:
    """Stop the intelligence scheduler."""
    from app.intelligence.scheduler import stop_scheduler, get_scheduler
    stop_scheduler()
    return get_scheduler().get_status()


@router.post("/intelligence/scheduler/intervals")
def update_scheduler_intervals(
    news_interval: int = Query(None, ge=60),
    cleanup_interval: int = Query(None, ge=3600),
) -> dict:
    """Update scheduler intervals (seconds). News min 60s, cleanup min 3600s."""
    from app.intelligence.scheduler import get_scheduler
    sched = get_scheduler()
    sched.set_intervals(news_interval=news_interval, cleanup_interval=cleanup_interval)
    return sched.get_status()


# ---------------------------------------------------------------------------
# User Profile / Onboarding Endpoints
# ---------------------------------------------------------------------------

class OnboardingData(BaseModel):
    experience_level: str = "beginner"
    risk_tolerance: str = "moderate"
    asset_interests: list[str] = ["crypto"]
    capital_range: str = "100-1000"
    preferred_strategies: list[str] = ["swing"]
    trading_goal: str = "growth"
    preferred_language: str = "es"


@router.get("/intelligence/profile")
def get_user_profile(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Get the current user's onboarding profile."""
    import json
    from app.database.models.user_profile import UserProfile

    session = SessionLocal()
    try:
        profile = session.execute(
            select(UserProfile).where(UserProfile.user_id == current_user.id)
        ).scalar_one_or_none()

        if not profile:
            return {"onboarding_completed": False, "experience_level": None}

        return profile.to_dict()
    except Exception as exc:
        return {"onboarding_completed": False, "error": str(exc)}
    finally:
        session.close()


@router.post("/intelligence/profile")
def save_user_profile(
    data: OnboardingData,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Save or update the user's onboarding profile."""
    import json
    from app.database.models.user_profile import UserProfile

    session = SessionLocal()
    try:
        profile = session.execute(
            select(UserProfile).where(UserProfile.user_id == current_user.id)
        ).scalar_one_or_none()

        if not profile:
            profile = UserProfile(
                user_id=current_user.id,
                experience_level=data.experience_level,
                risk_tolerance=data.risk_tolerance,
                asset_interests=json.dumps(data.asset_interests),
                capital_range=data.capital_range,
                preferred_strategies=json.dumps(data.preferred_strategies),
                trading_goal=data.trading_goal,
                preferred_language=data.preferred_language,
                onboarding_completed=True,
            )
            session.add(profile)
        else:
            profile.experience_level = data.experience_level
            profile.risk_tolerance = data.risk_tolerance
            profile.asset_interests = json.dumps(data.asset_interests)
            profile.capital_range = data.capital_range
            profile.preferred_strategies = json.dumps(data.preferred_strategies)
            profile.trading_goal = data.trading_goal
            profile.preferred_language = data.preferred_language
            profile.onboarding_completed = True

        session.commit()
        return profile.to_dict()
    except Exception as exc:
        session.rollback()
        return {"error": str(exc)}
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Notification Endpoints (bell icon system)
# ---------------------------------------------------------------------------

@router.get("/notifications")
def get_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """Fetch user notifications, newest first."""
    from app.services.notification_service import get_notifications as _get

    session = SessionLocal()
    try:
        items = _get(session, unread_only=unread_only, limit=limit, offset=offset)
        return {"notifications": items, "count": len(items)}
    except Exception as exc:
        return {"notifications": [], "count": 0, "error": str(exc)}
    finally:
        session.close()


@router.get("/notifications/unread-count")
def get_unread_count() -> dict:
    """Get unread notification count for the bell badge."""
    from app.services.notification_service import get_unread_count as _count

    session = SessionLocal()
    try:
        return {"count": _count(session)}
    except Exception as exc:
        return {"count": 0, "error": str(exc)}
    finally:
        session.close()


@router.post("/notifications/{notif_id}/read")
def mark_notification_read(notif_id: int) -> dict:
    """Mark a single notification as read."""
    from app.services.notification_service import mark_read as _mark_read

    session = SessionLocal()
    try:
        ok = _mark_read(session, notif_id)
        return {"ok": ok}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        session.close()


@router.post("/notifications/read-all")
def mark_all_notifications_read() -> dict:
    """Mark all unread notifications as read."""
    from app.services.notification_service import mark_all_read as _mark_all

    session = SessionLocal()
    try:
        count = _mark_all(session)
        return {"ok": True, "updated": count}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        session.close()
