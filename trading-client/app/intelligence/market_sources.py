"""Market sources — categorized URLs for news, analysis, and data fetching.

These sources are used by the news fetcher and analysis agents to gather
market intelligence. Each category serves a different purpose in the
intelligence pipeline.

Sources are stored as structured data so agents can programmatically
access them by category, priority, or asset type.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MarketSource:
    """A single market data source."""
    url: str
    name: str
    category: str
    asset_type: str  # crypto, stocks, macro, general
    priority: int = 5  # 1=highest, 10=lowest
    has_rss: bool = False
    rss_url: str | None = None
    requires_auth: bool = False
    notes: str = ""


# All market sources organized by category
MARKET_SOURCES: list[MarketSource] = [
    # === Market Data / Gráficas ===
    MarketSource("https://www.tradingview.com", "TradingView", "market_data", "general", 3, notes="Charts, screener, ideas"),
    MarketSource("https://finance.yahoo.com", "Yahoo Finance", "market_data", "general", 2, notes="Free quotes, financials"),
    MarketSource("https://www.marketwatch.com", "MarketWatch", "market_data", "general", 4, notes="Market news, quotes"),

    # === Institucional ===
    MarketSource("https://www.bloomberg.com", "Bloomberg", "institutional", "general", 1, requires_auth=True, notes="Premium institutional news"),
    MarketSource("https://www.reuters.com/markets", "Reuters Markets", "institutional", "general", 2, notes="Global market news"),
    MarketSource("https://www.ft.com", "Financial Times", "institutional", "general", 1, requires_auth=True, notes="Premium financial news"),
    MarketSource("https://www.wsj.com/markets", "WSJ Markets", "institutional", "general", 1, requires_auth=True, notes="Wall Street Journal markets"),

    # === Fundamental Analysis ===
    MarketSource("https://www.morningstar.com", "Morningstar", "fundamental", "stocks", 3, notes="Stock fundamentals, ratings"),
    MarketSource("https://seekingalpha.com", "Seeking Alpha", "fundamental", "stocks", 3, notes="Analysis articles, earnings"),
    MarketSource("https://stockanalysis.com", "Stock Analysis", "fundamental", "stocks", 4, notes="Free stock data, financials"),
    MarketSource("https://www.macrotrends.net", "MacroTrends", "fundamental", "stocks", 4, notes="Historical charts, ratios"),

    # === Screeners ===
    MarketSource("https://finviz.com", "Finviz", "screener", "stocks", 3, notes="Stock screener, heat maps"),
    MarketSource("https://www.koyfin.com", "Koyfin", "screener", "general", 4, notes="Free Bloomberg alternative"),
    MarketSource("https://www.tradingview.com/screener/", "TradingView Screener", "screener", "general", 4, notes="Universal screener"),

    # === Crypto ===
    MarketSource("https://coinmarketcap.com", "CoinMarketCap", "crypto_data", "crypto", 2, notes="Prices, market cap, rankings"),
    MarketSource("https://www.coingecko.com", "CoinGecko", "crypto_data", "crypto", 2, notes="Prices, DeFi, NFT data"),
    MarketSource("https://defillama.com", "DefiLlama", "crypto_data", "crypto", 3, notes="TVL, DeFi protocols"),
    MarketSource("https://cryptoquant.com", "CryptoQuant", "crypto_onchain", "crypto", 2, requires_auth=True, notes="On-chain analytics"),
    MarketSource("https://glassnode.com", "Glassnode", "crypto_onchain", "crypto", 2, requires_auth=True, notes="On-chain metrics"),
    MarketSource("https://arkhamintelligence.com", "Arkham", "crypto_onchain", "crypto", 3, notes="Wallet tracking, entity labels"),
    MarketSource("https://app.intotheblock.com", "IntoTheBlock", "crypto_onchain", "crypto", 3, notes="On-chain signals, stats"),

    # === Whale Tracking ===
    MarketSource("https://whale-alert.io", "Whale Alert", "whale_tracking", "crypto", 2, notes="Large transaction alerts"),
    MarketSource("https://lookonchain.com", "Lookonchain", "whale_tracking", "crypto", 3, notes="On-chain whale tracking"),

    # === Derivados ===
    MarketSource("https://www.coinglass.com", "Coinglass", "derivatives", "crypto", 3, notes="Funding rates, OI, liquidations"),

    # === Macroeconomía ===
    MarketSource("https://fred.stlouisfed.org", "FRED", "macro", "macro", 2, notes="Fed economic data"),
    MarketSource("https://tradingeconomics.com", "Trading Economics", "macro", "macro", 3, notes="Economic indicators, calendar"),
    MarketSource("https://www.investing.com/economic-calendar/", "Investing Calendar", "macro", "macro", 3, notes="Economic events calendar"),
    MarketSource("https://www.macrosights.com", "MacroSights", "macro", "macro", 5, notes="Macro analysis"),

    # === Sentimiento ===
    MarketSource("https://alternative.me/crypto/fear-and-greed-index/", "Fear & Greed Index", "sentiment", "crypto", 2, notes="Crypto sentiment index"),
    MarketSource("https://app.santiment.net", "Santiment", "sentiment", "crypto", 3, requires_auth=True, notes="Social + on-chain metrics"),
    MarketSource("https://lunarcrush.com", "LunarCrush", "sentiment", "crypto", 4, notes="Social sentiment, altcoin rank"),

    # === SEC / Reportes ===
    MarketSource("https://www.sec.gov/edgar/search/", "SEC EDGAR", "regulatory", "stocks", 2, notes="SEC filings, 10-K, 10-Q"),
    MarketSource("https://companiesmarketcap.com", "Companies MarketCap", "regulatory", "general", 5, notes="Market cap rankings"),

    # === ETFs ===
    MarketSource("https://www.etf.com", "ETF.com", "etf", "general", 4, notes="ETF data, analysis"),
    MarketSource("https://etfdb.com", "ETF Database", "etf", "general", 4, notes="ETF screener, data"),

    # === Datos Profesionales ===
    MarketSource("https://www.factset.com", "FactSet", "professional", "general", 1, requires_auth=True, notes="Professional financial data"),
    MarketSource("https://www.lseg.com/en/ftse-russell/market-insights", "LSEG/FTSE Russell", "professional", "general", 3, notes="Index insights"),
    MarketSource("https://www.socratesplatform.com", "Socrates", "professional", "general", 5, requires_auth=True, notes="AI market analysis platform"),
]

# RSS feeds for news fetching (derived from sources that support RSS)
RSS_FEEDS_EXTENDED: list[dict[str, str]] = [
    # Crypto news RSS
    {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "category": "crypto", "priority": "1"},
    {"name": "CoinTelegraph", "url": "https://cointelegraph.com/rss", "category": "crypto", "priority": "1"},
    {"name": "CryptoSlate", "url": "https://cryptoslate.com/feed/", "category": "crypto", "priority": "2"},
    {"name": "The Block", "url": "https://www.theblock.co/rss.xml", "category": "crypto", "priority": "1"},
    {"name": "Decrypt", "url": "https://decrypt.co/feed", "category": "crypto", "priority": "2"},
    {"name": "Bitcoinist", "url": "https://bitcoinist.com/feed/", "category": "crypto", "priority": "3"},
    {"name": "NewsBTC", "url": "https://www.newsbtc.com/feed/", "category": "crypto", "priority": "3"},
    {"name": "CryptoNews", "url": "https://cryptonews.com/news/feed/", "category": "crypto", "priority": "2"},
    # General market news RSS
    {"name": "Reuters Markets", "url": "https://www.reuters.com/markets/rss", "category": "general", "priority": "1"},
    {"name": "MarketWatch", "url": "https://www.marketwatch.com/rss/topstories", "category": "general", "priority": "2"},
    {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex", "category": "general", "priority": "2"},
    {"name": "Seeking Alpha", "url": "https://seekingalpha.com/market_currents.xml", "category": "stocks", "priority": "2"},
    {"name": "Investing News", "url": "https://www.investing.com/rss/news.rss", "category": "general", "priority": "3"},
    # Macro
    {"name": "FRED News", "url": "https://fred.stlouisfed.org/rss", "category": "macro", "priority": "2"},
]

# Source categories for agent context
SOURCE_CATEGORIES: dict[str, str] = {
    "market_data": "Real-time prices, charts, and market data",
    "institutional": "Institutional-grade financial news and analysis",
    "fundamental": "Fundamental analysis tools for stocks",
    "screener": "Stock and asset screeners for filtering",
    "crypto_data": "Crypto market data, prices, and rankings",
    "crypto_onchain": "On-chain analytics and blockchain data",
    "whale_tracking": "Large transaction and whale movement tracking",
    "derivatives": "Futures, options, funding rates, and liquidations",
    "macro": "Macroeconomic indicators and economic calendar",
    "sentiment": "Market sentiment and social metrics",
    "regulatory": "SEC filings and regulatory documents",
    "etf": "ETF data and analysis",
    "professional": "Professional-grade financial data platforms",
}


def get_sources_by_category(category: str) -> list[MarketSource]:
    """Get all sources in a specific category."""
    return [s for s in MARKET_SOURCES if s.category == category]


def get_sources_by_asset_type(asset_type: str) -> list[MarketSource]:
    """Get all sources for a specific asset type (crypto, stocks, macro, general)."""
    return [s for s in MARKET_SOURCES if s.asset_type == asset_type or s.asset_type == "general"]


def get_sources_for_agent_context(
    *,
    asset: str | None = None,
    include_crypto: bool = True,
    include_stocks: bool = True,
    include_macro: bool = True,
) -> str:
    """Build a context string of relevant sources for an AI agent prompt.

    This lets the AI agent know which sources are available for analysis
    without hardcoding URLs in the prompt.
    """
    lines: list[str] = ["Available market data sources:"]
    
    categories_to_include: list[str] = []
    if include_crypto:
        categories_to_include.extend(["crypto_data", "crypto_onchain", "whale_tracking", "derivatives", "sentiment"])
    if include_stocks:
        categories_to_include.extend(["fundamental", "screener", "regulatory", "etf"])
    if include_macro:
        categories_to_include.extend(["macro", "institutional", "market_data"])

    for cat in categories_to_include:
        sources = get_sources_by_category(cat)
        if sources:
            desc = SOURCE_CATEGORIES.get(cat, cat)
            lines.append(f"\n  [{cat}] {desc}:")
            for s in sorted(sources, key=lambda x: x.priority):
                auth_tag = " (requires auth)" if s.requires_auth else ""
                lines.append(f"    - {s.name}: {s.url}{auth_tag} — {s.notes}")

    return "\n".join(lines)


def get_rss_feeds(
    *,
    category: str | None = None,
    min_priority: int = 3,
) -> list[dict[str, str]]:
    """Get RSS feeds for news fetching, optionally filtered by category.
    
    Priority: 1=highest (always fetch), 3=medium (fetch when time allows)
    """
    feeds = RSS_FEEDS_EXTENDED
    if category:
        feeds = [f for f in feeds if f["category"] == category]
    else:
        feeds = [f for f in feeds if int(f["priority"]) <= min_priority]
    return feeds
