"""Aplicación FastAPI para consulta y supervisión (FASE 6)."""

import json
from collections.abc import Generator
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.api.schemas import (
    AccountSnapshotOut,
    BacktestRunOut,
    HealthOut,
    OrderOut,
    PositionOut,
    SignalOut,
    StrategyRunOut,
    TradeOut,
)
from app.config import get_settings
from app.database.models import (
    AccountSnapshot,
    BacktestRun,
    Order,
    Position,
    PredictionRecord,
    Signal,
    StrategyRun,
    Trade,
    User,
)
from app.database.session import SessionLocal

app = FastAPI(
    title="Alvora — AI Trading System",
    description="API REST para consulta y supervisión del sistema de trading algorítmico Alvora.",
    version="0.2.0",
)

_DASHBOARD_HTML = (Path(__file__).parent / "dashboard.html").read_text(encoding="utf-8")
_LANDING_HTML = (Path(__file__).parent / "landing.html").read_text(encoding="utf-8")

# Serve static files (images, etc.) from project root /images
_static_path = Path(__file__).resolve().parent.parent.parent / "images"
if _static_path.exists():
    app.mount("/images", StaticFiles(directory=str(_static_path)), name="images")

# ---------------------------------------------------------------------------
# Authentication (JWT)
# ---------------------------------------------------------------------------
from app.services.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    hash_password,
)


class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    username: str
    subscription: str
    risk_profile: str
    is_active: bool
    created_at: str


@app.post("/api/auth/register")
def auth_register(req: RegisterRequest) -> dict:
    """Registra un nuevo usuario (plan free por defecto)."""
    db = SessionLocal()
    try:
        existing = db.execute(select(User).where(User.email == req.email)).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Email ya registrado")
        existing_user = db.execute(select(User).where(User.username == req.username)).scalar_one_or_none()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username ya registrado")
        user = User(
            email=req.email,
            username=req.username,
            hashed_password=hash_password(req.password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token(user.id)
        return {
            "token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "subscription": user.subscription,
                "risk_profile": user.risk_profile,
            },
        }
    finally:
        db.close()


@app.post("/api/auth/login")
def auth_login(req: LoginRequest) -> dict:
    """Login con email y password, retorna JWT."""
    db = SessionLocal()
    try:
        user = authenticate_user(db, req.email, req.password)
        if not user:
            raise HTTPException(status_code=401, detail="Credenciales inválidas")
        token = create_access_token(user.id)
        return {
            "token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "subscription": user.subscription,
                "risk_profile": user.risk_profile,
            },
        }
    finally:
        db.close()


@app.get("/api/auth/me")
def auth_me(current_user: Annotated[User, Depends(get_current_user)]) -> dict:
    """Retorna el usuario autenticado actual."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "subscription": current_user.subscription,
        "risk_profile": current_user.risk_profile,
        "is_active": current_user.is_active,
        "created_at": str(current_user.created_at),
    }


# ---------------------------------------------------------------------------
# User Settings
# ---------------------------------------------------------------------------
from app.services.crypto import decrypt, encrypt
from app.services.rate_limit import get_plan_limits, has_feature


class UpdateSettingsRequest(BaseModel):
    binance_api_key: str | None = None
    binance_api_secret: str | None = None
    risk_profile: str | None = None
    default_symbols: str | None = None
    telegram_chat_id: str | None = None
    telegram_alerts: bool | None = None
    ai_groq_key: str | None = None
    ai_gemini_key: str | None = None


@app.get("/api/user/settings")
def get_user_settings(current_user: Annotated[User, Depends(get_current_user)]) -> dict:
    """Obtiene la configuración del usuario actual."""
    has_api_key = bool(current_user.binance_api_key_enc)
    has_groq_key = bool(current_user.ai_groq_key_enc)
    has_gemini_key = bool(current_user.ai_gemini_key_enc)
    limits = get_plan_limits(current_user.subscription)
    can_use_own_keys = "ai_provider_keys" in limits["features"]
    return {
        "email": current_user.email,
        "username": current_user.username,
        "subscription": current_user.subscription,
        "risk_profile": current_user.risk_profile,
        "has_binance_api_key": has_api_key,
        "binance_api_key_preview": decrypt(current_user.binance_api_key_enc)[:8] + "..." if has_api_key else None,
        "telegram_chat_id": current_user.telegram_chat_id,
        "telegram_alerts": current_user.telegram_alerts,
        "has_groq_key": has_groq_key,
        "has_gemini_key": has_gemini_key,
        "can_use_own_ai_keys": can_use_own_keys,
        "min_ai_interval": limits["max_ai_interval_seconds"],
    }


@app.patch("/api/user/settings")
def update_user_settings(
    req: UpdateSettingsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Actualiza la configuración del usuario."""
    db = SessionLocal()
    try:
        user = db.get(User, current_user.id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if req.binance_api_key is not None:
            user.binance_api_key_enc = encrypt(req.binance_api_key) if req.binance_api_key else None
        if req.binance_api_secret is not None:
            user.binance_api_secret_enc = encrypt(req.binance_api_secret) if req.binance_api_secret else None
        if req.risk_profile is not None:
            if req.risk_profile not in ("conservative", "moderate", "aggressive"):
                raise HTTPException(status_code=400, detail="risk_profile inválido")
            user.risk_profile = req.risk_profile
        if req.telegram_chat_id is not None:
            user.telegram_chat_id = req.telegram_chat_id
        if req.telegram_alerts is not None:
            user.telegram_alerts = req.telegram_alerts
        if req.ai_groq_key is not None:
            limits = get_plan_limits(user.subscription)
            if "ai_provider_keys" not in limits["features"]:
                raise HTTPException(status_code=403, detail="Tu plan no permite configurar API keys propias de IA. Mejora a PRO o PREMIUM.")
            user.ai_groq_key_enc = encrypt(req.ai_groq_key) if req.ai_groq_key else None
        if req.ai_gemini_key is not None:
            limits = get_plan_limits(user.subscription)
            if "ai_provider_keys" not in limits["features"]:
                raise HTTPException(status_code=403, detail="Tu plan no permite configurar API keys propias de IA. Mejora a PRO o PREMIUM.")
            user.ai_gemini_key_enc = encrypt(req.ai_gemini_key) if req.ai_gemini_key else None
        db.commit()
        db.refresh(user)
        return {
            "email": user.email,
            "username": user.username,
            "subscription": user.subscription,
            "risk_profile": user.risk_profile,
            "has_binance_api_key": bool(user.binance_api_key_enc),
            "telegram_chat_id": user.telegram_chat_id,
            "telegram_alerts": user.telegram_alerts,
            "has_groq_key": bool(user.ai_groq_key_enc),
            "has_gemini_key": bool(user.ai_gemini_key_enc),
        }
    finally:
        db.close()


@app.get("/api/user/plan")
def get_user_plan(current_user: Annotated[User, Depends(get_current_user)]) -> dict:
    """Retorna los límites y features del plan del usuario."""
    limits = get_plan_limits(current_user.subscription)
    return {
        "plan": current_user.subscription,
        "max_pairs": limits["max_pairs"] if limits["max_pairs"] < 999 else -1,
        "max_positions": limits["max_positions"] if limits["max_positions"] < 999 else -1,
        "max_ai_requests_per_day": limits["max_ai_requests_per_day"] if limits["max_ai_requests_per_day"] < 99999 else -1,
        "max_ai_interval_seconds": limits["max_ai_interval_seconds"],
        "features": limits["features"],
    }


@app.post("/api/user/telegram/test")
def test_telegram(current_user: Annotated[User, Depends(get_current_user)]) -> dict:
    """Envía un mensaje de prueba a Telegram del usuario."""
    if not current_user.telegram_chat_id:
        raise HTTPException(status_code=400, detail="Configura tu Telegram Chat ID primero")
    from app.services.telegram import send_telegram_message_sync
    ok = send_telegram_message_sync(
        current_user.telegram_chat_id,
        "✅ <b>Alvora — Test de Notificaciones</b>\n\n"
        "Tu Telegram está configurado correctamente.\n"
        "Recibirás alertas de cada operación del AI Agent.",
    )
    if not ok:
        raise HTTPException(status_code=500, detail="No se pudo enviar el mensaje. Verifica el Bot Token y Chat ID.")
    return {"ok": True, "message": "Mensaje de prueba enviado"}


# ---------------------------------------------------------------------------
# Binance Pay — Subscription payments
# ---------------------------------------------------------------------------
from app.services.binance_pay import PLAN_PRICES, create_payment_order, query_order_status


class PaymentRequest(BaseModel):
    plan: str  # "pro" or "premium"


@app.post("/api/payments/create")
def create_payment(
    req: PaymentRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Crea una orden de pago en Binance Pay para upgrade de plan."""
    if req.plan not in ("pro", "premium"):
        raise HTTPException(status_code=400, detail="Plan inválido. Opciones: pro, premium")
    if current_user.subscription == req.plan:
        raise HTTPException(status_code=400, detail=f"Ya tienes el plan {req.plan}")

    result = create_payment_order(req.plan, current_user.id, current_user.email)
    if not result:
        raise HTTPException(
            status_code=503,
            detail="Binance Pay no configurado. Contacta al administrador.",
        )
    return result


@app.get("/api/payments/status/{order_id}")
def check_payment_status(
    order_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Verifica el estado de una orden de pago."""
    result = query_order_status(order_id)
    if not result:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    # If paid, upgrade the user's plan
    if result.get("status") == "PAID":
        db = SessionLocal()
        try:
            user = db.get(User, current_user.id)
            if user and user.subscription != result.get("plan"):
                # Extract plan from order_id: ALVORA-PRO-123-...
                parts = order_id.split("-")
                if len(parts) >= 2:
                    plan = parts[1].lower()
                    if plan in ("pro", "premium"):
                        user.subscription = plan
                        db.commit()
                        result["upgraded"] = True
                        result["new_plan"] = plan
        finally:
            db.close()
    return result


@app.get("/api/payments/plans")
def get_payment_plans() -> dict:
    """Retorna los planes disponibles con precios."""
    return {
        "plans": {
            key: {
                "label": val["label"],
                "price": val["amount"],
                "currency": val["currency"],
                "duration": val["duration"],
            }
            for key, val in PLAN_PRICES.items()
        },
        "payment_method": "binance_pay",
        "enabled": bool(get_settings().BINANCE_PAY_API_KEY),
    }


@app.post("/api/payments/webhook")
async def binance_pay_webhook(request: Request) -> dict:
    """Webhook para recibir notificaciones de pago de Binance Pay."""
    body = await request.body()
    payload = body.decode()

    # Verify signature
    timestamp = request.headers.get("BinancePay-Timestamp", "")
    nonce = request.headers.get("BinancePay-Nonce", "")
    signature = request.headers.get("BinancePay-Signature", "")

    from app.services.binance_pay import verify_webhook_signature
    if not verify_webhook_signature(timestamp, nonce, payload, signature):
        raise HTTPException(status_code=401, detail="Signature verification failed")

    data = json.loads(payload)
    merchant_trade_no = data.get("merchantTradeNo", "")
    status = data.get("status", "")
    plan = data.get("goods", {}).get("referenceGoodsId", "").replace("alvora-", "").replace("-monthly", "")

    if status == "PAID" and plan in ("pro", "premium"):
        db = SessionLocal()
        try:
            # Extract user_id from order: ALVORA-PRO-123-1690293...
            parts = merchant_trade_no.split("-")
            if len(parts) >= 3:
                user_id = int(parts[2])
                user = db.get(User, user_id)
                if user:
                    user.subscription = plan
                    db.commit()
        except Exception:
            pass
        finally:
            db.close()

    return {"returnCode": "SUCCESS", "returnMessage": "OK"}


# ---------------------------------------------------------------------------
# ML training status (in-memory, single-instance)
# ---------------------------------------------------------------------------
import threading as _threading
import time as _time

_ml_status: dict = {
    "is_training": False,
    "logs": [],
    "result": None,
    "error": None,
    "started_at": None,
    "finished_at": None,
    "symbol": None,
    "progress": 0,
    "continuous": False,
    "loop_count": 0,
}
_ml_lock = _threading.Lock()
_ml_cancel = _threading.Event()


def _ml_log(msg: str) -> None:
    with _ml_lock:
        _ml_status["logs"].append(f"[{_time.strftime('%H:%M:%S')}] {msg}")
        if len(_ml_status["logs"]) > 200:
            _ml_status["logs"] = _ml_status["logs"][-200:]


# ---------------------------------------------------------------------------
# WebSocket price stream (Binance real-time)
# ---------------------------------------------------------------------------
from app.data.price_stream import init_price_stream, stop_price_stream, get_price_stream


@app.on_event("startup")
def _startup_price_stream() -> None:
    settings = get_settings()
    try:
        init_price_stream(settings.symbols_list, testnet=settings.BINANCE_TESTNET)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Failed to start price stream: %s", exc)


@app.on_event("shutdown")
def _shutdown_price_stream() -> None:
    stop_price_stream()


@app.get("/api/prices/live")
def live_prices() -> dict:
    """Precios en tiempo real desde WebSocket de Binance."""
    stream = get_price_stream()
    if not stream:
        return {"connected": False, "prices": {}, "reconnect_count": 0, "last_update_age": -1}
    return {
        "connected": stream.is_connected,
        "prices": {k: str(v) for k, v in stream.get_all_prices().items()},
        "reconnect_count": stream.reconnect_count,
        "last_update_age": round(stream.get_last_update_age(), 1),
    }


@app.get("/api/prices/live/{symbol}")
def live_price(symbol: str) -> dict:
    """Precio en tiempo real para un símbolo específico."""
    stream = get_price_stream()
    if not stream:
        return {"symbol": symbol.upper(), "price": None, "connected": False}
    price = stream.get_price(symbol)
    return {
        "symbol": symbol.upper(),
        "price": str(price) if price else None,
        "connected": stream.is_connected,
    }


@app.get("/", response_class=HTMLResponse)
def landing() -> HTMLResponse:
    """Landing page de Alvora."""
    return HTMLResponse(_LANDING_HTML)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    """Dashboard web interactivo (requiere login)."""
    return HTMLResponse(_DASHBOARD_HTML)


def get_db() -> Generator[Session, None, None]:
    """Dependencia que provee una sesión de BD por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db)]
PaginateSkip = Annotated[int, Query(ge=0)]
PaginateLimit = Annotated[int, Query(ge=1, le=200)]
SymbolQuery = Annotated[str | None, Query()]
StatusQuery = Annotated[str | None, Query()]
RunIdQuery = Annotated[int | None, Query()]


@app.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    """Estado del sistema."""
    settings = get_settings()
    stream = get_price_stream()
    ws_connected = stream.is_connected if stream else False
    return HealthOut(
        status="ok",
        trading_mode=settings.TRADING_MODE,
        live_trading_enabled=settings.LIVE_TRADING_ENABLED,
    )


@app.get("/api/market/movers")
def market_movers(
    market: str = Query("spot", pattern="^(spot|futures)$"),
    limit: int = Query(20, ge=1, le=100),
    quote: str = Query("USDT"),
) -> dict:
    """Top gainers y losers de Binance (spot o futuros USD) en 24h."""
    from app.data.binance_source import BinanceDataSource

    ds = BinanceDataSource()
    try:
        return ds.get_top_movers(market=market, limit=limit, quote=quote)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/market/smart-money")
def smart_money(
    period: str = Query("7d", pattern="^(24h|3d|7d|30d|90d|1y|all)$"),
    stat_type: str = Query("ROI", pattern="^(ROI|PNL)$"),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    """Top traders del leaderboard de Binance Futures (Smart Money)."""
    from app.data.binance_leaderboard import BinanceLeaderboard

    lb = BinanceLeaderboard()
    try:
        return lb.get_top_traders(period=period, stat_type=stat_type, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/market/smart-money/{encrypted_uid}/positions")
def smart_money_positions(encrypted_uid: str) -> list[dict]:
    """Posiciones abiertas de un trader específico del leaderboard."""
    from app.data.binance_leaderboard import BinanceLeaderboard

    lb = BinanceLeaderboard()
    try:
        return lb.get_trader_positions(encrypted_uid)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/market/smart-money/{encrypted_uid}/info")
def smart_money_info(encrypted_uid: str) -> dict:
    """Información detallada de un trader del leaderboard."""
    from app.data.binance_leaderboard import BinanceLeaderboard

    lb = BinanceLeaderboard()
    try:
        return lb.get_trader_info(encrypted_uid)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/strategy-runs", response_model=list[StrategyRunOut])
def list_strategy_runs(
    db: DbSession,
    skip: PaginateSkip = 0,
    limit: PaginateLimit = 50,
) -> list[StrategyRun]:
    return db.query(StrategyRun).order_by(StrategyRun.id.desc()).offset(skip).limit(limit).all()


@app.get("/api/strategy-runs/{run_id}", response_model=StrategyRunOut)
def get_strategy_run(run_id: int, db: DbSession) -> StrategyRun:
    run = db.get(StrategyRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="StrategyRun not found")
    return run


@app.get("/api/signals", response_model=list[SignalOut])
def list_signals(
    db: DbSession,
    skip: PaginateSkip = 0,
    limit: PaginateLimit = 50,
    symbol: SymbolQuery = None,
) -> list[Signal]:
    query = db.query(Signal)
    if symbol:
        query = query.filter(Signal.symbol == symbol.upper())
    return query.order_by(Signal.id.desc()).offset(skip).limit(limit).all()


class ManualSignalRequest(BaseModel):
    """Payload para importar una señal manual."""
    symbol: str
    signal_type: str  # BUY, SELL, HOLD
    entry_price: float | None = None
    confidence: float = 1.0
    explanation: str = ""


@app.post("/api/signals", response_model=SignalOut, status_code=201)
def create_signal(req: ManualSignalRequest, db: DbSession) -> Signal:
    """Importa una señal manual para trackear trends."""
    from datetime import UTC, datetime

    signal = Signal(
        timestamp=datetime.now(tz=UTC),
        symbol=req.symbol.upper(),
        signal_type=req.signal_type.upper(),
        confidence=Decimal(str(req.confidence)),
        entry_price=Decimal(str(req.entry_price)) if req.entry_price else None,
        suggested_stop_loss=None,
        suggested_take_profit=None,
        strategy_name="Manual",
        explanation=req.explanation or "Señal importada manualmente",
        metadata_json={"source": "manual"},
        status="active",
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal


@app.delete("/api/signals/{signal_id}")
def delete_signal(signal_id: int, db: DbSession) -> dict:
    """Elimina una señal por ID."""
    signal = db.get(Signal, signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    db.delete(signal)
    db.commit()
    return {"status": "deleted", "id": signal_id}


@app.get("/api/orders", response_model=list[OrderOut])
def list_orders(
    db: DbSession,
    skip: PaginateSkip = 0,
    limit: PaginateLimit = 50,
    symbol: SymbolQuery = None,
) -> list[Order]:
    query = db.query(Order)
    if symbol:
        query = query.filter(Order.symbol == symbol.upper())
    return query.order_by(Order.id.desc()).offset(skip).limit(limit).all()


@app.get("/api/positions", response_model=list[PositionOut])
def list_positions(
    db: DbSession,
    skip: PaginateSkip = 0,
    limit: PaginateLimit = 50,
    status: StatusQuery = None,
) -> list[Position]:
    query = db.query(Position)
    if status:
        query = query.filter(Position.status == status.lower())
    # Sort: open positions first, then by id desc
    positions = query.order_by(
        case((Position.status == "open", 0), else_=1),
        Position.id.desc(),
    ).offset(skip).limit(limit).all()

    # Update current_price and unrealized_pnl for open positions
    open_positions = [p for p in positions if p.status == "open"]
    if open_positions:
        import httpx as _httpx
        from decimal import Decimal as Dec
        updated = False
        for pos in open_positions:
            try:
                live = None
                resp = _httpx.get(
                    f"https://api.binance.com/api/v3/ticker/price?symbol={pos.symbol}",
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    live = float(resp.json()["price"])
                else:
                    resp = _httpx.get(
                        f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={pos.symbol}",
                        timeout=5.0,
                    )
                    if resp.status_code == 200:
                        live = float(resp.json()["price"])
                if live and live > 0:
                    pos.current_price = Dec(str(live))
                    pos.unrealized_pnl = (Dec(str(live)) - pos.entry_price) * pos.quantity
                    updated = True
            except Exception:
                pass
        if updated:
            db.commit()

    return positions


@app.get("/api/trades", response_model=list[TradeOut])
def list_trades(
    db: DbSession,
    skip: PaginateSkip = 0,
    limit: PaginateLimit = 50,
    symbol: SymbolQuery = None,
) -> list[Trade]:
    query = db.query(Trade)
    if symbol:
        query = query.filter(Trade.symbol == symbol.upper())
    return query.order_by(Trade.id.desc()).offset(skip).limit(limit).all()


@app.get("/api/backtests", response_model=list[BacktestRunOut])
def list_backtests(
    db: DbSession,
    skip: PaginateSkip = 0,
    limit: PaginateLimit = 50,
) -> list[BacktestRun]:
    return db.query(BacktestRun).order_by(BacktestRun.id.desc()).offset(skip).limit(limit).all()


@app.get("/api/backtests/{run_id}", response_model=BacktestRunOut)
def get_backtest(run_id: int, db: DbSession) -> BacktestRun:
    run = db.get(BacktestRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="BacktestRun not found")
    return run


@app.get("/api/snapshots", response_model=list[AccountSnapshotOut])
def list_snapshots(
    db: DbSession,
    skip: PaginateSkip = 0,
    limit: PaginateLimit = 50,
    strategy_run_id: RunIdQuery = None,
) -> list[AccountSnapshot]:
    query = db.query(AccountSnapshot)
    if strategy_run_id is not None:
        query = query.filter(AccountSnapshot.strategy_run_id == strategy_run_id)
    return query.order_by(AccountSnapshot.id.desc()).offset(skip).limit(limit).all()


class PaperTradingStartRequest(BaseModel):
    """Payload para iniciar paper trading."""
    strategies: list[str] = ["trend"]  # "trend", "ml", o ambas
    timeframe: str | None = None  # ej: "5m", "15m", "1h", "1d"
    interval_seconds: int | None = None  # intervalo entre ticks (min 5s)


class DepositRequest(BaseModel):
    """Payload para depositar fondos en la cuenta de paper trading."""
    amount: float


class SellRequest(BaseModel):
    """Payload para cerrar una posicion manualmente."""
    symbol: str


_paper_trading_state: dict = {"schedulers": [], "run_ids": []}
_ai_shared_broker = None
# Initialize from config so it persists across server restarts
_ai_allocated_capital: float = float(get_settings().AI_ALLOCATED_CAPITAL) if get_settings().AI_ALLOCATED_CAPITAL else 0.0


def _build_strategy(name: str, settings):
    """Construye una estrategia por nombre."""
    if name == "ml":
        from pathlib import Path
        from app.ml import MLPredictor
        model_path = "models/BTCUSDT_ml_model.json"
        if not Path(model_path).exists():
            raise HTTPException(status_code=400, detail="No hay modelo ML entrenado. Entrena uno primero.")
        predictor = MLPredictor.load(model_path)
        from app.ml.strategy import MLStrategy, MLStrategyConfig
        return MLStrategy(model=predictor.model, feature_engineer=predictor.feature_engineer, config=MLStrategyConfig())
    # default: trend
    from app.strategies import TrendMomentumConfig, TrendMomentumStrategy
    return TrendMomentumStrategy(TrendMomentumConfig())


@app.post("/api/paper-trading/start")
def paper_trading_start(req: PaperTradingStartRequest | None = None) -> dict:
    """Inicia paper trading desde la API."""
    if _paper_trading_state["schedulers"]:
        return {"status": "already_running", "run_ids": _paper_trading_state["run_ids"]}

    from app.data import MarketDataService
    from app.factories import create_broker, create_data_source
    from app.paper_trading import PaperTradingScheduler
    from app.risk import RiskManager

    settings = get_settings()
    if not settings.PAPER_TRADING_ENABLED:
        raise HTTPException(status_code=400, detail="PAPER_TRADING_ENABLED=false")

    strategy_names = req.strategies if req else ["trend"]
    if not strategy_names:
        strategy_names = ["trend"]

    if req and req.timeframe:
        settings.DATA_TIMEFRAME = req.timeframe
    if req and req.interval_seconds and req.interval_seconds >= 5:
        settings.PAPER_TRADING_INTERVAL_SECONDS = req.interval_seconds

    schedulers = []
    run_ids = []
    from app.brokers import MockBroker
    shared_broker = MockBroker(initial_cash=settings.PAPER_TRADING_INITIAL_CASH)
    # Sync broker state from DB open positions (handles restarts)
    from app.database.models.position import Position as PosModel
    sync_session = SessionLocal()
    try:
        open_pos = sync_session.query(PosModel).filter_by(status="open").all()
        if open_pos:
            shared_broker.sync_from_db(open_pos, settings.PAPER_TRADING_INITIAL_CASH)
    finally:
        sync_session.close()
    for name in strategy_names:
        strategy = _build_strategy(name, settings)
        scheduler = PaperTradingScheduler(
            settings=settings,
            strategy=strategy,
            data_service=MarketDataService(create_data_source(settings)),
            broker=shared_broker,
            risk_manager=RiskManager(settings),
            session_factory=SessionLocal,
        )
        run = scheduler.start()
        schedulers.append(scheduler)
        run_ids.append(run.id)

    _paper_trading_state["schedulers"] = schedulers
    _paper_trading_state["run_ids"] = run_ids
    return {"status": "started", "run_ids": run_ids, "strategies": strategy_names}


@app.post("/api/paper-trading/stop")
def paper_trading_stop() -> dict:
    """Detiene paper trading desde la API."""
    schedulers = _paper_trading_state["schedulers"]
    if not schedulers:
        return {"status": "not_running", "run_ids": []}
    run_ids = _paper_trading_state["run_ids"]
    for scheduler in schedulers:
        try:
            scheduler.stop()
        except Exception:
            pass
    _paper_trading_state["schedulers"] = []
    _paper_trading_state["run_ids"] = []
    return {"status": "stopped", "run_ids": run_ids}


@app.get("/api/paper-trading/status")
def paper_trading_status() -> dict:
    """Estado del paper trading."""
    settings = get_settings()
    schedulers = _paper_trading_state["schedulers"]
    interval = settings.PAPER_TRADING_INTERVAL_SECONDS
    if not schedulers:
        return {"status": "stopped", "run_ids": [], "local_time": settings.now_local().strftime("%Y-%m-%d %H:%M:%S %Z"), "interval_seconds": interval}
    any_running = any(s.is_running for s in schedulers)
    return {"status": "running" if any_running else "stopped", "run_ids": _paper_trading_state["run_ids"], "local_time": settings.now_local().strftime("%Y-%m-%d %H:%M:%S %Z"), "interval_seconds": interval}


class IntervalRequest(BaseModel):
    """Payload para cambiar el intervalo de ticks."""
    interval_seconds: int


@app.patch("/api/paper-trading/interval")
def paper_trading_set_interval(req: IntervalRequest) -> dict:
    """Cambia el intervalo de ticks del paper trading en tiempo real."""
    if req.interval_seconds < 5:
        raise HTTPException(status_code=400, detail="El intervalo mínimo es 5 segundos")
    settings = get_settings()
    settings.PAPER_TRADING_INTERVAL_SECONDS = req.interval_seconds
    schedulers = _paper_trading_state["schedulers"]
    for scheduler in schedulers:
        scheduler.set_interval(req.interval_seconds)
    return {"status": "ok", "interval_seconds": req.interval_seconds}


@app.post("/api/paper-trading/deposit")
def paper_trading_deposit(req: DepositRequest) -> dict:
    """Deposita fondos en la cuenta de paper trading activa."""
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser positivo")
    schedulers = _paper_trading_state["schedulers"]
    if not schedulers:
        raise HTTPException(status_code=400, detail="Paper trading no está activo")
    from decimal import Decimal
    results = []
    for scheduler in schedulers:
        broker = scheduler.broker
        if hasattr(broker, "deposit"):
            new_cash = broker.deposit(Decimal(str(req.amount)))
            results.append({"broker": broker.name, "cash": str(new_cash)})
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Broker {broker.name} no soporta depósitos",
            )
    return {"status": "deposited", "amount": req.amount, "accounts": results}


@app.post("/api/paper-trading/sell")
def paper_trading_sell(req: SellRequest) -> dict:
    """Cierra una posicion manualmente por simbolo."""
    schedulers = _paper_trading_state["schedulers"]
    if not schedulers:
        raise HTTPException(status_code=400, detail="Paper trading no está activo")
    results = []
    for scheduler in schedulers:
        result = scheduler.manual_sell(req.symbol)
        results.append(result)
    return {"status": "sell_completed", "symbol": req.symbol, "results": results}


class MLTrainRequest(BaseModel):
    """Payload para entrenar modelo ML."""
    symbol: str = "BTCUSDT"
    forward_window: int = 5
    threshold: float = 0.005
    timeframe: str = "1h"
    continuous: bool = False


@app.post("/api/ml/train")
def ml_train(req: MLTrainRequest) -> dict:
    """Entrena un modelo ML en background con logs en tiempo real."""
    with _ml_lock:
        if _ml_status["is_training"]:
            raise HTTPException(status_code=409, detail="Ya hay un entrenamiento en curso")

    _ml_cancel.clear()

    def _train_one():
        """Ejecuta una iteración completa de entrenamiento. Retorna (version_id, metrics, model_path)."""
        from datetime import UTC, date, datetime, timedelta
        from pathlib import Path

        from app.data import MarketDataService
        from app.database.models.model_version import ModelVersion
        from app.factories import create_data_source
        from app.ml import MLPredictor

        _ml_log(f"Iniciando entrenamiento para {req.symbol} (timeframe={req.timeframe}, FW={req.forward_window})")
        _ml_log("Creando predictor y feature engineer...")
        predictor = MLPredictor()
        _ml_log(f"Features: {len(predictor.feature_engineer.FEATURE_COLUMNS)} columnas técnicas")
        _ml_log(f"Algoritmo: {'LightGBM' if predictor.model._use_sklearn else 'LogisticRegression'}")

        _ml_log("Conectando a Binance para descargar datos históricos (365 días)...")
        _ml_status["progress"] = 10
        ds = MarketDataService(create_data_source(get_settings()))
        end = date.today()
        start = end - timedelta(days=365)
        df = ds.get_historical_bars(req.symbol, start, end, timeframe=req.timeframe)

        _ml_log(f"Datos descargados: {len(df)} barras de {df.index[0] if len(df) > 0 else 'N/A'} a {df.index[-1] if len(df) > 0 else 'N/A'}")
        _ml_status["progress"] = 30

        min_bars = predictor.feature_engineer.min_bars + 10
        if len(df) < min_bars:
            raise ValueError(f"Datos insuficientes: {len(df)} barras (mínimo {min_bars})")

        _ml_log("Construyendo features técnicos (EMA, RSI, ATR, Bollinger, MACD, volatilidad...)...")
        _ml_status["progress"] = 40
        x, y = predictor.feature_engineer.build_training_data(df, req.forward_window, req.threshold)
        _ml_log(f"Dataset de entrenamiento: {len(x)} samples, {len(x.columns)} features")
        _ml_log(f"Distribución de labels: BUY={int((y == 1).sum())}, SELL={int((y == 0).sum())}")

        _ml_log("Entrenando modelo ML...")
        _ml_status["progress"] = 60
        t0 = _time.time()
        metrics = predictor.train(df, forward_window=req.forward_window, threshold=req.threshold)
        elapsed = _time.time() - t0
        _ml_log(f"Modelo entrenado en {elapsed:.1f}s")
        _ml_log(f"Train Accuracy: {(metrics['train_accuracy'] * 100):.1f}% | Val Accuracy: {(metrics.get('val_accuracy', 0) * 100):.1f}%")
        _ml_log(f"Algoritmo: {metrics.get('algorithm', 'unknown')} | Split: {metrics.get('train_size', 0)} train / {metrics.get('test_size', 0)} test")
        _ml_log(f"Samples: {metrics['n_samples']}, Features: {metrics['n_features']}")
        _ml_status["progress"] = 80

        _ml_log("Guardando modelo a disco...")
        Path("models").mkdir(exist_ok=True)
        model_path = f"models/{req.symbol}_ml_model.json"
        predictor.save(model_path)
        _ml_log(f"Modelo guardado en: {model_path}")

        _ml_log("Registrando versión en base de datos...")
        _ml_status["progress"] = 90
        db_session = SessionLocal()
        try:
            version = ModelVersion(
                name=f"{req.symbol}_lgbm",
                version=datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S"),
                path=model_path,
                metrics=metrics,
                status="experimental",
            )
            db_session.add(version)
            db_session.commit()
            db_session.refresh(version)
            version_id = version.id
        finally:
            db_session.close()

        _ml_log(f"Entrenamiento completado. Version ID: {version_id}")
        return version_id, metrics, model_path

    def _train_worker():
        from datetime import UTC, datetime

        try:
            with _ml_lock:
                _ml_status["is_training"] = True
                _ml_status["logs"] = []
                _ml_status["result"] = None
                _ml_status["error"] = None
                _ml_status["started_at"] = datetime.now(tz=UTC).isoformat()
                _ml_status["finished_at"] = None
                _ml_status["symbol"] = req.symbol
                _ml_status["progress"] = 0
                _ml_status["continuous"] = req.continuous
                _ml_status["loop_count"] = 0

            loop = 0
            while True:
                loop += 1
                with _ml_lock:
                    _ml_status["loop_count"] = loop
                if req.continuous:
                    _ml_log(f"=== Ciclo continuo #{loop} ===")

                _ml_status["progress"] = 0
                version_id, metrics, model_path = _train_one()

                _ml_status["progress"] = 100
                with _ml_lock:
                    _ml_status["result"] = {
                        "status": "trained",
                        "model_version_id": version_id,
                        "metrics": metrics,
                        "path": model_path,
                        "loop": loop,
                    }

                if not req.continuous:
                    break

                if _ml_cancel.is_set():
                    _ml_log("Entrenamiento continuo cancelado por el usuario")
                    break

                _ml_log("Esperando 5s antes del siguiente ciclo...")
                for _ in range(5):
                    if _ml_cancel.is_set():
                        break
                    _time.sleep(1)

                if _ml_cancel.is_set():
                    _ml_log("Entrenamiento continuo cancelado por el usuario")
                    break

                _ml_log("Iniciando siguiente ciclo de entrenamiento...")

            with _ml_lock:
                _ml_status["finished_at"] = datetime.now(tz=UTC).isoformat()
                _ml_status["is_training"] = False
                _ml_status["continuous"] = False
        except Exception as exc:
            _ml_log(f"ERROR: {exc}")
            with _ml_lock:
                _ml_status["error"] = str(exc)
                _ml_status["is_training"] = False
                _ml_status["continuous"] = False
                _ml_status["finished_at"] = datetime.now(tz=UTC).isoformat()

    thread = _threading.Thread(target=_train_worker, daemon=True)
    thread.start()
    return {"status": "started", "message": "Entrenamiento iniciado en background" + (" (continuo)" if req.continuous else "")}


@app.post("/api/ml/cancel")
def ml_cancel() -> dict:
    """Cancela el entrenamiento ML en curso (incluye modo continuo)."""
    _ml_cancel.set()
    return {"status": "cancel_requested"}


@app.post("/api/ml/reset")
def ml_reset() -> dict:
    """Fuerza el reset del estado de entrenamiento (para entrenamientos atorados)."""
    _ml_cancel.set()
    with _ml_lock:
        _ml_status["is_training"] = False
        _ml_status["continuous"] = False
        _ml_status["progress"] = 0
        _ml_status["finished_at"] = datetime.now(tz=UTC).isoformat()
    return {"status": "reset_ok"}


@app.get("/api/ml/status")
def ml_status() -> dict:
    """Retorna el estado actual del entrenamiento ML con logs en tiempo real."""
    with _ml_lock:
        return {
            "is_training": _ml_status["is_training"],
            "logs": list(_ml_status["logs"]),
            "result": _ml_status["result"],
            "error": _ml_status["error"],
            "started_at": _ml_status["started_at"],
            "finished_at": _ml_status["finished_at"],
            "symbol": _ml_status["symbol"],
            "progress": _ml_status["progress"],
            "continuous": _ml_status["continuous"],
            "loop_count": _ml_status["loop_count"],
        }


@app.get("/api/ml/model-info")
def ml_model_info(db: DbSession) -> dict:
    """Info del modelo ML actual: última versión, métricas, algoritmo, features."""
    from app.database.models.model_version import ModelVersion

    version = (
        db.query(ModelVersion)
        .order_by(ModelVersion.id.desc())
        .first()
    )
    if not version:
        return {"has_model": False}
    m = version.metrics or {}
    return {
        "has_model": True,
        "id": version.id,
        "name": version.name,
        "version": version.version,
        "status": version.status,
        "created_at": version.created_at.isoformat() if version.created_at else None,
        "path": version.path,
        "algorithm": m.get("algorithm"),
        "train_accuracy": m.get("train_accuracy"),
        "val_accuracy": m.get("val_accuracy"),
        "n_samples": m.get("n_samples"),
        "n_features": m.get("n_features"),
        "forward_window": m.get("forward_window"),
        "threshold": m.get("threshold"),
        "live_accuracy": m.get("live_accuracy"),
        "live_evaluated": m.get("live_evaluated"),
    }


@app.get("/api/ml/predictions")
def ml_predictions(
    db: DbSession,
    skip: PaginateSkip = 0,
    limit: PaginateLimit = 50,
    symbol: SymbolQuery = None,
) -> list[dict]:
    """Lista las predicciones ML registradas durante paper trading."""
    query = db.query(PredictionRecord)
    if symbol:
        query = query.filter(PredictionRecord.symbol == symbol.upper())
    records = query.order_by(PredictionRecord.id.desc()).offset(skip).limit(limit).all()
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp.isoformat(),
            "symbol": r.symbol,
            "signal_type": r.signal_type,
            "probability": float(r.probability),
            "price_at_prediction": float(r.price_at_prediction),
            "evaluated": r.evaluated,
            "actual_direction": r.actual_direction,
            "correct": r.correct,
            "price_at_evaluation": float(r.price_at_evaluation) if r.price_at_evaluation else None,
            "evaluated_at": r.evaluated_at.isoformat() if r.evaluated_at else None,
            "strategy_run_id": r.strategy_run_id,
        }
        for r in records
    ]


@app.get("/api/ml/accuracy")
def ml_accuracy(db: DbSession) -> dict:
    """Accuracy en vivo del modelo ML basado en predicciones evaluadas."""
    from sqlalchemy import and_, case, func

    rows = db.query(
        func.sum(case((PredictionRecord.evaluated == True, 1), else_=0)).label("total_evaluated"),
        func.sum(case((and_(PredictionRecord.evaluated == True, PredictionRecord.correct == True), 1), else_=0)).label("correct"),
        func.sum(case((PredictionRecord.evaluated == False, 1), else_=0)).label("pending"),
        func.sum(case((and_(PredictionRecord.evaluated == True, PredictionRecord.signal_type == "BUY", PredictionRecord.correct == True), 1), else_=0)).label("buy_correct"),
        func.sum(case((and_(PredictionRecord.evaluated == True, PredictionRecord.signal_type == "BUY"), 1), else_=0)).label("buy_total"),
        func.sum(case((and_(PredictionRecord.evaluated == True, PredictionRecord.signal_type == "SELL", PredictionRecord.correct == True), 1), else_=0)).label("sell_correct"),
        func.sum(case((and_(PredictionRecord.evaluated == True, PredictionRecord.signal_type == "SELL"), 1), else_=0)).label("sell_total"),
    ).one()

    total = int(rows.total_evaluated or 0)
    correct = int(rows.correct or 0)
    pending = int(rows.pending or 0)
    buy_total = int(rows.buy_total or 0)
    buy_correct = int(rows.buy_correct or 0)
    sell_total = int(rows.sell_total or 0)
    sell_correct = int(rows.sell_correct or 0)

    return {
        "total_evaluated": total,
        "correct": correct,
        "accuracy": correct / total if total > 0 else None,
        "pending": pending,
        "buy_accuracy": buy_correct / buy_total if buy_total > 0 else None,
        "buy_total": buy_total,
        "sell_accuracy": sell_correct / sell_total if sell_total > 0 else None,
        "sell_total": sell_total,
    }


@app.post("/api/ml/retrain")
def ml_retrain(req: MLTrainRequest) -> dict:
    """Re-entrena el modelo con feedback de paper trading en background."""
    with _ml_lock:
        if _ml_status["is_training"]:
            raise HTTPException(status_code=409, detail="Ya hay un entrenamiento en curso")

    def _retrain_worker():
        from datetime import UTC, date, datetime, timedelta
        from pathlib import Path

        from app.data import MarketDataService
        from app.database.models.model_version import ModelVersion
        from app.factories import create_data_source
        from app.ml import MLPredictor

        try:
            with _ml_lock:
                _ml_status["is_training"] = True
                _ml_status["logs"] = []
                _ml_status["result"] = None
                _ml_status["error"] = None
                _ml_status["started_at"] = datetime.now(tz=UTC).isoformat()
                _ml_status["finished_at"] = None
                _ml_status["symbol"] = req.symbol
                _ml_status["progress"] = 0

            _ml_log(f"Iniciando RE-entrenamiento para {req.symbol} con feedback...")
            predictor = MLPredictor()
            _ml_log(f"Algoritmo: {'LightGBM' if predictor.model._use_sklearn else 'LogisticRegression'}")

            _ml_log("Descargando datos históricos (365 días)...")
            _ml_status["progress"] = 10
            ds = MarketDataService(create_data_source(get_settings()))
            end = date.today()
            start = end - timedelta(days=365)
            df = ds.get_historical_bars(req.symbol, start, end, timeframe=req.timeframe)
            _ml_log(f"Datos: {len(df)} barras")
            _ml_status["progress"] = 30

            min_bars = predictor.feature_engineer.min_bars + 10
            if len(df) < min_bars:
                raise ValueError(f"Datos insuficientes: {len(df)} barras (mínimo {min_bars})")

            _ml_log("Construyendo features y dataset...")
            _ml_status["progress"] = 40
            x, y = predictor.feature_engineer.build_training_data(df, req.forward_window, req.threshold)
            _ml_log(f"Dataset: {len(x)} samples, BUY={int((y == 1).sum())}, SELL={int((y == 0).sum())}")

            _ml_log("Entrenando modelo...")
            _ml_status["progress"] = 60
            t0 = _time.time()
            metrics = predictor.train(df, forward_window=req.forward_window, threshold=req.threshold)
            elapsed = _time.time() - t0
            _ml_log(f"Modelo entrenado en {elapsed:.1f}s")
            _ml_log(f"Train Accuracy: {(metrics['train_accuracy'] * 100):.1f}% | Val Accuracy: {(metrics.get('val_accuracy', 0) * 100):.1f}%")
            _ml_log(f"Algoritmo: {metrics.get('algorithm', 'unknown')} | Split: {metrics.get('train_size', 0)} train / {metrics.get('test_size', 0)} test")

            _ml_log("Evaluando accuracy en vivo desde paper trading...")
            _ml_status["progress"] = 75
            db_session = SessionLocal()
            try:
                acc = ml_accuracy(db_session)
            finally:
                db_session.close()
            metrics["live_accuracy"] = acc["accuracy"]
            metrics["live_evaluated"] = acc["total_evaluated"]
            if acc["accuracy"] is not None:
                _ml_log(f"Live Accuracy: {(acc['accuracy'] * 100):.1f}% ({acc['correct']}/{acc['total_evaluated']})")
            else:
                _ml_log("Sin predicciones evaluadas aún para live accuracy")

            _ml_log("Guardando modelo a disco...")
            _ml_status["progress"] = 85
            Path("models").mkdir(exist_ok=True)
            model_path = f"models/{req.symbol}_ml_model.json"
            predictor.save(model_path)

            _ml_log("Registrando versión en BD...")
            _ml_status["progress"] = 95
            db_session = SessionLocal()
            try:
                version = ModelVersion(
                    name=f"{req.symbol}_lgbm_retrained",
                    version=datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S"),
                    path=model_path,
                    metrics=metrics,
                    status="experimental",
                )
                db_session.add(version)
                db_session.commit()
                db_session.refresh(version)
                version_id = version.id
            finally:
                db_session.close()

            _ml_log(f"Re-entrenamiento completado. Version ID: {version_id}")
            _ml_status["progress"] = 100
            with _ml_lock:
                _ml_status["result"] = {
                    "status": "retrained",
                    "model_version_id": version_id,
                    "metrics": metrics,
                    "live_accuracy": acc,
                    "path": model_path,
                }
                _ml_status["finished_at"] = datetime.now(tz=UTC).isoformat()
                _ml_status["is_training"] = False
        except Exception as exc:
            _ml_log(f"ERROR: {exc}")
            with _ml_lock:
                _ml_status["error"] = str(exc)
                _ml_status["is_training"] = False
                _ml_status["finished_at"] = datetime.now(tz=UTC).isoformat()

    thread = _threading.Thread(target=_retrain_worker, daemon=True)
    thread.start()
    return {"status": "started", "message": "Re-entrenamiento iniciado en background"}


@app.get("/api/stats")
def trading_stats(db: DbSession) -> dict:
    """Estadisticas de performance por periodo: hoy, ayer, semana, todo."""
    from datetime import UTC, datetime, timedelta

    now = datetime.now(tz=UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    week_start = today_start - timedelta(days=7)

    def _period_stats(start: datetime | None) -> dict:
        q = db.query(Trade).filter(Trade.side == "SELL")
        if start is not None:
            q = q.filter(Trade.timestamp >= start)
        trades = q.all()
        pnls = [float(t.realized_pnl) for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        total_pnl = sum(pnls)
        total_trades = len(pnls)
        win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0
        avg_win = (sum(wins) / len(wins)) if wins else 0
        avg_loss = (sum(losses) / len(losses)) if losses else 0
        best_trade = max(pnls) if pnls else 0
        worst_trade = min(pnls) if pnls else 0

        # Count buy trades (entries) in the period
        buy_q = db.query(Trade).filter(Trade.side == "BUY")
        if start is not None:
            buy_q = buy_q.filter(Trade.timestamp >= start)
        entries = buy_q.count()

        # Open positions count
        open_pos = db.query(Position).filter(Position.status == "open").count()

        return {
            "trades_closed": total_trades,
            "entries": entries,
            "open_positions": open_pos,
            "total_pnl": round(total_pnl, 2),
            "win_rate": round(win_rate, 1),
            "wins": len(wins),
            "losses": len(losses),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "best_trade": round(best_trade, 2),
            "worst_trade": round(worst_trade, 2),
        }

    # Daily PnL series (last 14 days)
    daily_pnl = []
    for i in range(13, -1, -1):
        day_start = (today_start - timedelta(days=i)).replace(tzinfo=UTC)
        day_end = day_start + timedelta(days=1)
        day_trades = (
            db.query(Trade)
            .filter(Trade.side == "SELL", Trade.timestamp >= day_start, Trade.timestamp < day_end)
            .all()
        )
        day_total = sum(float(t.realized_pnl) for t in day_trades)
        daily_pnl.append({
            "date": day_start.strftime("%m-%d"),
            "pnl": round(day_total, 2),
            "trades": len(day_trades),
        })

    return {
        "today": _period_stats(today_start),
        "yesterday": _period_stats(yesterday_start),
        "week": _period_stats(week_start),
        "all_time": _period_stats(None),
        "daily_pnl": daily_pnl,
    }


@app.get("/api/risk-events")
def list_risk_events(
    db: DbSession,
    skip: PaginateSkip = 0,
    limit: PaginateLimit = 20,
) -> list[dict]:
    """Eventos de riesgo recientes (señales rechazadas y motivos)."""
    from app.database.models.risk_event import RiskEvent
    events = (
        db.query(RiskEvent)
        .order_by(RiskEvent.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": e.id,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "symbol": e.symbol,
            "reason": e.reason,
            "severity": e.severity,
            "signal_type": (e.details or {}).get("signal_type", ""),
            "strategy_name": (e.details or {}).get("strategy_name", ""),
        }
        for e in events
    ]


@app.get("/api/stats/symbols")
def stats_by_symbol(db: DbSession) -> list[dict]:
    """Estadísticas por símbolo: trades, win rate, PnL, frecuencia."""
    from sqlalchemy import and_, case, func

    rows = (
        db.query(
            Trade.symbol,
            func.count(Trade.id).label("total_trades"),
            func.sum(case((Trade.side == "BUY", 1), else_=0)).label("buys"),
            func.sum(case((Trade.side == "SELL", 1), else_=0)).label("sells"),
            func.sum(case((and_(Trade.side == "SELL", Trade.realized_pnl > 0), 1), else_=0)).label("wins"),
            func.sum(case((and_(Trade.side == "SELL", Trade.realized_pnl < 0), 1), else_=0)).label("losses"),
            func.sum(Trade.realized_pnl).label("total_pnl"),
            func.avg(Trade.price).label("avg_price"),
        )
        .group_by(Trade.symbol)
        .order_by(func.count(Trade.id).desc())
        .all()
    )

    result = []
    for r in rows:
        sells = int(r.sells or 0)
        wins = int(r.wins or 0)
        losses = int(r.losses or 0)
        win_rate = (wins / sells * 100) if sells > 0 else 0
        result.append({
            "symbol": r.symbol,
            "total_trades": int(r.total_trades),
            "buys": int(r.buys or 0),
            "sells": sells,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 1),
            "total_pnl": round(float(r.total_pnl or 0), 2),
            "avg_price": round(float(r.avg_price or 0), 4),
        })
    return result


@app.get("/api/stats/simulations")
def stats_simulations(db: DbSession) -> list[dict]:
    """Estadísticas por simulación (strategy run): PnL, trades, win rate, símbolos."""
    from sqlalchemy import case, func

    runs = (
        db.query(StrategyRun)
        .filter(StrategyRun.mode == "paper")
        .order_by(StrategyRun.id.desc())
        .limit(20)
        .all()
    )

    result = []
    for run in runs:
        sell_trades = (
            db.query(Trade)
            .filter(Trade.side == "SELL")
            .all()
        )
        sell_pnls = [float(t.realized_pnl) for t in sell_trades]
        wins = [p for p in sell_pnls if p > 0]
        losses = [p for p in sell_pnls if p < 0]
        total_pnl = sum(sell_pnls)
        win_rate = (len(wins) / len(sell_pnls) * 100) if sell_pnls else 0

        symbols_traded = list(set(t.symbol for t in sell_trades))
        buy_count = (
            db.query(func.count(Trade.id))
            .filter(Trade.side == "BUY")
            .scalar() or 0
        )

        result.append({
            "run_id": run.id,
            "strategy": run.strategy_name,
            "status": run.status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "ended_at": run.ended_at.isoformat() if run.ended_at else None,
            "total_trades": len(sell_pnls) + int(buy_count),
            "trades_closed": len(sell_pnls),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(win_rate, 1),
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(sum(wins) / len(wins), 2) if wins else 0,
            "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0,
            "symbols": symbols_traded,
            "symbol_count": len(symbols_traded),
        })
    return result


@app.get("/api/stats/by-strategy")
def stats_by_strategy(db: DbSession) -> list[dict]:
    """Estadísticas agrupadas por estrategia: win rate, PnL, trades."""
    from sqlalchemy import and_, case, func

    rows = (
        db.query(
            Signal.strategy_name,
            func.count(Trade.id).label("total_trades"),
            func.sum(case((Trade.side == "BUY", 1), else_=0)).label("buys"),
            func.sum(case((Trade.side == "SELL", 1), else_=0)).label("sells"),
            func.sum(case((and_(Trade.side == "SELL", Trade.realized_pnl > 0), 1), else_=0)).label("wins"),
            func.sum(case((and_(Trade.side == "SELL", Trade.realized_pnl < 0), 1), else_=0)).label("losses"),
            func.sum(Trade.realized_pnl).label("total_pnl"),
        )
        .join(Order, Trade.order_id == Order.id)
        .join(Signal, Order.signal_id == Signal.id)
        .group_by(Signal.strategy_name)
        .all()
    )

    result = []
    for r in rows:
        sells = int(r.sells or 0)
        wins = int(r.wins or 0)
        losses = int(r.losses or 0)
        win_rate = (wins / sells * 100) if sells > 0 else 0
        pnl = float(r.total_pnl or 0)
        result.append({
            "strategy": r.strategy_name,
            "total_trades": int(r.total_trades or 0),
            "buys": int(r.buys or 0),
            "sells": sells,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 1),
            "total_pnl": round(pnl, 2),
            "avg_pnl": round(pnl / sells, 2) if sells > 0 else 0,
        })
    return result


@app.post("/api/stats/reset")
def reset_stats(db: DbSession, force: bool = Query(False)) -> dict:
    """Elimina todos los trades, orders, signals, positions y snapshots para reiniciar stats.

    En modo live, bloquea el reset si hay posiciones abiertas para evitar
    perder el rastreo de posiciones reales en Binance.
    Usa ?force=true para forzar el reset (ej: posiciones de test atoradas).
    """
    settings = get_settings()
    is_live = settings.TRADING_MODE == "live" and settings.LIVE_TRADING_ENABLED

    if is_live and not force:
        open_count = db.query(Position).filter(Position.status == "open").count()
        if open_count > 0:
            raise HTTPException(
                status_code=403,
                detail=f"No se puede reiniciar stats en modo live con {open_count} posiciones abiertas. "
                       "Cierra todas las posiciones primero, o usa force=true si son posiciones de test.",
            )

    db.query(Trade).delete()
    db.query(Order).delete()
    db.query(Signal).delete()
    db.query(Position).delete()
    db.query(AccountSnapshot).delete()
    db.query(PredictionRecord).delete()
    db.query(StrategyRun).filter(StrategyRun.mode == "paper").delete()
    db.commit()
    return {"status": "ok", "message": "Stats reiniciados" + (" (forzado)" if force and is_live else "")}


@app.get("/api/charts/position/{symbol}")
def position_chart_data(symbol: str, db: DbSession) -> dict:
    """Datos para graficar una posicion abierta: niveles de entrada, SL, TP y precio live."""
    from app.config import get_settings

    settings = get_settings()
    pos = db.query(Position).filter_by(symbol=symbol.upper(), status="open").first()
    if pos is None:
        raise HTTPException(status_code=404, detail="No hay posicion abierta para " + symbol)

    # Fetch live price from Binance (spot first, then futures)
    live_price = None
    try:
        import httpx as _httpx
        resp = _httpx.get(
            f"https://api.binance.com/api/v3/ticker/price?symbol={symbol.upper()}",
            timeout=5.0,
        )
        if resp.status_code == 200:
            live_price = float(resp.json()["price"])
        else:
            resp = _httpx.get(
                f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol.upper()}",
                timeout=5.0,
            )
            if resp.status_code == 200:
                live_price = float(resp.json()["price"])
    except Exception:
        pass

    # Update position current_price and unrealized_pnl in DB
    if live_price and live_price > 0:
        from decimal import Decimal as Dec
        pos.current_price = Dec(str(live_price))
        pos.unrealized_pnl = (Dec(str(live_price)) - pos.entry_price) * pos.quantity
        db.add(pos)
        db.commit()

    entry = float(pos.entry_price)
    pnl_pct = ((live_price - entry) / entry * 100) if live_price and entry > 0 else 0.0

    return {
        "symbol": symbol.upper(),
        "entry_price": entry,
        "current_price": live_price,
        "stop_loss": float(pos.stop_loss) if pos.stop_loss else None,
        "take_profit": float(pos.take_profit) if pos.take_profit else None,
        "quantity": float(pos.quantity),
        "opened_at": pos.opened_at.isoformat() if pos.opened_at else None,
        "live_price": live_price,
        "unrealized_pnl": float(pos.unrealized_pnl) if pos.unrealized_pnl else 0.0,
        "pnl_pct": pnl_pct,
        "timeframe": settings.DATA_TIMEFRAME,
    }


# ---------------------------------------------------------------------------
# AI Agent — agente de IA autónomo
# ---------------------------------------------------------------------------

from app.ai.agent import AITradingAgent

_ai_agent: AITradingAgent | None = None
_ai_lock = _threading.Lock()


def _get_or_create_agent() -> AITradingAgent:
    global _ai_agent
    with _ai_lock:
        if _ai_agent is None:
            settings = get_settings()
            _ai_agent = AITradingAgent(
                provider=getattr(settings, "AI_PROVIDER", "groq"),
                groq_api_key=getattr(settings, "GROQ_API_KEY", None),
                groq_model=getattr(settings, "AI_MODEL", "llama-3.1-8b-instant"),
                gemini_api_key=getattr(settings, "GEMINI_API_KEY", None),
                gemini_model=getattr(settings, "AI_MODEL", "gemini-2.0-flash"),
                ollama_url=getattr(settings, "OLLAMA_URL", "http://localhost:11434"),
                ollama_model=getattr(settings, "OLLAMA_MODEL", "qwen2.5:14b"),
                interval_seconds=getattr(settings, "AI_INTERVAL_SECONDS", 30),
                auto_trade=getattr(settings, "AI_AUTO_TRADE", True),
            )
        return _ai_agent


class AIStartRequest(BaseModel):
    provider: str | None = None
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    model: str | None = None
    interval_seconds: int | None = None
    auto_trade: bool | None = None


@app.post("/api/ai-agent/start")
def ai_agent_start(
    req: AIStartRequest = AIStartRequest(),
    current_user: Annotated[User, Depends(get_current_user)] = None,
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
    agent = _get_or_create_agent()
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
        else:
            agent.ollama_model = req.model

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

    agent.start()
    # Create initial snapshot so overview tab shows data
    try:
        broker = _get_shared_broker()
        _create_ai_snapshot(broker)
    except Exception:
        pass
    return agent.get_status()


@app.post("/api/ai-agent/stop")
def ai_agent_stop() -> dict:
    """Detiene el agente de IA."""
    agent = _get_or_create_agent()
    agent.stop()
    return agent.get_status()


@app.get("/api/ai-agent/status")
def ai_agent_status() -> dict:
    """Obtiene el estado del agente de IA."""
    agent = _get_or_create_agent()
    return agent.get_status()


@app.get("/api/ai-agent/log")
def ai_agent_log(limit: int = Query(50, ge=1, le=200)) -> list[dict]:
    """Obtiene el log de decisiones del agente de IA."""
    agent = _get_or_create_agent()
    return agent.get_log(limit=limit)


@app.patch("/api/ai-agent/interval")
def ai_agent_set_interval(interval_seconds: int = Query(30, ge=10)) -> dict:
    """Cambia el intervalo de análisis del agente de IA."""
    agent = _get_or_create_agent()
    agent.set_interval(interval_seconds)
    return agent.get_status()


@app.get("/api/binance/balance")
def get_binance_balance() -> dict:
    """Consulta el saldo real de Binance en tiempo real.

    Retorna todos los activos con balance > 0, valor en USD y MXN.
    Solo funciona si BROKER_PROVIDER=binance con API keys configuradas.
    """
    import httpx as _httpx

    settings = get_settings()
    if settings.BROKER_PROVIDER != "binance" or not settings.BROKER_API_KEY:
        return {"error": "Binance no configurado", "assets": [], "total_usd": 0, "total_mxn": 0}

    from app.brokers.binance_broker import BinanceBroker

    broker = BinanceBroker(
        api_key=settings.BROKER_API_KEY,
        api_secret=settings.BROKER_API_SECRET,
        testnet=settings.BINANCE_TESTNET,
    )

    try:
        resp = broker._signed_request("GET", "/api/v3/account", {})
    except Exception as exc:
        return {"error": f"No se pudo conectar a Binance: {exc}", "assets": [], "total_usd": 0, "total_mxn": 0}

    balances = resp.get("balances", [])
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
        free = float(b["free"])
        locked = float(b["locked"])
        total = free + locked
        if total <= 0:
            continue

        asset = b["asset"]
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


@app.patch("/api/ai-agent/auto-trade")
def ai_agent_set_auto_trade(enabled: bool = Query(True)) -> dict:
    """Habilita o deshabilita la ejecución automática de trades."""
    agent = _get_or_create_agent()
    agent.auto_trade = enabled
    return agent.get_status()


@app.get("/api/trading-mode")
def get_trading_mode() -> dict:
    """Retorna el modo de trading actual y configuración de safety."""
    global _ai_allocated_capital
    settings = get_settings()
    is_live = settings.TRADING_MODE == "live" and settings.LIVE_TRADING_ENABLED
    is_binance = settings.BROKER_PROVIDER == "binance" and bool(settings.BROKER_API_KEY)
    # Use runtime override if set, otherwise use config value
    allocated = _ai_allocated_capital if _ai_allocated_capital > 0 else settings.AI_ALLOCATED_CAPITAL
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


@app.patch("/api/ai-agent/capital")
def set_ai_capital(amount: float = Query(0, ge=0)) -> dict:
    """Asigna cuánto capital (USD) puede usar el AI Agent para trading.

    Set 0 para usar todo el saldo disponible de la cuenta.
    Persiste el valor en .env para que sobreviva reinicios del server.
    """
    global _ai_allocated_capital
    _ai_allocated_capital = amount

    # Persist to .env file
    import os
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


@app.patch("/api/kill-switch")
def toggle_kill_switch(enabled: bool = Query(True)) -> dict:
    """Activa o desactiva el kill switch global para trading live."""
    import os
    os.environ["LIVE_KILL_SWITCH"] = str(enabled).lower()
    # Clear cached settings
    get_settings.cache_clear()
    settings = get_settings()
    return {
        "kill_switch": settings.LIVE_KILL_SWITCH,
        "message": "KILL SWITCH ACTIVADO - Todas las órdenes live bloqueadas" if enabled else "Kill switch desactivado",
    }


class AIExecuteRequest(BaseModel):
    """Payload para que el agente IA ejecute una operación directamente."""
    action_type: str  # "buy" o "sell"
    symbol: str
    confidence: float = 0.7
    reason: str = ""
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None


@app.post("/api/ai-agent/execute")
def ai_agent_execute(req: AIExecuteRequest) -> dict:
    """Ejecuta una operación de trading directamente desde el agente IA.

    No requiere paper trading activo. Usa el broker compartido y el risk manager.
    En modo live (BinanceBroker), ejecuta órdenes reales en Binance.
    """
    from datetime import UTC, datetime
    from decimal import Decimal

    from app.brokers import MockBroker
    from app.execution import ExecutionEngine
    from app.models.signal import SignalCreate
    from app.risk import RiskManager

    settings = get_settings()
    symbol = req.symbol.upper()
    action = req.action_type.lower()

    # Determinar si estamos en modo live
    is_live = settings.TRADING_MODE == "live" and settings.LIVE_TRADING_ENABLED
    is_binance_broker = settings.BROKER_PROVIDER == "binance" and bool(settings.BROKER_API_KEY)

    # Safety: Kill switch (blocks buys, allows sells to close positions)
    if is_live and settings.LIVE_KILL_SWITCH and action == "buy":
        return {"status": "rejected", "action": action, "symbol": symbol, "reason": "KILL SWITCH activado. Compras bloqueadas. Sells permitidos para cerrar posiciones."}

    # Obtener o crear broker compartido
    broker = _get_shared_broker()

    # Safety: Check daily loss limit for live mode
    if is_live and action == "buy":
        session_check = SessionLocal()
        try:
            from app.database.models.trade import Trade
            from datetime import timedelta
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
            global _ai_allocated_capital
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
            is_auto_mode = _ai_allocated_capital <= 0
            if _ai_allocated_capital > 0:
                allocated = _ai_allocated_capital
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
                _create_ai_snapshot(broker)
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
                _create_ai_snapshot(broker)
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


def _get_shared_broker():
    """Obtiene el broker compartido del paper trading o usa/crea uno persistente para AI agent.

    En modo live con BROKER_PROVIDER=binance y API keys configuradas,
    retorna un BinanceBroker real que ejecuta órdenes en Binance.
    """
    global _ai_shared_broker

    schedulers = _paper_trading_state.get("schedulers", [])
    if schedulers:
        return schedulers[0].broker

    # Reusar broker persistente del AI agent
    if _ai_shared_broker is not None:
        return _ai_shared_broker

    # Crear broker usando la factory (MockBroker o BinanceBroker según config)
    from app.database.models.position import Position as PosModel
    from app.factories import create_broker

    settings = get_settings()
    broker = create_broker(settings)

    # Si es MockBroker, sincronizar desde BD para mantener estado
    if hasattr(broker, "sync_from_db"):
        session = SessionLocal()
        try:
            open_pos = session.query(PosModel).filter_by(status="open").all()
            if open_pos:
                broker.sync_from_db(open_pos, settings.PAPER_TRADING_INITIAL_CASH)
        finally:
            session.close()

    _ai_shared_broker = broker
    return broker


def _create_ai_snapshot(broker) -> None:
    """Crea un snapshot de cuenta para que el tab Resumen muestre datos del AI Agent."""
    from datetime import UTC, datetime

    from app.database.models.account_snapshot import AccountSnapshot

    account = broker.get_account()
    session = SessionLocal()
    try:
        snapshot = AccountSnapshot(
            timestamp=datetime.now(tz=UTC),
            cash=account.cash,
            equity=account.equity,
            buying_power=account.buying_power,
            margin_used=account.margin_used,
            daily_pnl=account.daily_pnl,
            total_pnl=account.total_pnl,
            open_positions_count=account.open_positions_count,
            strategy_run_id=None,
        )
        session.add(snapshot)
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


@app.get("/api/ai-agent/stats")
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
        agent = _get_or_create_agent()
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
