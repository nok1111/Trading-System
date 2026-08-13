"""Technical analysis service — computes indicators and generates signals.

Uses the indicators module (RSI, MACD, EMA, ATR, Bollinger, volume) to analyze
a symbol and produce a structured technical analysis with trend direction,
momentum, volatility, and actionable signals.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any

import httpx
import pandas as pd

from app.brokers.models import denormalize_symbol, normalize_symbol
from app.config import get_settings
from app.indicators import indicators as ind
from app.services.market_data_service import get_market_data_service

logger = logging.getLogger(__name__)


@dataclass
class TechnicalAnalysis:
    """Structured technical analysis result for a symbol."""

    symbol: str
    interval: str
    current_price: float
    trend: str  # "bullish", "bearish", "neutral"
    trend_strength: str  # "strong", "moderate", "weak"
    rsi: float
    rsi_signal: str  # "oversold", "neutral", "overbought"
    macd_histogram: float
    macd_signal: str  # "bullish", "bearish", "neutral"
    ema_fast: float
    ema_slow: float
    ema_cross: str  # "golden_cross", "death_cross", "none"
    atr: float
    atr_pct: float  # ATR as % of price
    bollinger_position: str  # "upper", "middle", "lower", "above_upper", "below_lower"
    bollinger_upper: float
    bollinger_lower: float
    volume_relative: float
    volume_signal: str  # "high", "normal", "low"
    support: float
    resistance: float
    signal: str  # "STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"
    signal_reasons: list[str] = field(default_factory=list)
    stop_loss: float | None = None
    take_profit: float | None = None
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def fetch_klines(symbol: str, interval: str = "1h", limit: int = 200) -> pd.DataFrame:
    """Fetch klines from Binance public API and return as DataFrame."""
    base_url = get_market_data_service()._get_public_base_url()
    canonical = normalize_symbol(symbol)
    native = denormalize_symbol(canonical, get_settings().DEFAULT_BROKER_ID)
    resp = httpx.get(
        f"{base_url}/api/v3/klines",
        params={"symbol": native, "interval": interval, "limit": limit},
        timeout=10,
    )
    resp.raise_for_status()
    raw = resp.json()
    df = pd.DataFrame(
        raw,
        columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore",
        ],
    )
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df = df.set_index("open_time")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    return df[["open", "high", "low", "close", "volume"]]


def analyze_symbol(symbol: str, interval: str = "1h", limit: int = 200) -> TechnicalAnalysis:
    """Compute full technical analysis for a symbol.

    Args:
        symbol: Trading symbol (e.g. "BTCUSDT")
        interval: Kline interval (1m, 5m, 15m, 1h, 4h, 1d)
        limit: Number of candles to fetch

    Returns:
        TechnicalAnalysis with all indicators and a signal.
    """
    df = fetch_klines(symbol, interval, limit)
    return _analyze_df(symbol, interval, df)


def _analyze_df(symbol: str, interval: str, df: pd.DataFrame) -> TechnicalAnalysis:
    """Analyze a DataFrame of OHLCV data."""
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]
    current_price = float(close.iloc[-1])

    # EMAs
    ema_fast = ind.ema(close, 9)
    ema_slow = ind.ema(close, 21)
    ema_trend = ind.ema(close, 50)
    ema_fast_val = float(ema_fast.iloc[-1])
    ema_slow_val = float(ema_slow.iloc[-1])
    ema_trend_val = float(ema_trend.iloc[-1]) if not ema_trend.isna().iloc[-1] else ema_slow_val

    # RSI
    rsi_series = ind.rsi(close, 14)
    rsi_val = float(rsi_series.iloc[-1]) if not rsi_series.isna().iloc[-1] else 50.0

    # MACD
    macd_df = ind.macd(close)
    macd_hist = float(macd_df["histogram"].iloc[-1]) if not macd_df["histogram"].isna().iloc[-1] else 0.0

    # ATR
    atr_series = ind.atr(df, 14)
    atr_val = float(atr_series.iloc[-1]) if not atr_series.isna().iloc[-1] else 0.0
    atr_pct = (atr_val / current_price * 100) if current_price > 0 else 0.0

    # Bollinger Bands
    bb_df = ind.bollinger_bands(close, 20, 2.0)
    bb_upper = float(bb_df["upper"].iloc[-1]) if not bb_df["upper"].isna().iloc[-1] else current_price * 1.02
    bb_lower = float(bb_df["lower"].iloc[-1]) if not bb_df["lower"].isna().iloc[-1] else current_price * 0.98
    bb_middle = float(bb_df["middle"].iloc[-1]) if not bb_df["middle"].isna().iloc[-1] else current_price

    if current_price > bb_upper:
        bb_pos = "above_upper"
    elif current_price < bb_lower:
        bb_pos = "below_lower"
    elif current_price > bb_middle:
        bb_pos = "upper"
    else:
        bb_pos = "lower"

    # Volume
    vol_rel_series = ind.relative_volume(volume, 20)
    vol_rel = float(vol_rel_series.iloc[-1]) if not vol_rel_series.isna().iloc[-1] else 1.0

    # Support / Resistance (recent swing high/low)
    lookback = min(50, len(df))
    recent = df.iloc[-lookback:]
    support = float(recent["low"].min())
    resistance = float(recent["high"].max())

    # Trend determination
    if ema_fast_val > ema_slow_val > ema_trend_val:
        trend = "bullish"
        trend_strength = "strong"
    elif ema_fast_val > ema_slow_val:
        trend = "bullish"
        trend_strength = "moderate"
    elif ema_fast_val < ema_slow_val < ema_trend_val:
        trend = "bearish"
        trend_strength = "strong"
    elif ema_fast_val < ema_slow_val:
        trend = "bearish"
        trend_strength = "moderate"
    else:
        trend = "neutral"
        trend_strength = "weak"

    # EMA cross detection
    if len(ema_fast) >= 2 and len(ema_slow) >= 2:
        prev_fast = float(ema_fast.iloc[-2])
        prev_slow = float(ema_slow.iloc[-2])
        if prev_fast <= prev_slow and ema_fast_val > ema_slow_val:
            ema_cross = "golden_cross"
        elif prev_fast >= prev_slow and ema_fast_val < ema_slow_val:
            ema_cross = "death_cross"
        else:
            ema_cross = "none"
    else:
        ema_cross = "none"

    # RSI signal
    if rsi_val < 30:
        rsi_signal = "oversold"
    elif rsi_val > 70:
        rsi_signal = "overbought"
    else:
        rsi_signal = "neutral"

    # MACD signal
    if macd_hist > 0:
        macd_signal = "bullish"
    elif macd_hist < 0:
        macd_signal = "bearish"
    else:
        macd_signal = "neutral"

    # Volume signal
    if vol_rel > 1.5:
        volume_signal = "high"
    elif vol_rel < 0.5:
        volume_signal = "low"
    else:
        volume_signal = "normal"

    # Generate composite signal
    reasons: list[str] = []
    buy_score = 0
    sell_score = 0

    if trend == "bullish":
        buy_score += 2 if trend_strength == "strong" else 1
        reasons.append(f"EMA trend bullish ({trend_strength})")
    elif trend == "bearish":
        sell_score += 2 if trend_strength == "strong" else 1
        reasons.append(f"EMA trend bearish ({trend_strength})")

    if ema_cross == "golden_cross":
        buy_score += 2
        reasons.append("Golden cross (EMA9 crossed above EMA21)")
    elif ema_cross == "death_cross":
        sell_score += 2
        reasons.append("Death cross (EMA9 crossed below EMA21)")

    if rsi_signal == "oversold":
        buy_score += 1
        reasons.append(f"RSI oversold ({rsi_val:.0f})")
    elif rsi_signal == "overbought":
        sell_score += 1
        reasons.append(f"RSI overbought ({rsi_val:.0f})")

    if macd_signal == "bullish":
        buy_score += 1
        reasons.append("MACD histogram positive")
    elif macd_signal == "bearish":
        sell_score += 1
        reasons.append("MACD histogram negative")

    if bb_pos == "below_lower":
        buy_score += 1
        reasons.append("Price below Bollinger lower band (potential bounce)")
    elif bb_pos == "above_upper":
        sell_score += 1
        reasons.append("Price above Bollinger upper band (potential reversal)")

    if volume_signal == "high":
        reasons.append(f"High volume ({vol_rel:.1f}x average)")
        if trend == "bullish":
            buy_score += 1
        elif trend == "bearish":
            sell_score += 1

    # Determine final signal
    if buy_score >= 5:
        signal = "STRONG_BUY"
    elif buy_score >= 3:
        signal = "BUY"
    elif sell_score >= 5:
        signal = "STRONG_SELL"
    elif sell_score >= 3:
        signal = "SELL"
    else:
        signal = "HOLD"
        reasons.append("No clear directional bias")

    # Calculate stop-loss and take-profit based on ATR
    stop_loss = None
    take_profit = None
    if signal in ("BUY", "STRONG_BUY"):
        stop_loss = current_price - (atr_val * 1.5)
        take_profit = current_price + (atr_val * 3.0)
    elif signal in ("SELL", "STRONG_SELL"):
        stop_loss = current_price + (atr_val * 1.5)
        take_profit = current_price - (atr_val * 3.0)

    from datetime import UTC, datetime
    return TechnicalAnalysis(
        symbol=symbol,
        interval=interval,
        current_price=round(current_price, 6),
        trend=trend,
        trend_strength=trend_strength,
        rsi=round(rsi_val, 2),
        rsi_signal=rsi_signal,
        macd_histogram=round(macd_hist, 6),
        macd_signal=macd_signal,
        ema_fast=round(ema_fast_val, 6),
        ema_slow=round(ema_slow_val, 6),
        ema_cross=ema_cross,
        atr=round(atr_val, 6),
        atr_pct=round(atr_pct, 2),
        bollinger_position=bb_pos,
        bollinger_upper=round(bb_upper, 6),
        bollinger_lower=round(bb_lower, 6),
        volume_relative=round(vol_rel, 2),
        volume_signal=volume_signal,
        support=round(support, 6),
        resistance=round(resistance, 6),
        signal=signal,
        signal_reasons=reasons,
        stop_loss=round(stop_loss, 6) if stop_loss else None,
        take_profit=round(take_profit, 6) if take_profit else None,
        timestamp=datetime.now(UTC).isoformat(),
    )
