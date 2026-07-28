"""Local intelligence endpoints — uses free public APIs, no AI Server needed.

Provides real data for:
- Fear & Greed Index (alternative.me)
- BTC/ETH Dominance (CoinGecko)
- Market Overview (CoinGecko + Binance)
- Whale Activity (Binance large trades)
- Macro Events (RSS feeds via news_fetcher)
- Daily Report (compiled from local data)
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])

# Simple in-memory cache
_cache: dict[str, tuple[Any, float]] = {}
_CACHE_TTL = 300  # 5 min default


def _cached(key: str) -> Any | None:
    entry = _cache.get(key)
    if entry and entry[1] > datetime.now(UTC).timestamp():
        return entry[0]
    return None


def _set_cache(key: str, data: Any, ttl: int = _CACHE_TTL) -> None:
    _cache[key] = (data, datetime.now(UTC).timestamp() + ttl)


@router.get("/fear-greed")
def get_fear_greed() -> dict:
    """Fear & Greed Index from alternative.me (free, no auth)."""
    cached = _cached("fear_greed")
    if cached:
        return cached
    try:
        resp = httpx.get("https://api.alternative.me/fng/?limit=30", timeout=10)
        resp.raise_for_status()
        raw = resp.json().get("data", [])
        if not raw:
            return {"value": 50, "classification": "Neutral", "previousValue": 50, "previousClassification": "Neutral", "history": [], "timestamp": datetime.now(UTC).isoformat()}

        current = raw[0]
        previous = raw[1] if len(raw) > 1 else raw[0]
        history = [
            {"timestamp": str(int(entry["timestamp"])), "value": int(entry["value"])}
            for entry in raw[:30]
        ]
        result = {
            "value": int(current["value"]),
            "classification": current.get("value_classification", "Neutral"),
            "previousValue": int(previous["value"]),
            "previousClassification": previous.get("value_classification", "Neutral"),
            "history": history,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        _set_cache("fear_greed", result, 300)
        return result
    except Exception as exc:
        logger.warning("Fear&Greed fetch failed: %s", exc)
        return {"value": 50, "classification": "Neutral", "previousValue": 50, "previousClassification": "Neutral", "history": [], "timestamp": datetime.now(UTC).isoformat()}


@router.get("/dominance")
def get_dominance() -> dict:
    """BTC/ETH dominance from CoinGecko (free, no auth)."""
    cached = _cached("dominance")
    if cached:
        return cached
    try:
        resp = httpx.get("https://api.coingecko.com/api/v3/global", timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        market_cap_pct = data.get("market_cap_percentage", {})
        btc_dom = market_cap_pct.get("btc", 0)
        eth_dom = market_cap_pct.get("eth", 0)
        others = max(100 - btc_dom - eth_dom, 0)
        total_mcap = data.get("total_market_cap", {}).get("usd", 0)
        total_vol = data.get("total_volume", {}).get("usd", 0)
        mcap_change_24h = data.get("market_cap_change_percentage_24h_usd", 0)

        result = {
            "btc": round(btc_dom, 2),
            "eth": round(eth_dom, 2),
            "others": round(others, 2),
            "totalMarketCap": total_mcap,
            "totalVolume": total_vol,
            "marketCapChange24h": round(mcap_change_24h, 2),
            "history": [],
            "timestamp": datetime.now(UTC).isoformat(),
        }
        _set_cache("dominance", result, 300)
        return result
    except Exception as exc:
        logger.warning("Dominance fetch failed: %s", exc)
        return {"btc": 52, "eth": 17, "others": 31, "history": [], "timestamp": datetime.now(UTC).isoformat()}


@router.get("/market-overview")
def get_market_overview() -> dict:
    """Market overview: regime, risk level, summary from CoinGecko + Binance."""
    cached = _cached("market_overview")
    if cached:
        return cached
    try:
        # Get global data
        resp = httpx.get("https://api.coingecko.com/api/v3/global", timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        mcap_change = data.get("market_cap_change_percentage_24h_usd", 0)
        total_mcap = data.get("total_market_cap", {}).get("usd", 0)

        # Get BTC 24h ticker from Binance
        btc_resp = httpx.get(
            "https://api.binance.com/api/v3/ticker/24hr",
            params={"symbol": "BTCUSDT"},
            timeout=10,
        )
        btc_data = btc_resp.json() if btc_resp.status_code == 200 else {}
        btc_price = float(btc_data.get("lastPrice", 0))
        btc_change = float(btc_data.get("priceChangePercent", 0))

        # Determine regime
        if mcap_change > 3 and btc_change > 2:
            regime = "Risk-On"
            risk_level = "low"
            risk_on = "risk_on"
        elif mcap_change < -3 and btc_change < -2:
            regime = "Risk-Off"
            risk_level = "high"
            risk_on = "risk_off"
        elif mcap_change < -1:
            regime = "Cautious"
            risk_level = "medium"
            risk_on = "risk_off"
        else:
            regime = "Neutral"
            risk_level = "medium"
            risk_on = "risk_on"

        summary = f"Market cap {'up' if mcap_change >= 0 else 'down'} {abs(mcap_change):.1f}% (24h). BTC ${btc_price:,.0f} ({btc_change:+.1f}%). Regime: {regime}."

        result = {
            "regime": regime,
            "riskLevel": risk_level,
            "riskOnOff": risk_on,
            "summary": summary,
            "totalMarketCap": total_mcap,
            "btcPrice": btc_price,
            "btcChange24h": btc_change,
            "marketCapChange24h": round(mcap_change, 2),
            "timestamp": datetime.now(UTC).isoformat(),
        }
        _set_cache("market_overview", result, 300)
        return result
    except Exception as exc:
        logger.warning("Market overview fetch failed: %s", exc)
        return {"regime": "Neutral", "riskLevel": "medium", "riskOnOff": "risk_on", "summary": "Data unavailable", "timestamp": datetime.now(UTC).isoformat()}


@router.get("/whale-activity")
def get_whale_activity(limit: int = 20) -> list[dict]:
    """Whale activity: large trades from Binance aggTrades (free, no auth)."""
    cache_key = f"whale_{limit}"
    cached = _cached(cache_key)
    if cached:
        return cached
    try:
        # Fetch large BTC trades from Binance aggTrades
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        activities: list[dict] = []

        for sym in symbols:
            try:
                resp = httpx.get(
                    f"https://api.binance.com/api/v3/aggTrades",
                    params={"symbol": sym, "limit": 100},
                    timeout=10,
                )
                if resp.status_code != 200:
                    continue
                trades = resp.json()
                # Filter for large trades (whale threshold per symbol)
                thresholds = {"BTCUSDT": 100000, "ETHUSDT": 50000, "SOLUSDT": 20000}
                threshold = thresholds.get(sym, 50000)

                for t in trades:
                    price = float(t.get("p", 0))
                    qty = float(t.get("q", 0))
                    value_usd = price * qty
                    if value_usd < threshold:
                        continue
                    is_buyer_maker = t.get("m", False)
                    activities.append({
                        "id": f"{sym}_{t.get('a', '')}",
                        "asset": sym.replace("USDT", ""),
                        "amount": qty,
                        "amountUsd": round(value_usd, 2),
                        "direction": "inflow" if not is_buyer_maker else "outflow",
                        "fromAddress": "Binance",
                        "toAddress": "Binance",
                        "timestamp": datetime.fromtimestamp(
                            t.get("T", 0) / 1000, tz=UTC
                        ).isoformat(),
                        "exchange": "Binance",
                    })
            except Exception:
                continue

        # Sort by USD value descending and take top N
        activities.sort(key=lambda x: x["amountUsd"], reverse=True)
        result = activities[:limit]
        _set_cache(cache_key, result, 120)
        return result
    except Exception as exc:
        logger.warning("Whale activity fetch failed: %s", exc)
        return []


@router.get("/macro-events")
def get_macro_events() -> list[dict]:
    """Macro events calendar — fetches from investing.com RSS / forex factory."""
    cached = _cached("macro_events")
    if cached:
        return cached
    try:
        # Try Forex Factory calendar RSS (free XML feed)
        resp = httpx.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", timeout=10)
        resp.raise_for_status()
        events = resp.json()

        result = []
        for ev in events[:30]:
            impact = ev.get("impact", "Low").lower()
            if impact not in ("high", "medium", "low"):
                impact = "low"
            result.append({
                "id": f"macro_{ev.get('title', '')[:20]}_{ev.get('date', '')}",
                "event": ev.get("title", ""),
                "date": ev.get("date", ""),
                "country": ev.get("country", ""),
                "impact": impact,
                "actual": ev.get("actual") or None,
                "forecast": ev.get("forecast") or None,
                "previous": ev.get("previous") or None,
            })
        _set_cache("macro_events", result, 600)
        return result
    except Exception as exc:
        logger.warning("Macro events fetch failed: %s", exc)
        return []


@router.get("/daily-report")
def get_daily_report() -> dict:
    """Daily report compiled from local data: positions, PnL, news, fear&greed."""
    cached = _cached("daily_report")
    if cached:
        return cached
    try:
        today = datetime.now(UTC).strftime("%Y-%m-%d")

        # Get Fear & Greed
        fg = get_fear_greed()
        fg_value = fg.get("value", 50)
        fg_class = fg.get("classification", "Neutral")

        # Get BTC price from Binance
        btc_resp = httpx.get(
            "https://api.binance.com/api/v3/ticker/24hr",
            params={"symbol": "BTCUSDT"},
            timeout=10,
        )
        btc_data = btc_resp.json() if btc_resp.status_code == 200 else {}
        btc_price = float(btc_data.get("lastPrice", 0))
        btc_change = float(btc_data.get("priceChangePercent", 0))

        # Get dominance
        dom = get_dominance()
        btc_dom = dom.get("btc", 0)

        # Get news from local DB
        news_summary = "No news available"
        try:
            from app.intelligence.news_fetcher import get_news
            news_items = get_news(limit=5)
            if news_items:
                titles = [n.title for n in news_items[:3]]
                news_summary = "; ".join(titles)
        except Exception:
            pass

        # Get positions from local DB
        portfolio_summary = "No positions"
        try:
            from app.database.session import SessionLocal
            from app.database.models.position import Position
            db = SessionLocal()
            try:
                positions = db.query(Position).filter(Position.status == "open").all()
                if positions:
                    total_pnl = sum(float(p.unrealized_pnl or 0) for p in positions)
                    portfolio_summary = f"{len(positions)} open positions, PnL: ${total_pnl:.2f}"
            finally:
                db.close()
        except Exception:
            pass

        regime = "Neutral"
        if btc_change > 2:
            regime = "Bullish"
        elif btc_change < -2:
            regime = "Bearish"

        result = {
            "date": today,
            "summary": f"BTC ${btc_price:,.0f} ({btc_change:+.1f}%). Fear&Greed: {fg_value} ({fg_class}). BTC Dominance: {btc_dom:.1f}%. Regime: {regime}.",
            "sections": {
                "marketOverview": f"Bitcoin trading at ${btc_price:,.0f}, {'up' if btc_change >= 0 else 'down'} {abs(btc_change):.1f}% in 24h. Market sentiment: {fg_class} ({fg_value}/100). BTC dominance at {btc_dom:.1f}%.",
                "keyEvents": news_summary,
                "performance": portfolio_summary,
                "outlook": f"Market regime appears {regime.lower()}. {'Risk appetite increasing' if btc_change > 0 else 'Caution advised'}. Monitor for {'continuation' if btc_change > 0 else 'stabilization'}.",
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }
        _set_cache("daily_report", result, 300)
        return result
    except Exception as exc:
        logger.warning("Daily report fetch failed: %s", exc)
        return {
            "date": datetime.now(UTC).strftime("%Y-%m-%d"),
            "summary": "Report unavailable",
            "sections": {
                "marketOverview": "",
                "keyEvents": "",
                "performance": "",
                "outlook": "",
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }
