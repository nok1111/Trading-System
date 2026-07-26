"""Alvora Auth Server — FastAPI application.

Handles: user registration, login, JWT auth, subscription management,
Binance Pay payments, and license validation for Trading Clients.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database.session import init_db
from app.routes import ai_grant, auth, license, payments


@asynccontextmanager
async def lifespan(app: FastAPI):
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


@app.get("/health")
def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "auth-server"}
