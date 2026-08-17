"""Alvora configuration model — per-user AI advisor settings.

Stores the primary provider, fallback chain, and persona/behavior settings
for the Alvora chat advisor. Separate from UserSettings (which stores the
autonomous agent config) so the two can evolve independently.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AlvoraConfig(Base):
    """Per-user Alvora advisor configuration.

    All settings are stored as simple columns. The fallback chain is stored
    as a JSON string in fallback_chain_json.
    """

    __tablename__ = "alvora_config"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)

    # ─── Primary provider ────────────────────────────────────────────────
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="gemini")
    api_key_enc: Mapped[str | None] = mapped_column(String(500), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ─── Fallback chain (JSON array of {provider, api_key_enc, model}) ───
    fallback_chain_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ─── Persona / behavior ──────────────────────────────────────────────
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="es")
    response_style: Mapped[str] = mapped_column(String(20), nullable=False, default="detailed")
    risk_advice_level: Mapped[str] = mapped_column(String(20), nullable=False, default="balanced")
    auto_suggest_actions: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=1800, nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)

    # ─── Context inclusion ───────────────────────────────────────────────
    include_positions: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    include_market_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    include_profile: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    include_recommendations: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, include_keys: bool = False) -> dict:
        """Return config as dict. By default, API keys are masked/not included."""
        import json
        from app.services.crypto import decrypt

        fallback = []
        if self.fallback_chain_json:
            try:
                raw = json.loads(self.fallback_chain_json)
                for item in raw:
                    entry = {
                        "provider": item.get("provider", ""),
                        "model": item.get("model", ""),
                        "api_key_set": bool(item.get("api_key_enc")),
                    }
                    if include_keys and item.get("api_key_enc"):
                        try:
                            entry["api_key"] = decrypt(item["api_key_enc"])
                        except Exception:
                            pass
                    fallback.append(entry)
            except Exception:
                pass

        result = {
            "provider": self.provider,
            "api_key_set": bool(self.api_key_enc),
            "model": self.model or "",
            "fallback_chain": fallback,
            "language": self.language,
            "response_style": self.response_style,
            "risk_advice_level": self.risk_advice_level,
            "auto_suggest_actions": self.auto_suggest_actions,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "include_positions": self.include_positions,
            "include_market_data": self.include_market_data,
            "include_profile": self.include_profile,
            "include_recommendations": self.include_recommendations,
        }
        if include_keys and self.api_key_enc:
            try:
                result["api_key"] = decrypt(self.api_key_enc)
            except Exception:
                pass
        return result
