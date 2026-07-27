"""Router de niveles — selecciona modelo LLM según plan del usuario.

Niveles:
- Económico (free): modelo pequeño/fast
- Medio (pro): modelo mediano
- Avanzado (premium): modelo grande o ensemble
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings


@dataclass(frozen=True)
class ModelConfig:
    """Configuración del modelo seleccionado para un análisis."""

    provider: str
    model: str
    max_tokens: int
    temperature: float
    level: str


def get_model_for_plan(plan: str) -> ModelConfig:
    """Selecciona el modelo LLM según el plan del usuario."""
    settings = get_settings()

    if plan == "premium":
        return ModelConfig(
            provider=settings.AI_PROVIDER,
            model=settings.GROQ_MODEL_ADVANCED,
            max_tokens=2000,
            temperature=0.4,
            level="advanced",
        )
    elif plan == "pro":
        return ModelConfig(
            provider=settings.AI_PROVIDER,
            model=settings.GROQ_MODEL_MEDIUM,
            max_tokens=1500,
            temperature=0.3,
            level="medium",
        )
    else:
        return ModelConfig(
            provider=settings.AI_PROVIDER,
            model=settings.GROQ_MODEL_ECONOMIC,
            max_tokens=1000,
            temperature=0.3,
            level="economic",
        )
