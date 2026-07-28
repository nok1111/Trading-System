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


# ---------------------------------------------------------------------------
# Technical Analysis Endpoints
# ---------------------------------------------------------------------------

@router.get("/signals/technical")
def get_technical_signals(
    interval: str = "1h",
    symbols: str | None = None,
) -> list[dict]:
    """Get technical analysis signals for all DEFAULT_SYMBOLS or specified symbols.

    Query params:
        interval: 1m, 5m, 15m, 1h, 4h, 1d (default 1h)
        symbols: comma-separated list (default: from settings.DEFAULT_SYMBOLS)
    """
    from app.config import get_settings
    from app.services.technical_analysis import analyze_symbol

    settings = get_settings()
    symbol_list = (
        [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if symbols
        else settings.symbols_list
    )

    results: list[dict] = []
    for sym in symbol_list:
        try:
            analysis = analyze_symbol(sym, interval=interval)
            results.append(analysis.to_dict())
        except Exception as exc:
            logger.warning("Technical analysis failed for %s: %s", sym, exc)
            results.append({
                "symbol": sym,
                "interval": interval,
                "error": str(exc),
                "signal": "HOLD",
                "signal_reasons": [f"Analysis failed: {exc}"],
            })

    signal_order = {"STRONG_BUY": 0, "BUY": 1, "HOLD": 2, "SELL": 3, "STRONG_SELL": 4}
    results.sort(key=lambda x: signal_order.get(x.get("signal", "HOLD"), 2))
    return results


@router.get("/signals/technical/{symbol}")
def get_technical_signal(
    symbol: str,
    interval: str = "1h",
) -> dict:
    """Get detailed technical analysis for a single symbol."""
    from app.services.technical_analysis import analyze_symbol

    try:
        analysis = analyze_symbol(symbol, interval=interval)
        return analysis.to_dict()
    except Exception as exc:
        logger.warning("Technical analysis failed for %s: %s", symbol, exc)
        return {
            "symbol": symbol.upper(),
            "interval": interval,
            "error": str(exc),
            "signal": "HOLD",
            "signal_reasons": [f"Analysis failed: {exc}"],
        }


# ---------------------------------------------------------------------------
# Backtesting Endpoints
# ---------------------------------------------------------------------------

from pydantic import BaseModel as _BaseModel


class BacktestRequest(_BaseModel):
    symbol: str
    strategy: str = "trend_momentum"
    interval: str = "1h"
    limit: int = 500
    initial_cash: float = 10000.0


@router.post("/backtest/run")
def run_backtest_endpoint(req: BacktestRequest) -> dict:
    """Run a backtest and return results."""
    from app.services.backtest_service import run_backtest

    try:
        result = run_backtest(
            symbol=req.symbol,
            strategy=req.strategy,
            interval=req.interval,
            limit=req.limit,
            initial_cash=req.initial_cash,
        )
        return result.to_dict()
    except Exception as exc:
        logger.warning("Backtest failed: %s", exc)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Alerts & Notifications Endpoints
# ---------------------------------------------------------------------------

# In-memory price alerts store (simple, no DB needed)
_price_alerts: list[dict] = []
_alert_id_counter = 0


class PriceAlertRequest(_BaseModel):
    symbol: str
    condition: str  # "above" or "below"
    target_price: float
    note: str | None = None


@router.get("/alerts")
def get_alerts(limit: int = 20) -> list[dict]:
    """Get recent alerts — generated from price alerts and risk events."""
    alerts: list[dict] = []

    # Check price alerts that have been triggered
    for a in _price_alerts:
        if a.get("triggered"):
            alerts.append({
                "id": a["id"],
                "type": "price_alert",
                "symbol": a["symbol"],
                "message": f"{a['symbol']} {'subió por encima de' if a['condition'] == 'above' else 'bajó por debajo de'} ${a['target_price']:,.2f}",
                "severity": "info",
                "timestamp": a.get("triggered_at", a.get("created_at")),
            })

    # Add recent signals as alerts
    try:
        from app.services.technical_analysis import analyze_symbol
        from app.config import get_settings
        settings = get_settings()
        for sym in settings.symbols_list[:5]:
            try:
                ta = analyze_symbol(sym, interval="1h")
                if ta.signal in ("STRONG_BUY", "STRONG_SELL"):
                    alerts.append({
                        "id": f"sig_{sym}_{ta.timestamp}",
                        "type": "signal",
                        "symbol": sym,
                        "message": f"{sym}: señal {ta.signal} — {', '.join(ta.signal_reasons[:2])}",
                        "severity": "high" if ta.signal == "STRONG_SELL" else "medium",
                        "timestamp": ta.timestamp,
                    })
            except Exception:
                continue
    except Exception:
        pass

    alerts.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return alerts[:limit]


@router.get("/pending")
def get_pending_notifications(user_hash: str = "") -> list[dict]:
    """Get pending notifications for a user (simplified local version)."""
    # Return triggered price alerts that haven't been acknowledged
    return [
        {
            "id": a["id"],
            "type": "price_alert",
            "title": f"Alerta de precio: {a['symbol']}",
            "message": f"{a['symbol']} {'subió por encima de' if a['condition'] == 'above' else 'bajó por debajo de'} ${a['target_price']:,.2f}",
            "read": a.get("acknowledged", False),
            "timestamp": a.get("triggered_at", a.get("created_at")),
        }
        for a in _price_alerts
        if a.get("triggered") and not a.get("acknowledged")
    ]


@router.post("/pending/{alert_id}/read")
def mark_alert_read(alert_id: int) -> dict:
    """Mark a price alert notification as read."""
    for a in _price_alerts:
        if a["id"] == alert_id:
            a["acknowledged"] = True
            return {"status": "ok"}
    return {"status": "not_found"}


@router.post("/price-alerts")
def create_price_alert(req: PriceAlertRequest) -> dict:
    """Create a new price alert."""
    global _alert_id_counter
    _alert_id_counter += 1
    alert = {
        "id": _alert_id_counter,
        "symbol": req.symbol.upper(),
        "condition": req.condition,
        "target_price": req.target_price,
        "note": req.note,
        "triggered": False,
        "acknowledged": False,
        "created_at": datetime.now(UTC).isoformat(),
    }
    _price_alerts.append(alert)
    return {"status": "ok", "alert": alert}


@router.get("/price-alerts")
def list_price_alerts() -> list[dict]:
    """List all price alerts."""
    return list(_price_alerts)


@router.delete("/price-alerts/{alert_id}")
def delete_price_alert(alert_id: int) -> dict:
    """Delete a price alert."""
    global _price_alerts
    _price_alerts = [a for a in _price_alerts if a["id"] != alert_id]
    return {"status": "ok"}


@router.post("/price-alerts/check")
def check_price_alerts() -> dict:
    """Check all active price alerts against current prices and trigger if met."""
    if not _price_alerts:
        return {"status": "ok", "triggered": 0}

    # Fetch current prices
    try:
        resp = httpx.get("https://api.binance.com/api/v3/ticker/price", timeout=10)
        resp.raise_for_status()
        prices = {d["symbol"]: float(d["price"]) for d in resp.json()}
    except Exception as exc:
        logger.warning("Failed to fetch prices for alert check: %s", exc)
        return {"status": "error", "error": str(exc)}

    triggered_count = 0
    for alert in _price_alerts:
        if alert.get("triggered"):
            continue
        current = prices.get(alert["symbol"])
        if current is None:
            continue
        if alert["condition"] == "above" and current >= alert["target_price"]:
            alert["triggered"] = True
            alert["triggered_at"] = datetime.now(UTC).isoformat()
            alert["triggered_price"] = current
            triggered_count += 1
        elif alert["condition"] == "below" and current <= alert["target_price"]:
            alert["triggered"] = True
            alert["triggered_at"] = datetime.now(UTC).isoformat()
            alert["triggered_price"] = current
            triggered_count += 1

    return {"status": "ok", "triggered": triggered_count}


