"""News fetcher — periodically fetches and stores important crypto news.

Fetches from multiple RSS feeds (CoinDesk, CoinTelegraph, Bitcoin Magazine, etc.),
filters by relevance, optionally uses AI (Gemini/Groq) to rate impact and generate
summary, and stores in the intelligence_news table.

Designed to run every 5-10 minutes as part of the agent scheduler.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from xml.etree import ElementTree

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.intelligence_news import IntelligenceNews
from app.database.session import SessionLocal

logger = logging.getLogger(__name__)

# RSS feeds — free, no API key needed
RSS_FEEDS: list[dict[str, str]] = [
    {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
    {"name": "CoinTelegraph", "url": "https://cointelegraph.com/rss"},
    {"name": "Bitcoin Magazine", "url": "https://bitcoinmagazine.com/.rss/full/"},
    {"name": "CryptoSlate", "url": "https://cryptoslate.com/feed/"},
    {"name": "The Block", "url": "https://www.theblock.co/rss.xml"},
]

# Keywords that indicate high-impact news
HIGH_IMPACT_KEYWORDS = [
    "etf", "sec", "fed", "approval", "rejected", "ban", "lawsuit",
    "hack", "exploit", "collapse", "bankruptcy", "arrest",
    "partnership", "adoption", "institutional", "treasury",
    "halving", "upgrade", "fork", "merge",
    "fed", "rate", "inflation", "cpi", "fomc", "powell",
    "binance", "coinbase", "blackrock", "fidelity",
]

# Asset tickers to detect in news titles
ASSET_PATTERNS: dict[str, list[str]] = {
    "BTC": ["bitcoin", "btc", "ordinals"],
    "ETH": ["ethereum", "eth", "ether", "vitalik", "l2", "layer 2"],
    "SOL": ["solana", "sol"],
    "XRP": ["ripple", "xrp"],
    "DOGE": ["dogecoin", "doge"],
    "ADA": ["cardano", "ada"],
    "AVAX": ["avalanche", "avax"],
    "LINK": ["chainlink", "link"],
    "BNB": ["binance coin", "bnb"],
    "DOT": ["polkadot", "dot"],
}

# Categories detection
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "regulation": ["sec", "regulation", "law", "compliance", "ban", "lawsuit", "court"],
    "etf": ["etf", "spot", "approval", "filing"],
    "macro": ["fed", "rate", "inflation", "cpi", "fomc", "powell", "treasury", "dollar", "dxy"],
    "partnership": ["partnership", "collaboration", "integration", "adoption"],
    "hack": ["hack", "exploit", "drained", "stolen", "vulnerability", "breach"],
    "technology": ["upgrade", "fork", "merge", "scaling", "layer 2", "l2", "protocol"],
    "market": ["rally", "crash", "surge", "dump", "pump", "liquidation", "funding"],
}


def _detect_assets(title: str, summary: str) -> list[str]:
    """Detect which crypto assets are mentioned in the text."""
    text = (title + " " + summary).lower()
    found = []
    for asset, keywords in ASSET_PATTERNS.items():
        if any(kw in text for kw in keywords):
            found.append(asset)
    return found


def _detect_categories(title: str, summary: str) -> list[str]:
    """Detect news categories from text."""
    text = (title + " " + summary).lower()
    found = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            found.append(category)
    return found


def _rate_impact(title: str, summary: str, assets: list[str]) -> str:
    """Rate the impact of the news (deterministic, no LLM needed)."""
    text = (title + " " + summary).lower()
    impact_score = 0

    # High-impact keywords
    for kw in HIGH_IMPACT_KEYWORDS:
        if kw in text:
            impact_score += 1

    # Multiple assets affected = higher impact
    if len(assets) >= 3:
        impact_score += 2
    elif len(assets) >= 1:
        impact_score += 1

    # Breaking/urgent indicators
    if any(word in text for word in ["breaking", "urgent", "just in", "alert"]):
        impact_score += 3

    if impact_score >= 5:
        return "critical"
    elif impact_score >= 3:
        return "high"
    elif impact_score >= 1:
        return "medium"
    return "low"


def _rate_sentiment(title: str, summary: str) -> str:
    """Rate sentiment (deterministic)."""
    text = (title + " " + summary).lower()
    bullish_words = ["surge", "rally", "bullish", "approval", "adopt", "gain", "rise", "up", "positive", "breakout"]
    bearish_words = ["crash", "dump", "bearish", "ban", "reject", "lawsuit", "hack", "exploit", "fall", "drop", "collapse", "stolen"]

    bull_count = sum(1 for w in bullish_words if w in text)
    bear_count = sum(1 for w in bearish_words if w in text)

    if bull_count > bear_count:
        return "bullish"
    elif bear_count > bull_count:
        return "bearish"
    return "neutral"


def _extract_image(item: ElementTree.Element) -> str | None:
    """Try to extract image URL from RSS item."""
    # Try media:content, media:thumbnail, enclosures
    ns = {"media": "http://search.yahoo.com/mrss/"}
    for tag in ["media:content", "media:thumbnail"]:
        elem = item.find(tag, ns)
        if elem is not None and "url" in elem.attrib:
            return elem.attrib["url"]

    # Try enclosure
    enc = item.find("enclosure")
    if enc is not None and "url" in enc.attrib:
        url = enc.attrib["url"]
        if "image" in enc.attrib.get("type", ""):
            return url

    # Try content:encoded for img tags
    ns2 = {"content": "http://purl.org/rss/1.0/modules/content/"}
    content = item.find("content:encoded", ns2)
    if content is not None and content.text:
        img_match = re.search(r'<img[^>]+src="([^"]+)"', content.text)
        if img_match:
            return img_match.group(1)

    return None


def _parse_date(date_str: str) -> datetime:
    """Parse RFC 2822 date string to datetime."""
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except Exception:
        return datetime.now(UTC)


def _is_already_stored(session: Session, url: str) -> bool:
    """Check if a news article with this URL is already stored."""
    stmt = select(IntelligenceNews.id).where(IntelligenceNews.url == url).limit(1)
    return session.execute(stmt).first() is not None


def fetch_and_store_news(
    *,
    max_per_feed: int = 10,
    min_impact: str = "medium",
    ai_provider: Any | None = None,
) -> int:
    """Fetch news from all RSS feeds and store important ones.

    Args:
        max_per_feed: Max articles to check per feed
        min_impact: Minimum impact level to store (low, medium, high, critical)
        ai_provider: Optional AI provider for summary/analysis generation

    Returns:
        Number of new articles stored
    """
    impact_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    min_impact_score = impact_order.get(min_impact, 1)

    session = SessionLocal()
    stored_count = 0

    try:
        for feed_info in RSS_FEEDS:
            feed_name = feed_info["name"]
            feed_url = feed_info["url"]

            try:
                resp = httpx.get(feed_url, timeout=15.0, follow_redirects=True)
                resp.raise_for_status()
                root = ElementTree.fromstring(resp.content)
            except Exception as exc:
                logger.warning("[NewsFetcher] Failed to fetch %s: %s", feed_name, exc)
                continue

            # RSS 2.0: channel/item, Atom: feed/entry
            items = root.findall(".//item")
            if not items:
                items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

            count = 0
            for item in items[:max_per_feed]:
                title_elem = item.find("title")
                link_elem = item.find("link")
                desc_elem = item.find("description")
                date_elem = item.find("pubDate")

                if title_elem is None or not title_elem.text:
                    continue

                title = title_elem.text.strip()

                # Get URL
                url = ""
                if link_elem is not None and link_elem.text:
                    url = link_elem.text.strip()
                else:
                    # Atom format
                    link_attr = item.find("{http://www.w3.org/2005/Atom}link")
                    if link_attr is not None:
                        url = link_attr.attrib.get("href", "")

                if not url:
                    continue

                # Skip if already stored
                if _is_already_stored(session, url):
                    continue

                # Get description/summary
                summary = ""
                if desc_elem is not None and desc_elem.text:
                    # Strip HTML tags
                    summary = re.sub(r'<[^>]+>', '', desc_elem.text).strip()[:500]

                # Get publish date
                published_at = datetime.now(UTC)
                if date_elem is not None and date_elem.text:
                    published_at = _parse_date(date_elem.text)

                # Skip news older than 48h
                if published_at < datetime.now(UTC) - timedelta(hours=48):
                    continue

                # Analyze
                assets = _detect_assets(title, summary)
                categories = _detect_categories(title, summary)
                impact = _rate_impact(title, summary, assets)
                sentiment = _rate_sentiment(title, summary)

                # Filter by minimum impact
                if impact_order.get(impact, 0) < min_impact_score:
                    continue

                # Extract image
                image_url = _extract_image(item)

                # Optional: AI analysis (only for high/critical impact)
                ai_analysis = None
                if ai_provider and impact in ("high", "critical"):
                    try:
                        prompt = (
                            f"Analyze this crypto news in 2-3 sentences. "
                            f"Title: {title}\nSummary: {summary[:200]}\n"
                            f"Focus on: market impact, affected assets, what to expect."
                        )
                        response = ai_provider.ask(prompt)
                        ai_analysis = response.text[:500] if response else None
                    except Exception as exc:
                        logger.debug("[NewsFetcher] AI analysis failed: %s", exc)

                # Store
                news = IntelligenceNews(
                    title=title[:500],
                    url=url[:1000],
                    source=feed_name,
                    image_url=image_url[:1000] if image_url else None,
                    summary=summary[:500] if summary else None,
                    impact=impact,
                    affected_assets={"assets": assets},
                    categories={"categories": categories},
                    sentiment=sentiment,
                    ai_analysis=ai_analysis,
                    published_at=published_at,
                )
                session.add(news)
                session.commit()
                session.refresh(news)
                stored_count += 1
                count += 1

                logger.info("[NewsFetcher] Stored: [%s] %s (%s)", impact, title[:60], feed_name)

            logger.info("[NewsFetcher] %s: %d new articles stored", feed_name, count)

    finally:
        session.close()

    logger.info("[NewsFetcher] Total new articles stored: %d", stored_count)
    return stored_count


def get_news(
    *,
    hours: int = 24,
    impact: str | None = None,
    asset: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query stored news articles."""
    session = SessionLocal()
    try:
        since = datetime.now(UTC) - timedelta(hours=hours)
        stmt = select(IntelligenceNews).where(IntelligenceNews.published_at > since)

        if impact:
            stmt = stmt.where(IntelligenceNews.impact == impact)
        if asset:
            # Filter by JSON array contains — SQLite json_each
            stmt = stmt.where(IntelligenceNews.affected_assets.contains(asset))

        stmt = stmt.order_by(
            # Critical first, then by date
            IntelligenceNews.impact.desc(),
            IntelligenceNews.published_at.desc(),
        ).limit(limit).offset(offset)

        results = list(session.execute(stmt).scalars().all())
        return [_news_to_dict(n) for n in results]
    finally:
        session.close()


def _news_to_dict(n: IntelligenceNews) -> dict[str, Any]:
    """Convert IntelligenceNews to dict for API response."""
    return {
        "id": n.id,
        "title": n.title,
        "url": n.url,
        "source": n.source,
        "image_url": n.image_url,
        "summary": n.summary,
        "impact": n.impact,
        "affected_assets": n.affected_assets.get("assets", []),
        "categories": n.categories.get("categories", []),
        "sentiment": n.sentiment,
        "ai_analysis": n.ai_analysis,
        "published_at": n.published_at.isoformat() if n.published_at else "",
        "fetched_at": n.fetched_at.isoformat() if n.fetched_at else "",
    }
