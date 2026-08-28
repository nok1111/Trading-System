"""Alvora Academy endpoints — tutorial progress tracking, gamification, and learning paths.

Endpoints:
  GET  /api/academy/progress                  — user's progress across all tutorials
  POST /api/academy/progress/{tutorial_id}    — update progress for a specific tutorial
  GET  /api/academy/tutorials                 — list all available tutorials
  GET  /api/academy/paths                     — list learning paths with progress
  GET  /api/academy/badges                    — list badges with earned status
  GET  /api/academy/leaderboard               — top users by XP
  POST /api/academy/quiz-result               — record quiz result
"""

from __future__ import annotations

import json
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
    {"id": "what_is_crypto", "title": "Qué es Bitcoin y las Criptomonedas", "category": "Primeros pasos", "difficulty": "beginner", "steps": 4, "xp": 50},
    {"id": "what_is_trading", "title": "Qué es el Trading: Spot, Futures, Margin", "category": "Primeros pasos", "difficulty": "beginner", "steps": 5, "xp": 50},
    {"id": "first_trade", "title": "Tu Primera Operación en Alvora", "category": "Primeros pasos", "difficulty": "beginner", "steps": 4, "xp": 75},
    {"id": "sl_tp_basics", "title": "Stop-Loss y Take-Profit: Lo Básico", "category": "Trading", "difficulty": "beginner", "steps": 4, "xp": 75},
    {"id": "order_types", "title": "Tipos de Órdenes: Market, Limit, Stop, OCO", "category": "Trading", "difficulty": "beginner", "steps": 5, "xp": 75},
    {"id": "reading_charts", "title": "Cómo Leer un Gráfico de Trading", "category": "Trading", "difficulty": "beginner", "steps": 5, "xp": 100},
    {"id": "candlestick_patterns", "title": "Patrones de Velas Japonesas", "category": "Technical Analysis", "difficulty": "intermediate", "steps": 5, "xp": 100},
    {"id": "support_resistance", "title": "Soporte y Resistencia", "category": "Technical Analysis", "difficulty": "intermediate", "steps": 4, "xp": 100},
    {"id": "moving_averages", "title": "Medias Móviles: SMA, EMA, WMA", "category": "Technical Analysis", "difficulty": "intermediate", "steps": 4, "xp": 100},
    {"id": "rsi_macd", "title": "RSI y MACD: Osciladores Clave", "category": "Technical Analysis", "difficulty": "intermediate", "steps": 5, "xp": 125},
    {"id": "chart_patterns", "title": "Patrones Gráficos: Triángulos, Banderas", "category": "Technical Analysis", "difficulty": "intermediate", "steps": 5, "xp": 125},
    {"id": "volume_analysis", "title": "Análisis de Volumen y OBV", "category": "Technical Analysis", "difficulty": "intermediate", "steps": 4, "xp": 100},
    {"id": "market_regimes", "title": "Regímenes de Mercado", "category": "Technical Analysis", "difficulty": "advanced", "steps": 4, "xp": 150},
    {"id": "grid_bot_explained", "title": "Cómo Funciona un Grid Bot", "category": "Bots", "difficulty": "intermediate", "steps": 4, "xp": 125},
    {"id": "dca_bot_explained", "title": "DCA Bot: Inversión Sistemática", "category": "Bots", "difficulty": "beginner", "steps": 4, "xp": 100},
    {"id": "bot_backtesting", "title": "Backtesting de Bots", "category": "Bots", "difficulty": "intermediate", "steps": 4, "xp": 125},
    {"id": "bot_optimization", "title": "Optimización con Monte Carlo", "category": "Bots", "difficulty": "advanced", "steps": 4, "xp": 150},
    {"id": "strategy_builder", "title": "Visual Strategy Builder sin Código", "category": "Bots", "difficulty": "intermediate", "steps": 5, "xp": 150},
    {"id": "risk_management", "title": "Gestión de Riesgo para Traders", "category": "Risk Management", "difficulty": "intermediate", "steps": 4, "xp": 125},
    {"id": "position_sizing", "title": "Position Sizing: Kelly, Fijo, Porcentual", "category": "Risk Management", "difficulty": "advanced", "steps": 5, "xp": 150},
    {"id": "portfolio_correlation", "title": "Correlación y Diversificación", "category": "Risk Management", "difficulty": "advanced", "steps": 4, "xp": 150},
    {"id": "defi_basics", "title": "Qué es DeFi: Uniswap, Aave, Compound", "category": "DeFi", "difficulty": "intermediate", "steps": 5, "xp": 125},
    {"id": "wallet_safety", "title": "Seguridad de Wallets: Hot vs Cold", "category": "DeFi", "difficulty": "beginner", "steps": 4, "xp": 100},
    {"id": "dex_trading", "title": "Trading en DEXs: Slippage e IL", "category": "DeFi", "difficulty": "advanced", "steps": 5, "xp": 150},
    {"id": "staking_liquidity", "title": "Staking y Liquidity Mining", "category": "DeFi", "difficulty": "intermediate", "steps": 4, "xp": 125},
    {"id": "ai_trading_intro", "title": "Introducción al AI Trading con Alvora", "category": "AI Trading", "difficulty": "advanced", "steps": 5, "xp": 150},
    {"id": "ai_signals", "title": "Cómo Interpretar Señales de AI", "category": "AI Trading", "difficulty": "advanced", "steps": 4, "xp": 150},
    {"id": "copilot_mastery", "title": "Dominando el Alvora Copilot", "category": "AI Trading", "difficulty": "intermediate", "steps": 4, "xp": 125},
    {"id": "auto_pilot", "title": "Auto-Pilot: Trading Automático con AI", "category": "AI Trading", "difficulty": "advanced", "steps": 5, "xp": 175},
    {"id": "trading_psychology", "title": "Psicología del Trading: FOMO y FUD", "category": "Psychology", "difficulty": "intermediate", "steps": 5, "xp": 125},
    {"id": "tax_reporting", "title": "Reportes Fiscales con Tax Studio", "category": "Taxes", "difficulty": "intermediate", "steps": 4, "xp": 125},
]

# ─── Learning paths ───────────────────────────────────────────────────────────

LEARNING_PATHS = [
    {"id": "beginner_trader", "title": "Beginner Trader Path", "icon": "🌱", "color": "var(--color-success)", "tutorial_ids": ["what_is_crypto", "what_is_trading", "first_trade", "sl_tp_basics", "order_types", "reading_charts", "risk_management"]},
    {"id": "technical_analyst", "title": "Technical Analyst Path", "icon": "📊", "color": "var(--color-primary)", "tutorial_ids": ["candlestick_patterns", "support_resistance", "moving_averages", "rsi_macd", "chart_patterns", "volume_analysis", "market_regimes"]},
    {"id": "bot_master", "title": "Bot Master Path", "icon": "🤖", "color": "var(--color-accent)", "tutorial_ids": ["grid_bot_explained", "dca_bot_explained", "bot_backtesting", "bot_optimization", "strategy_builder"]},
    {"id": "ai_trader", "title": "AI Trader Path", "icon": "🧠", "color": "var(--color-warning)", "tutorial_ids": ["ai_trading_intro", "ai_signals", "copilot_mastery", "auto_pilot"]},
    {"id": "defi_explorer", "title": "DeFi Explorer Path", "icon": "⛓️", "color": "#f59e0b", "tutorial_ids": ["defi_basics", "wallet_safety", "dex_trading", "staking_liquidity"]},
    {"id": "advanced_trader", "title": "Advanced Trader Path", "icon": "🏆", "color": "var(--color-danger)", "tutorial_ids": ["trading_psychology", "position_sizing", "portfolio_correlation", "tax_reporting"]},
]

# ─── Badges ────────────────────────────────────────────────────────────────────

BADGES_CATALOG = [
    {"id": "first_steps", "name": "Primeros Pasos", "description": "Completa tu primer tutorial", "icon": "🎯"},
    {"id": "quick_learner", "name": "Aprendiz Rápido", "description": "Completa 3 tutoriales", "icon": "⚡"},
    {"id": "dedicated", "name": "Dedicado", "description": "Completa todos los tutoriales", "icon": "🏆"},
    {"id": "perfect_quiz", "name": "Quiz Perfecto", "description": "Responde todas las preguntas de un tutorial correctamente", "icon": "💯"},
    {"id": "quiz_master", "name": "Maestro de Quizzes", "description": "Responde perfectamente 3 tutoriales", "icon": "🧠"},
    {"id": "quiz_master_5", "name": "Quiz Master 5x", "description": "Responde perfectamente 5 tutoriales", "icon": "🎓"},
    {"id": "streak_3", "name": "Racha de 3", "description": "Estudia 3 días seguidos", "icon": "🔥"},
    {"id": "streak_7", "name": "Racha de 7", "description": "Estudia 7 días seguidos", "icon": "🚀"},
    {"id": "streak_30", "name": "Racha de 30", "description": "Estudia 30 días seguidos", "icon": "💎"},
    {"id": "level_5", "name": "Trader Avanzado", "description": "Alcanza el nivel 5", "icon": "🎖️"},
    {"id": "risk_aware", "name": "Consciente del Riesgo", "description": "Completa el tutorial de gestión de riesgo", "icon": "🛡️"},
    {"id": "bot_master", "name": "Maestro de Bots", "description": "Completa todos los tutoriales de bots", "icon": "🤖"},
    {"id": "ai_pioneer", "name": "Pionero de AI", "description": "Completa el tutorial de AI Trading", "icon": "🧬"},
    {"id": "xp_500", "name": "500 XP", "description": "Acumula 500 puntos de experiencia", "icon": "⭐"},
    {"id": "xp_1000", "name": "1000 XP", "description": "Acumula 1000 puntos de experiencia", "icon": "🌟"},
    {"id": "half_done", "name": "Por la Mitad", "description": "Completa el 50% de los tutoriales", "icon": "🎯"},
    {"id": "ta_master", "name": "Maestro del Análisis Técnico", "description": "Completa todos los tutoriales de análisis técnico", "icon": "📊"},
    {"id": "defi_explorer_badge", "name": "Explorador DeFi", "description": "Completa todos los tutoriales de DeFi", "icon": "⛓️"},
    {"id": "risk_expert", "name": "Experto en Riesgo", "description": "Completa todos los tutoriales de gestión de riesgo", "icon": "🛡️"},
    {"id": "path_beginner", "name": "Beginner Path Complete", "description": "Completa el learning path de principiante", "icon": "🌱"},
    {"id": "path_ta", "name": "Technical Analyst Path", "description": "Completa el learning path de análisis técnico", "icon": "📈"},
]


# ─── Request models ───────────────────────────────────────────────────────────


class ProgressUpdateRequest(BaseModel):
    progress_percent: int = 0
    completed: bool = False
    xp_earned: int = 0
    perfect_quiz: bool = False
    quiz_scores: list[int] | None = None


class QuizResultRequest(BaseModel):
    tutorial_id: str
    correct: int
    total: int
    perfect: bool = False


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/tutorials")
def list_tutorials() -> dict:
    """List all available tutorials in the academy."""
    return {"tutorials": TUTORIAL_CATALOG}


@router.get("/paths")
def list_paths(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """List learning paths with user's progress on each."""
    session = SessionLocal()
    try:
        rows = (
            session.query(AcademyProgress)
            .filter(AcademyProgress.user_id == current_user.id)
            .all()
        )
        completed_ids = {r.tutorial_id for r in rows if r.completed}

        paths = []
        for path in LEARNING_PATHS:
            completed_count = sum(1 for tid in path["tutorial_ids"] if tid in completed_ids)
            total = len(path["tutorial_ids"])
            paths.append({
                **path,
                "completed_count": completed_count,
                "total": total,
                "progress_percent": round((completed_count / total) * 100) if total > 0 else 0,
                "is_completed": completed_count == total,
            })
        return {"paths": paths}
    finally:
        session.close()


@router.get("/badges")
def list_badges(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """List all badges with earned status for the current user."""
    session = SessionLocal()
    try:
        rows = (
            session.query(AcademyProgress)
            .filter(AcademyProgress.user_id == current_user.id)
            .all()
        )
        completed_ids = {r.tutorial_id for r in rows if r.completed}
        perfect_ids = {r.tutorial_id for r in rows if r.perfect_quiz}
        total_xp = sum(r.xp_earned for r in rows)

        # Determine earned badges
        earned = []
        for badge in BADGES_CATALOG:
            bid = badge["id"]
            if bid == "first_steps" and len(completed_ids) >= 1:
                earned.append(bid)
            elif bid == "quick_learner" and len(completed_ids) >= 3:
                earned.append(bid)
            elif bid == "dedicated" and len(completed_ids) >= len(TUTORIAL_CATALOG):
                earned.append(bid)
            elif bid == "perfect_quiz" and len(perfect_ids) >= 1:
                earned.append(bid)
            elif bid == "quiz_master" and len(perfect_ids) >= 3:
                earned.append(bid)
            elif bid == "quiz_master_5" and len(perfect_ids) >= 5:
                earned.append(bid)
            elif bid == "level_5" and total_xp >= 500:
                earned.append(bid)
            elif bid == "risk_aware" and "risk_management" in completed_ids:
                earned.append(bid)
            elif bid == "ai_pioneer" and "ai_trading_intro" in completed_ids:
                earned.append(bid)
            elif bid == "xp_500" and total_xp >= 500:
                earned.append(bid)
            elif bid == "xp_1000" and total_xp >= 1000:
                earned.append(bid)
            elif bid == "half_done" and len(completed_ids) >= len(TUTORIAL_CATALOG) // 2:
                earned.append(bid)

        return {
            "badges": BADGES_CATALOG,
            "earned_badge_ids": earned,
            "total_xp": total_xp,
            "completed_count": len(completed_ids),
            "perfect_quiz_count": len(perfect_ids),
        }
    finally:
        session.close()


@router.get("/leaderboard")
def get_leaderboard(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Get top users by XP (academy)."""
    session = SessionLocal()
    try:
        from sqlalchemy import func as sqlfunc
        # Aggregate XP by user
        results = (
            session.query(
                AcademyProgress.user_id,
                sqlfunc.sum(AcademyProgress.xp_earned).label("total_xp"),
                sqlfunc.count(sqlfunc.distinct(AcademyProgress.tutorial_id)).filter(
                    AcademyProgress.completed == True  # noqa: E712
                ).label("completed_count"),
            )
            .group_by(AcademyProgress.user_id)
            .order_by(sqlfunc.sum(AcademyProgress.xp_earned).desc())
            .limit(20)
            .all()
        )
        leaderboard = []
        for i, (uid, xp, completed) in enumerate(results, 1):
            leaderboard.append({
                "rank": i,
                "user_id": uid,
                "total_xp": xp or 0,
                "completed_count": completed or 0,
            })
        return {"leaderboard": leaderboard}
    finally:
        session.close()


@router.post("/quiz-result")
def record_quiz_result(
    req: QuizResultRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Record a quiz result for a tutorial."""
    session = SessionLocal()
    try:
        row = (
            session.query(AcademyProgress)
            .filter(
                AcademyProgress.user_id == current_user.id,
                AcademyProgress.tutorial_id == req.tutorial_id,
            )
            .first()
        )
        if row:
            row.perfect_quiz = req.perfect
            row.quiz_scores_json = json.dumps({"correct": req.correct, "total": req.total})
        else:
            row = AcademyProgress(
                user_id=current_user.id,
                tutorial_id=req.tutorial_id,
                completed=False,
                progress_percent=0,
                perfect_quiz=req.perfect,
                quiz_scores_json=json.dumps({"correct": req.correct, "total": req.total}),
            )
            session.add(row)
        session.commit()
        return {"ok": True, "perfect": req.perfect, "score": f"{req.correct}/{req.total}"}
    except Exception as exc:
        session.rollback()
        logger.error("Failed to record quiz result: %s", exc)
        return {"ok": False, "error": str(exc)}
    finally:
        session.close()


@router.get("/progress")
def get_progress(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Get the current user's progress across all tutorials."""
    session = SessionLocal()
    try:
        rows = (
            session.query(AcademyProgress)
            .filter(AcademyProgress.user_id == current_user.id)
            .all()
        )
        total_xp = sum(r.xp_earned for r in rows)
        perfect_count = sum(1 for r in rows if r.perfect_quiz)
        return {
            "progress": [
                {
                    "tutorial_id": r.tutorial_id,
                    "completed": r.completed,
                    "progress_percent": r.progress_percent,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    "xp_earned": r.xp_earned,
                    "perfect_quiz": r.perfect_quiz,
                }
                for r in rows
            ],
            "total_tutorials": len(TUTORIAL_CATALOG),
            "completed_count": sum(1 for r in rows if r.completed),
            "total_xp": total_xp,
            "perfect_quiz_count": perfect_count,
        }
    finally:
        session.close()


@router.post("/progress/{tutorial_id}")
def update_progress(
    tutorial_id: str,
    req: ProgressUpdateRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Update progress for a specific tutorial."""
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

        quiz_scores_json = None
        if req.quiz_scores is not None:
            quiz_scores_json = json.dumps(req.quiz_scores)

        if row:
            row.progress_percent = req.progress_percent
            row.completed = req.completed
            if req.xp_earned > 0 and row.xp_earned == 0:
                row.xp_earned = req.xp_earned
            if req.perfect_quiz:
                row.perfect_quiz = True
            if quiz_scores_json:
                row.quiz_scores_json = quiz_scores_json
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
                xp_earned=req.xp_earned,
                perfect_quiz=req.perfect_quiz,
                quiz_scores_json=quiz_scores_json,
                completed_at=datetime.now(tz=UTC) if req.completed else None,
            )
            session.add(row)

        session.commit()
        return {
            "ok": True,
            "tutorial_id": tutorial_id,
            "completed": req.completed,
            "progress_percent": req.progress_percent,
            "xp_earned": req.xp_earned,
        }
    except Exception as exc:
        session.rollback()
        logger.error("Failed to update academy progress: %s", exc)
        return {"ok": False, "error": str(exc)}
    finally:
        session.close()
