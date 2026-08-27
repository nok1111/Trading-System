"""Alvora Academy endpoints — tutorial progress tracking.

Endpoints:
  GET  /api/academy/progress                  — user's progress across all tutorials
  POST /api/academy/progress/{tutorial_id}    — update progress for a specific tutorial
  GET  /api/academy/tutorials                 — list all available tutorials
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.database.session import SessionLocal
from app.database.models.academy_progress import AcademyProgress
from app.services.auth import LocalUser, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/academy", tags=["academy"])


# ─── Tutorial catalog (mirrors frontend data) ─────────────────────────────────

TUTORIAL_CATALOG = [
    {"id": "first_trade", "title": "Tu Primera Operación en Alvora", "category": "Primeros pasos", "difficulty": "beginner", "steps": 4},
    {"id": "grid_bot_explained", "title": "Cómo Funciona un Grid Bot", "category": "Bots", "difficulty": "intermediate", "steps": 4},
    {"id": "risk_management", "title": "Gestión de Riesgo para Traders", "category": "Risk Management", "difficulty": "intermediate", "steps": 4},
    {"id": "sl_tp_basics", "title": "Stop-Loss y Take-Profit: Lo Básico", "category": "Trading", "difficulty": "beginner", "steps": 4},
    {"id": "dca_bot_explained", "title": "DCA Bot: Inversión Sistemática", "category": "Bots", "difficulty": "beginner", "steps": 4},
    {"id": "ai_trading_intro", "title": "Introducción al AI Trading con Alvora", "category": "AI Trading", "difficulty": "advanced", "steps": 5},
]


# ─── Request models ───────────────────────────────────────────────────────────


class ProgressUpdateRequest(BaseModel):
    progress_percent: int = 0
    completed: bool = False


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/tutorials")
def list_tutorials() -> dict:
    """List all available tutorials in the academy.

    Returns the tutorial catalog with id, title, category, difficulty, and step count.
    This endpoint is public (no auth required) so users can browse before logging in.
    """
    return {"tutorials": TUTORIAL_CATALOG}


@router.get("/progress")
def get_progress(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Get the current user's progress across all tutorials.

    Returns a list of progress entries with tutorial_id, completed, progress_percent,
    and completed_at timestamp.
    """
    session = SessionLocal()
    try:
        rows = (
            session.query(AcademyProgress)
            .filter(AcademyProgress.user_id == current_user.id)
            .all()
        )
        return {
            "progress": [
                {
                    "tutorial_id": r.tutorial_id,
                    "completed": r.completed,
                    "progress_percent": r.progress_percent,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                }
                for r in rows
            ],
            "total_tutorials": len(TUTORIAL_CATALOG),
            "completed_count": sum(1 for r in rows if r.completed),
        }
    finally:
        session.close()


@router.post("/progress/{tutorial_id}")
def update_progress(
    tutorial_id: str,
    req: ProgressUpdateRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Update progress for a specific tutorial.

    Creates or updates the progress record for the given tutorial.
    If completed=True, sets completed_at to the current time.
    """
    session = SessionLocal()
    try:
        row = (
            session.query(AcademyProgress)
            .filter(
                AcademyProgress.user_id == current_user.id,
                AcademyProgress.tutorial_id == tutorial_id,
            )
            .first()
        )

        if row:
            row.progress_percent = req.progress_percent
            row.completed = req.completed
            if req.completed and not row.completed_at:
                row.completed_at = datetime.now(tz=UTC)
            elif not req.completed:
                row.completed_at = None
        else:
            row = AcademyProgress(
                user_id=current_user.id,
                tutorial_id=tutorial_id,
                completed=req.completed,
                progress_percent=req.progress_percent,
                completed_at=datetime.now(tz=UTC) if req.completed else None,
            )
            session.add(row)

        session.commit()
        return {
            "ok": True,
            "tutorial_id": tutorial_id,
            "completed": req.completed,
            "progress_percent": req.progress_percent,
        }
    except Exception as exc:
        session.rollback()
        logger.error("Failed to update academy progress: %s", exc)
        return {"ok": False, "error": str(exc)}
    finally:
        session.close()
