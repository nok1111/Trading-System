"""Alvora AI Server — FastAPI application.

Provides AI intelligence for trading clients via 12 specialized agents.
Security: HMAC service-to-service + JWT validation against Auth Server.
Never receives broker API keys or sensitive user data.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the intelligence scheduler automatically
    from app.services.scheduler import get_scheduler
    sched = get_scheduler()
    if sched.start():
        logger.info("Intelligence scheduler started automatically")
    else:
        logger.info("Intelligence scheduler not started (disabled or already running)")
    yield
    sched.stop()


settings = get_settings()

app = FastAPI(
    title="Alvora AI Server",
    description="Cloud AI intelligence service with 12 specialized agents and event-driven scheduler.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ai-server"}


# Include routers (imported after app creation to avoid circular imports)
from app.routes import analyze, intelligence

app.include_router(analyze.router)
app.include_router(intelligence.router)
