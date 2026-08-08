"""Alvora Auth Server — FastAPI application.

Handles: user registration, login, JWT auth, subscription management,
Binance Pay payments, and license validation for Trading Clients.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.database.session import init_db
from app.routes import admin, ai_grant, auth, license, payments


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate critical config before starting
    if settings.APP_ENV != "development" and settings.JWT_SECRET == "change-me-in-production":
        raise RuntimeError("JWT_SECRET must be overridden in non-development environments")
    if settings.APP_ENV != "development" and settings.CORS_ORIGINS == "*":
        raise RuntimeError("CORS_ORIGINS must not be '*' in non-development environments")
    # Create tables on startup (for dev; use Alembic in production)
    init_db()
    yield


app = FastAPI(
    title="Alvora Auth Server",
    description="Cloud authentication, subscription management, and license validation.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow Trading Client to connect
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(payments.router)
app.include_router(license.router)
app.include_router(ai_grant.router)
app.include_router(admin.router)


@app.get("/admin", response_class=HTMLResponse)
def admin_panel() -> HTMLResponse:
    """Serve the admin web panel."""
    html_path = Path(__file__).parent / "admin_panel.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/health")
def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "auth-server"}
