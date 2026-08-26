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
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends

from app.api.helpers import safe_error
from app.config import get_settings
from app.services.auth import LocalUser, get_current_user
from app.services.market_data_service import get_market_data_service

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


def _clear_cache(prefix: str) -> None:
    keys_to_delete = [k for k in _cache if k.startswith(prefix)]
    for k in keys_to_delete:
        del _cache[k]


@router.get("/fear-greed")
def get_fear_greed() -> dict:
    """Fear & Greed Index from alternative.me (free, no auth)."""
    cached = _cached("fear_greed")
    if cached:
        return cached
    try:
        raw = get_market_data_service().get_fear_greed(limit=30)
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
        data = get_market_data_service().get_global_crypto_stats()
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
        data = get_market_data_service().get_global_crypto_stats()
        mcap_change = data.get("market_cap_change_percentage_24h_usd", 0)
        total_mcap = data.get("total_market_cap", {}).get("usd", 0)

        # Get BTC 24h ticker from market data service
        btc_data = get_market_data_service().get_24hr_ticker("BTC/USDT") or {}
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
        # Fetch large trades from public market data API
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        activities: list[dict] = []
        mds = get_market_data_service()
        base_url = mds._get_public_base_url()

        for sym in symbols:
            try:
                native_sym = mds._to_native_symbol(sym)
                resp = httpx.get(
                    f"{base_url}/api/v3/aggTrades",
                    params={"symbol": native_sym, "limit": 100},
                    timeout=10,
                )
                if resp.status_code != 200:
                    continue
                trades = resp.json()
                # Filter for large trades (whale threshold per symbol)
                thresholds = {"BTC/USDT": 100000, "ETH/USDT": 50000, "SOL/USDT": 20000}
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
                        "asset": sym.split("/")[0],
                        "amount": qty,
                        "amountUsd": round(value_usd, 2),
                        "direction": "inflow" if not is_buyer_maker else "outflow",
                        "fromAddress": "Market",
                        "toAddress": "Market",
                        "timestamp": datetime.fromtimestamp(
                            t.get("T", 0) / 1000, tz=UTC
                        ).isoformat(),
                        "exchange": get_settings().DEFAULT_BROKER_ID,
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
        # Try Forex Factory calendar (free JSON feed)
        events = get_market_data_service().get_macro_events()

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

        # Get BTC price from market data service
        btc_data = get_market_data_service().get_24hr_ticker("BTC/USDT") or {}
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
                "error": safe_error(exc),
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
            "error": safe_error(exc),
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
        return {"error": safe_error(exc)}


class OptimizeRequest(_BaseModel):
    symbol: str
    strategy: str = "trend_momentum"
    interval: str = "1h"
    limit: int = 500
    initial_cash: float = 10000.0
    max_combinations: int = 50


@router.post("/backtest/optimize")
def optimize_endpoint(req: OptimizeRequest) -> dict:
    """Run parameter optimization (grid search) and return best params."""
    from app.services.backtest_service import run_optimization

    try:
        result = run_optimization(
            symbol=req.symbol,
            strategy=req.strategy,
            interval=req.interval,
            limit=req.limit,
            initial_cash=req.initial_cash,
            max_combinations=req.max_combinations,
        )
        return result.to_dict()
    except Exception as exc:
        logger.warning("Optimization failed: %s", exc)
        return {"error": safe_error(exc)}


class MonteCarloRequest(_BaseModel):
    symbol: str
    strategy: str = "trend_momentum"
    interval: str = "1h"
    limit: int = 500
    initial_cash: float = 10000.0
    num_simulations: int = 1000
    ruin_threshold_pct: float = 0.5
    seed: int | None = None


@router.post("/backtest/monte-carlo")
def monte_carlo_endpoint(req: MonteCarloRequest) -> dict:
    """Run Monte Carlo simulation on a backtest to test robustness."""
    from app.services.backtest_service import run_backtest
    from app.services.monte_carlo import run_monte_carlo

    try:
        # First run the backtest
        result = run_backtest(
            symbol=req.symbol,
            strategy=req.strategy,
            interval=req.interval,
            limit=req.limit,
            initial_cash=req.initial_cash,
        )
        # Then run Monte Carlo on the trades
        mc_result = run_monte_carlo(
            backtest_result=result,
            num_simulations=req.num_simulations,
            ruin_threshold_pct=req.ruin_threshold_pct,
            seed=req.seed,
        )
        return {
            "backtest": result.to_dict(),
            "monte_carlo": mc_result.to_dict(),
        }
    except Exception as exc:
        logger.warning("Monte Carlo failed: %s", exc)
        return {"error": safe_error(exc)}


class CompareStrategiesRequest(_BaseModel):
    symbol: str
    strategies: list[str] = ["trend_momentum", "mean_reversion", "breakout", "macd_momentum"]
    interval: str = "1h"
    limit: int = 500
    initial_cash: float = 10000.0


@router.post("/backtest/compare")
def compare_strategies_endpoint(req: CompareStrategiesRequest) -> dict:
    """Compare multiple strategies on the same symbol and identify the best."""
    from app.services.backtest_service import run_backtest
    from app.services.monte_carlo import compare_strategies

    try:
        results = []
        for strategy_name in req.strategies:
            result = run_backtest(
                symbol=req.symbol,
                strategy=strategy_name,
                interval=req.interval,
                limit=req.limit,
                initial_cash=req.initial_cash,
            )
            results.append((strategy_name, result))

        comparison = compare_strategies(results)
        return comparison.to_dict()
    except Exception as exc:
        logger.warning("Strategy comparison failed: %s", exc)
        return {"error": safe_error(exc)}
    symbols: list[str] = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "DOGE/USDT", "PEPE/USDT"]
    interval: str = "1h"
    limit: int = 500
    initial_cash: float = 10000.0


@router.post("/backtest/auto-assign")
def auto_assign_endpoint(req: AutoAssignRequest) -> dict:
    """Run all 4 strategies on each symbol and assign the best one."""
    from app.services.strategy_assignment import auto_assign_strategies, update_assignment_cache, _last_full_evaluation
    import datetime as _dt

    try:
        result = auto_assign_strategies(
            symbols=req.symbols,
            interval=req.interval,
            limit=req.limit,
            initial_cash=req.initial_cash,
        )
        # Cache all assignments
        for a in result.assignments:
            update_assignment_cache(a)
        return result.to_dict()
    except Exception as exc:
        logger.warning("Auto-assign failed: %s", exc)
        return {"error": safe_error(exc)}


@router.get("/backtest/assignments")
def get_assignments_endpoint() -> dict:
    """Get cached strategy assignments."""
    from app.services.strategy_assignment import get_all_cached_assignments, get_last_evaluation_time

    cache = get_all_cached_assignments()
    last_eval = get_last_evaluation_time()
    return {
        "assignments": {k: v.to_dict() for k, v in cache.items()},
        "last_evaluation": last_eval.isoformat() if last_eval else None,
        "total": len(cache),
    }


# ---------------------------------------------------------------------------
# Market Regime & Auto-Pilot Endpoints
# ---------------------------------------------------------------------------

class RegimeRequest(_BaseModel):
    symbol: str
    interval: str = "1h"
    limit: int = 200


@router.post("/regime/detect")
def detect_regime_endpoint(req: RegimeRequest) -> dict:
    """Detect market regime for a symbol."""
    from app.services.market_regime import detect_regime

    try:
        regime = detect_regime(req.symbol, req.interval, req.limit)
        return regime.to_dict()
    except Exception as exc:
        logger.warning("Regime detection failed: %s", exc)
        return {"error": safe_error(exc)}


class RegimeBatchRequest(_BaseModel):
    symbols: list[str] = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
    interval: str = "1h"
    limit: int = 200


@router.post("/regime/detect-batch")
def detect_regime_batch_endpoint(req: RegimeBatchRequest) -> dict:
    """Detect market regime for multiple symbols."""
    from app.services.market_regime import detect_regimes_batch

    try:
        regimes = detect_regimes_batch(req.symbols, req.interval, req.limit)
        return {
            "regimes": [r.to_dict() for r in regimes],
            "total": len(regimes),
            "distribution": _regime_distribution(regimes),
        }
    except Exception as exc:
        logger.warning("Regime batch failed: %s", exc)
        return {"error": safe_error(exc)}


def _regime_distribution(regimes) -> dict[str, int]:
    dist: dict[str, int] = {}
    for r in regimes:
        dist[r.regime] = dist.get(r.regime, 0) + 1
    return dist


class AutoPilotRequest(_BaseModel):
    risk_tolerance: str = "moderate"
    experience_level: str = "beginner"
    capital_range: str = "100-1000"
    trading_goal: str = "growth"
    interval: str = "1h"
    max_symbols: int = 5


@router.post("/auto-pilot/plan")
def auto_pilot_plan_endpoint(req: AutoPilotRequest) -> dict:
    """Generate a complete auto-pilot trading plan based on user profile + market conditions."""
    from app.services.auto_pilot import generate_auto_pilot_plan

    try:
        plan = generate_auto_pilot_plan(
            risk_tolerance=req.risk_tolerance,
            experience_level=req.experience_level,
            capital_range=req.capital_range,
            trading_goal=req.trading_goal,
            interval=req.interval,
            max_symbols=req.max_symbols,
        )
        return plan.to_dict()
    except Exception as exc:
        logger.warning("Auto-pilot plan failed: %s", exc)
        return {"error": safe_error(exc)}


@router.get("/profile/recommendations")
def profile_recommendations_endpoint(
    risk_tolerance: str = "moderate",
    experience_level: str = "beginner",
) -> dict:
    """Get personalized recommendations based on user profile."""
    from app.services.market_regime import get_profile_recommendations

    try:
        return get_profile_recommendations(risk_tolerance, experience_level)
    except Exception as exc:
        logger.warning("Profile recommendations failed: %s", exc)
        return {"error": safe_error(exc)}


# ---------------------------------------------------------------------------
# Alerts & Notifications Endpoints
# ---------------------------------------------------------------------------

# ─── Multi-Timeframe (MTF) Endpoints ──────────────────────────────────────────

class MTFRequest(_BaseModel):
    symbol: str
    primary_interval: str = "1h"
    strategy_name: str = "trend_momentum"


@router.post("/mtf/confirm")
def mtf_confirm_endpoint(req: MTFRequest) -> dict:
    """Get multi-timeframe confirmation for a trading signal."""
    from app.services.multi_timeframe import confirm_entry_mtf

    try:
        result = confirm_entry_mtf(req.symbol, req.primary_interval, req.strategy_name)
        return result
    except Exception as exc:
        logger.warning("MTF confirm failed: %s", exc)
        return {"error": safe_error(exc)}


@router.get("/mtf/trend")
def mtf_trend_endpoint(symbol: str, interval: str = "4h") -> dict:
    """Get trend direction for a specific timeframe."""
    from app.services.multi_timeframe import get_mtf_trend

    try:
        return get_mtf_trend(symbol, interval)
    except Exception as exc:
        logger.warning("MTF trend failed: %s", exc)
        return {"error": safe_error(exc)}


class MTFBatchRequest(_BaseModel):
    symbols: list[str] = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    primary_interval: str = "1h"


@router.post("/mtf/confirm-batch")
def mtf_confirm_batch_endpoint(req: MTFBatchRequest) -> dict:
    """Get MTF confirmation for multiple symbols."""
    from app.services.multi_timeframe import confirm_entry_mtf

    results = []
    for sym in req.symbols:
        try:
            r = confirm_entry_mtf(sym, req.primary_interval, "trend_momentum")
            r["symbol"] = sym
            results.append(r)
        except Exception as exc:
            results.append({"symbol": sym, "error": safe_error(exc)})
    return {"results": results, "total": len(results)}


# ─── Walk-Forward Endpoints ───────────────────────────────────────────────────

class WalkForwardRequest(_BaseModel):
    symbol: str
    strategy: str = "trend_momentum"
    interval: str = "1h"
    limit: int = 1000
    initial_cash: float = 10000.0
    num_windows: int = 5
    train_ratio: float = 0.7


@router.post("/backtest/walk-forward")
def walk_forward_endpoint(req: WalkForwardRequest) -> dict:
    """Run walk-forward optimization to validate strategy robustness."""
    from app.services.walk_forward import run_walk_forward

    try:
        result = run_walk_forward(
            symbol=req.symbol,
            strategy=req.strategy,
            interval=req.interval,
            limit=req.limit,
            initial_cash=req.initial_cash,
            num_windows=req.num_windows,
            train_ratio=req.train_ratio,
        )
        return result.to_dict()
    except Exception as exc:
        logger.warning("Walk-forward failed: %s", exc)
        return {"error": safe_error(exc)}


class PriceAlertRequest(_BaseModel):
    symbol: str
    condition: str  # "above" or "below"
    target_price: float
    note: str | None = None


def _pa_to_dict(a) -> dict:
    return {
        "id": a.id,
        "symbol": a.symbol,
        "condition": a.condition,
        "target_price": float(a.target_price),
        "note": a.note,
        "triggered": a.triggered,
        "acknowledged": a.acknowledged,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "triggered_at": a.triggered_at.isoformat() if a.triggered_at else None,
        "triggered_price": float(a.triggered_price) if a.triggered_price else None,
    }


@router.get("/alerts")
def get_alerts(
    limit: int = 20,
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> list[dict]:
    """Get recent alerts — generated from price alerts and risk events."""
    uid = current_user.id if current_user else 0
    alerts: list[dict] = []

    # Check price alerts that have been triggered (from DB)
    try:
        from app.database.session import SessionLocal
        from app.database.models.price_alert import PriceAlert

        db = SessionLocal()
        try:
            triggered = db.query(PriceAlert).filter(
                PriceAlert.user_id == uid,
                PriceAlert.triggered == True,
            ).order_by(PriceAlert.triggered_at.desc()).limit(limit).all()
            for a in triggered:
                alerts.append({
                    "id": a.id,
                    "type": "price_alert",
                    "symbol": a.symbol,
                    "message": f"{a.symbol} {'subió por encima de' if a.condition == 'above' else 'bajó por debajo de'} ${float(a.target_price):,.2f}",
                    "severity": "info",
                    "timestamp": a.triggered_at.isoformat() if a.triggered_at else (a.created_at.isoformat() if a.created_at else ""),
                })
        finally:
            db.close()
    except Exception:
        pass

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
def get_pending_notifications(
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> list[dict]:
    """Get pending notifications for a user."""
    uid = current_user.id if current_user else 0
    try:
        from app.database.session import SessionLocal
        from app.database.models.price_alert import PriceAlert

        db = SessionLocal()
        try:
            pending = db.query(PriceAlert).filter(
                PriceAlert.user_id == uid,
                PriceAlert.triggered == True,
                PriceAlert.acknowledged == False,
            ).all()
            return [
                {
                    "id": a.id,
                    "type": "price_alert",
                    "title": f"Alerta de precio: {a.symbol}",
                    "message": f"{a.symbol} {'subió por encima de' if a.condition == 'above' else 'bajó por debajo de'} ${float(a.target_price):,.2f}",
                    "read": a.acknowledged,
                    "timestamp": a.triggered_at.isoformat() if a.triggered_at else (a.created_at.isoformat() if a.created_at else ""),
                }
                for a in pending
            ]
        finally:
            db.close()
    except Exception:
        return []


@router.post("/pending/{alert_id}/read")
def mark_alert_read(alert_id: int) -> dict:
    """Mark a price alert notification as read."""
    try:
        from app.database.session import SessionLocal
        from app.database.models.price_alert import PriceAlert

        db = SessionLocal()
        try:
            a = db.query(PriceAlert).filter(PriceAlert.id == alert_id).first()
            if a:
                a.acknowledged = True
                db.commit()
                return {"status": "ok"}
            return {"status": "not_found"}
        finally:
            db.close()
    except Exception:
        return {"status": "error"}


@router.post("/price-alerts")
def create_price_alert(
    req: PriceAlertRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Create a new price alert."""
    uid = current_user.id if current_user else 0
    try:
        from app.database.session import SessionLocal
        from app.database.models.price_alert import PriceAlert

        db = SessionLocal()
        try:
            alert = PriceAlert(
                user_id=uid,
                symbol=req.symbol.upper(),
                condition=req.condition,
                target_price=req.target_price,
                note=req.note,
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)
            return {"status": "ok", "alert": _pa_to_dict(alert)}
        finally:
            db.close()
    except Exception as exc:
        return {"status": "error", "error": safe_error(exc)}


@router.get("/price-alerts")
def list_price_alerts(
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> list[dict]:
    """List all price alerts for the current user."""
    uid = current_user.id if current_user else 0
    try:
        from app.database.session import SessionLocal
        from app.database.models.price_alert import PriceAlert

        db = SessionLocal()
        try:
            alerts = db.query(PriceAlert).filter(
                PriceAlert.user_id == uid,
            ).order_by(PriceAlert.created_at.desc()).all()
            return [_pa_to_dict(a) for a in alerts]
        finally:
            db.close()
    except Exception:
        return []


@router.delete("/price-alerts/{alert_id}")
def delete_price_alert(alert_id: int) -> dict:
    """Delete a price alert."""
    try:
        from app.database.session import SessionLocal
        from app.database.models.price_alert import PriceAlert

        db = SessionLocal()
        try:
            a = db.query(PriceAlert).filter(PriceAlert.id == alert_id).first()
            if a:
                db.delete(a)
                db.commit()
            return {"status": "ok"}
        finally:
            db.close()
    except Exception:
        return {"status": "error"}


@router.post("/price-alerts/check")
def check_price_alerts() -> dict:
    """Check all active price alerts against current prices and trigger if met."""
    try:
        from app.database.session import SessionLocal
        from app.database.models.price_alert import PriceAlert

        db = SessionLocal()
        try:
            active = db.query(PriceAlert).filter(PriceAlert.triggered == False).all()
            if not active:
                return {"status": "ok", "triggered": 0}
        finally:
            db.close()
    except Exception:
        return {"status": "ok", "triggered": 0}

    # Fetch current prices
    try:
        tickers = get_market_data_service()._get_all_tickers_public()
        # Public API returns 24hr format; extract just price symbols
        all_prices = {}
        for t in tickers:
            if "symbol" in t and "lastPrice" in t:
                all_prices[t["symbol"]] = float(t["lastPrice"])
        # Also try the simpler ticker/price endpoint
        base_url = get_market_data_service()._get_public_base_url()
        resp = httpx.get(f"{base_url}/api/v3/ticker/price", timeout=10)
        if resp.status_code == 200:
            prices = {d["symbol"]: float(d["price"]) for d in resp.json()}
        else:
            prices = all_prices
    except Exception as exc:
        logger.warning("Failed to fetch prices for alert check: %s", exc)
        return {"status": "error", "error": safe_error(exc)}

    triggered_count = 0
    try:
        db = SessionLocal()
        try:
            for alert in active:
                current = prices.get(alert.symbol)
                if current is None:
                    continue
                if alert.condition == "above" and current >= alert.target_price:
                    alert.triggered = True
                    alert.triggered_at = datetime.now(UTC)
                    alert.triggered_price = current
                    triggered_count += 1
                elif alert.condition == "below" and current <= alert.target_price:
                    alert.triggered = True
                    alert.triggered_at = datetime.now(UTC)
                    alert.triggered_price = current
                    triggered_count += 1
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Failed to update alerts: %s", exc)

    return {"status": "ok", "triggered": triggered_count}


# ---------------------------------------------------------------------------
# Risk Management Endpoints
# ---------------------------------------------------------------------------

# Default risk config values (used when no DB row exists for user)
_DEFAULT_RISK_CONFIG = {
    "trailing_stop_pct": 2.0,
    "hard_stop_loss_pct": 3.0,
    "take_profit_pct": 6.0,
    "max_position_size_pct": 10.0,
    "max_open_positions": 5,
    "daily_loss_limit_pct": 5.0,
    "circuit_breaker_enabled": True,
    "auto_sell_rsi_overbought": 70.0,
    "auto_sell_max_position_hours": 24.0,
    "auto_sell_min_volume_relative": 0.5,
    "auto_sell_macd_bearish": True,
    "auto_sell_rsi_enabled": True,
    "auto_sell_time_enabled": True,
    "auto_sell_volume_enabled": True,
}

# Fallback in-memory for unauthenticated requests
_risk_config: dict = dict(_DEFAULT_RISK_CONFIG)


def _get_risk_config_db(db, user_id: int) -> dict:
    """Load risk config from DB for a user, or return defaults."""
    from app.database.models.risk_config import RiskConfig
    rc = db.query(RiskConfig).filter(RiskConfig.user_id == user_id).first()
    if rc:
        return {
            "trailing_stop_pct": rc.trailing_stop_pct,
            "hard_stop_loss_pct": rc.hard_stop_loss_pct,
            "take_profit_pct": rc.take_profit_pct,
            "max_position_size_pct": rc.max_position_size_pct,
            "max_open_positions": rc.max_open_positions,
            "daily_loss_limit_pct": rc.daily_loss_limit_pct,
            "circuit_breaker_enabled": rc.circuit_breaker_enabled,
            "auto_sell_rsi_overbought": rc.auto_sell_rsi_overbought,
            "auto_sell_max_position_hours": rc.auto_sell_max_position_hours,
            "auto_sell_min_volume_relative": rc.auto_sell_min_volume_relative,
            "auto_sell_macd_bearish": rc.auto_sell_macd_bearish,
            "auto_sell_rsi_enabled": rc.auto_sell_rsi_enabled,
            "auto_sell_time_enabled": rc.auto_sell_time_enabled,
            "auto_sell_volume_enabled": rc.auto_sell_volume_enabled,
        }
    return dict(_DEFAULT_RISK_CONFIG)


class RiskConfigRequest(_BaseModel):
    trailing_stop_pct: float | None = None
    hard_stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    max_position_size_pct: float | None = None
    max_open_positions: int | None = None
    daily_loss_limit_pct: float | None = None
    circuit_breaker_enabled: bool | None = None
    auto_sell_rsi_overbought: float | None = None
    auto_sell_max_position_hours: float | None = None
    auto_sell_min_volume_relative: float | None = None
    auto_sell_macd_bearish: bool | None = None
    auto_sell_rsi_enabled: bool | None = None
    auto_sell_time_enabled: bool | None = None
    auto_sell_volume_enabled: bool | None = None


@router.get("/risk/config")
def get_risk_config(
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Get current risk management configuration (per-user from DB)."""
    if not current_user:
        return dict(_risk_config)
    from app.database.session import SessionLocal
    from app.database.models.risk_config import RiskConfig
    db = SessionLocal()
    try:
        return _get_risk_config_db(db, current_user.id)
    finally:
        db.close()


@router.post("/risk/config")
def update_risk_config(
    req: RiskConfigRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Update risk management configuration (per-user in DB)."""
    if not current_user:
        # Fallback to in-memory for unauthenticated
        changes = []
        for field, value in req.model_dump(exclude_none=True).items():
            old = _risk_config.get(field)
            _risk_config[field] = value
            changes.append(f"{field}: {old} -> {value}")
        logger.info("Risk config updated (in-memory): %s", "; ".join(changes))
        return {"status": "ok", "config": dict(_risk_config)}

    from app.database.session import SessionLocal
    from app.database.models.risk_config import RiskConfig
    db = SessionLocal()
    try:
        rc = db.query(RiskConfig).filter(RiskConfig.user_id == current_user.id).first()
        if not rc:
            rc = RiskConfig(user_id=current_user.id)
            db.add(rc)
        changes = []
        for field, value in req.model_dump(exclude_none=True).items():
            old = getattr(rc, field)
            setattr(rc, field, value)
            changes.append(f"{field}: {old} -> {value}")
        db.commit()
        logger.info("Risk config updated (DB, user=%s): %s", current_user.id, "; ".join(changes))
        return {"status": "ok", "config": _get_risk_config_db(db, current_user.id)}
    finally:
        db.close()


@router.get("/risk/status")
def get_risk_status(
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Get current risk status — open positions, exposure, circuit breaker state."""
    uid = current_user.id if current_user else 0
    try:
        from app.database.session import SessionLocal
        from app.database.models.position import Position
        db = SessionLocal()
        try:
            rc = _get_risk_config_db(db, uid) if current_user else dict(_risk_config)
            positions = db.query(Position).filter(Position.status == "open", Position.user_id == uid).all()
            total_exposure = sum(
                abs(float(p.quantity or 0)) * float(p.current_price or p.entry_price or 0)
                for p in positions
            )
            total_pnl = sum(float(p.unrealized_pnl or 0) for p in positions)

            # Check circuit breaker conditions
            daily_loss = abs(min(total_pnl, 0))
            daily_loss_pct = (daily_loss / total_exposure * 100) if total_exposure > 0 else 0
            circuit_triggered = (
                rc.get("circuit_breaker_enabled", True)
                and daily_loss_pct >= rc.get("daily_loss_limit_pct", 5.0)
            )

            return {
                "open_positions": len(positions),
                "max_open_positions": rc.get("max_open_positions", 5),
                "total_exposure": round(total_exposure, 2),
                "total_unrealized_pnl": round(total_pnl, 2),
                "daily_loss_pct": round(daily_loss_pct, 2),
                "daily_loss_limit_pct": rc.get("daily_loss_limit_pct", 5.0),
                "circuit_breaker_enabled": rc.get("circuit_breaker_enabled", True),
                "circuit_breaker_triggered": circuit_triggered,
                "trailing_stop_pct": rc.get("trailing_stop_pct", 2.0),
                "hard_stop_loss_pct": rc.get("hard_stop_loss_pct", 3.0),
                "take_profit_pct": rc.get("take_profit_pct", 6.0),
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
            "error": safe_error(exc),
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


@router.get("/scenarios/{asset}")
def get_remote_scenarios(asset: str, limit: int = 5) -> list[dict]:
    """Fetch probabilistic scenarios from the AI Server for an asset."""
    cached = _cached(f"scenarios_{asset}_{limit}")
    if cached:
        return cached

    try:
        from app.config import get_settings
        settings = get_settings()
        if settings.USE_INTELLIGENCE_API and settings.REMOTE_AI_URL:
            url = f"{settings.REMOTE_AI_URL.rstrip('/')}/v1/intelligence/scenarios/{asset.upper()}"
            headers: dict[str, str] = {}
            if settings.REMOTE_AI_TOKEN:
                headers["Authorization"] = f"Bearer {settings.REMOTE_AI_TOKEN}"
            resp = httpx.get(url, headers=headers, params={"limit": limit}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            scenarios = data.get("scenarios", [])
            _set_cache(f"scenarios_{asset}_{limit}", scenarios, 120)
            return scenarios
    except Exception as exc:
        logger.warning("Remote scenarios fetch failed: %s", exc)

    return []


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


def _build_live_data(
    asset: str,
    stop_loss_pct: float | None,
    take_profit_pct: float | None,
    user_id: int,
) -> dict | None:
    """Build live trading data for a BUY recommendation: balance, quantity, SL/TP prices, risk summary."""
    try:
        import app.api.state as _state
        from app.api.helpers import get_shared_broker, resolve_binancekeys
        from app.config import get_settings
        from app.database.session import SessionLocal
        from app.database.models.position import Position
        from decimal import Decimal as Dec
        import httpx as _httpx

        settings = get_settings()
        symbol = asset.upper() + "USDT"

        # Fetch live price from market data service
        current_price: float | None = None
        try:
            from app.brokers.models import normalize_symbol
            canonical = normalize_symbol(symbol)
            ticker = get_market_data_service().get_ticker(canonical)
            if ticker:
                current_price = float(ticker.price)
        except Exception:
            pass

        # Get open positions
        db = SessionLocal()
        try:
            open_positions = db.query(Position).filter(
                Position.status == "open",
                Position.user_id == user_id,
            ).all()
            open_count = len(open_positions)
            open_symbols = [p.symbol for p in open_positions]
            has_existing = any(p.symbol == symbol for p in open_positions)
        finally:
            db.close()

        # Get USDT balance from Binance
        usdt_balance: float | None = None
        allocated_capital: float | None = None
        available_capital: float | None = None
        kill_switch_active = False

        try:
            is_live = settings.TRADING_MODE == "live" and settings.LIVE_TRADING_ENABLED
            kill_switch_active = bool(is_live and settings.LIVE_KILL_SWITCH)

            if is_live:
                # Resolve Binance keys for this user
                # User model was removed — resolve_binancekeys only needs user_id
                from types import SimpleNamespace
                user = SimpleNamespace(id=user_id)

                keys = resolve_binancekeys(user)
                if keys:
                        broker = get_shared_broker(keys)
                        if hasattr(broker, "_signed_request"):
                            acct_data = broker._signed_request("GET", "/api/v3/account", {})
                            for bal in acct_data.get("balances", []):
                                if bal.get("asset") == "USDT":
                                    usdt_balance = float(bal["free"])
                                    break
            else:
                # Paper mode — use snapshots
                from app.database.models.account_snapshot import AccountSnapshot
                snap_db = SessionLocal()
                try:
                    snap = snap_db.query(AccountSnapshot).order_by(
                        AccountSnapshot.timestamp.desc()
                    ).first()
                    if snap:
                        usdt_balance = float(snap.cash or 0)
                finally:
                    snap_db.close()
        except Exception:
            pass

        # Calculate allocated/available capital
        ai_allocated = getattr(_state, "ai_allocated_capital", 0) or 0
        if ai_allocated > 0:
            allocated_capital = float(ai_allocated)
            if usdt_balance is not None and allocated_capital > usdt_balance:
                allocated_capital = usdt_balance
            # Subtract committed capital from open positions
            committed = sum(
                float(p.entry_price or 0) * float(p.quantity or 0)
                for p in open_positions
            )
            available_capital = max(0, allocated_capital - committed)
        else:
            allocated_capital = usdt_balance
            available_capital = usdt_balance

        # Max positions
        base_max = getattr(settings, "MAX_OPEN_POSITIONS", 5)
        dynamic_max = base_max + max(0, int(((allocated_capital or 0) - 50000) / 20000))

        # Calculate SL/TP prices
        sl_price = None
        tp_price = None
        if current_price and stop_loss_pct:
            sl_price = current_price * (1 - stop_loss_pct / 100)
        if current_price and take_profit_pct:
            tp_price = current_price * (1 + take_profit_pct / 100)

        # Estimated quantity
        est_qty = None
        est_value = None
        if current_price and available_capital and available_capital > 0:
            est_qty = available_capital / current_price
            est_value = available_capital

        return {
            "usdt_balance": usdt_balance,
            "allocated_capital": allocated_capital,
            "available_capital": available_capital,
            "open_positions_count": open_count,
            "max_positions": dynamic_max,
            "open_positions_symbols": open_symbols,
            "has_existing_position": has_existing,
            "estimated_quantity": est_qty,
            "estimated_value": est_value,
            "stop_loss_price": sl_price,
            "take_profit_price": tp_price,
            "current_price": current_price,
            "kill_switch_active": kill_switch_active,
        }
    except Exception as exc:
        logger.warning("Failed to build live_data for %s: %s", asset, exc)
        return None


@router.get("/reports/all")
def get_all_reports(
    limit: int = 50,
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> list[dict]:
    """Get all recent AI agent recommendations across all assets for the Reports tab."""
    uid = current_user.id if current_user else 0
    cached = _cached(f"reports_all_{uid}_{limit}")
    if cached:
        return cached

    result: list[dict] = []

    try:
        from app.database.session import SessionLocal
        from app.database.models.ai_recommendation import AIRecommendation

        db = SessionLocal()
        try:
            recs = db.query(AIRecommendation).filter(
                AIRecommendation.user_id == uid
            ).order_by(
                AIRecommendation.timestamp.desc()
            ).limit(limit).all()

            for r in recs:
                if r.action_type == "position_analysis":
                    meta = r.metadata_json or {}
                    result.append({
                        "id": f"rec-{r.id}",
                        "date": r.timestamp.strftime("%Y-%m-%d %H:%M") if r.timestamp else "",
                        "type": "daily",
                        "asset": r.asset,
                        "summary": f"Análisis de {meta.get('symbol', r.asset)} — {r.reason or 'Sin razón especificada'}",
                        "sections": {
                            "marketOverview": f"Símbolo: {meta.get('symbol', 'N/A')} | Posición ID: {meta.get('position_id', 'N/A')}",
                            "keyEvents": f"SL actual: {meta.get('current_sl', 'N/A')} → SL sugerido: {meta.get('suggested_sl', 'N/A')}",
                            "performance": f"TP actual: {meta.get('current_tp', 'N/A')} → TP sugerido: {meta.get('suggested_tp', 'N/A')}",
                            "outlook": f"Horizonte: {meta.get('time_horizon', 'N/A')} | {r.reason or ''}",
                            "detailedAnalysis": meta.get("detailed_analysis", ""),
                        },
                        "action_type": r.action_type,
                        "confidence": float(r.confidence),
                        "status": r.status,
                        "trading_mode": r.trading_mode,
                        "broker_name": r.broker_name,
                        "metadata": meta,
                        "timestamp": r.timestamp.isoformat() if r.timestamp else "",
                    })
                else:
                    action_label = "Compra recomendada" if r.action_type == "BUY" else "Venta recomendada" if r.action_type == "SELL" else "Mantener"
                    meta = r.metadata_json or {}
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
                        "stop_loss_pct": r.stop_loss_pct,
                        "take_profit_pct": r.take_profit_pct,
                        "reason": r.reason or "",
                        "metadata": {
                            "time_horizon": meta.get("time_horizon", ""),
                            "main_reasons": meta.get("main_reasons", []),
                            "main_risks": meta.get("main_risks", []),
                        },
                        "live_data": _build_live_data(r.asset, float(r.stop_loss_pct) if r.stop_loss_pct else None, float(r.take_profit_pct) if r.take_profit_pct else None, uid) if r.action_type == "BUY" and r.status == "pending" else None,
                        "timestamp": r.timestamp.isoformat() if r.timestamp else "",
                    })
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Reports(all) fetch failed: %s", exc)

    # 2. Executed trades from Trade table
    try:
        from app.database.session import SessionLocal
        from app.database.models.trade import Trade
        from app.database.models.order import Order
        from app.config import get_settings

        settings = get_settings()
        db = SessionLocal()
        try:
            trades = db.query(Trade).order_by(
                Trade.timestamp.desc()
            ).limit(limit).all()

            for t in trades:
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
                    "asset": t.symbol.replace("USDT", "").replace("/", "") if t.symbol else "",
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
        logger.warning("Trades fetch for reports(all) failed: %s", exc)

    # 3. Sort by timestamp descending
    result.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    # 4. If still empty, include daily reports for major assets as fallback
    if not result:
        try:
            daily = get_daily_report()
            for asset_name in ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX"]:
                result.append({
                    "id": f"daily-{asset_name}",
                    "date": daily.get("date", ""),
                    "type": "daily",
                    "asset": asset_name,
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

    _set_cache(f"reports_all_{uid}_{limit}", result, ttl=10)
    return result


@router.get("/reports/{asset}")
def get_reports(
    asset: str,
    limit: int = 20,
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> list[dict]:
    """Get AI agent recommendations and executed trades for an asset.

    Returns:
    - AI recommendations saved when auto_trade=false (status=pending)
    - Executed trades from the Trade table (paper and live)
    """
    uid = current_user.id if current_user else 0
    cached = _cached(f"reports_{uid}_{asset}_{limit}")
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
                AIRecommendation.asset == asset_upper,
                AIRecommendation.user_id == uid,
            ).order_by(AIRecommendation.timestamp.desc()).limit(limit).all()

            for r in recs:
                if r.action_type == "position_analysis":
                    meta = r.metadata_json or {}
                    result.append({
                        "id": f"rec-{r.id}",
                        "date": r.timestamp.strftime("%Y-%m-%d %H:%M") if r.timestamp else "",
                        "type": "daily",
                        "asset": r.asset,
                        "summary": f"Análisis de {meta.get('symbol', r.asset)} — {r.reason or 'Sin razón especificada'}",
                        "sections": {
                            "marketOverview": f"Símbolo: {meta.get('symbol', 'N/A')} | Posición ID: {meta.get('position_id', 'N/A')}",
                            "keyEvents": f"SL actual: {meta.get('current_sl', 'N/A')} → SL sugerido: {meta.get('suggested_sl', 'N/A')}",
                            "performance": f"TP actual: {meta.get('current_tp', 'N/A')} → TP sugerido: {meta.get('suggested_tp', 'N/A')}",
                            "outlook": f"Horizonte: {meta.get('time_horizon', 'N/A')} | {r.reason or ''}",
                            "detailedAnalysis": meta.get("detailed_analysis", ""),
                        },
                        "action_type": r.action_type,
                        "confidence": float(r.confidence),
                        "status": r.status,
                        "trading_mode": r.trading_mode,
                        "broker_name": r.broker_name,
                        "metadata": meta,
                        "timestamp": r.timestamp.isoformat() if r.timestamp else "",
                    })
                else:
                    action_label = "Compra recomendada" if r.action_type == "BUY" else "Venta recomendada" if r.action_type == "SELL" else "Mantener"
                    meta = r.metadata_json or {}
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
                        "stop_loss_pct": r.stop_loss_pct,
                        "take_profit_pct": r.take_profit_pct,
                        "reason": r.reason or "",
                        "metadata": {
                            "time_horizon": meta.get("time_horizon", ""),
                            "main_reasons": meta.get("main_reasons", []),
                            "main_risks": meta.get("main_risks", []),
                        },
                        "live_data": _build_live_data(r.asset, float(r.stop_loss_pct) if r.stop_loss_pct else None, float(r.take_profit_pct) if r.take_profit_pct else None, uid) if r.action_type == "BUY" and r.status == "pending" else None,
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

    _set_cache(f"reports_{uid}_{asset}_{limit}", result, 60)
    return result


@router.post("/reports/{rec_id}/accept")
def accept_recommendation(
    rec_id: int,
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
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

        # ─── Position Analysis: update existing position's SL/TP ───────────────
        if rec.action_type == "position_analysis":
            meta = rec.metadata_json or {}
            position_id = meta.get("position_id")
            suggested_sl = meta.get("suggested_sl")
            suggested_tp = meta.get("suggested_tp")

            if not position_id:
                return {"status": "error", "reason": "No se encontró position_id en la sugerencia"}

            pos = db.query(Position).filter(Position.id == position_id).first()
            if not pos:
                return {"status": "error", "reason": f"Posición {position_id} no encontrada"}

            old_sl = pos.stop_loss
            old_tp = pos.take_profit

            # Update DB
            if suggested_sl is not None:
                pos.stop_loss = Dec(str(suggested_sl))
            if suggested_tp is not None:
                pos.take_profit = Dec(str(suggested_tp))

            rec.status = "executed"
            db.commit()
            _clear_cache("reports_")

            return {
                "status": "applied",
                "position_id": position_id,
                "old_sl": str(old_sl) if old_sl else None,
                "old_tp": str(old_tp) if old_tp else None,
                "new_sl": str(suggested_sl) if suggested_sl else None,
                "new_tp": str(suggested_tp) if suggested_tp else None,
                "broker_updated": False,
                "broker_error": None,
            }

        # ─── Default: paper trade buy (existing logic) ─────────────────────────
        symbol = rec.asset.upper() + "USDT"

        # Fetch live price from market data service
        try:
            from app.brokers.models import normalize_symbol
            canonical = normalize_symbol(symbol)
            ticker = get_market_data_service().get_ticker(canonical)
            if not ticker:
                return {"status": "error", "reason": f"No se pudo obtener precio de {symbol}"}
            live_price = Dec(str(ticker.price))
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
        from app.api.helpers import resolve_user_broker_id
        broker_id = resolve_user_broker_id(current_user) or "binance"
        pos = Position(
            user_id=0,
            broker_id=broker_id,
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

        _clear_cache("reports_")

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
        return {"status": "error", "reason": safe_error(exc)}
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

        _clear_cache("reports_")

        return {"status": "dismissed", "id": rec_id}
    except Exception as exc:
        db.rollback()
        return {"status": "error", "reason": safe_error(exc)}
    finally:
        db.close()


class BuyLiveRequest(_BaseModel):
    """Optional overrides for live buy execution."""
    sl_pct: float | None = None
    tp_pct: float | None = None
    amount: float | None = None  # USD amount to invest (overrides auto budget)


@router.post("/reports/{rec_id}/buy-live")
def buy_live_recommendation(
    rec_id: int,
    req: BuyLiveRequest = BuyLiveRequest(),
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Execute a real BUY order from an AI recommendation via the configured broker.

    Uses the same execution engine as the AI agent: resolves Binance keys,
    fetches live price, calculates SL/TP, checks kill switch / max positions /
    diversification, and executes via ExecutionEngine.
    """
    import app.api.state as _state
    from app.api.helpers import get_shared_broker, resolve_binancekeys
    from app.brokers import MockBroker
    from app.config import get_settings
    from app.database.models.ai_recommendation import AIRecommendation
    from app.database.models.position import Position
    from app.database.session import SessionLocal
    from app.execution import ExecutionEngine
    from app.models.signal import SignalCreate
    from app.risk import RiskManager
    from datetime import timedelta
    from decimal import Decimal as Dec
    import httpx as _httpx

    settings = get_settings()
    db = SessionLocal()
    try:
        rec = db.query(AIRecommendation).filter(AIRecommendation.id == rec_id).first()
        if not rec:
            return {"status": "error", "reason": "Recomendación no encontrada"}
        if rec.status != "pending":
            return {"status": "error", "reason": f"Recomendación ya {rec.status}"}
        # Allow buying from any recommendation type (not just BUY)

        symbol = rec.asset.upper() + "USDT"
        is_live = settings.TRADING_MODE == "live" and settings.LIVE_TRADING_ENABLED

        # Kill switch
        if is_live and settings.LIVE_KILL_SWITCH:
            return {"status": "rejected", "symbol": symbol, "reason": "KILL SWITCH activado. Compras bloqueadas."}

        # Resolve broker keys
        keys = resolve_binancekeys(current_user)
        broker = get_shared_broker(keys)

        # Daily loss limit check
        if is_live:
            from app.database.models.trade import Trade
            today_start = datetime.now(tz=UTC) - timedelta(hours=24)
            recent_trades = db.query(Trade).filter(
                Trade.timestamp >= today_start,
                Trade.side == "SELL",
            ).all()
            daily_loss = sum(float(t.realized_pnl) for t in recent_trades if float(t.realized_pnl) < 0)
            if abs(daily_loss) >= settings.LIVE_DAILY_LOSS_LIMIT_USD:
                return {"status": "rejected", "symbol": symbol, "reason": f"Pérdida diaria (${abs(daily_loss):.2f}) alcanzó el límite (${settings.LIVE_DAILY_LOSS_LIMIT_USD})."}

        # Get live price
        live_price = None
        try:
            from app.data.price_stream import get_price_stream
            stream = get_price_stream()
            if stream and stream.is_connected:
                p = stream.get_price(symbol)
                if p and p > 0:
                    live_price = Dec(str(p))
        except Exception:
            pass

        if not live_price or live_price <= 0:
            try:
                from app.brokers.models import normalize_symbol
                canonical = normalize_symbol(symbol)
                ticker = get_market_data_service().get_ticker(canonical)
                if ticker and ticker.price > 0:
                    live_price = Dec(str(ticker.price))
                else:
                    return {"status": "error", "symbol": symbol, "reason": f"Símbolo {symbol} no existe o sin precio"}
            except Exception as exc:
                return {"status": "error", "symbol": symbol, "reason": f"No se pudo validar {symbol}: {exc}"}

        if not live_price or live_price <= 0:
            return {"status": "error", "symbol": symbol, "reason": f"Precio inválido para {symbol}"}

        # Diversification check
        existing = db.query(Position).filter(
            Position.symbol == symbol,
            Position.status == "open",
            Position.user_id == current_user.id,
        ).first()
        if existing:
            return {"status": "rejected", "symbol": symbol, "reason": f"Ya hay posición abierta en {symbol}"}

        # Get account info
        acct = broker.get_account()
        usdt_balance = 0.0
        try:
            if hasattr(broker, "_signed_request"):
                acct_data = broker._signed_request("GET", "/api/v3/account", {})
                for bal in acct_data.get("balances", []):
                    if bal.get("asset") == "USDT":
                        usdt_balance = float(bal["free"])
                        break
        except Exception:
            pass

        # Calculate allocated/available capital
        open_positions = db.query(Position).filter(
            Position.status == "open",
            Position.user_id == current_user.id,
        ).all()
        is_auto_mode = _state.ai_allocated_capital <= 0
        if _state.ai_allocated_capital > 0:
            allocated = float(_state.ai_allocated_capital)
            if usdt_balance > 0 and allocated > usdt_balance:
                allocated = usdt_balance
        else:
            allocated = usdt_balance if usdt_balance > 0 else float(acct.equity)

        if is_auto_mode:
            available = allocated
        else:
            committed = sum(float(p.entry_price or 0) * float(p.quantity or 0) for p in open_positions)
            available = allocated - committed

        if available <= 0:
            return {"status": "rejected", "symbol": symbol, "reason": f"Capital asignado (${allocated:.2f}) ya está comprometido en {len(open_positions)} posiciones."}

        # Max positions — limit removed per user request, no cap
        open_count = len(open_positions)
        dynamic_max = 999

        # SL/TP from request overrides or recommendation defaults
        sl_pct = float(req.sl_pct) if req.sl_pct else (float(rec.stop_loss_pct) if rec.stop_loss_pct else float(getattr(settings, "DEFAULT_STOP_LOSS_PERCENT", 3.0)))
        tp_pct = float(req.tp_pct) if req.tp_pct else (float(rec.take_profit_pct) if rec.take_profit_pct else float(getattr(settings, "DEFAULT_TAKE_PROFIT_PERCENT", 6.0)))
        stop_loss = live_price * (Dec(1) - Dec(str(sl_pct)) / Dec(100))
        take_profit = live_price * (Dec(1) + Dec(str(tp_pct)) / Dec(100))

        # Position budget — use custom amount if provided, else auto-calculate
        if req.amount and req.amount > 0:
            position_budget = Dec(str(req.amount))
            if position_budget > Dec(str(available)):
                position_budget = Dec(str(available))
        else:
            remaining_slots = max(1, dynamic_max - open_count)
            position_budget = available / remaining_slots

        # Enforce minimum order size (Binance NOTIONAL filter requires ~$5-10)
        MIN_ORDER_USD = Dec("10")
        if position_budget < MIN_ORDER_USD:
            position_budget = MIN_ORDER_USD
        # If even the minimum exceeds available capital, reject with clear message
        if position_budget > Dec(str(available)) and available > 0:
            return {
                "status": "rejected",
                "symbol": symbol,
                "reason": f"Capital disponible (${available:.2f}) insuficiente para orden mínima (${float(MIN_ORDER_USD):.0f}). Usa una cantidad menor o agrega fondos.",
            }

        from app.database.models.account_snapshot import AccountSnapshot as AcctModel
        acct_override = AcctModel(
            timestamp=datetime.now(tz=UTC),
            cash=Dec(str(position_budget)),
            equity=Dec(str(position_budget)),
            buying_power=Dec(str(position_budget)),
            margin_used=Dec("0"),
            daily_pnl=Dec("0"),
            total_pnl=Dec("0"),
            open_positions_count=open_count,
            strategy_run_id=None,
        )

        signal = SignalCreate(
            timestamp=datetime.now(tz=UTC),
            symbol=symbol,
            signal_type="BUY",
            confidence=Dec(str(rec.confidence)),
            entry_price=live_price,
            strategy_name="AI-Agent",
            explanation=f"[AI Recommendation] {rec.reason or ''}",
            metadata_json={"source": "ai_recommendation", "recommendation_id": rec.id},
            suggested_stop_loss=stop_loss,
            suggested_take_profit=take_profit,
        )

        risk_manager = RiskManager(settings)
        engine = ExecutionEngine(broker, risk_manager, db, settings, user_id=current_user.id)
        order = engine.process_signal(signal, account=acct_override)
        db.commit()

        if order:
            rec.status = "executed"
            db.commit()
            _clear_cache("reports_")
            return {
                "status": "executed",
                "symbol": symbol,
                "side": order.side,
                "quantity": str(order.filled_quantity),
                "price": str(order.price) if order.price else None,
                "order_id": order.id,
                "stop_loss": str(stop_loss),
                "take_profit": str(take_profit),
                "trading_mode": "live" if is_live else "paper",
            }
        else:
            return {"status": "rejected", "symbol": symbol, "reason": "Rechazado por risk manager"}
    except Exception as exc:
        db.rollback()
        return {"status": "error", "reason": safe_error(exc)}
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
        base_url = get_market_data_service()._get_public_base_url()
        tickers = httpx.get(f"{base_url}/api/v3/ticker/price", timeout=10).json()
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
            from app.brokers.models import normalize_symbol
            canonical = normalize_symbol(pos.symbol)
            ticker = get_market_data_service().get_ticker(canonical)
            if not ticker:
                return {"status": "error", "reason": "No se pudo obtener precio"}
            sell_price = Dec(str(ticker.price))
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
        return {"status": "error", "reason": safe_error(exc)}
    finally:
        db.close()


# ─── SL/TP OCO and Monitoring endpoints ───────────────────────────────────────

from pydantic import BaseModel as _BM


class OcoRequest(_BM):
    stop_loss: float
    take_profit: float


class OcoResultRequest(_BM):
    """Client sends the OCO result from Binance (placed via proxy)."""
    oco_order_id: int | str
    stop_loss: float
    take_profit: float
    symbol: str | None = None
    quantity: float | None = None
    entry_price: float | None = None


class OcoCancelResultRequest(_BM):
    """Client sends confirmation that OCO was cancelled on Binance (via proxy)."""
    oco_order_id: int | str


def _create_notification(
    *,
    type: str,
    title: str,
    message: str = "",
    severity: str = "info",
    asset: str | None = None,
    action_url: str | None = None,
    user_id: int = 0,
) -> None:
    """Create an in-app notification (shown in the bell dropdown)."""
    try:
        from app.database.session import SessionLocal
        from app.services.notification_service import create_notification

        db = SessionLocal()
        create_notification(
            db,
            type=type,
            title=title,
            message=message,
            severity=severity,
            asset=asset,
            action_url=action_url,
            user_id=user_id,
        )
        db.close()
    except Exception:
        pass


@router.post("/positions/{position_id}/update-oco")
def update_oco_on_position(
    position_id: int,
    req: OcoResultRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Update position in DB after client placed OCO on Binance via proxy."""
    from app.database.session import SessionLocal
    from app.database.models.position import Position
    from decimal import Decimal as Dec

    db = SessionLocal()
    try:
        pos = db.query(Position).filter(Position.id == position_id).first()
        if not pos and req.symbol:
            # position_id=0 means broker-managed — try to find by symbol
            sym = req.symbol.upper().replace("/", "").replace("-", "").replace("_", "")
            pos = db.query(Position).filter(
                Position.user_id == current_user.id,
                Position.status == "open",
            ).filter(Position.symbol.ilike(f"%{sym}%")).first()
        if not pos and req.symbol:
            # Still no DB position — create one from the OCO data
            from datetime import datetime, UTC
            from app.api.helpers import resolve_user_broker_id
            sym = req.symbol.upper()
            if "/" not in sym:
                sym = sym.replace("USDT", "/USDT")
            entry = req.entry_price or req.stop_loss  # fallback
            qty = req.quantity or 0
            broker_id = resolve_user_broker_id(current_user) or "binance"
            pos = Position(
                user_id=current_user.id,
                broker_id=broker_id,
                symbol=sym,
                opened_at=datetime.now(tz=UTC),
                side="long",
                quantity=Dec(str(qty)),
                entry_price=Dec(str(entry)),
                current_price=Dec(str(entry)),
                status="open",
                strategy_name="manual",
                metadata_json={"source": "oco_update", "broker_managed": True},
            )
            db.add(pos)
            db.commit()
        if not pos:
            return {"status": "error", "error": f"Posición {position_id} no encontrada"}
        if pos.status != "open":
            return {"status": "error", "error": f"Posición {position_id} no está abierta"}

        sl_price = Dec(str(req.stop_loss))
        tp_price = Dec(str(req.take_profit))

        pos.stop_loss = sl_price
        pos.take_profit = tp_price
        meta = pos.metadata_json or {}
        meta["oco_order_id"] = req.oco_order_id
        meta["monitoring_active"] = False
        pos.metadata_json = meta
        db.commit()

        # Notify WS subscribers
        try:
            from app.api.routes.realtime import notify_position_update
            notify_position_update(current_user.id if current_user else 0)
        except Exception:
            pass

        _create_notification(
            type="trade_executed",
            title=f"OCO colocado: {pos.symbol}",
            message=f"SL: {sl_price} | TP: {tp_price} | Qty: {pos.quantity} | Order ID: {req.oco_order_id}",
            severity="info",
            asset=pos.symbol,
            action_url="/broker",
            user_id=current_user.id if current_user else 0,
        )

        return {
            "status": "placed",
            "oco_order_id": req.oco_order_id,
            "sl": str(sl_price),
            "tp": str(tp_price),
        }
    except Exception as exc:
        db.rollback()
        return {"status": "error", "error": safe_error(exc)}
    finally:
        db.close()


@router.delete("/positions/{position_id}/clear-oco")
def clear_oco_on_position(
    position_id: int,
    req: OcoCancelResultRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Clear OCO from position metadata after client cancelled it on Binance via proxy."""
    from app.database.session import SessionLocal
    from app.database.models.position import Position

    db = SessionLocal()
    try:
        pos = db.query(Position).filter(Position.id == position_id).first()
        if not pos:
            return {"status": "error", "error": f"Posición {position_id} no encontrada"}

        meta = pos.metadata_json or {}
        oco_order_id = meta.get("oco_order_id")
        if not oco_order_id:
            return {"status": "error", "error": "No hay OCO activo en esta posición"}

        meta.pop("oco_order_id", None)
        pos.metadata_json = meta
        db.commit()

        _create_notification(
            type="system_event",
            title=f"OCO cancelado: {pos.symbol}",
            message=f"Orden OCO {oco_order_id} cancelada en Binance para {pos.symbol}",
            severity="info",
            asset=pos.symbol,
            action_url="/broker",
            user_id=current_user.id if current_user else 0,
        )

        return {"status": "cancelled", "oco_order_id": oco_order_id}
    except Exception as exc:
        db.rollback()
        return {"status": "error", "error": safe_error(exc)}
    finally:
        db.close()


@router.post("/positions/{position_id}/stop-monitoring")
def stop_monitoring(position_id: int) -> dict:
    """Stop SL/TP monitoring for a position."""
    from app.database.session import SessionLocal
    from app.database.models.position import Position

    db = SessionLocal()
    try:
        pos = db.query(Position).filter(Position.id == position_id).first()
        if not pos:
            return {"status": "error", "error": f"Posición {position_id} no encontrada"}

        meta = pos.metadata_json or {}
        meta["monitoring_active"] = False
        pos.metadata_json = meta
        db.commit()

        return {"status": "monitoring_stopped", "position_id": position_id}
    except Exception as exc:
        db.rollback()
        return {"status": "error", "error": safe_error(exc)}
    finally:
        db.close()


@router.post("/reports/{rec_id}/monitor-only")
def monitor_only(rec_id: int) -> dict:
    """Accept a position_analysis recommendation but only monitor (no Binance orders)."""
    from app.database.session import SessionLocal
    from app.database.models.ai_recommendation import AIRecommendation
    from app.database.models.position import Position
    from decimal import Decimal as Dec

    db = SessionLocal()
    try:
        rec = db.query(AIRecommendation).filter(AIRecommendation.id == rec_id).first()
        if not rec:
            return {"status": "error", "reason": "Recomendación no encontrada"}
        if rec.status != "pending":
            return {"status": "error", "reason": f"Recomendación ya {rec.status}"}

        if rec.action_type != "position_analysis":
            return {"status": "error", "reason": "Solo aplica a sugerencias de position_analysis"}

        meta = rec.metadata_json or {}
        position_id = meta.get("position_id")
        suggested_sl = meta.get("suggested_sl")
        suggested_tp = meta.get("suggested_tp")

        if not position_id:
            return {"status": "error", "reason": "No se encontró position_id en la sugerencia"}

        pos = db.query(Position).filter(Position.id == position_id).first()
        if not pos:
            return {"status": "error", "reason": f"Posición {position_id} no encontrada"}

        if suggested_sl is not None:
            pos.stop_loss = Dec(str(suggested_sl))
        if suggested_tp is not None:
            pos.take_profit = Dec(str(suggested_tp))

        pos_meta = pos.metadata_json or {}
        pos_meta["monitoring_active"] = True
        pos.metadata_json = pos_meta

        rec.status = "executed"
        db.commit()
        _clear_cache("reports_")

        return {
            "status": "monitoring",
            "position_id": position_id,
            "sl": str(suggested_sl) if suggested_sl else None,
            "tp": str(suggested_tp) if suggested_tp else None,
        }
    except Exception as exc:
        db.rollback()
        return {"status": "error", "reason": safe_error(exc)}
    finally:
        db.close()


@router.post("/reports/{rec_id}/apply-oco")
def apply_oco_from_report(
    rec_id: int,
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Return SL/TP data for client to place OCO on Binance via proxy.

    The client receives the suggested SL/TP and position info, places the OCO
    via the VPS proxy, then calls /positions/{id}/update-oco to confirm.
    """
    from app.database.session import SessionLocal
    from app.database.models.ai_recommendation import AIRecommendation
    from app.database.models.position import Position

    db = SessionLocal()
    try:
        rec = db.query(AIRecommendation).filter(AIRecommendation.id == rec_id).first()
        if not rec:
            return {"status": "error", "reason": "Recomendación no encontrada"}
        if rec.status != "pending":
            return {"status": "error", "reason": f"Recomendación ya {rec.status}"}

        if rec.action_type != "position_analysis":
            return {"status": "error", "reason": "Solo aplica a sugerencias de position_analysis"}

        meta = rec.metadata_json or {}
        position_id = meta.get("position_id")
        suggested_sl = meta.get("suggested_sl")
        suggested_tp = meta.get("suggested_tp")

        if not position_id or not suggested_sl or not suggested_tp:
            return {"status": "error", "reason": "Faltan datos de SL/TP en la sugerencia"}

        pos = db.query(Position).filter(Position.id == position_id).first()
        if not pos:
            return {"status": "error", "reason": f"Posición {position_id} no encontrada"}

        pos_meta = pos.metadata_json or {}
        is_futures = "futures" in (pos_meta.get("source") or "")

        # If spot position, check if there's also a futures position for the same symbol
        # (import may have created spot first and skipped futures). Use futures if available.
        if not is_futures:
            futures_pos = db.query(Position).filter(
                Position.symbol == pos.symbol,
                Position.status == "open",
                Position.user_id == pos.user_id,
            ).all()
            for fp in futures_pos:
                fp_meta = fp.metadata_json or {}
                if "futures" in (fp_meta.get("source") or ""):
                    pos = fp
                    pos_meta = fp_meta
                    is_futures = True
                    position_id = fp.id
                    break

        return {
            "status": "ready",
            "position_id": position_id,
            "symbol": pos.symbol,
            "quantity": float(pos.quantity),
            "stop_loss": float(suggested_sl),
            "take_profit": float(suggested_tp),
            "side": pos.side,
            "is_futures": is_futures,
            "message": "Coloca el OCO en Binance via proxy y luego confirma con /update-oco",
        }
    except Exception as exc:
        db.rollback()
        return {"status": "error", "reason": safe_error(exc)}
    finally:
        db.close()


@router.post("/paper-positions/{position_id}/place-oco")
def paper_place_oco(position_id: int, req: OcoRequest) -> dict:
    """Set SL/TP on a paper position and activate monitoring (simulated OCO)."""
    from app.database.session import SessionLocal
    from app.database.models.position import Position
    from decimal import Decimal as Dec

    db = SessionLocal()
    try:
        pos = db.query(Position).filter(Position.id == position_id).first()
        if not pos:
            return {"status": "error", "error": f"Posición {position_id} no encontrada"}
        if pos.status != "open":
            return {"status": "error", "error": f"Posición {position_id} no está abierta"}

        pos.stop_loss = Dec(str(req.stop_loss))
        pos.take_profit = Dec(str(req.take_profit))
        meta = pos.metadata_json or {}
        meta["monitoring_active"] = True
        pos.metadata_json = meta
        db.commit()

        return {
            "status": "monitoring",
            "position_id": position_id,
            "sl": str(req.stop_loss),
            "tp": str(req.take_profit),
        }
    except Exception as exc:
        db.rollback()
        return {"status": "error", "error": safe_error(exc)}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# One-Click Trade from Intelligence — P0
# ---------------------------------------------------------------------------


class SuggestTradeRequest(_BM):
    signal_type: str  # "whale", "alert", "news", "macro"
    asset: str
    signal_data: dict = {}


@router.post("/suggest-trade")
def suggest_trade_from_intelligence(
    req: SuggestTradeRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Suggest a trade (side + SL/TP) based on an intelligence signal.

    Maps intelligence signals to trade suggestions:
    - whale inflow -> BUY (smart money accumulating)
    - whale outflow -> SELL (smart money distributing)
    - high-impact positive news -> BUY
    - high-impact negative news -> SELL
    - macro event (CPI, FOMC) -> HOLD/caution
    - alert (price) -> based on alert direction
    """
    uid = current_user.id if current_user else 0
    asset = req.asset.upper().replace("/", "")
    signal_type = req.signal_type.lower()
    signal_data = req.signal_data or {}

    suggested_side = "buy"
    suggested_sl_pct = 3.0
    suggested_tp_pct = 6.0
    reason = ""

    if signal_type == "whale":
        direction = signal_data.get("direction", "inflow")
        amount_usd = signal_data.get("amount_usd", 0)
        if direction == "inflow":
            suggested_side = "buy"
            suggested_sl_pct = 2.5
            suggested_tp_pct = 5.0
            reason = f"Whale inflow detectado (${amount_usd:,.0f}) — smart money acumulando {asset}"
        else:
            suggested_side = "sell"
            suggested_sl_pct = 2.5
            suggested_tp_pct = 5.0
            reason = f"Whale outflow detectado (${amount_usd:,.0f}) — smart money distribuyendo {asset}"

    elif signal_type == "news":
        sentiment = signal_data.get("sentiment", "neutral")
        impact = signal_data.get("impact", "medium")
        if sentiment == "positive" and impact in ("high", "critical"):
            suggested_side = "buy"
            suggested_sl_pct = 3.0
            suggested_tp_pct = 8.0
            reason = f"Noticia positiva de alto impacto: {signal_data.get('title', '')[:100]}"
        elif sentiment == "negative" and impact in ("high", "critical"):
            suggested_side = "sell"
            suggested_sl_pct = 3.0
            suggested_tp_pct = 8.0
            reason = f"Noticia negativa de alto impacto: {signal_data.get('title', '')[:100]}"
        else:
            suggested_side = "hold"
            reason = "Noticia de impacto medio/bajo — no se recomienda operar"

    elif signal_type == "alert":
        alert_type = signal_data.get("type", "price")
        if alert_type == "price_above":
            suggested_side = "buy"
            suggested_sl_pct = 2.0
            suggested_tp_pct = 4.0
            reason = f"Alerta de precio superado — posible momentum alcista en {asset}"
        elif alert_type == "price_below":
            suggested_side = "sell"
            suggested_sl_pct = 2.0
            suggested_tp_pct = 4.0
            reason = f"Alerta de precio roto — posible momentum bajista en {asset}"
        else:
            reason = f"Alerta: {alert_type}"

    elif signal_type == "macro":
        event_impact = signal_data.get("impact", "medium")
        if event_impact == "high":
            suggested_side = "hold"
            reason = f"Evento macro de alto impacto: {signal_data.get('title', '')[:100]} — esperar claridad"
        else:
            suggested_side = "hold"
            reason = "Evento macro programado — precaucion"

    # Adjust SL/TP based on user risk profile
    try:
        from app.database.models.user_profile import UserProfile
        from app.database.session import SessionLocal as _SL
        profile_db = _SL()
        try:
            profile = profile_db.query(UserProfile).filter(UserProfile.user_id == uid).first()
            if profile and profile.risk_tolerance:
                if profile.risk_tolerance == "conservative":
                    suggested_sl_pct = min(suggested_sl_pct, 2.0)
                    suggested_tp_pct = min(suggested_tp_pct, 4.0)
                elif profile.risk_tolerance == "aggressive":
                    suggested_sl_pct = max(suggested_sl_pct, 4.0)
                    suggested_tp_pct = max(suggested_tp_pct, 10.0)
        finally:
            profile_db.close()
    except Exception:
        pass

    return {
        "status": "ok",
        "asset": asset,
        "suggested_side": suggested_side,
        "suggested_sl_pct": suggested_sl_pct,
        "suggested_tp_pct": suggested_tp_pct,
        "reason": reason,
        "signal_type": signal_type,
    }
