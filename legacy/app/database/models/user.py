from datetime import datetime
from enum import Enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SubscriptionPlan(str, Enum):
    free = "free"
    pro = "pro"
    premium = "premium"


class User(Base):
    """Usuario del sistema SaaS."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(default=False, nullable=False)
    subscription: Mapped[str] = mapped_column(
        SAEnum(SubscriptionPlan), nullable=False, default=SubscriptionPlan.free
    )
    # Encrypted API keys (stored encrypted at rest)
    binance_api_key_enc: Mapped[str | None] = mapped_column(String(512), nullable=True)
    binance_api_secret_enc: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # AI provider keys (encrypted)
    ai_groq_key_enc: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ai_gemini_key_enc: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Premium AI provider (OpenAI-compatible: OpenAI, DeepSeek, Mistral, Together, Perplexity, Grok)
    ai_premium_key_enc: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ai_premium_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_premium_base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ai_premium_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # User preferences
    risk_profile: Mapped[str] = mapped_column(String(20), nullable=False, default="moderate")
    # Telegram notifications
    telegram_chat_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    telegram_alerts: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now(), onupdate=func.now()
    )
