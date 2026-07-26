"""Local user settings model — stores encrypted API keys per user in local SQLite."""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class UserSettings(Base):
    """Per-user encrypted API keys stored locally in the Trading Client.

    Keys are encrypted with Fernet (see app.services.crypto).
    No plaintext keys are ever stored.
    """

    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    binance_api_key_enc: Mapped[str | None] = mapped_column(String(500), nullable=True)
    binance_api_secret_enc: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ai_groq_key_enc: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ai_gemini_key_enc: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ai_premium_key_enc: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ai_premium_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_premium_base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ai_premium_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    telegram_alerts: Mapped[bool] = mapped_column(default=False, nullable=False)
