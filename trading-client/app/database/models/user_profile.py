"""User profile model — stores onboarding data for adaptive dashboard."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class UserProfile(Base):
    """Per-user onboarding profile for personalized dashboard experience.

    Created on first login after the user completes the onboarding form.
    Used to tailor the dashboard display, recommendations, and strategy suggestions.
    """

    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)

    # Experience level
    experience_level: Mapped[str] = mapped_column(String(20), nullable=False, default="beginner")
    # beginner | intermediate | advanced

    # Risk tolerance
    risk_tolerance: Mapped[str] = mapped_column(String(20), nullable=False, default="moderate")
    # conservative | moderate | aggressive

    # Asset interests (JSON array stored as text)
    asset_interests: Mapped[str] = mapped_column(Text, nullable=False, default='["crypto"]')
    # crypto | stocks | forex | commodities

    # Capital range
    capital_range: Mapped[str] = mapped_column(String(20), nullable=False, default="100-1000")
    # <100 | 100-1000 | 1000-10000 | 10000-50000 | 50000+

    # Preferred strategies (JSON array stored as text)
    preferred_strategies: Mapped[str] = mapped_column(Text, nullable=False, default='["swing"]')
    # scalping | day_trading | swing | position | dca | hold

    # Trading goals
    trading_goal: Mapped[str] = mapped_column(String(50), nullable=False, default="growth")
    # growth | income | preservation | speculation

    # Preferred language for UI hints
    preferred_language: Mapped[str] = mapped_column(String(10), nullable=False, default="es")

    # Onboarding completed
    onboarding_completed: Mapped[bool] = mapped_column(default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self) -> dict:
        import json
        return {
            "user_id": self.user_id,
            "experience_level": self.experience_level,
            "risk_tolerance": self.risk_tolerance,
            "asset_interests": json.loads(self.asset_interests) if self.asset_interests else [],
            "capital_range": self.capital_range,
            "preferred_strategies": json.loads(self.preferred_strategies) if self.preferred_strategies else [],
            "trading_goal": self.trading_goal,
            "preferred_language": self.preferred_language,
            "onboarding_completed": self.onboarding_completed,
        }
