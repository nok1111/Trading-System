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
                positions = db.query(Position).filter(Position.status == "open", Position.user_id == 0).all()
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


# ---------------------------------------------------------------------------
# Risk Management Endpoints
# ---------------------------------------------------------------------------

# In-memory risk config (persisted via settings in production)
_risk_config: dict = {
    "trailing_stop_pct": 2.0,
    "hard_stop_loss_pct": 3.0,
    "take_profit_pct": 6.0,
    "max_position_size_pct": 10.0,
    "max_open_positions": 5,
    "daily_loss_limit_pct": 5.0,
    "circuit_breaker_enabled": True,
}


class RiskConfigRequest(_BaseModel):
    trailing_stop_pct: float | None = None
    hard_stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    max_position_size_pct: float | None = None
    max_open_positions: int | None = None
    daily_loss_limit_pct: float | None = None
    circuit_breaker_enabled: bool | None = None


@router.get("/risk/config")
def get_risk_config() -> dict:
    """Get current risk management configuration."""
    return dict(_risk_config)


@router.post("/risk/config")
def update_risk_config(req: RiskConfigRequest) -> dict:
    """Update risk management configuration."""
    changes = []
    for field, value in req.model_dump(exclude_none=True).items():
        old = _risk_config.get(field)
        _risk_config[field] = value
        changes.append(f"{field}: {old} -> {value}")
    logger.info("Risk config updated: %s", "; ".join(changes))
    return {"status": "ok", "config": dict(_risk_config)}


@router.get("/risk/status")
def get_risk_status() -> dict:
    """Get current risk status — open positions, exposure, circuit breaker state."""
    try:
        from app.database.session import SessionLocal
        from app.database.models.position import Position
        db = SessionLocal()
        try:
            positions = db.query(Position).filter(Position.status == "open", Position.user_id == 0).all()
            total_exposure = sum(
                abs(float(p.quantity or 0)) * float(p.current_price or p.entry_price or 0)
                for p in positions
            )
            total_pnl = sum(float(p.unrealized_pnl or 0) for p in positions)

            # Check circuit breaker conditions
            daily_loss = abs(min(total_pnl, 0))
            daily_loss_pct = (daily_loss / total_exposure * 100) if total_exposure > 0 else 0
            circuit_triggered = (
                _risk_config.get("circuit_breaker_enabled", True)
                and daily_loss_pct >= _risk_config.get("daily_loss_limit_pct", 5.0)
            )

            return {
                "open_positions": len(positions),
                "max_open_positions": _risk_config.get("max_open_positions", 5),
                "total_exposure": round(total_exposure, 2),
                "total_unrealized_pnl": round(total_pnl, 2),
                "daily_loss_pct": round(daily_loss_pct, 2),
                "daily_loss_limit_pct": _risk_config.get("daily_loss_limit_pct", 5.0),
                "circuit_breaker_enabled": _risk_config.get("circuit_breaker_enabled", True),
                "circuit_breaker_triggered": circuit_triggered,
                "trailing_stop_pct": _risk_config.get("trailing_stop_pct", 2.0),
                "hard_stop_loss_pct": _risk_config.get("hard_stop_loss_pct", 3.0),
                "take_profit_pct": _risk_config.get("take_profit_pct", 6.0),
                "positions": [
                    {
                        "symbol": p.symbol,
                        "quantity": float(p.quantity or 0),
                        "entry_price": float(p.entry_price or 0),
                        "current_price": float(p.current_price or 0),
                        "unrealized_pnl": float(p.unrealized_pnl or 0),
                        "unrealized_pnl_pct": (
                            round(float(p.unrealized_pnl or 0) / (float(p.entry_price or 1) * float(p.quantity or 1)) * 100, 2)
                            if p.entry_price and p.quantity else 0
                        ),
                    }
                    for p in positions
                ],
            }
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Risk status fetch failed: %s", exc)
        return {
            "open_positions": 0,
            "max_open_positions": _risk_config.get("max_open_positions", 5),
            "total_exposure": 0,
            "total_unrealized_pnl": 0,
            "circuit_breaker_enabled": _risk_config.get("circuit_breaker_enabled", True),
            "circuit_breaker_triggered": False,
            "positions": [],
            "error": str(exc),
        }


def _fetch_remote_signals(settings: Any, limit: int) -> list[dict]:
    """Fetch active signals from the AI Server and convert to frontend format.

    No token cost — the AI Server just reads from its database.
    """
    import httpx

    url = f"{settings.REMOTE_AI_URL.rstrip('/')}/v1/intelligence/signals"
    headers: dict[str, str] = {}
    if settings.REMOTE_AI_TOKEN:
        headers["Authorization"] = f"Bearer {settings.REMOTE_AI_TOKEN}"

    resp = httpx.get(url, headers=headers, params={"limit": limit}, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    raw_signals = data.get("signals", [])

    result = []
    for s in raw_signals:
        asset = s.get("asset", "").upper().replace("USDT", "").replace("USDC", "")
        decision = s.get("decision", s.get("signal_type", "HOLD"))
        if decision not in ("BUY", "SELL", "HOLD"):
            decision = "HOLD"
        confidence = int(float(s.get("confidence", 0)) * 100)
        consensus = s.get("consensus_data", {})
        entry = consensus.get("entryZone", {})
        targets_raw = consensus.get("targets", [])
        invalidation = consensus.get("invalidation", {})

        targets = []
        for t in targets_raw:
            if isinstance(t, dict) and t.get("price"):
                targets.append({"price": float(t["price"]), "probability": int(float(t.get("probability", 0.5)) * 100)})
            elif isinstance(t, (int, float)):
                targets.append({"price": float(t), "probability": confidence})

        entry_min = float(entry.get("min", 0)) if isinstance(entry, dict) else 0
        entry_max = float(entry.get("max", 0)) if isinstance(entry, dict) else 0

        result.append({
            "id": f"ai-sig-{s.get('id', '')}",
            "asset": asset,
            "decision": decision,
            "confidence": confidence,
            "riskLevel": consensus.get("riskLevel", "medium"),
            "entryZone": {"min": entry_min, "max": entry_max},
            "targets": targets,
            "invalidation": {"type": invalidation.get("type", "none"), "value": float(invalidation.get("value", 0))} if isinstance(invalidation, dict) else {"type": "none", "value": 0},
            "agentVotes": [],
            "mainReasons": s.get("main_reasons", consensus.get("mainReasons", [])),
            "mainRisks": s.get("main_risks", consensus.get("mainRisks", [])),
            "validFrom": s.get("timestamp", ""),
            "expiresAt": s.get("expires_at"),
            "requiresConfirmation": False,
            "status": "ACTIVE",
            "timestamp": s.get("timestamp", ""),
        })

    return result


@router.get("/signals")
def get_active_signals(limit: int = 10) -> list[dict]:
    """Get active signals for the dashboard 'Señales activas' card.

    When USE_INTELLIGENCE_API=True, fetches global signals from the AI Server
    (no extra token cost — just a DB read on the AI Server side).
    Otherwise, reads from the local Signal table (status='active').
    """
    cached = _cached(f"signals_{limit}")
    if cached:
        return cached

    # ── Intelligence Platform mode: fetch from AI Server ──
    try:
        from app.config import get_settings
        settings = get_settings()
        if settings.USE_INTELLIGENCE_API and settings.REMOTE_AI_URL:
            remote_signals = _fetch_remote_signals(settings, limit)
            if remote_signals:
                _set_cache(f"signals_{limit}", remote_signals, 60)
                return remote_signals
            # If remote returns empty, fall through to local DB
    except Exception as exc:
        logger.warning("Remote signals fetch failed, falling back to local: %s", exc)

    # ── Local mode: read from local Signal table ──
    try:
        from app.database.session import SessionLocal
        from app.database.models.signal import Signal as SignalModel

        db = SessionLocal()
        try:
            signals = db.query(SignalModel).filter(
                SignalModel.status == "active"
            ).order_by(SignalModel.timestamp.desc()).limit(limit).all()

            result = []
            for s in signals:
                asset = s.symbol.upper().replace("USDT", "").replace("USDC", "")
                decision = s.signal_type if s.signal_type in ("BUY", "SELL") else "HOLD"
                confidence = int(float(s.confidence) * 100) if s.confidence else 50
                entry_price = float(s.entry_price) if s.entry_price else 0
                sl = float(s.suggested_stop_loss) if s.suggested_stop_loss else None
                tp = float(s.suggested_take_profit) if s.suggested_take_profit else None

                targets = []
                if tp:
                    targets.append({"price": tp, "probability": confidence})
                invalidation = {"type": "stop_loss", "value": sl} if sl else {"type": "none", "value": 0}

                result.append({
                    "id": f"sig-{s.id}",
                    "asset": asset,
                    "decision": decision,
                    "confidence": confidence,
                    "riskLevel": "medium",
                    "entryZone": {"min": entry_price * 0.99, "max": entry_price * 1.01},
                    "targets": targets,
                    "invalidation": invalidation,
                    "agentVotes": [],
                    "mainReasons": [s.explanation] if s.explanation else [],
                    "mainRisks": [],
                    "validFrom": s.timestamp.isoformat() if s.timestamp else "",
                    "expiresAt": None,
                    "requiresConfirmation": False,
                    "status": "ACTIVE",
                    "timestamp": s.timestamp.isoformat() if s.timestamp else "",
                })
            _set_cache(f"signals_{limit}", result, 60)
            return result
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Signals fetch failed: %s", exc)
        return []


@router.get("/reports/{asset}")
def get_reports(asset: str, limit: int = 20) -> list[dict]:
    """Get AI agent recommendations and executed trades for an asset.

    Returns:
    - AI recommendations saved when auto_trade=false (status=pending)
    - Executed trades from the Trade table (paper and live)
    """
    cached = _cached(f"reports_{asset}_{limit}")
    if cached:
        return cached

    result: list[dict] = []
    asset_upper = asset.upper().strip()

    # 1. AI Agent recommendations from DB
    try:
        from app.database.session import SessionLocal
        from app.database.models.ai_recommendation import AIRecommendation

        db = SessionLocal()
        try:
            recs = db.query(AIRecommendation).filter(
                AIRecommendation.asset == asset_upper
            ).order_by(AIRecommendation.timestamp.desc()).limit(limit).all()

            for r in recs:
                action_label = "Compra recomendada" if r.action_type == "BUY" else "Venta recomendada" if r.action_type == "SELL" else "Mantener"
                result.append({
                    "id": f"rec-{r.id}",
                    "date": r.timestamp.strftime("%Y-%m-%d %H:%M") if r.timestamp else "",
                    "type": "daily",
                    "asset": r.asset,
                    "summary": f"{action_label} — {r.reason or 'Sin razón especificada'}",
                    "sections": {
                        "marketOverview": f"Decisión del mercado: {r.market_decision or 'N/A'}",
                        "keyEvents": f"Recomendación personal: {r.personal_recommendation or 'N/A'} (confianza: {float(r.confidence):.0%})",
                        "performance": f"Stop loss: {r.stop_loss_pct or 'N/A'}% | Take profit: {r.take_profit_pct or 'N/A'}%",
                        "outlook": r.reason or "",
                    },
                    "action_type": r.action_type,
                    "confidence": float(r.confidence),
                    "status": r.status,
                    "trading_mode": r.trading_mode,
                    "broker_name": r.broker_name,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else "",
                })
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Reports fetch failed: %s", exc)

    # 2. Executed trades from Trade table
    try:
        from app.database.session import SessionLocal
        from app.database.models.trade import Trade
        from app.database.models.order import Order
        from app.config import get_settings

        settings = get_settings()
        symbol = asset_upper + "USDT"

        db = SessionLocal()
        try:
            trades = db.query(Trade).filter(
                Trade.symbol == symbol
            ).order_by(Trade.timestamp.desc()).limit(limit).all()

            for t in trades:
                # Determine trading mode from linked order's broker_order_id
                trading_mode = "paper"
                broker_name = None
                if t.order_id:
                    order = db.query(Order).filter(Order.id == t.order_id).first()
                    if order and order.broker_order_id:
                        if not order.broker_order_id.startswith("MOCK-"):
                            trading_mode = "live"
                            broker_name = settings.BROKER_PROVIDER

                side_label = "Compra ejecutada" if t.side.upper() == "BUY" else "Venta ejecutada"
                result.append({
                    "id": f"trade-{t.id}",
                    "date": t.timestamp.strftime("%Y-%m-%d %H:%M") if t.timestamp else "",
                    "type": "daily",
                    "asset": asset_upper,
                    "summary": f"{side_label} — {float(t.quantity):.6f} @ ${float(t.price):,.2f}" + (f" (PnL: ${float(t.realized_pnl):,.2f})" if float(t.realized_pnl) != 0 else ""),
                    "sections": {
                        "marketOverview": f"Cantidad: {float(t.quantity):.6f}",
                        "keyEvents": f"Precio: ${float(t.price):,.2f}",
                        "performance": f"Comisión: ${float(t.commission):,.2f}" + (f" | PnL realizado: ${float(t.realized_pnl):,.2f}" if float(t.realized_pnl) != 0 else ""),
                        "outlook": t.strategy_name or "",
                    },
                    "action_type": t.side.upper(),
                    "confidence": None,
                    "status": "executed",
                    "trading_mode": trading_mode,
                    "broker_name": broker_name,
                    "timestamp": t.timestamp.isoformat() if t.timestamp else "",
                })
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Trades fetch for reports failed: %s", exc)

    # 3. Sort by timestamp descending
    result.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    # 4. If still empty, include the daily report as fallback
    if not result:
        try:
            daily = get_daily_report()
            result.append({
                "id": f"daily-{asset}",
                "date": daily.get("date", ""),
                "type": "daily",
                "asset": asset_upper,
                "summary": daily.get("summary", "Sin datos"),
                "sections": daily.get("sections", {
                    "marketOverview": "",
                    "keyEvents": "",
                    "performance": "",
                    "outlook": "",
                }),
                "trading_mode": None,
                "broker_name": None,
            })
        except Exception:
            pass

    _set_cache(f"reports_{asset}_{limit}", result, 60)
    return result


@router.post("/reports/{rec_id}/accept")
def accept_recommendation(rec_id: int) -> dict:
    """Accept an AI recommendation and execute a simulated buy (paper mode).

    Creates a Position and Trade in the DB with strategy_name='AI-Recommendation'.
    Uses real live price from Binance for the entry.
    """
    from app.database.session import SessionLocal
    from app.database.models.ai_recommendation import AIRecommendation
    from app.database.models.position import Position
    from app.database.models.trade import Trade
    from decimal import Decimal as Dec
    import httpx as _httpx

    db = SessionLocal()
    try:
        rec = db.query(AIRecommendation).filter(AIRecommendation.id == rec_id).first()
        if not rec:
            return {"status": "error", "reason": "Recomendación no encontrada"}
        if rec.status != "pending":
            return {"status": "error", "reason": f"Recomendación ya {rec.status}"}

        symbol = rec.asset.upper() + "USDT"

        # Fetch live price from Binance
        try:
            resp = _httpx.get(
                f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}",
                timeout=10.0,
            )
            if resp.status_code != 200:
                return {"status": "error", "reason": f"No se pudo obtener precio de {symbol}"}
            live_price = Dec(str(resp.json()["price"]))
        except Exception as exc:
            return {"status": "error", "reason": f"Error obteniendo precio: {exc}"}

        # Calculate SL/TP prices
        sl_pct = rec.stop_loss_pct or 3.0
        tp_pct = rec.take_profit_pct or 6.0
        stop_loss = live_price * (Dec(1) - Dec(str(sl_pct)) / Dec(100))
        take_profit = live_price * (Dec(1) + Dec(str(tp_pct)) / Dec(100))

        # Position size: use a fixed paper budget per trade ($1000 or 10% of default cash)
        paper_budget = Dec("1000")

        # Check if already has an open position in this symbol (paper)
        existing = db.query(Position).filter(
            Position.symbol == symbol,
            Position.status == "open",
            Position.strategy_name == "AI-Recommendation",
        ).first()
        if existing:
            return {"status": "rejected", "reason": f"Ya hay posición paper abierta en {symbol}"}

        quantity = paper_budget / live_price

        # Create Position
        pos = Position(
            user_id=0,
            symbol=symbol,
            opened_at=datetime.now(tz=UTC),
            side="long",
            quantity=quantity,
            entry_price=live_price,
            current_price=live_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            unrealized_pnl=Dec("0"),
            status="open",
            strategy_name="AI-Recommendation",
            metadata_json={
                "source": "ai_recommendation",
                "recommendation_id": rec.id,
                "reason": rec.reason,
                "confidence": float(rec.confidence),
                "trading_mode": "paper",
            },
        )
        db.add(pos)
        db.flush()

        # Create Trade
        trade = Trade(
            user_id=0,
            timestamp=datetime.now(tz=UTC),
            symbol=symbol,
            side="BUY",
            quantity=quantity,
            price=live_price,
            commission=Dec("0"),
            slippage=Dec("0"),
            realized_pnl=Dec("0"),
            strategy_name="AI-Recommendation",
            position_id=pos.id,
            metadata_json={
                "source": "ai_recommendation",
                "recommendation_id": rec.id,
                "trading_mode": "paper",
            },
        )
        db.add(trade)

        # Update recommendation status
        rec.status = "executed"

        db.commit()

        return {
            "status": "executed",
            "symbol": symbol,
            "side": "BUY",
            "quantity": str(quantity),
            "price": str(live_price),
            "stop_loss": str(stop_loss),
            "take_profit": str(take_profit),
            "position_id": pos.id,
            "trading_mode": "paper",
        }
    except Exception as exc:
        db.rollback()
        return {"status": "error", "reason": str(exc)}
    finally:
        db.close()


@router.post("/reports/{rec_id}/decline")
def decline_recommendation(rec_id: int) -> dict:
    """Decline an AI recommendation — marks it as dismissed."""
    from app.database.session import SessionLocal
    from app.database.models.ai_recommendation import AIRecommendation

    db = SessionLocal()
    try:
        rec = db.query(AIRecommendation).filter(AIRecommendation.id == rec_id).first()
        if not rec:
            return {"status": "error", "reason": "Recomendación no encontrada"}
        if rec.status != "pending":
            return {"status": "error", "reason": f"Recomendación ya {rec.status}"}

        rec.status = "dismissed"
        db.commit()

        return {"status": "dismissed", "id": rec_id}
    except Exception as exc:
        db.rollback()
        return {"status": "error", "reason": str(exc)}
    finally:
        db.close()


@router.get("/paper-positions")
def get_paper_positions() -> list[dict]:
    """Get paper positions created from accepted AI recommendations.

    These are simulated positions that compete with real prices in real-time.
    """
    from app.database.session import SessionLocal
    from app.database.models.position import Position
    from decimal import Decimal as Dec
    import httpx as _httpx

    # Fetch live prices
    price_map: dict[str, float] = {}
    try:
        tickers = _httpx.get("https://api.binance.com/api/v3/ticker/price", timeout=10).json()
        for t in tickers:
            price_map[t["symbol"]] = float(t["price"])
    except Exception:
        pass

    db = SessionLocal()
    try:
        positions = db.query(Position).filter(
            Position.strategy_name == "AI-Recommendation",
            Position.status == "open",
        ).order_by(Position.opened_at.desc()).all()

        result = []
        for p in positions:
            current_price = price_map.get(p.symbol, float(p.current_price or p.entry_price or 0))
            entry = float(p.entry_price or 0)
            qty = float(p.quantity or 0)
            pnl = (current_price - entry) * qty
            pnl_pct = ((current_price - entry) / entry * 100) if entry > 0 else 0

            # Update DB with live price
            p.current_price = Dec(str(current_price))
            p.unrealized_pnl = Dec(str(pnl))

            result.append({
                "id": p.id,
                "symbol": p.symbol,
                "side": p.side,
                "quantity": qty,
                "entry_price": entry,
                "current_price": current_price,
                "stop_loss": float(p.stop_loss) if p.stop_loss else None,
                "take_profit": float(p.take_profit) if p.take_profit else None,
                "unrealized_pnl": round(pnl, 4),
                "pnl_pct": round(pnl_pct, 2),
                "status": p.status,
                "strategy_name": p.strategy_name,
                "opened_at": p.opened_at.isoformat() if p.opened_at else None,
                "metadata_json": p.metadata_json,
                "invested": round(qty * entry, 2),
                "usd_value": round(qty * current_price, 2),
            })
        db.commit()
        return result
    except Exception as exc:
        logger.warning("Paper positions fetch failed: %s", exc)
        return []
    finally:
        db.close()


@router.post("/paper-positions/{position_id}/sell")
def sell_paper_position(position_id: int) -> dict:
    """Close a paper position at current market price."""
    from app.database.session import SessionLocal
    from app.database.models.position import Position
    from app.database.models.trade import Trade
    from decimal import Decimal as Dec
    import httpx as _httpx

    db = SessionLocal()
    try:
        pos = db.query(Position).filter(
            Position.id == position_id,
            Position.strategy_name == "AI-Recommendation",
            Position.status == "open",
        ).first()
        if not pos:
            return {"status": "error", "reason": "Posición paper no encontrada"}

        # Fetch live price
        try:
            resp = _httpx.get(
                f"https://api.binance.com/api/v3/ticker/price?symbol={pos.symbol}",
                timeout=10.0,
            )
            if resp.status_code != 200:
                return {"status": "error", "reason": "No se pudo obtener precio"}
            sell_price = Dec(str(resp.json()["price"]))
        except Exception as exc:
            return {"status": "error", "reason": f"Error obteniendo precio: {exc}"}

        entry = pos.entry_price
        qty = pos.quantity
        realized_pnl = (sell_price - entry) * qty

        # Close position
        pos.status = "closed"
        pos.closed_at = datetime.now(tz=UTC)
        pos.current_price = sell_price
        pos.realized_pnl = realized_pnl

        # Create sell trade
        trade = Trade(
            user_id=0,
            timestamp=datetime.now(tz=UTC),
            symbol=pos.symbol,
            side="SELL",
            quantity=qty,
            price=sell_price,
            commission=Dec("0"),
            slippage=Dec("0"),
            realized_pnl=realized_pnl,
            strategy_name="AI-Recommendation",
            position_id=pos.id,
            metadata_json={"source": "ai_recommendation", "trading_mode": "paper"},
        )
        db.add(trade)
        db.commit()

        return {
            "status": "executed",
            "symbol": pos.symbol,
            "side": "SELL",
            "quantity": str(qty),
            "price": str(sell_price),
            "realized_pnl": str(realized_pnl),
            "position_id": pos.id,
        }
    except Exception as exc:
        db.rollback()
        return {"status": "error", "reason": str(exc)}
    finally:
        db.close()
