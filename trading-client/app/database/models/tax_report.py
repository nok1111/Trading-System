"""TaxReport model — persists generated tax reports per user/year/country."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class TaxReport(Base):
    """A generated tax report for a given user, year, country, and lot method.

    Stores the full report as JSON plus an optional path to a generated PDF.
    """

    __tablename__ = "tax_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="fifo")
    report_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_tax_reports_user_year", "user_id", "year"),
    )
