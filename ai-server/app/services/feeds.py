"""Data feed stubs for the Market Data Engine.

Each feed provides an interface for external data sources.
Stubs return empty data — real implementations come in Phase 7 (Multi-Broker Real).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class NewsItem:
    """A single news item from a news feed."""

    headline: str
    source: str
    url: str = ""
    timestamp: str = ""
    assets: list[str] = field(default_factory=list)
    category: str = "general"  # regulation, market, tech, macro, rumor
    is_rumor: bool = False


@dataclass
class OnchainData:
    """On-chain metrics for a single asset."""

    asset: str
    exchange_inflow: float | None = None
    exchange_outflow: float | None = None
    net_flow: float | None = None
    whale_movements: list[dict] = field(default_factory=list)
    active_addresses: int | None = None
    reserve: float | None = None
    stablecoin_supply: float | None = None
    mvrv: float | None = None
    timestamp: str = ""


@dataclass
class MacroData:
    """Macroeconomic indicators."""

    macro_regime: str = "unknown"  # risk_on, risk_off, neutral
    interest_rate: float | None = None
    inflation: float | None = None
    dxy: float | None = None  # Dollar Index
    gold: float | None = None
    oil: float | None = None
    spy: float | None = None  # S&P 500 ETF
    bitcoin_dominance: float | None = None
    key_events: list[dict] = field(default_factory=list)
    timestamp: str = ""


@dataclass
class SentimentData:
    """Sentiment analysis data for an asset."""

    asset: str
    sentiment_score: float = 0.0  # -1.0 to 1.0
    fear_greed_index: int | None = None  # 0-100
    social_mentions: int | None = None
    social_volume_change: float | None = None
    narrative: str = ""
    euphoria_detected: bool = False
    fear_detected: bool = False
    coordinated_activity: bool = False
    timestamp: str = ""


class BaseFeed(ABC):
    """Abstract base class for data feeds."""

    @abstractmethod
    def fetch(self, *args, **kwargs) -> Any:
        """Fetch data from the feed."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Feed name."""
        ...


class NewsFeed(BaseFeed):
    """News feed — stub returns empty list.

    Real implementation will integrate RSS feeds, crypto news APIs
    (CryptoPanic, CoinDesk, etc.).
    """

    @property
    def name(self) -> str:
        return "news"

    def fetch(self, assets: list[str] | None = None, limit: int = 50) -> list[NewsItem]:
        if not settings.ENABLE_NEWS_FEED:
            logger.debug("News feed disabled — returning empty list")
            return []
        # TODO: Implement real news feed integration
        return []


class OnchainFeed(BaseFeed):
    """On-chain data feed — stub returns empty data.

    Real implementation will integrate Glassnode, CryptoQuant, or
    direct blockchain node queries.
    """

    @property
    def name(self) -> str:
        return "onchain"

    def fetch(self, asset: str) -> OnchainData:
        if not settings.ENABLE_ONCHAIN_FEED:
            logger.debug("On-chain feed disabled — returning empty data")
            return OnchainData(asset=asset)
        # TODO: Implement real on-chain feed integration
        return OnchainData(asset=asset)


class MacroFeed(BaseFeed):
    """Macroeconomic data feed — stub returns empty data.

    Real implementation will integrate FRED API, Yahoo Finance for
    DXY/Gold/Oil/SPY, and economic calendar APIs.
    """

    @property
    def name(self) -> str:
        return "macro"

    def fetch(self) -> MacroData:
        if not settings.ENABLE_MACRO_FEED:
            logger.debug("Macro feed disabled — returning empty data")
            return MacroData()
        # TODO: Implement real macro feed integration
        return MacroData()


class SentimentFeed(BaseFeed):
    """Sentiment data feed — stub returns empty data.

    Real implementation will integrate social media APIs (Twitter/X,
    Reddit, LunarCrush, etc.) and Fear & Greed Index.
    """

    @property
    def name(self) -> str:
        return "sentiment"

    def fetch(self, asset: str) -> SentimentData:
        if not settings.ENABLE_SENTIMENT_FEED:
            logger.debug("Sentiment feed disabled — returning empty data")
            return SentimentData(asset=asset)
        # TODO: Implement real sentiment feed integration
        return SentimentData(asset=asset)


# Singleton instances
_news_feed: NewsFeed | None = None
_onchain_feed: OnchainFeed | None = None
_macro_feed: MacroFeed | None = None
_sentiment_feed: SentimentFeed | None = None


def get_news_feed() -> NewsFeed:
    global _news_feed
    if _news_feed is None:
        _news_feed = NewsFeed()
    return _news_feed


def get_onchain_feed() -> OnchainFeed:
    global _onchain_feed
    if _onchain_feed is None:
        _onchain_feed = OnchainFeed()
    return _onchain_feed


def get_macro_feed() -> MacroFeed:
    global _macro_feed
    if _macro_feed is None:
        _macro_feed = MacroFeed()
    return _macro_feed


def get_sentiment_feed() -> SentimentFeed:
    global _sentiment_feed
    if _sentiment_feed is None:
        _sentiment_feed = SentimentFeed()
    return _sentiment_feed
