"""Trading Client — FastAPI application with license validation middleware."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.schemas import HealthOut
from app.config import get_settings
from app.data.price_stream import get_price_stream, init_price_stream, stop_price_stream
from app.intelligence.scheduler import start_scheduler as start_intel_scheduler, stop_scheduler as stop_intel_scheduler
from app.services.license import validate_license

app = FastAPI(
    title="Alvora Trading Client",
    description="Local trading client — AI Agent, broker, dashboard. Requires Auth Server connection.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_DASHBOARD_HTML = (Path(__file__).parent / "dashboard.html").read_text(encoding="utf-8")
_LANDING_HTML = (Path(__file__).parent / "landing.html").read_text(encoding="utf-8")

# Serve static files (images, etc.) from project root /images
_static_path = Path(__file__).resolve().parent.parent.parent / "images"
if _static_path.exists():
    app.mount("/images", StaticFiles(directory=str(_static_path)), name="images")

# ---------------------------------------------------------------------------
# License validation middleware
# ---------------------------------------------------------------------------

# Paths that don't require license validation
_PUBLIC_PATHS = {"/", "/dashboard", "/health", "/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect", "/api/log", "/api/binance/price"}


@app.middleware("http")
async def license_check(request: Request, call_next):
    """Validate JWT against Auth Server on every request.

    Skips public paths (health, dashboard HTML, docs).
    Attaches license info to request.state for downstream use.
    """
    if request.url.path in _PUBLIC_PATHS or request.url.path.startswith("/images") or request.url.path.startswith("/api/binance/") or request.url.path.startswith("/api/klines/"):
        return await call_next(request)

    # Allow CORS preflight requests without auth
    if request.method == "OPTIONS":
        return await call_next(request)

    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})

    license_info = validate_license(token)
    if not license_info or not license_info.get("valid"):
        return JSONResponse(
            status_code=403,
            content={"detail": "Suscripción inactiva o sin conexión al Auth Server"},
        )

    request.state.user = license_info
    request.state.plan_limits = license_info.get("plan_limits", {})
    return await call_next(request)


# ---------------------------------------------------------------------------
# Include API routers (trading only — no auth/payments/settings)
# ---------------------------------------------------------------------------
from app.api.routes import (
    ai_agent,
    broker_accounts,
    brokers,
    market,
    ml,
    paper_trading,
    settings,
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

# ---------------------------------------------------------------------------
# Startup / Shutdown events
# ---------------------------------------------------------------------------


@app.on_event("startup")
def _startup_services() -> None:
    settings = get_settings()
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


@app.on_event("shutdown")
def _shutdown_services() -> None:
    stop_price_stream()
    stop_intel_scheduler()


# ---------------------------------------------------------------------------
# Core routes (HTML pages + health)
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
def landing() -> HTMLResponse:
    """Landing page de Alvora."""
    return HTMLResponse(_LANDING_HTML)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    """Dashboard web interactivo (requiere login)."""
    return HTMLResponse(_DASHBOARD_HTML)


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
    return JSONResponse(status_code=500, content={"detail": str(exc)})


