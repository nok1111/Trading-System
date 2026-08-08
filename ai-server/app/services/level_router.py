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


_VALID_PLANS = {"free", "pro", "premium"}


def get_model_for_plan(plan: str) -> ModelConfig:
    """Selecciona el modelo LLM según el plan del usuario.

    Only accepts validated plan values. Unknown plans default to "free"
    (most restrictive) to prevent privilege escalation via crafted plan strings.
    """
    # Validate plan — default to "free" for any unknown value
    if plan not in _VALID_PLANS:
        plan = "free"
    settings = get_settings()
    provider = settings.AI_PROVIDER

    # Pick model name based on provider
    if provider == "omniroute":
        # OmniRoute: 'auto' smart routing handles model selection across 291 providers
        model_economic = settings.OMNIROUTE_MODEL
        model_medium = settings.OMNIROUTE_MODEL
        model_advanced = settings.OMNIROUTE_MODEL
    elif provider == "gemini":
        model_economic = settings.GEMINI_MODEL
        model_medium = settings.GEMINI_MODEL
        model_advanced = settings.GEMINI_MODEL
    elif provider == "groq":
        model_economic = settings.GROQ_MODEL_ECONOMIC
        model_medium = settings.GROQ_MODEL_MEDIUM
        model_advanced = settings.GROQ_MODEL_ADVANCED
    else:
        model_economic = settings.GROQ_MODEL_ECONOMIC
        model_medium = settings.GROQ_MODEL_MEDIUM
        model_advanced = settings.GROQ_MODEL_ADVANCED

    if plan == "premium":
        return ModelConfig(
            provider=provider,
            model=model_advanced,
            max_tokens=2000,
            temperature=0.4,
            level="advanced",
        )
    elif plan == "pro":
        return ModelConfig(
            provider=provider,
            model=model_medium,
            max_tokens=1500,
            temperature=0.3,
            level="medium",
        )
    else:
        return ModelConfig(
            provider=provider,
            model=model_economic,
            max_tokens=1000,
            temperature=0.3,
            level="economic",
        )
