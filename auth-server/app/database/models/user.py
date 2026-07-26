"""User model — NO Binance/AI API keys (those live on the Trading Client only)."""

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
    """User for the Alvora SaaS Auth Server.

    NOTE: This model does NOT store Binance API keys, AI provider keys,
    or any trading-related data. Those are stored ONLY on the local
    Trading Client for privacy.
    """

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
    # User preferences (non-sensitive)
    risk_profile: Mapped[str] = mapped_column(String(20), nullable=False, default="moderate")
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now(), onupdate=func.now()
    )
