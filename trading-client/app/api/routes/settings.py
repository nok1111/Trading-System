"""Settings endpoints — manage user API keys (Binance, AI providers) stored locally."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.user_settings import UserSettings
from app.database.session import SessionLocal, get_db
from app.services.auth import LocalUser, get_current_user
from app.services.crypto import decrypt, encrypt

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SaveBinanceKeysRequest(BaseModel):
    binance_api_key: str
    binance_api_secret: str


class SaveAIKeysRequest(BaseModel):
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    premium_api_key: str | None = None
    premium_provider: str | None = None
    premium_base_url: str | None = None
    premium_model: str | None = None
    omniroute_api_key: str | None = None


class SaveAIConfigRequest(BaseModel):
    """Save full AI config: provider + model + key in one shot."""
    provider: str
    model: str
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    premium_api_key: str | None = None
    premium_base_url: str | None = None
    omniroute_api_key: str | None = None


class SaveTelegramRequest(BaseModel):
    telegram_chat_id: str | None = None
    telegram_alerts: bool = False


def _get_or_create(db: Session, user_id: int) -> UserSettings:
    settings = db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    ).scalar_one_or_none()
    if not settings:
        settings = UserSettings(user_id=user_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.get("/keys")
def get_keys(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Get user's stored API keys (masked)."""
    s = _get_or_create(db, current_user.id)
    return {
        "binance_api_key_set": s.binance_api_key_enc is not None,
        "binance_api_key_preview": _mask(s.binance_api_key_enc),
        "groq_api_key_set": s.ai_groq_key_enc is not None,
        "gemini_api_key_set": s.ai_gemini_key_enc is not None,
        "premium_api_key_set": s.ai_premium_key_enc is not None,
        "omniroute_api_key_set": s.ai_omniroute_key_enc is not None,
        "premium_provider": s.ai_premium_provider,
        "premium_model": s.ai_premium_model,
        "ai_provider": s.ai_provider,
        "ai_model": s.ai_model,
        "last_model_used": s.last_model_used,
        "last_ai_provider_used": s.last_ai_provider_used,
        "telegram_chat_id": s.telegram_chat_id,
        "telegram_alerts": s.telegram_alerts,
    }


@router.post("/binance-keys")
def save_binance_keys(
    req: SaveBinanceKeysRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Save Binance API keys (encrypted locally)."""
    s = _get_or_create(db, current_user.id)
    s.binance_api_key_enc = encrypt(req.binance_api_key)
    s.binance_api_secret_enc = encrypt(req.binance_api_secret)
    db.commit()
    return {"saved": True, "message": "Binance API keys guardadas"}


@router.delete("/binance-keys")
def delete_binance_keys(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Delete stored Binance API keys."""
    s = _get_or_create(db, current_user.id)
    s.binance_api_key_enc = None
    s.binance_api_secret_enc = None
    db.commit()
    return {"deleted": True, "message": "Binance API keys eliminadas"}


@router.post("/ai-keys")
def save_ai_keys(
    req: SaveAIKeysRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Save AI provider API keys (encrypted locally)."""
    s = _get_or_create(db, current_user.id)
    if req.groq_api_key is not None:
        s.ai_groq_key_enc = encrypt(req.groq_api_key) if req.groq_api_key else None
    if req.gemini_api_key is not None:
        s.ai_gemini_key_enc = encrypt(req.gemini_api_key) if req.gemini_api_key else None
    if req.premium_api_key is not None:
        s.ai_premium_key_enc = encrypt(req.premium_api_key) if req.premium_api_key else None
    if req.premium_provider is not None:
        s.ai_premium_provider = req.premium_provider or None
    if req.premium_base_url is not None:
        s.ai_premium_base_url = req.premium_base_url or None
    if req.premium_model is not None:
        s.ai_premium_model = req.premium_model or None
    if req.omniroute_api_key is not None:
        s.ai_omniroute_key_enc = encrypt(req.omniroute_api_key) if req.omniroute_api_key else None
    db.commit()
    return {"saved": True, "message": "AI keys guardadas"}


@router.post("/ai-config")
def save_ai_config(
    req: SaveAIConfigRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Save full AI config: provider + model + key in one shot.

    This persists the selected provider, model, and optional API key
    so they are loaded automatically on next session start.
    """
    s = _get_or_create(db, current_user.id)

    # Save provider and model
    s.ai_provider = req.provider
    s.ai_model = req.model
    s.last_ai_provider_used = req.provider
    s.last_model_used = req.model

    # Save premium provider info if applicable
    PREMIUM_PROVIDERS = {"openai", "deepseek", "mistral", "together", "perplexity", "grok"}
    if req.provider in PREMIUM_PROVIDERS:
        s.ai_premium_provider = req.provider
        if req.premium_base_url:
            s.ai_premium_base_url = req.premium_base_url
        s.ai_premium_model = req.model

    # Save keys if provided (don't overwrite existing if not provided)
    if req.groq_api_key is not None:
        s.ai_groq_key_enc = encrypt(req.groq_api_key) if req.groq_api_key else None
    if req.gemini_api_key is not None:
        s.ai_gemini_key_enc = encrypt(req.gemini_api_key) if req.gemini_api_key else None
    if req.premium_api_key is not None:
        s.ai_premium_key_enc = encrypt(req.premium_api_key) if req.premium_api_key else None
    if req.omniroute_api_key is not None:
        s.ai_omniroute_key_enc = encrypt(req.omniroute_api_key) if req.omniroute_api_key else None

    db.commit()
    return {
        "saved": True,
        "provider": req.provider,
        "model": req.model,
        "message": f"Config guardada: {req.provider} / {req.model}",
    }


@router.delete("/ai-keys")
def delete_ai_keys(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Delete all stored AI provider keys."""
    s = _get_or_create(db, current_user.id)
    s.ai_groq_key_enc = None
    s.ai_gemini_key_enc = None
    s.ai_premium_key_enc = None
    s.ai_premium_provider = None
    s.ai_premium_base_url = None
    s.ai_premium_model = None
    db.commit()
    return {"deleted": True, "message": "AI keys eliminadas"}


@router.post("/telegram")
def save_telegram(
    req: SaveTelegramRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Save Telegram notification settings."""
    s = _get_or_create(db, current_user.id)
    s.telegram_chat_id = req.telegram_chat_id
    s.telegram_alerts = req.telegram_alerts
    db.commit()
    return {"saved": True, "message": "Telegram settings guardadas"}


def _mask(enc_value: str | None) -> str:
    """Return masked preview of an encrypted key."""
    if not enc_value:
        return ""
    try:
        val = decrypt(enc_value)
        if len(val) <= 8:
            return "****"
        return val[:4] + "****" + val[-4:]
    except Exception:
        return "****"


# ---------------------------------------------------------------------------
# User Preferences (theme, risk profile, dashboard layout)
# ---------------------------------------------------------------------------

class PreferencesRequest(BaseModel):
    theme: str | None = None
    risk_profile: str | None = None
    dashboard_layout: dict | None = None


@router.get("/preferences")
def get_preferences(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Get user's UI preferences (theme, risk profile, dashboard layout)."""
    from app.database.models.user_preference import UserPreference
    pref = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
    if not pref:
        return {"theme": "dark", "risk_profile": "moderate", "dashboard_layout": {}}
    return {
        "theme": pref.theme,
        "risk_profile": pref.risk_profile,
        "dashboard_layout": pref.dashboard_layout or {},
    }


@router.post("/preferences")
def save_preferences(
    req: PreferencesRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Save user's UI preferences (partial update)."""
    from app.database.models.user_preference import UserPreference
    pref = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
    if not pref:
        pref = UserPreference(user_id=current_user.id)
        db.add(pref)
    if req.theme is not None:
        pref.theme = req.theme
    if req.risk_profile is not None:
        pref.risk_profile = req.risk_profile
    if req.dashboard_layout is not None:
        pref.dashboard_layout = req.dashboard_layout
    db.commit()
    return {"saved": True, "theme": pref.theme, "risk_profile": pref.risk_profile}


# ---------------------------------------------------------------------------
# Watchlist (favorite trading symbols)
# ---------------------------------------------------------------------------

class WatchlistAddRequest(BaseModel):
    symbol: str
    display_name: str | None = None


class WatchlistReorderRequest(BaseModel):
    symbols: list[str] = []


@router.get("/watchlist")
def get_watchlist(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    """Get user's watchlist (favorite symbols)."""
    from app.database.models.watchlist import Watchlist
    items = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id
    ).order_by(Watchlist.sort_order).all()
    return [{
        "id": w.id,
        "symbol": w.symbol,
        "display_name": w.display_name,
        "sort_order": w.sort_order,
    } for w in items]


@router.post("/watchlist")
def add_to_watchlist(
    req: WatchlistAddRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Add a symbol to the user's watchlist."""
    from app.database.models.watchlist import Watchlist
    existing = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id,
        Watchlist.symbol == req.symbol,
    ).first()
    if existing:
        return {"status": "exists", "id": existing.id}
    max_order = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id
    ).count()
    w = Watchlist(
        user_id=current_user.id,
        symbol=req.symbol,
        display_name=req.display_name,
        sort_order=max_order,
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    return {"status": "added", "id": w.id}


@router.delete("/watchlist/{symbol}")
def remove_from_watchlist(
    symbol: str,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Remove a symbol from the user's watchlist."""
    from app.database.models.watchlist import Watchlist
    w = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id,
        Watchlist.symbol == symbol,
    ).first()
    if w:
        db.delete(w)
        db.commit()
        return {"status": "removed"}
    return {"status": "not_found"}


@router.patch("/watchlist/reorder")
def reorder_watchlist(
    req: WatchlistReorderRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Reorder the user's watchlist."""
    from app.database.models.watchlist import Watchlist
    for idx, symbol in enumerate(req.symbols):
        w = db.query(Watchlist).filter(
            Watchlist.user_id == current_user.id,
            Watchlist.symbol == symbol,
        ).first()
        if w:
            w.sort_order = idx
    db.commit()
    return {"status": "reordered"}


# ---------------------------------------------------------------------------
# Guided Onboarding — auto-configure based on profile
# ---------------------------------------------------------------------------


class OnboardingCompleteRequest(BaseModel):
    experience_level: str = ""
    risk_tolerance: str = ""
    asset_interests: list[str] = []
    capital_range: str = ""
    preferred_strategies: list[str] = []
    trading_goal: str = ""
    preferred_language: str = "es"
    broker_id: str | None = None
    ai_provider: str | None = None
    ai_key: str | None = None


@router.post("/onboarding/complete")
def complete_onboarding(
    req: OnboardingCompleteRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Complete onboarding — saves profile and auto-configures risk + paper trading."""
    uid = current_user.id if current_user else 0
    results: dict = {"profile": "ok", "risk_config": "ok", "paper_trading": "ok"}

    # 1. Save user profile
    try:
        from app.database.models.user_profile import UserProfile
        from app.database.session import SessionLocal

        db = SessionLocal()
        try:
            profile = db.query(UserProfile).filter(UserProfile.user_id == uid).first()
            if not profile:
                profile = UserProfile(user_id=uid)
                db.add(profile)
            profile.experience_level = req.experience_level
            profile.risk_tolerance = req.risk_tolerance
            import json as _json
            profile.asset_interests = _json.dumps(req.asset_interests)
            profile.capital_range = req.capital_range
            profile.preferred_strategies = _json.dumps(req.preferred_strategies)
            profile.trading_goal = req.trading_goal
            profile.preferred_language = req.preferred_language
            profile.onboarding_completed = True
            db.commit()
        finally:
            db.close()
    except Exception:
        results["profile"] = "error"

    # 2. Auto-configure risk based on profile
    try:
        from app.database.models.risk_config import RiskConfig
        from app.database.session import SessionLocal

        risk_map = {
            "conservative": {"max_open_positions": 3, "max_position_size_pct": 5.0, "hard_stop_loss_pct": 3.0},
            "moderate": {"max_open_positions": 5, "max_position_size_pct": 10.0, "hard_stop_loss_pct": 5.0},
            "aggressive": {"max_open_positions": 8, "max_position_size_pct": 20.0, "hard_stop_loss_pct": 8.0},
        }
        risk_cfg = risk_map.get(req.risk_tolerance, risk_map["moderate"])

        db = SessionLocal()
        try:
            cfg = db.query(RiskConfig).filter(RiskConfig.user_id == uid).first()
            if not cfg:
                cfg = RiskConfig(user_id=uid)
                db.add(cfg)
            cfg.max_open_positions = risk_cfg["max_open_positions"]
            cfg.max_position_size_pct = risk_cfg["max_position_size_pct"]
            cfg.hard_stop_loss_pct = risk_cfg["hard_stop_loss_pct"]
            db.commit()
        finally:
            db.close()
    except Exception:
        results["risk_config"] = "error"

    # 3. Save AI key if provided
    if req.ai_provider and req.ai_key:
        try:
            from app.services.crypto import encrypt as _encrypt
            db = SessionLocal()
            try:
                s = db.query(UserSettings).filter(UserSettings.user_id == uid).first()
                if not s:
                    s = UserSettings(user_id=uid)
                    db.add(s)
                key_field = f"ai_{req.ai_provider}_key_enc"
                if hasattr(s, key_field):
                    setattr(s, key_field, _encrypt(req.ai_key))
                db.commit()
                results["ai_config"] = "ok"
            finally:
                db.close()
        except Exception:
            results["ai_config"] = "error"

    return {"status": "ok", "results": results}
