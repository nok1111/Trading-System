"""Data feeds for the Market Data Engine.

Real implementations using free public APIs:
- NewsFeed: CryptoPanic API (requires NEWS_API_TOKEN)
- OnchainFeed: Glassnode API (requires ONCHAIN_API_KEY)
- MacroFeed: CoinGecko + alternative.me (no key needed)
- SentimentFeed: alternative.me Fear & Greed Index (no key needed)

All feeds degrade gracefully on errors or missing API keys.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
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
    """News feed — fetches from CryptoPanic free API.

    Requires NEWS_API_TOKEN for CryptoPanic. Degrades gracefully without it.
    """

    @property
    def name(self) -> str:
        return "news"

    def fetch(self, assets: list[str] | None = None, limit: int = 50) -> list[NewsItem]:
        if not settings.ENABLE_NEWS_FEED:
            logger.debug("News feed disabled — returning empty list")
            return []

        token = settings.NEWS_API_TOKEN
        if not token:
            logger.warning("News feed enabled but NEWS_API_TOKEN not set")
            return []

        try:
            import httpx

            params: dict[str, str | int] = {
                "auth_token": token,
                "public": "true",
                "kind": "news",
            }
            if assets:
                currencies = ",".join(a.lower().replace("usdt", "") for a in assets[:5])
                params["currencies"] = currencies

            resp = httpx.get(
                "https://cryptopanic.com/api/free/v1/posts/",
                params=params,
                timeout=settings.FEED_TIMEOUT_SECONDS,
            )
            if resp.status_code != 200:
                logger.warning("News feed HTTP %d", resp.status_code)
                return []

            results = resp.json().get("results", [])
            items: list[NewsItem] = []
            for r in results[:limit]:
                items.append(NewsItem(
                    headline=r.get("title", ""),
                    source=r.get("source", {}).get("name", "unknown"),
                    url=r.get("url", ""),
                    timestamp=r.get("published_at", ""),
                    assets=[c.get("code", "") for c in r.get("currencies", [])],
                    category=r.get("kind", "news"),
                    is_rumor=r.get("kind") == "rumor",
                ))
            logger.info("News feed: fetched %d items", len(items))
            return items
        except Exception as exc:  # noqa: BLE001
            logger.error("News feed error: %s", exc)
            return []


class OnchainFeed(BaseFeed):
    """On-chain data feed — fetches from Glassnode free tier.

    Requires ONCHAIN_API_KEY. Degrades gracefully without it.
    """

    @property
    def name(self) -> str:
        return "onchain"

    def fetch(self, asset: str) -> OnchainData:
        if not settings.ENABLE_ONCHAIN_FEED:
            logger.debug("On-chain feed disabled — returning empty data")
            return OnchainData(asset=asset)

        api_key = settings.ONCHAIN_API_KEY
        if not api_key:
            logger.warning("Onchain feed enabled but ONCHAIN_API_KEY not set")
            return OnchainData(asset=asset)

        try:
            import httpx

            symbol = asset.lower().replace("usdt", "")
            base_url = "https://api.glassnode.com/v1/metrics"
            headers = {"X-Glassnode-API-Key": api_key}
            params = {"a": symbol, "i": "24h"}
            timeout = settings.FEED_TIMEOUT_SECONDS

            data = OnchainData(asset=asset, timestamp=datetime.now(UTC).isoformat())

            # Exchange net flow
            try:
                resp = httpx.get(
                    f"{base_url}/transactions/transfers/volume_sum",
                    headers=headers,
                    params=params,
                    timeout=timeout,
                )
                if resp.status_code == 200:
                    series = resp.json()
                    if series:
                        data.exchange_inflow = series[-1].get("v", 0)
            except Exception:  # noqa: BLE001
                pass

            # MVRV ratio
            try:
                resp = httpx.get(
                    f"{base_url}/market/mvrv",
                    headers=headers,
                    params=params,
                    timeout=timeout,
                )
                if resp.status_code == 200:
                    series = resp.json()
                    if series:
                        data.mvrv = series[-1].get("v", 0)
            except Exception:  # noqa: BLE001
                pass

            # Active addresses
            try:
                resp = httpx.get(
                    f"{base_url}/addresses/active_count",
                    headers=headers,
                    params=params,
                    timeout=timeout,
                )
                if resp.status_code == 200:
                    series = resp.json()
                    if series:
                        data.active_addresses = int(series[-1].get("v", 0))
            except Exception:  # noqa: BLE001
                pass

            logger.info("Onchain feed: fetched data for %s (mvrv=%s)", asset, data.mvrv)
            return data
        except Exception as exc:  # noqa: BLE001
            logger.error("Onchain feed error: %s", exc)
            return OnchainData(asset=asset)


class MacroFeed(BaseFeed):
    """Macroeconomic data feed — fetches from CoinGecko + alternative.me.

    No API key required (free public APIs). Degrades gracefully on errors.
    """

    @property
    def name(self) -> str:
        return "macro"

    def fetch(self) -> MacroData:
        if not settings.ENABLE_MACRO_FEED:
            logger.debug("Macro feed disabled — returning empty data")
            return MacroData()

        data = MacroData(timestamp=datetime.now(UTC).isoformat())
        timeout = settings.FEED_TIMEOUT_SECONDS

        try:
            import httpx

            # CoinGecko global — BTC dominance
            try:
                resp = httpx.get(
                    "https://api.coingecko.com/api/v3/global",
                    timeout=timeout,
                )
                if resp.status_code == 200:
                    glob = resp.json().get("data", {})
                    data.bitcoin_dominance = glob.get("market_cap_percentage", {}).get("btc")
            except Exception:  # noqa: BLE001
                pass

            # alternative.me Fear & Greed — determine macro regime
            try:
                resp = httpx.get(
                    "https://api.alternative.me/fng/?limit=1",
                    timeout=timeout,
                )
                if resp.status_code == 200:
                    fng = resp.json().get("data", [{}])[0]
                    fng_value = int(fng.get("value", 50))
                    if fng_value >= 70:
                        data.macro_regime = "risk_on"
                    elif fng_value <= 25:
                        data.macro_regime = "risk_off"
                    else:
                        data.macro_regime = "neutral"
            except Exception:  # noqa: BLE001
                pass

            logger.info("Macro feed: regime=%s, btc_dom=%s", data.macro_regime, data.bitcoin_dominance)
            return data
        except Exception as exc:  # noqa: BLE001
            logger.error("Macro feed error: %s", exc)
            return data


class SentimentFeed(BaseFeed):
    """Sentiment data feed — fetches Fear & Greed Index from alternative.me.

    No API key required (free public API). Degrades gracefully on errors.
    """

    @property
    def name(self) -> str:
        return "sentiment"

    def fetch(self, asset: str) -> SentimentData:
        if not settings.ENABLE_SENTIMENT_FEED:
            logger.debug("Sentiment feed disabled — returning empty data")
            return SentimentData(asset=asset)

        data = SentimentData(asset=asset, timestamp=datetime.now(UTC).isoformat())

        try:
            import httpx

            # Fear & Greed Index (crypto-wide, not per-asset)
            resp = httpx.get(
                "https://api.alternative.me/fng/?limit=1",
                timeout=settings.FEED_TIMEOUT_SECONDS,
            )
            if resp.status_code == 200:
                fng = resp.json().get("data", [{}])[0]
                data.fear_greed_index = int(fng.get("value", 50))
                classification = fng.get("value_classification", "Neutral")

                # Derive sentiment score from F&G (0-100 → -1 to 1)
                data.sentiment_score = (data.fear_greed_index - 50) / 50.0

                # Detect extremes
                if data.fear_greed_index >= 85:
                    data.euphoria_detected = True
                    data.narrative = f"Extreme Greed ({classification})"
                elif data.fear_greed_index <= 15:
                    data.fear_detected = True
                    data.narrative = f"Extreme Fear ({classification})"
                else:
                    data.narrative = classification

            logger.info(
                "Sentiment feed: %s F&G=%s score=%.2f narrative=%s",
                asset, data.fear_greed_index, data.sentiment_score, data.narrative,
            )
            return data
        except Exception as exc:  # noqa: BLE001
            logger.error("Sentiment feed error: %s", exc)
            return data


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
