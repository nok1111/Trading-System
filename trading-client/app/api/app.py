"""Trading Client — FastAPI application with license validation middleware."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.rate_limit import limiter
from app.api.schemas import HealthOut
from app.config import get_settings
from app.data.price_stream import get_price_stream, init_price_stream, stop_price_stream
from app.intelligence.scheduler import start_scheduler as start_intel_scheduler, stop_scheduler as stop_intel_scheduler
from app.services.social_scheduler import start_social_scheduler, stop_social_scheduler
from app.services.license import validate_license

app = FastAPI(
    title="Alvora Trading Client",
    description="Local trading client — AI Agent, broker, dashboard. Requires Auth Server connection.",
    version="1.0.0",
)

# Rate limiting (slowapi)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_ALLOWED_ORIGINS = ["http://localhost:1420", "http://127.0.0.1:1420", "http://tauri.localhost"]
_ALLOWED_ORIGINS_STR = ",".join(_ALLOWED_ORIGINS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-XSS-Protection"] = "1; mode=block"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return resp


# Serve static files (images, etc.) from project root /images
_static_path = Path(__file__).resolve().parent.parent.parent / "images"
if _static_path.exists():
    app.mount("/images", StaticFiles(directory=str(_static_path)), name="images")

# ---------------------------------------------------------------------------
# License validation middleware
# ---------------------------------------------------------------------------

# Paths that don't require license validation (public market data only)
_PUBLIC_PATHS = {"/", "/health", "/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect", "/api/log", "/api/binance/price", "/api/brokers"}


@app.middleware("http")
async def license_check(request: Request, call_next):
    """Validate JWT against Auth Server on every request.

    Skips public paths (health, dashboard HTML, docs, public market data).
    Attaches license info to request.state for downstream use.
    WebSocket endpoints authenticate via query token internally.
    """
    path = request.url.path
    is_public = (
        path in _PUBLIC_PATHS
        or path.startswith("/images")
        or path.startswith("/api/binance/price")
        or path.startswith("/api/klines/")
        or path.startswith("/api/social/leaders")
        or path.startswith("/api/social/leaderboard")
        or path.startswith("/api/social/signals/feed")
        or path.startswith("/api/social/ws/")
        or (
            path.startswith("/api/broker/")
            and ("/ticker" in path or "/klines" in path or "/movers" in path or "/market-info" in path or "/symbols" in path)
        )
    )
    if is_public:
        return await call_next(request)

    # Allow CORS preflight requests without auth
    if request.method == "OPTIONS":
        return await call_next(request)

    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        resp = JSONResponse(status_code=401, content={"detail": "No autenticado"})
        resp.headers["Access-Control-Allow-Origin"] = _ALLOWED_ORIGINS_STR
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        return resp

    license_info = validate_license(token)
    if not license_info or not license_info.get("valid"):
        resp = JSONResponse(
            status_code=403,
            content={"detail": "Suscripción inactiva o sin conexión al Auth Server"},
        )
        resp.headers["Access-Control-Allow-Origin"] = _ALLOWED_ORIGINS_STR
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        return resp

    request.state.user = license_info
    request.state.plan_limits = license_info.get("plan_limits", {})
    return await call_next(request)


# ---------------------------------------------------------------------------
# Include API routers (trading only — no auth/payments/settings)
# ---------------------------------------------------------------------------
from app.api.routes import (
    ai_agent,
    bots,
    broker_accounts,
    broker_data,
    brokers,
    intelligence,
    market,
    ml,
    paper_trading,
    settings,
    social,
    stats,
    trading,
)

app.include_router(market.router)
app.include_router(trading.router)
app.include_router(paper_trading.router)
app.include_router(ml.router)
app.include_router(stats.router)
app.include_router(ai_agent.router)
app.include_router(settings.router)
app.include_router(brokers.router)
app.include_router(broker_accounts.router)
app.include_router(broker_data.router)
app.include_router(intelligence.router)
app.include_router(bots.router)
app.include_router(social.router)

# ---------------------------------------------------------------------------
# Startup / Shutdown events
# ---------------------------------------------------------------------------

_MIGRATIONS = {
    "ai_recommendations": [
        ("user_id", "INTEGER NOT NULL DEFAULT 0"),
        ("trading_mode", "VARCHAR(10) NOT NULL DEFAULT 'paper'"),
        ("broker_name", "VARCHAR(30)"),
        ("created_at", "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"),
    ],
    "user_settings": [
        ("ai_provider", "VARCHAR(50)"),
        ("ai_model", "VARCHAR(100)"),
        ("last_model_used", "VARCHAR(100)"),
        ("last_ai_provider_used", "VARCHAR(50)"),
        ("ai_symbol_whitelist", "VARCHAR(500)"),
        ("ai_symbol_blacklist", "VARCHAR(500)"),
        ("ai_use_market_regime", "BOOLEAN NOT NULL DEFAULT 1"),
        ("ai_use_mtf_confirm", "BOOLEAN NOT NULL DEFAULT 1"),
        ("ai_use_correlation_filter", "BOOLEAN NOT NULL DEFAULT 1"),
        ("ai_custom_instructions", "VARCHAR(1000)"),
        ("ai_omniroute_key_enc", "VARCHAR(500)"),
    ],
    "signals": [
        ("user_id", "INTEGER NOT NULL DEFAULT 0"),
        ("broker_id", "VARCHAR(50) NOT NULL DEFAULT 'binance'"),
    ],
    "risk_events": [
        ("user_id", "INTEGER NOT NULL DEFAULT 0"),
    ],
    "account_snapshots": [
        ("user_id", "INTEGER NOT NULL DEFAULT 0"),
        ("broker_id", "VARCHAR(50) NOT NULL DEFAULT 'binance'"),
    ],
    "prediction_records": [
        ("user_id", "INTEGER NOT NULL DEFAULT 0"),
    ],
    "order_reconciliations": [
        ("user_id", "INTEGER NOT NULL DEFAULT 0"),
        ("broker_id", "VARCHAR(50) NOT NULL DEFAULT 'binance'"),
    ],
    "system_events": [
        ("user_id", "INTEGER NOT NULL DEFAULT 0"),
    ],
    "backtest_runs": [
        ("user_id", "INTEGER NOT NULL DEFAULT 0"),
    ],
    "intelligence_analyses": [
        ("user_id", "INTEGER NOT NULL DEFAULT 0"),
    ],
    "intelligence_events": [
        ("user_id", "INTEGER NOT NULL DEFAULT 0"),
    ],
    "positions": [
        ("broker_id", "VARCHAR(50) NOT NULL DEFAULT 'binance'"),
    ],
    "orders": [
        ("broker_id", "VARCHAR(50) NOT NULL DEFAULT 'binance'"),
    ],
    "trades": [
        ("broker_id", "VARCHAR(50) NOT NULL DEFAULT 'binance'"),
    ],
}


def _auto_migrate_columns(engine) -> None:
    """Add missing columns to existing tables (ALTER TABLE ADD COLUMN).
    
    Works with both SQLite and PostgreSQL. For PostgreSQL, uses IF NOT EXISTS.
    """
    from sqlalchemy import text, inspect

    inspector = inspect(engine)
    is_postgres = not str(engine.url).startswith("sqlite")
    for table_name, columns in _MIGRATIONS.items():
        if not inspector.has_table(table_name):
            continue
        existing = {col["name"] for col in inspector.get_columns(table_name)}
        for col_name, col_def in columns:
            if col_name not in existing:
                with engine.connect() as conn:
                    if is_postgres:
                        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {col_name} {col_def}"))
                    else:
                        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"))
                    conn.commit()
                import logging
                logging.getLogger(__name__).info("Auto-migrated: added column %s.%s", table_name, col_name)


@app.on_event("startup")
def _startup_services() -> None:
    settings = get_settings()
    # Auto-create any new tables (idempotent — only creates missing tables)
    try:
        from app.database.base import Base
        import app.database.models  # noqa: F401 — ensure all models are registered
        from app.database.session import engine
        Base.metadata.create_all(bind=engine)
        # Auto-migrate: add missing columns to existing tables (SQLite doesn't support ADD COLUMN via ORM)
        _auto_migrate_columns(engine)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Failed to auto-create/migrate DB tables: %s", exc)
    try:
        init_price_stream(settings.symbols_list, testnet=settings.BINANCE_TESTNET)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Failed to start price stream: %s", exc)
    # Start intelligence scheduler (news fetcher + cleanup)
    try:
        start_intel_scheduler()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Failed to start intelligence scheduler: %s", exc)
    # Start social trading scheduler (auto-copy + stats)
    try:
        start_social_scheduler()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Failed to start social scheduler: %s", exc)
    # Start position reconciler (auto-sync DB positions with broker)
    try:
        from app.services.position_reconciler import get_position_reconciler
        get_position_reconciler().start()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Failed to start position reconciler: %s", exc)


@app.on_event("shutdown")
def _shutdown_services() -> None:
    stop_price_stream()
    stop_intel_scheduler()
    stop_social_scheduler()
    try:
        from app.services.position_reconciler import get_position_reconciler
        get_position_reconciler().stop()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Core routes
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Frontend log endpoint
# ---------------------------------------------------------------------------

import json
from datetime import datetime
from pydantic import BaseModel

class LogEntry(BaseModel):
    level: str = "info"
    message: str
    data: str | None = None
    timestamp: str | None = None

_LOG_FILE = Path(__file__).resolve().parent.parent.parent / "frontend.log"


@app.post("/api/log")
def frontend_log(entry: LogEntry) -> dict:
    """Receive frontend logs and write them to frontend.log file."""
    try:
        ts = entry.timestamp or datetime.now().isoformat()
        line = f"[{ts}] [{entry.level.upper()}] {entry.message}"
        if entry.data:
            line += f" | {entry.data}"
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    return {"logged": True}


@app.get("/api/log")
def get_frontend_log(lines: int = 100) -> dict:
    """Read recent frontend logs."""
    try:
        if _LOG_FILE.exists():
            all_lines = _LOG_FILE.read_text(encoding="utf-8").strip().split("\n")
            return {"logs": all_lines[-lines:] if lines < len(all_lines) else all_lines}
    except Exception:
        pass
    return {"logs": []}


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import logging
    logging.getLogger(__name__).error("Unhandled exception: %s | Path: %s", exc, request.url.path)
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] [ERROR] Unhandled: {exc} | Path: {request.url.path}\n")
    except Exception:
        pass
    settings = get_settings()
    detail = str(exc) if settings.APP_ENV == "development" else "Error interno del servidor"
    return JSONResponse(status_code=500, content={"detail": detail})


