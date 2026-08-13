"""Market Regime Detection — automatically classify market conditions.

Detects whether the market is trending, ranging, volatile, or reversing
and recommends the best strategy for each condition.

Regimes:
- TRENDING_UP:   ADX > 25, EMA fast > EMA slow, +DI > -DI
- TRENDING_DOWN: ADX > 25, EMA fast < EMA slow, -DI > +DI
- RANGING:       ADX < 20, price oscillating
- VOLATILE:      ATR percentile > 80, high volatility
- SQUEEZE:       ATR percentile < 20, low volatility (consolidation)
- REVERSAL:      RSI divergence detected
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
import numpy as np
import pandas as pd

from app.brokers.models import normalize_symbol
from app.config import get_settings
from app.indicators import indicators as ind

logger = logging.getLogger(__name__)


@dataclass
class MarketRegime:
    """Detected market regime for a symbol."""

    symbol: str
    regime: str  # trending_up | trending_down | ranging | volatile | squeeze | reversal
    adx: float
    rsi: float
    atr_percentile: float
    ema_fast: float
    ema_slow: float
    plus_di: float
    minus_di: float
    bb_width: float
    recommended_strategies: list[str]
    confidence: float
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "regime": self.regime,
            "adx": round(self.adx, 2),
            "rsi": round(self.rsi, 2),
            "atr_percentile": round(self.atr_percentile, 1),
            "ema_fast": round(self.ema_fast, 6),
            "ema_slow": round(self.ema_slow, 6),
            "plus_di": round(self.plus_di, 2),
            "minus_di": round(self.minus_di, 2),
            "bb_width": round(self.bb_width, 4),
            "recommended_strategies": self.recommended_strategies,
            "confidence": round(self.confidence, 2),
            "description": self.description,
        }


# Regime → Strategy mapping
REGIME_STRATEGY_MAP: dict[str, list[str]] = {
    "trending_up": ["supertrend", "trend_momentum", "macd_momentum"],
    "trending_down": [],  # don't trade long in downtrend
    "ranging": ["mean_reversion", "grid"],
    "volatile": ["breakout", "bollinger_squeeze"],
    "squeeze": ["bollinger_squeeze", "breakout"],
    "reversal": ["rsi_divergence", "mean_reversion"],
}

REGIME_DESCRIPTIONS: dict[str, str] = {
    "trending_up": "Mercado en tendencia alcista — estrategias de trend following funcionan mejor",
    "trending_down": "Mercado en tendencia bajista — evitar compras, esperar reversal",
    "ranging": "Mercado lateral — mean reversion y grid generan income en el rango",
    "volatile": "Alta volatilidad — breakouts pueden capturar movimientos grandes",
    "squeeze": "Baja volatilidad (compresion) — prepararse para expansion inminente",
    "reversal": "Posible reversal detectada — divergencia RSI sugiere cambio de direccion",
}


def _fetch_klines(symbol: str, interval: str = "1h", limit: int = 200) -> pd.DataFrame:
    """Fetch klines from public market data API (configurable)."""
    settings = get_settings()
    canonical = normalize_symbol(symbol)
    from app.brokers.models import denormalize_symbol
    native = denormalize_symbol(canonical, settings.DEFAULT_BROKER_ID)
    base_url = settings.PUBLIC_MARKET_DATA_URL
    resp = httpx.get(
        f"{base_url}/api/v3/klines",
        params={"symbol": native, "interval": interval, "limit": limit},
        timeout=10,
    )
    resp.raise_for_status()
    raw = resp.json()
    df = pd.DataFrame(raw, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_base",
        "taker_buy_quote", "ignore",
    ])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df = df.set_index("open_time")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    return df[["open", "high", "low", "close", "volume"]]


def detect_regime(
    symbol: str,
    interval: str = "1h",
    limit: int = 200,
) -> MarketRegime:
    """Detect the current market regime for a symbol.

    Args:
        symbol: Trading symbol (e.g. "BTCUSDT")
        interval: Kline interval
        limit: Number of candles to analyze

    Returns:
        MarketRegime with classification and strategy recommendations
    """
    df = _fetch_klines(symbol, interval, limit)
    close = df["close"]

    # Calculate indicators
    adx_df = ind.adx(df, 14)
    adx_val = float(adx_df["adx"].iloc[-1]) if not np.isnan(adx_df["adx"].iloc[-1]) else 0
    plus_di = float(adx_df["plus_di"].iloc[-1]) if not np.isnan(adx_df["plus_di"].iloc[-1]) else 0
    minus_di = float(adx_df["minus_di"].iloc[-1]) if not np.isnan(adx_df["minus_di"].iloc[-1]) else 0

    rsi_series = ind.rsi(close, 14)
    rsi_val = float(rsi_series.iloc[-1]) if not rsi_series.isna().iloc[-1] else 50

    atr_pct_series = ind.atr_percentile(df, 14, 50)
    atr_pct = float(atr_pct_series.iloc[-1]) if not atr_pct_series.isna().iloc[-1] else 50

    ema_fast = ind.ema(close, 9)
    ema_slow = ind.ema(close, 21)
    ema_f = float(ema_fast.iloc[-1]) if not ema_fast.isna().iloc[-1] else 0
    ema_s = float(ema_slow.iloc[-1]) if not ema_slow.isna().iloc[-1] else 0

    bb = ind.bollinger_bands(close, 20, 2.0)
    bb_width = float(((bb["upper"] - bb["lower"]) / bb["middle"]).iloc[-1]) if not bb["middle"].isna().iloc[-1] else 0

    # Detect RSI divergence (simplified — check last 20 bars)
    reversal = False
    if len(close) >= 30:
        recent_close = close.iloc[-20:]
        recent_rsi = rsi_series.iloc[-20:]
        # Find last 2 lows in close
        close_lows = []
        rsi_lows = []
        for j in range(2, len(recent_close) - 2):
            if recent_close.iloc[j] < recent_close.iloc[j-1] and recent_close.iloc[j] < recent_close.iloc[j+1]:
                close_lows.append((j, recent_close.iloc[j]))
            if not np.isnan(recent_rsi.iloc[j]) and recent_rsi.iloc[j] < recent_rsi.iloc[j-1] and recent_rsi.iloc[j] < recent_rsi.iloc[j+1]:
                rsi_lows.append((j, recent_rsi.iloc[j]))

        if len(close_lows) >= 2 and len(rsi_lows) >= 2:
            # Price lower low, RSI higher low
            if close_lows[-1][1] < close_lows[-2][1] and rsi_lows[-1][1] > rsi_lows[-2][1] and rsi_val < 40:
                reversal = True

    # Classify regime
    if reversal:
        regime = "reversal"
    elif atr_pct > 80:
        regime = "volatile"
    elif atr_pct < 20:
        regime = "squeeze"
    elif adx_val > 25:
        if ema_f > ema_s and plus_di > minus_di:
            regime = "trending_up"
        elif ema_f < ema_s and minus_di > plus_di:
            regime = "trending_down"
        else:
            regime = "trending_up" if plus_di > minus_di else "trending_down"
    elif adx_val < 20:
        regime = "ranging"
    else:
        # ADX 20-25 — transition zone
        if ema_f > ema_s:
            regime = "trending_up"
        else:
            regime = "ranging"

    recommended = REGIME_STRATEGY_MAP.get(regime, ["trend_momentum"])
    confidence = _calculate_regime_confidence(regime, adx_val, atr_pct, rsi_val, reversal)
    description = REGIME_DESCRIPTIONS.get(regime, "Mercado sin clasificacion clara")

    return MarketRegime(
        symbol=symbol.upper(),
        regime=regime,
        adx=adx_val,
        rsi=rsi_val,
        atr_percentile=atr_pct,
        ema_fast=ema_f,
        ema_slow=ema_s,
        plus_di=plus_di,
        minus_di=minus_di,
        bb_width=bb_width,
        recommended_strategies=recommended,
        confidence=confidence,
        description=description,
        metadata={
            "interval": interval,
            "limit": limit,
            "close": float(close.iloc[-1]),
        },
    )


def _calculate_regime_confidence(
    regime: str,
    adx_val: float,
    atr_pct: float,
    rsi_val: float,
    reversal: bool,
) -> float:
    """Calculate confidence in the regime classification (0-1)."""
    if regime == "trending_up" or regime == "trending_down":
        # Higher ADX = more confidence in trend
        return min((adx_val - 20) / 30, 1.0) if adx_val > 20 else 0.3
    elif regime == "ranging":
        # Lower ADX = more confidence in range
        return min((20 - adx_val) / 20, 1.0) if adx_val < 20 else 0.3
    elif regime == "volatile":
        return min((atr_pct - 80) / 20, 1.0) if atr_pct > 80 else 0.3
    elif regime == "squeeze":
        return min((20 - atr_pct) / 20, 1.0) if atr_pct < 20 else 0.3
    elif regime == "reversal":
        return 0.6 if reversal else 0.3
    return 0.5


def detect_regimes_batch(
    symbols: list[str],
    interval: str = "1h",
    limit: int = 200,
) -> list[MarketRegime]:
    """Detect regime for multiple symbols."""
    regimes: list[MarketRegime] = []
    for sym in symbols:
        try:
            r = detect_regime(sym, interval, limit)
            regimes.append(r)
        except Exception as exc:
            logger.warning("Failed to detect regime for %s: %s", sym, exc)
    return regimes


# ─── Profile → Strategy/Symbol mapping ────────────────────────────────────────

# Map onboarding risk_tolerance to allowed strategies and symbols
PROFILE_STRATEGY_MAP: dict[str, list[str]] = {
    "conservative": ["grid", "mean_reversion", "trend_momentum"],  # safe, income-focused
    "moderate": ["trend_momentum", "mean_reversion", "breakout", "supertrend", "macd_momentum"],
    "aggressive": ["breakout", "supertrend", "macd_momentum", "bollinger_squeeze", "rsi_divergence"],
}

PROFILE_SYMBOL_FILTER: dict[str, list[str]] = {
    "conservative": ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"],  # majors only
    "moderate": [
        "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT", "AVAX/USDT",
        "LINK/USDT", "DOT/USDT", "ATOM/USDT", "NEAR/USDT", "INJ/USDT",
    ],
    "aggressive": [],  # empty = all symbols allowed
}

# Map onboarding experience_level to feature access
EXPERIENCE_FEATURES: dict[str, dict[str, Any]] = {
    "beginner": {
        "show_advanced_metrics": False,
        "default_interval": "4h",
        "show_all_strategies": False,
        "auto_pilot_default": True,
        "tooltips": True,
    },
    "intermediate": {
        "show_advanced_metrics": True,
        "default_interval": "1h",
        "show_all_strategies": True,
        "auto_pilot_default": False,
        "tooltips": True,
    },
    "advanced": {
        "show_advanced_metrics": True,
        "default_interval": "15m",
        "show_all_strategies": True,
        "auto_pilot_default": False,
        "tooltips": False,
    },
}


def get_profile_recommendations(
    risk_tolerance: str,
    experience_level: str = "beginner",
    regime: MarketRegime | None = None,
) -> dict[str, Any]:
    """Get personalized recommendations based on user profile + market regime.

    Args:
        risk_tolerance: conservative | moderate | aggressive
        experience_level: beginner | intermediate | advanced
        regime: Current market regime (optional)

    Returns:
        Dict with recommended strategies, symbols, and settings
    """
    # Base strategies from profile
    profile_strategies = PROFILE_STRATEGY_MAP.get(risk_tolerance, PROFILE_STRATEGY_MAP["moderate"])

    # Filter by regime if available
    regime_strategies = regime.recommended_strategies if regime else []
    if regime_strategies:
        # Intersection: strategies allowed by profile AND recommended by regime
        recommended = [s for s in regime_strategies if s in profile_strategies]
        if not recommended:
            # If no overlap, use profile strategies (profile takes priority for safety)
            recommended = profile_strategies[:2]
    else:
        recommended = profile_strategies[:3]

    # Symbols from profile
    allowed_symbols = PROFILE_SYMBOL_FILTER.get(risk_tolerance, [])

    # Experience features
    features = EXPERIENCE_FEATURES.get(experience_level, EXPERIENCE_FEATURES["beginner"])

    return {
        "risk_tolerance": risk_tolerance,
        "experience_level": experience_level,
        "recommended_strategies": recommended,
        "allowed_symbols": allowed_symbols,
        "features": features,
        "regime": regime.to_dict() if regime else None,
        # Risk limits from PROFILE_RISK_LIMITS (same source as AI agent)
        "risk_limits": _get_profile_risk_limits(risk_tolerance),
    }


def _get_profile_risk_limits(risk_tolerance: str) -> dict[str, Any]:
    """Get risk limits for a profile — same source as AI agent."""
    # Import from agent.py to keep single source of truth
    try:
        from app.ai.agent import PROFILE_RISK_LIMITS
        limits = PROFILE_RISK_LIMITS.get(risk_tolerance, PROFILE_RISK_LIMITS["moderate"])
        return {
            "sl_range": limits["sl_range"],
            "tp_range": limits["tp_range"],
            "min_confidence": limits["min_confidence"],
            "max_positions": limits["max_positions"],
        }
    except ImportError:
        # Fallback if import fails
        defaults = {
            "conservative": {"sl_range": (2.0, 3.0), "tp_range": (4.0, 8.0), "min_confidence": 0.7, "max_positions": 999},
            "moderate": {"sl_range": (3.0, 4.0), "tp_range": (6.0, 10.0), "min_confidence": 0.6, "max_positions": 999},
            "aggressive": {"sl_range": (4.0, 5.0), "tp_range": (8.0, 15.0), "min_confidence": 0.5, "max_positions": 999},
        }
        limits = defaults.get(risk_tolerance, defaults["moderate"])
        return {
            "sl_range": limits["sl_range"],
            "tp_range": limits["tp_range"],
            "min_confidence": limits["min_confidence"],
            "max_positions": limits["max_positions"],
        }
