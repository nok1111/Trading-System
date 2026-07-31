"""UserPreference model — per-user UI preferences (theme, risk profile, dashboard layout)."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class UserPreference(Base):
    """Per-user UI and dashboard preferences.

    Stores theme, risk profile, and dashboard layout configuration
    so that the user's UI is consistent across devices.
    """

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    theme: Mapped[str] = mapped_column(String(10), nullable=False, default="dark")
    # dark, light
    risk_profile: Mapped[str] = mapped_column(String(20), nullable=False, default="moderate")
    # conservative, moderate, aggressive
    dashboard_layout: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # {"modules": [{"id": "overview", "visible": true, "order": 0}, ...], "columns": 2}
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), server_default=func.now(), onupdate=func.now()
    )
