"""Multi-Timeframe (MTF) Confirmation — align entries with higher & lower TF trends.

Confirms trading signals by checking:
- HIGHER timeframe (e.g. 4h): trend direction (EMA9 vs EMA21, ADX, +DI/-DI)
- PRIMARY timeframe (e.g. 1h): the signal's own timeframe
- LOWER timeframe (e.g. 15m): entry precision (RSI not overbought, near support)

This module provides:
- ``MultiTimeframeAnalyzer`` — class that fetches all 3 timeframes and produces
  a confirmation dict with ``confirmed``, ``confidence_boost`` and ``reasons``.
- ``get_mtf_trend`` — standalone function returning trend direction for a TF.
- ``confirm_entry_mtf`` — convenience wrapper for quick entry confirmation.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

import httpx
import numpy as np
import pandas as pd

from app.brokers.models import denormalize_symbol, normalize_symbol
from app.config import get_settings
from app.indicators import indicators as ind
from app.services.market_data_service import get_market_data_service

logger = logging.getLogger(__name__)

# ─── Timeframe hierarchy ──────────────────────────────────────────────────────
# Ordered from lowest to highest resolution. Used to pick the adjacent higher
# and lower timeframes relative to a given primary interval.
TIMEFRAME_ORDER: list[str] = [
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1M",
]

# Pre-computed index map for O(1) lookups.
_TF_INDEX: dict[str, int] = {tf: i for i, tf in enumerate(TIMEFRAME_ORDER)}


# ─── Defaults ─────────────────────────────────────────────────────────────────
DEFAULT_LIMIT = 200
HTTP_TIMEOUT = 15

# RSI thresholds
RSI_OVERBOUGHT = 70.0
RSI_OVERSOLD = 30.0

# ADX threshold for trend strength
ADX_TREND_THRESHOLD = 20.0

# Confidence boost constants
BOOST_BULLISH = 0.15
PENALTY_BEARISH = -0.20
BOOST_OVERSOLD = 0.10
MAX_BOOST = 0.30

# Bollinger / Donchian lookback for "near support" detection
SUPPORT_LOOKBACK = 20


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _higher_tf(interval: str) -> str:
    """Return the next higher timeframe relative to ``interval``.

    Falls back to the highest available timeframe if ``interval`` is already
    the highest one.
    """
    idx = _TF_INDEX.get(interval)
    if idx is None or idx >= len(TIMEFRAME_ORDER) - 1:
        return TIMEFRAME_ORDER[-1]
    return TIMEFRAME_ORDER[idx + 1]


def _lower_tf(interval: str) -> str:
    """Return the next lower timeframe relative to ``interval``.

    Falls back to the lowest available timeframe if ``interval`` is already
    the lowest one.
    """
    idx = _TF_INDEX.get(interval)
    if idx is None or idx <= 0:
        return TIMEFRAME_ORDER[0]
    return TIMEFRAME_ORDER[idx - 1]


def _fetch_klines(symbol: str, interval: str, limit: int = DEFAULT_LIMIT) -> pd.DataFrame:
    """Fetch klines from Binance and return a DataFrame.

    Args:
        symbol: Trading symbol, e.g. ``"BTCUSDT"``.
        interval: Binance kline interval, e.g. ``"1h"``.
        limit: Number of candles to fetch.

    Returns:
        DataFrame indexed by ``open_time`` (datetime) with columns
        ``open, high, low, close, volume`` (all float).
    """
    base_url = get_market_data_service()._get_public_base_url()
    canonical = normalize_symbol(symbol)
    native = denormalize_symbol(canonical, get_settings().DEFAULT_BROKER_ID)
    resp = httpx.get(
        f"{base_url}/api/v3/klines",
        params={"symbol": native, "interval": interval, "limit": limit},
        timeout=HTTP_TIMEOUT,
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


def _safe_last(series: pd.Series, default: float = 0.0) -> float:
    """Return the last non-NaN value of a Series, or ``default``."""
    if series is None or series.empty:
        return default
    val = series.iloc[-1]
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    return float(val)


# ─── Core trend function ──────────────────────────────────────────────────────
def get_mtf_trend(symbol: str, interval: str) -> dict[str, Any]:
    """Return the trend direction for a given timeframe.

    Fetches klines for ``interval`` and calculates EMA9, EMA21, ADX(14) and
    RSI(14). Classifies the trend as bullish, bearish, or neutral.

    Args:
        symbol: Trading symbol, e.g. ``"BTCUSDT"``.
        interval: Binance kline interval, e.g. ``"1h"`` or ``"4h"``.

    Returns:
        Dict with keys::

            {
                "trend": "bullish" | "bearish" | "neutral",
                "adx": float,
                "rsi": float,
                "ema_fast": float,
                "ema_slow": float,
            }

        On error, returns a neutral trend with zeroed indicator values.
    """
    try:
        df = _fetch_klines(symbol, interval, DEFAULT_LIMIT)
        if df.empty or len(df) < 30:
            logger.warning(
                "get_mtf_trend: insufficient data for %s %s (rows=%d)",
                symbol, interval, len(df) if not df.empty else 0,
            )
            return _neutral_trend()

        close = df["close"]

        ema_fast_series = ind.ema(close, 9)
        ema_slow_series = ind.ema(close, 21)
        rsi_series = ind.rsi(close, 14)
        adx_df = ind.adx(df, 14)

        ema_fast = _safe_last(ema_fast_series)
        ema_slow = _safe_last(ema_slow_series)
        rsi_val = _safe_last(rsi_series, default=50.0)
        adx_val = _safe_last(adx_df["adx"])
        plus_di = _safe_last(adx_df["plus_di"])
        minus_di = _safe_last(adx_df["minus_di"])

        # Classify trend
        if (
            ema_fast > ema_slow
            and adx_val > ADX_TREND_THRESHOLD
            and plus_di > minus_di
        ):
            trend: Literal["bullish", "bearish", "neutral"] = "bullish"
        elif (
            ema_fast < ema_slow
            and adx_val > ADX_TREND_THRESHOLD
            and minus_di > plus_di
        ):
            trend = "bearish"
        else:
            trend = "neutral"

        return {
            "trend": trend,
            "adx": round(adx_val, 2),
            "rsi": round(rsi_val, 2),
            "ema_fast": round(ema_fast, 6),
            "ema_slow": round(ema_slow, 6),
        }

    except Exception as exc:  # noqa: BLE001 — intentionally broad for robustness
        logger.error("get_mtf_trend error for %s %s: %s", symbol, interval, exc)
        return _neutral_trend()


def _neutral_trend() -> dict[str, Any]:
    """Return a neutral trend dict used on errors / insufficient data."""
    return {
        "trend": "neutral",
        "adx": 0.0,
        "rsi": 50.0,
        "ema_fast": 0.0,
        "ema_slow": 0.0,
    }


# ─── Analyzer class ───────────────────────────────────────────────────────────
class MultiTimeframeAnalyzer:
    """Multi-Timeframe confirmation analyzer.

    Uses three timeframes to confirm a trading signal:
    - **Higher TF** (e.g. 4h): confirms the dominant trend direction.
    - **Primary TF** (e.g. 1h): the timeframe the signal originates from.
    - **Lower TF** (e.g. 15m): checks entry precision (RSI, proximity to support).

    Args:
        primary_interval: The signal's own timeframe, e.g. ``"1h"``.
        higher_interval: Trend-confirmation timeframe. If ``None``, auto-selected
            as the next higher timeframe from ``primary_interval``.
        lower_interval: Entry-precision timeframe. If ``None``, auto-selected
            as the next lower timeframe from ``primary_interval``.
        limit: Number of candles to fetch per timeframe.
    """

    def __init__(
        self,
        primary_interval: str = "1h",
        higher_interval: str | None = None,
        lower_interval: str | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> None:
        self.primary_interval = primary_interval
        self.higher_interval = higher_interval or _higher_tf(primary_interval)
        self.lower_interval = lower_interval or _lower_tf(primary_interval)
        self.limit = limit

    # ── Data fetching ──────────────────────────────────────────────────────
    def _fetch_all(self, symbol: str) -> dict[str, pd.DataFrame]:
        """Fetch klines for all three timeframes.

        Returns:
            Dict mapping each timeframe label to its DataFrame.
        """
        return {
            self.higher_interval: _fetch_klines(symbol, self.higher_interval, self.limit),
            self.primary_interval: _fetch_klines(symbol, self.primary_interval, self.limit),
            self.lower_interval: _fetch_klines(symbol, self.lower_interval, self.limit),
        }

    # ── Higher TF analysis ─────────────────────────────────────────────────
    def _analyze_higher_tf(self, df: pd.DataFrame) -> dict[str, Any]:
        """Analyze the higher timeframe for trend direction.

        Determines bullish/bearish/neutral based on EMA9 vs EMA21, ADX > 20,
        and +DI vs -DI.
        """
        close = df["close"]
        ema_fast = _safe_last(ind.ema(close, 9))
        ema_slow = _safe_last(ind.ema(close, 21))
        adx_df = ind.adx(df, 14)
        adx_val = _safe_last(adx_df["adx"])
        plus_di = _safe_last(adx_df["plus_di"])
        minus_di = _safe_last(adx_df["minus_di"])

        if (
            ema_fast > ema_slow
            and adx_val > ADX_TREND_THRESHOLD
            and plus_di > minus_di
        ):
            trend: Literal["bullish", "bearish", "neutral"] = "bullish"
        elif (
            ema_fast < ema_slow
            and adx_val > ADX_TREND_THRESHOLD
            and minus_di > plus_di
        ):
            trend = "bearish"
        else:
            trend = "neutral"

        return {
            "trend": trend,
            "adx": adx_val,
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "plus_di": plus_di,
            "minus_di": minus_di,
        }

    # ── Lower TF analysis ──────────────────────────────────────────────────
    def _analyze_lower_tf(self, df: pd.DataFrame) -> dict[str, Any]:
        """Analyze the lower timeframe for entry precision.

        Checks RSI (overbought / oversold) and whether price is near support
        (Bollinger lower band or Donchian lower channel).
        """
        close = df["close"]
        rsi_val = _safe_last(ind.rsi(close, 14), default=50.0)

        # Near support: price within 0.5% of Bollinger lower band or Donchian low
        bb = ind.bollinger_bands(close, SUPPORT_LOOKBACK, 2.0)
        dc = ind.donchian_channels(df, SUPPORT_LOOKBACK)
        bb_lower = _safe_last(bb["lower"])
        dc_lower = _safe_last(dc["lower"])
        last_close = _safe_last(close)

        near_support = False
        if last_close > 0 and bb_lower > 0:
            near_support = near_support or (last_close <= bb_lower * 1.005)
        if last_close > 0 and dc_lower > 0:
            near_support = near_support or (last_close <= dc_lower * 1.005)

        return {
            "rsi": rsi_val,
            "oversold": rsi_val < RSI_OVERSOLD,
            "overbought": rsi_val > RSI_OVERBOUGHT,
            "near_support": near_support,
            "close": last_close,
        }

    # ── Public API ─────────────────────────────────────────────────────────
    def get_mtf_confirmation(
        self,
        symbol: str,
        primary_interval: str | None = None,
        entry_signal_type: str = "long",
    ) -> dict[str, Any]:
        """Produce a multi-timeframe confirmation for a trading signal.

        Args:
            symbol: Trading symbol, e.g. ``"BTCUSDT"``.
            primary_interval: Override the primary timeframe. If ``None`` the
                instance default is used.
            entry_signal_type: ``"long"`` or ``"short"``. Affects how the
                higher-TF trend is interpreted for confirmation.

        Returns:
            Dict with keys::

                {
                    "higher_tf_trend": "bullish" | "bearish" | "neutral",
                    "higher_tf_adx": float,
                    "lower_tf_rsi": float,
                    "lower_tf_oversold": bool,
                    "confirmed": bool,
                    "confidence_boost": float,   # 0.0 to 0.3
                    "reasons": list[str],
                }

            On any error, a neutral confirmation (``confirmed=False``,
            ``confidence_boost=0.0``) is returned.
        """
        if primary_interval:
            self.primary_interval = primary_interval
            self.higher_interval = _higher_tf(self.primary_interval)
            self.lower_interval = _lower_tf(self.primary_interval)

        try:
            data = self._fetch_all(symbol)

            higher_df = data[self.higher_interval]
            lower_df = data[self.lower_interval]

            if higher_df.empty or lower_df.empty:
                logger.warning(
                    "MTF: empty data for %s (higher=%s, lower=%s)",
                    symbol, self.higher_interval, self.lower_interval,
                )
                return self._neutral_confirmation("insufficient data")

            higher = self._analyze_higher_tf(higher_df)
            lower = self._analyze_lower_tf(lower_df)

            reasons: list[str] = []
            confirmed = False
            confidence_boost = 0.0

            higher_trend = higher["trend"]
            is_long = entry_signal_type.lower() == "long"

            # ── Higher TF trend gate ────────────────────────────────────────
            if is_long:
                if higher_trend == "bullish":
                    confirmed = True
                    confidence_boost += BOOST_BULLISH
                    reasons.append(
                        f"Higher TF ({self.higher_interval}) bullish: "
                        f"EMA9>{higher['ema_fast']:.2f} vs EMA21>{higher['ema_slow']:.2f}, "
                        f"ADX={higher['adx']:.1f}"
                    )
                elif higher_trend == "bearish":
                    confirmed = False
                    confidence_boost += PENALTY_BEARISH
                    reasons.append(
                        f"Higher TF ({self.higher_interval}) bearish — "
                        f"counter-trend long rejected (ADX={higher['adx']:.1f})"
                    )
                else:
                    confirmed = True
                    confidence_boost += 0.0
                    reasons.append(
                        f"Higher TF ({self.higher_interval}) neutral — "
                        f"no trend confirmation (ADX={higher['adx']:.1f})"
                    )
            else:  # short signal
                if higher_trend == "bearish":
                    confirmed = True
                    confidence_boost += BOOST_BULLISH
                    reasons.append(
                        f"Higher TF ({self.higher_interval}) bearish: "
                        f"EMA9<{higher['ema_fast']:.2f} vs EMA21<{higher['ema_slow']:.2f}, "
                        f"ADX={higher['adx']:.1f}"
                    )
                elif higher_trend == "bullish":
                    confirmed = False
                    confidence_boost += PENALTY_BEARISH
                    reasons.append(
                        f"Higher TF ({self.higher_interval}) bullish — "
                        f"counter-trend short rejected (ADX={higher['adx']:.1f})"
                    )
                else:
                    confirmed = True
                    confidence_boost += 0.0
                    reasons.append(
                        f"Higher TF ({self.higher_interval}) neutral — "
                        f"no trend confirmation (ADX={higher['adx']:.1f})"
                    )

            # ── Lower TF entry precision ────────────────────────────────────
            rsi_val = lower["rsi"]
            if is_long:
                if lower["overbought"]:
                    confirmed = False
                    reasons.append(
                        f"Lower TF ({self.lower_interval}) RSI={rsi_val:.1f} > "
                        f"{RSI_OVERBOUGHT} — overbought, wait for pullback"
                    )
                elif lower["oversold"]:
                    confidence_boost += BOOST_OVERSOLD
                    reasons.append(
                        f"Lower TF ({self.lower_interval}) RSI={rsi_val:.1f} < "
                        f"{RSI_OVERSOLD} — oversold, favorable entry"
                    )
                else:
                    reasons.append(
                        f"Lower TF ({self.lower_interval}) RSI={rsi_val:.1f} — "
                        f"within normal range"
                    )

                if lower["near_support"]:
                    confidence_boost += 0.05
                    reasons.append(
                        f"Lower TF ({self.lower_interval}) price near support "
                        f"(BB lower / Donchian low)"
                    )
            else:  # short
                if lower["oversold"]:
                    confirmed = False
                    reasons.append(
                        f"Lower TF ({self.lower_interval}) RSI={rsi_val:.1f} < "
                        f"{RSI_OVERSOLD} — oversold, wait for bounce before shorting"
                    )
                elif lower["overbought"]:
                    confidence_boost += BOOST_OVERSOLD
                    reasons.append(
                        f"Lower TF ({self.lower_interval}) RSI={rsi_val:.1f} > "
                        f"{RSI_OVERBOUGHT} — overbought, favorable short entry"
                    )
                else:
                    reasons.append(
                        f"Lower TF ({self.lower_interval}) RSI={rsi_val:.1f} — "
                        f"within normal range"
                    )

            # Clamp confidence boost to [−0.20, 0.30]
            confidence_boost = max(-0.20, min(MAX_BOOST, confidence_boost))

            return {
                "higher_tf_trend": higher_trend,
                "higher_tf_adx": round(higher["adx"], 2),
                "lower_tf_rsi": round(rsi_val, 2),
                "lower_tf_oversold": lower["oversold"],
                "confirmed": confirmed,
                "confidence_boost": round(confidence_boost, 4),
                "reasons": reasons,
            }

        except Exception as exc:  # noqa: BLE001 — return neutral on any error
            logger.error("MTF confirmation error for %s: %s", symbol, exc)
            return self._neutral_confirmation(str(exc))

    @staticmethod
    def _neutral_confirmation(reason: str = "error") -> dict[str, Any]:
        """Return a neutral confirmation dict (used on errors)."""
        return {
            "higher_tf_trend": "neutral",
            "higher_tf_adx": 0.0,
            "lower_tf_rsi": 50.0,
            "lower_tf_oversold": False,
            "confirmed": False,
            "confidence_boost": 0.0,
            "reasons": [f"MTF confirmation skipped: {reason}"],
        }


# ─── Convenience function ────────────────────────────────────────────────────
def confirm_entry_mtf(
    symbol: str,
    primary_interval: str,
    strategy_name: str = "trend_momentum",
) -> dict[str, Any]:
    """Quick multi-timeframe entry confirmation.

    Gets the higher timeframe trend and the lower timeframe RSI, then returns
    a confirmation dict.

    Rules:
    - Higher TF bullish  -> confirmed=True,  boost=+0.15
    - Higher TF bearish  -> confirmed=False, boost=-0.20 (penalty)
    - Higher TF neutral  -> confirmed=True,  boost=0.0
    - Lower TF RSI > 70  -> confirmed=False (overbought, wait)
    - Lower TF RSI < 30  -> boost += 0.10 (oversold, better entry)

    On error, returns a neutral confirmation.
    """
    h_interval = _higher_tf(primary_interval)
    l_interval = _lower_tf(primary_interval)

    # Step 1: Higher TF trend
    higher = get_mtf_trend(symbol, h_interval)
    higher_trend = higher["trend"]
    higher_adx = higher["adx"]

    confirmed = False
    confidence_boost = 0.0
    reasons: list[str] = []

    if higher_trend == "bullish":
        confirmed = True
        confidence_boost = BOOST_BULLISH
        reasons.append(f"Higher TF {h_interval} bullish (ADX={higher_adx:.1f})")
    elif higher_trend == "bearish":
        confirmed = False
        confidence_boost = PENALTY_BEARISH
        reasons.append(f"Higher TF {h_interval} bearish (ADX={higher_adx:.1f})")
    else:
        confirmed = True
        reasons.append(f"Higher TF {h_interval} neutral (ADX={higher_adx:.1f})")

    # Step 2: Lower TF RSI
    try:
        lower_df = _fetch_klines(symbol, l_interval, DEFAULT_LIMIT)
        if lower_df is None or lower_df.empty or len(lower_df) < 15:
            lower_rsi = 50.0
            reasons.append(f"Lower TF {l_interval} sin datos — RSI skip")
        else:
            lower_rsi = _safe_last(ind.rsi(lower_df["close"], 14), default=50.0)
            if lower_rsi > RSI_OVERBOUGHT:
                confirmed = False
                reasons.append(f"Lower TF {l_interval} RSI={lower_rsi:.1f} overbought")
            elif lower_rsi < RSI_OVERSOLD:
                confidence_boost += BOOST_OVERSOLD
                reasons.append(f"Lower TF {l_interval} RSI={lower_rsi:.1f} oversold (+{BOOST_OVERSOLD})")
            else:
                reasons.append(f"Lower TF {l_interval} RSI={lower_rsi:.1f} normal")
    except Exception as exc:
        lower_rsi = 50.0
        reasons.append(f"Lower TF error: {exc}")

    confidence_boost = max(-0.20, min(MAX_BOOST, confidence_boost))

    return {
        "symbol": symbol.upper(),
        "strategy": strategy_name,
        "primary_interval": primary_interval,
        "higher_interval": h_interval,
        "lower_interval": l_interval,
        "higher_tf_trend": higher_trend,
        "higher_tf_adx": round(higher_adx, 2),
        "lower_tf_rsi": round(lower_rsi, 2),
        "confirmed": confirmed,
        "confidence_boost": round(confidence_boost, 4),
        "reasons": reasons,
    }
