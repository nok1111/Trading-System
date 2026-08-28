"""Modelo de progreso de Alvora Academy — tracking de tutoriales completados por usuario."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AcademyProgress(Base):
    """Progreso de un usuario en un tutorial de Alvora Academy.

    Registra qué tutoriales ha completado cada usuario y el porcentaje
    de progreso en cada uno. Se usa para mostrar el badge de
    'Alvora Certified Trader' cuando todos los tutoriales están completos.
    """

    __tablename__ = "academy_progress"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(nullable=False, default=0)
    tutorial_id: Mapped[str] = mapped_column(String(100), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    xp_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quiz_scores_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    perfect_quiz: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_academy_progress_user_id", "user_id"),
        Index("ix_academy_progress_tutorial_id", "tutorial_id"),
        Index("ix_academy_progress_user_tutorial", "user_id", "tutorial_id", unique=True),
    )
