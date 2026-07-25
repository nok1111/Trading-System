"""Rate limiting y límites por plan de suscripción."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.user import SubscriptionPlan, User
from app.database.session import get_db
from app.services.auth import get_current_user

PLAN_LIMITS: dict[str, dict] = {
    "free": {
        "max_pairs": 3,
        "max_positions": 3,
        "max_ai_requests_per_day": 50,
        "max_ai_interval_seconds": 120,
        "features": ["paper_trading", "ai_agent_analysis", "ai_agent_autotrade"],
    },
    "pro": {
        "max_pairs": 10,
        "max_positions": 10,
        "max_ai_requests_per_day": 500,
        "max_ai_interval_seconds": 15,
        "features": ["paper_trading", "ai_agent_analysis", "ai_agent_autotrade", "telegram_notifications", "ai_provider_keys"],
    },
    "premium": {
        "max_pairs": 999,
        "max_positions": 999,
        "max_ai_requests_per_day": 99999,
        "max_ai_interval_seconds": 10,
        "features": ["paper_trading", "ai_agent_analysis", "ai_agent_autotrade", "telegram_notifications", "ai_provider_keys", "priority_support", "custom_strategies"],
    },
}


def get_plan_limits(subscription: str) -> dict:
    return PLAN_LIMITS.get(subscription, PLAN_LIMITS["free"])


def has_feature(user: User, feature: str) -> bool:
    limits = get_plan_limits(user.subscription)
    return feature in limits["features"]


def require_feature(feature: str):
    """Dependency factory: raises 403 if user's plan doesn't include the feature."""
    def _check(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if not has_feature(current_user, feature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tu plan ({current_user.subscription}) no incluye esta función. Mejora tu plan.",
            )
        return current_user
    return _check


def check_ai_request_limit(user: User, db: Session) -> None:
    """Verifica si el usuario ha excedido el límite diario de requests de IA."""
    limits = get_plan_limits(user.subscription)
    max_per_day = limits["max_ai_requests_per_day"]
    if max_per_day >= 99999:
        return
    today = date.today()
    from app.database.models.prediction_record import PredictionRecord
    count = db.execute(
        select(PredictionRecord).where(
            PredictionRecord.timestamp >= today
        )
    ).all()
    if len(count) >= max_per_day:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Límite diario de IA alcanzado ({max_per_day} requests). Mejora tu plan para más requests.",
        )


def check_position_limit(user: User, current_positions: int) -> None:
    """Verifica si el usuario puede abrir más posiciones."""
    limits = get_plan_limits(user.subscription)
    max_pos = limits["max_positions"]
    if max_pos >= 999:
        return
    if current_positions >= max_pos:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Límite de posiciones alcanzado ({max_pos}). Mejora tu plan para más posiciones.",
        )


def check_pair_limit(user: User, requested_pairs: int) -> None:
    """Verifica si el usuario puede usar más pares de trading."""
    limits = get_plan_limits(user.subscription)
    max_pairs = limits["max_pairs"]
    if max_pairs >= 999:
        return
    if requested_pairs > max_pairs:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tu plan permite máximo {max_pairs} pares. Mejora tu plan para más pares.",
        )
