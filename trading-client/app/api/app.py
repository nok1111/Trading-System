"""Trading Client — FastAPI application with license validation middleware."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.schemas import HealthOut
from app.config import get_settings
from app.data.price_stream import get_price_stream, init_price_stream, stop_price_stream
from app.services.license import validate_license

app = FastAPI(
    title="Alvora Trading Client",
    description="Local trading client — AI Agent, broker, dashboard. Requires Auth Server connection.",
    version="1.0.0",
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
_PUBLIC_PATHS = {"/", "/dashboard", "/health", "/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"}


@app.middleware("http")
async def license_check(request: Request, call_next):
    """Validate JWT against Auth Server on every request.

    Skips public paths (health, dashboard HTML, docs).
    Attaches license info to request.state for downstream use.
    """
    if request.url.path in _PUBLIC_PATHS or request.url.path.startswith("/images"):
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
    market,
    ml,
    paper_trading,
    stats,
    trading,
)

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
