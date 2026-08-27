"""Strategy Marketplace — published strategies, subscriptions, reviews, and backtest verifications."""

from datetime import datetime

from sqlalchemy import Boolean, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class StrategyListing(Base):
    """A strategy published to the marketplace by a user."""

    __tablename__ = "strategy_listings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    creator_user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    strategy_type: Mapped[str] = mapped_column(String(30), nullable=False, default="custom")
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_premium: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    price_monthly: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now()
    )
    downloads: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rating_avg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Optional metadata — exchange and symbols the strategy targets
    exchange: Mapped[str | None] = mapped_column(String(50), nullable=True)
    symbols_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_strategy_listings_creator", "creator_user_id"),
        Index("ix_strategy_listings_public", "is_public"),
        Index("ix_strategy_listings_type", "strategy_type"),
    )


class StrategySubscription(Base):
    """A user's subscription to a marketplace strategy listing."""

    __tablename__ = "strategy_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    listing_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    subscribed_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_strategy_subscriptions_user", "user_id"),
        Index("ix_strategy_subscriptions_listing", "listing_id"),
    )


class StrategyReview(Base):
    """A user review/rating for a marketplace strategy listing."""

    __tablename__ = "strategy_reviews"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    listing_id: Mapped[int] = mapped_column(Integer, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_strategy_reviews_listing", "listing_id"),
        Index("ix_strategy_reviews_user", "user_id"),
    )


class StrategyBacktestVerification(Base):
    """Backtest verification metrics attached to a strategy listing."""

    __tablename__ = "strategy_backtest_verifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(Integer, nullable=False)
    backtest_hash: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    roi_90d: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_drawdown: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sharpe: Mapped[float | None] = mapped_column(Float, nullable=True)
    verified_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_strategy_backtest_verifications_listing", "listing_id"),
    )
