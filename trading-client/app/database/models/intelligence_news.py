"""Intelligence News model — stores important market news with metadata."""

from datetime import datetime

from sqlalchemy import JSON, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class IntelligenceNews(Base):
    """Important market news stored periodically by the news fetcher job.

    News is fetched every N minutes, filtered by relevance/impact, and stored
    with original link, image URL, affected assets, and AI-generated summary.
    Old news is cleaned up periodically to prevent unbounded growth.
    """

    __tablename__ = "intelligence_news"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="unknown")
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    summary: Mapped[str | None] = mapped_column(nullable=True)
    impact: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    # low, medium, high, critical
    affected_assets: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # {"assets": ["BTC", "ETH"], "sectors": ["L2", "DeFi"]}
    categories: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # ["regulation", "ETF", "partnership", "hack", "macro", etc.]
    sentiment: Mapped[str] = mapped_column(String(20), nullable=False, default="neutral")
    # bullish, bearish, neutral
    ai_analysis: Mapped[str | None] = mapped_column(nullable=True)
    # AI-generated analysis of why this news matters
    published_at: Mapped[datetime] = mapped_column(nullable=False)
    # Original publish date from the source
    fetched_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now()
    )
    # When we stored it

    __table_args__ = (
        Index("ix_intel_news_published", "published_at"),
        Index("ix_intel_news_impact", "impact"),
        Index("ix_intel_news_source", "source"),
        Index("ix_intel_news_fetched", "fetched_at"),
    )
