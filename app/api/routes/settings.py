"""User settings endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database.models import User
from app.database.session import SessionLocal
from app.services.auth import get_current_user
from app.services.crypto import decrypt, encrypt
from app.services.rate_limit import get_plan_limits

router = APIRouter(prefix="/api/user", tags=["settings"])


class UpdateSettingsRequest(BaseModel):
    binance_api_key: str | None = None
    binance_api_secret: str | None = None
    risk_profile: str | None = None
    default_symbols: str | None = None
    telegram_chat_id: str | None = None
    telegram_alerts: bool | None = None
    ai_groq_key: str | None = None
    ai_gemini_key: str | None = None
    ai_premium_key: str | None = None
    ai_premium_provider: str | None = None
    ai_premium_base_url: str | None = None
    ai_premium_model: str | None = None


@router.get("/settings")
def get_user_settings(current_user: Annotated[User, Depends(get_current_user)]) -> dict:
    """Obtiene la configuración del usuario actual."""
    has_api_key = bool(current_user.binance_api_key_enc)
    has_groq_key = bool(current_user.ai_groq_key_enc)
    has_gemini_key = bool(current_user.ai_gemini_key_enc)
    has_premium_key = bool(current_user.ai_premium_key_enc)
    limits = get_plan_limits(current_user.subscription)
    can_use_own_keys = "ai_provider_keys" in limits["features"]
    can_use_premium = "ai_premium_providers" in limits["features"]
    return {
        "email": current_user.email,
        "username": current_user.username,
        "subscription": current_user.subscription,
        "risk_profile": current_user.risk_profile,
        "has_binance_api_key": has_api_key,
        "binance_api_key_preview": decrypt(current_user.binance_api_key_enc)[:8] + "..." if has_api_key else None,
        "telegram_chat_id": current_user.telegram_chat_id,
        "telegram_alerts": current_user.telegram_alerts,
        "has_groq_key": has_groq_key,
        "has_gemini_key": has_gemini_key,
        "has_premium_key": has_premium_key,
        "premium_provider": current_user.ai_premium_provider,
        "premium_model": current_user.ai_premium_model,
        "can_use_own_ai_keys": can_use_own_keys,
        "can_use_premium_ai": can_use_premium,
        "min_ai_interval": limits["max_ai_interval_seconds"],
    }


@router.patch("/settings")
def update_user_settings(
    req: UpdateSettingsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Actualiza la configuración del usuario."""
    db = SessionLocal()
    try:
        user = db.get(User, current_user.id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if req.binance_api_key is not None:
            user.binance_api_key_enc = encrypt(req.binance_api_key) if req.binance_api_key else None
        if req.binance_api_secret is not None:
            user.binance_api_secret_enc = encrypt(req.binance_api_secret) if req.binance_api_secret else None
        if req.risk_profile is not None:
            if req.risk_profile not in ("conservative", "moderate", "aggressive"):
                raise HTTPException(status_code=400, detail="risk_profile inválido")
            user.risk_profile = req.risk_profile
        if req.telegram_chat_id is not None:
            user.telegram_chat_id = req.telegram_chat_id
        if req.telegram_alerts is not None:
            user.telegram_alerts = req.telegram_alerts
        if req.ai_groq_key is not None:
            limits = get_plan_limits(user.subscription)
            if "ai_provider_keys" not in limits["features"]:
                raise HTTPException(status_code=403, detail="Tu plan no permite configurar API keys propias de IA. Mejora a PRO o PREMIUM.")
            user.ai_groq_key_enc = encrypt(req.ai_groq_key) if req.ai_groq_key else None
        if req.ai_gemini_key is not None:
            limits = get_plan_limits(user.subscription)
            if "ai_provider_keys" not in limits["features"]:
                raise HTTPException(status_code=403, detail="Tu plan no permite configurar API keys propias de IA. Mejora a PRO o PREMIUM.")
            user.ai_gemini_key_enc = encrypt(req.ai_gemini_key) if req.ai_gemini_key else None
        if req.ai_premium_key is not None or req.ai_premium_provider is not None:
            limits = get_plan_limits(user.subscription)
            if "ai_premium_providers" not in limits["features"]:
                raise HTTPException(status_code=403, detail="Tu plan no permite usar providers de IA premium. Mejora a PRO o PREMIUM.")
            if req.ai_premium_key is not None:
                user.ai_premium_key_enc = encrypt(req.ai_premium_key) if req.ai_premium_key else None
            if req.ai_premium_provider is not None:
                user.ai_premium_provider = req.ai_premium_provider or None
            if req.ai_premium_base_url is not None:
                user.ai_premium_base_url = req.ai_premium_base_url or None
            if req.ai_premium_model is not None:
                user.ai_premium_model = req.ai_premium_model or None
        db.commit()
        db.refresh(user)
        return {
            "email": user.email,
            "username": user.username,
            "subscription": user.subscription,
            "risk_profile": user.risk_profile,
            "has_binance_api_key": bool(user.binance_api_key_enc),
            "telegram_chat_id": user.telegram_chat_id,
            "telegram_alerts": user.telegram_alerts,
            "has_groq_key": bool(user.ai_groq_key_enc),
            "has_gemini_key": bool(user.ai_gemini_key_enc),
            "has_premium_key": bool(user.ai_premium_key_enc),
            "premium_provider": user.ai_premium_provider,
            "premium_model": user.ai_premium_model,
        }
    finally:
        db.close()


@router.get("/plan")
def get_user_plan(current_user: Annotated[User, Depends(get_current_user)]) -> dict:
    """Retorna los límites y features del plan del usuario."""
    limits = get_plan_limits(current_user.subscription)
    return {
        "plan": current_user.subscription,
        "max_pairs": limits["max_pairs"] if limits["max_pairs"] < 999 else -1,
        "max_positions": limits["max_positions"] if limits["max_positions"] < 999 else -1,
        "max_ai_requests_per_day": limits["max_ai_requests_per_day"] if limits["max_ai_requests_per_day"] < 99999 else -1,
        "max_ai_interval_seconds": limits["max_ai_interval_seconds"],
        "features": limits["features"],
    }


@router.post("/telegram/test")
def test_telegram(current_user: Annotated[User, Depends(get_current_user)]) -> dict:
    """Envía un mensaje de prueba a Telegram del usuario."""
    if not current_user.telegram_chat_id:
        raise HTTPException(status_code=400, detail="Configura tu Telegram Chat ID primero")
    from app.services.telegram import send_telegram_message_sync
    ok = send_telegram_message_sync(
        current_user.telegram_chat_id,
        "✅ <b>Alvora — Test de Notificaciones</b>\n\n"
        "Tu Telegram está configurado correctamente.\n"
        "Recibirás alertas de cada operación del AI Agent.",
    )
    if not ok:
        raise HTTPException(status_code=500, detail="No se pudo enviar el mensaje. Verifica el Bot Token y Chat ID.")
    return {"ok": True, "message": "Mensaje de prueba enviado"}
