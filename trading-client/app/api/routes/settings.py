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
        "premium_provider": s.ai_premium_provider,
        "premium_model": s.ai_premium_model,
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
    db.commit()
    return {"saved": True, "message": "AI keys guardadas"}


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
