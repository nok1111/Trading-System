"""AI usage tracking model — daily quota per user."""

from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AIUsageLog(Base):
    """Tracks daily AI agent requests per user for quota enforcement."""

    __tablename__ = "ai_usage_logs"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_ai_usage_user_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    request_count: Mapped[int] = mapped_column(default=0, nullable=False)
    last_grant_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now(), onupdate=func.now()
    )
