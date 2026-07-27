"""Alvora AI Server — FastAPI application.

Provides AI analysis for trading clients via 8 specialized agents.
Security: HMAC service-to-service + JWT validation against Auth Server.
Never receives broker API keys or sensitive user data.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


settings = get_settings()

app = FastAPI(
    title="Alvora AI Server",
    description="Cloud AI analysis service with 8 specialized agents.",
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
