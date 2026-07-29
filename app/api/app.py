"""AplicaciÃ³n FastAPI para consulta y supervisiÃ³n (FASE 6)."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.schemas import HealthOut
from app.config import get_settings
from app.data.price_stream import get_price_stream, init_price_stream, stop_price_stream

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
# Include API routers
# ---------------------------------------------------------------------------
from app.api.routes import (
    ai_agent,
    auth,
    market,
    ml,
    paper_trading,
    payments,
    settings,
    stats,
    trading,
)

app.include_router(auth.router)
app.include_router(settings.router)
app.include_router(payments.router)
app.include_router(market.router)
app.include_router(trading.router)
app.include_router(paper_trading.router)
app.include_router(ml.router)
app.include_router(stats.router)
app.include_router(ai_agent.router)

# ---------------------------------------------------------------------------
# Startup / Shutdown events
# ---------------------------------------------------------------------------


@app.on_event("startup")
def _startup_price_stream() -> None:
    settings = get_settings()
    # Auto-create any new tables (idempotent — only creates missing tables)
    try:
        from app.database.base import Base
        import app.database.models  # noqa: F401 — ensure all models are registered
        from app.database.session import engine
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Failed to auto-create DB tables: %s", exc)
    try:
        init_price_stream(settings.symbols_list, testnet=settings.BINANCE_TESTNET)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Failed to start price stream: %s", exc)


@app.on_event("shutdown")
def _shutdown_price_stream() -> None:
    stop_price_stream()


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
