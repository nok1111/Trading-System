"""Market Data Engine — procesamiento determinista de datos de mercado.

NO usa IA. Computa indicadores técnicos, liquidez, correlaciones, anomalías
y validación de datos. Cachea resultados con TTL configurable.

Entrega datos limpios a los agentes IA.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass(frozen=True)
class DataQuality:
    """Quality assessment of market data."""

    level: str  # HIGH, MEDIUM, LOW
    is_stale: bool
    gaps: int
    timestamp: float


@dataclass
class IndicatorResult:
    """Result of indicator computation for a symbol."""

    symbol: str
    timeframe: str
    rsi: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None
    ema_20: float | None = None
    ema_50: float | None = None
    ema_200: float | None = None
    atr: float | None = None
    volatility: float | None = None
    volume_relative: float | None = None
    trend: str = "unknown"  # bullish, bearish, neutral
    support_levels: list[float] = field(default_factory=list)
    resistance_levels: list[float] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class LiquidityResult:
    """Liquidity analysis for a symbol."""

    symbol: str
    spread: float | None = None
    bid_depth: float | None = None
    ask_depth: float | None = None
    order_book_imbalance: float | None = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class AnomalyResult:
    """Detected anomaly in market data."""

    symbol: str
    anomaly_type: str  # volatility_spike, volume_spike, price_gap, liquidity_drop
    severity: str  # low, medium, high
    value: float
    threshold: float
    timestamp: float = field(default_factory=time.time)


class MarketDataEngine:
    """Computes market indicators deterministically — no IA.

    All methods are synchronous and cached with TTL.
    Data is fetched from exchange APIs via the provided data provider.
    """

    def __init__(self, data_provider: Any | None = None) -> None:
        self.data_provider = data_provider
        self._indicator_cache: dict[str, tuple[IndicatorResult, float]] = {}
        self._liquidity_cache: dict[str, tuple[LiquidityResult, float]] = {}
        self._correlation_cache: tuple[dict[str, dict[str, float]], float] | None = None
        self._lock = threading.Lock()
        self._ttl = settings.MARKET_DATA_CACHE_TTL_SECONDS

    def compute_indicators(
        self,
        symbol: str,
        timeframe: str = "1h",
        candles: list[dict] | None = None,
    ) -> IndicatorResult:
        """Compute technical indicators for a symbol.

        Args:
            symbol: Trading symbol (e.g. BTCUSDT).
            timeframe: Candle timeframe (15m, 1h, 4h, 1d).
            candles: Pre-fetched candles list of {open, high, low, close, volume, timestamp}.

        Returns:
            IndicatorResult with RSI, MACD, EMAs, ATR, volatility, etc.
        """
        cache_key = f"{symbol}:{timeframe}"
        now = time.time()

        with self._lock:
            cached = self._indicator_cache.get(cache_key)
            if cached and now < cached[1]:
                return cached[0]

        if candles is None:
            candles = self._fetch_candles(symbol, timeframe)

        if not candles or len(candles) < 30:
            logger.warning("Insufficient candles for %s %s: %d", symbol, timeframe, len(candles) if candles else 0)
            return IndicatorResult(symbol=symbol, timeframe=timeframe, trend="unknown")

        closes = [float(c["close"]) for c in candles]
        highs = [float(c["high"]) for c in candles]
        lows = [float(c["low"]) for c in candles]
        volumes = [float(c["volume"]) for c in candles]

        result = IndicatorResult(
            symbol=symbol,
            timeframe=timeframe,
            rsi=self._compute_rsi(closes),
            macd=self._compute_macd(closes)[0],
            macd_signal=self._compute_macd(closes)[1],
            macd_histogram=self._compute_macd(closes)[2],
            ema_20=self._compute_ema(closes, 20),
            ema_50=self._compute_ema(closes, 50),
            ema_200=self._compute_ema(closes, 200) if len(closes) >= 200 else None,
            atr=self._compute_atr(highs, lows, closes),
            volatility=self._compute_volatility(closes),
            volume_relative=self._compute_volume_relative(volumes),
            trend=self._determine_trend(closes),
            support_levels=self._find_support_levels(lows, closes),
            resistance_levels=self._find_resistance_levels(highs, closes),
        )

        with self._lock:
            self._indicator_cache[cache_key] = (result, now + self._ttl)

        return result

    def compute_liquidity(
        self,
        symbol: str,
        order_book: dict | None = None,
    ) -> LiquidityResult:
        """Analyze liquidity from order book data.

        Args:
            symbol: Trading symbol.
            order_book: Dict with 'bids' and 'asks' lists of [price, quantity].

        Returns:
            LiquidityResult with spread, depth, imbalance.
        """
        now = time.time()

        with self._lock:
            cached = self._liquidity_cache.get(symbol)
            if cached and now < cached[1]:
                return cached[0]

        if order_book is None:
            order_book = self._fetch_order_book(symbol)

        if not order_book or not order_book.get("bids") or not order_book.get("asks"):
            return LiquidityResult(symbol=symbol)

        bids = order_book["bids"]
        asks = order_book["asks"]

        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        spread = best_ask - best_bid
        spread_pct = (spread / best_ask) * 100 if best_ask > 0 else 0

        bid_depth = sum(float(b[1]) for b in bids[:20])
        ask_depth = sum(float(a[1]) for a in asks[:20])
        total_depth = bid_depth + ask_depth
        imbalance = (bid_depth - ask_depth) / total_depth if total_depth > 0 else 0

        result = LiquidityResult(
            symbol=symbol,
            spread=spread_pct,
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            order_book_imbalance=imbalance,
        )

        with self._lock:
            self._liquidity_cache[symbol] = (result, now + self._ttl)

        return result

    def compute_correlations(
        self,
        symbols: list[str],
        returns_data: dict[str, list[float]] | None = None,
    ) -> dict[str, dict[str, float]]:
        """Compute correlation matrix between symbols.

        Args:
            symbols: List of trading symbols.
            returns_data: Pre-computed returns per symbol.

        Returns:
            Correlation matrix {symbol: {symbol: correlation}}.
        """
        now = time.time()

        with self._lock:
            if self._correlation_cache and now < self._correlation_cache[1]:
                return self._correlation_cache[0]

        if returns_data is None:
            returns_data = {}
            for sym in symbols:
                candles = self._fetch_candles(sym, "1d")
                if candles and len(candles) > 2:
                    closes = [float(c["close"]) for c in candles]
                    returns_data[sym] = [
                        (closes[i] - closes[i - 1]) / closes[i - 1]
                        for i in range(1, len(closes))
                        if closes[i - 1] > 0
                    ]

        correlations: dict[str, dict[str, float]] = {}
        for sym1 in symbols:
            correlations[sym1] = {}
            for sym2 in symbols:
                if sym1 == sym2:
                    correlations[sym1][sym2] = 1.0
                elif sym1 in returns_data and sym2 in returns_data:
                    correlations[sym1][sym2] = self._pearson_correlation(
                        returns_data[sym1], returns_data[sym2],
                    )
                else:
                    correlations[sym1][sym2] = 0.0

        with self._lock:
            self._correlation_cache = (correlations, now + self._ttl)

        return correlations

    def detect_anomalies(
        self,
        symbol: str,
        candles: list[dict] | None = None,
        indicators: IndicatorResult | None = None,
    ) -> list[AnomalyResult]:
        """Detect anomalies in market data.

        Args:
            symbol: Trading symbol.
            candles: Price candles.
            indicators: Pre-computed indicators.

        Returns:
            List of detected anomalies.
        """
        if candles is None:
            candles = self._fetch_candles(symbol, "1h")
        if indicators is None:
            indicators = self.compute_indicators(symbol, "1h", candles)

        anomalies: list[AnomalyResult] = []
        if not candles or len(candles) < 30:
            return anomalies

        closes = [float(c["close"]) for c in candles]
        [float(c["volume"]) for c in candles]

        # Volatility spike
        if indicators.volatility and indicators.volatility > 0.05:
            anomalies.append(AnomalyResult(
                symbol=symbol,
                anomaly_type="volatility_spike",
                severity="high" if indicators.volatility > 0.08 else "medium",
                value=indicators.volatility,
                threshold=0.05,
            ))

        # Volume spike
        if indicators.volume_relative and indicators.volume_relative > 3.0:
            anomalies.append(AnomalyResult(
                symbol=symbol,
                anomaly_type="volume_spike",
                severity="high" if indicators.volume_relative > 5.0 else "medium",
                value=indicators.volume_relative,
                threshold=3.0,
            ))

        # Price gap
        if len(closes) >= 2:
            gap = abs(closes[-1] - closes[-2]) / closes[-2] if closes[-2] > 0 else 0
            if gap > 0.03:
                anomalies.append(AnomalyResult(
                    symbol=symbol,
                    anomaly_type="price_gap",
                    severity="high" if gap > 0.05 else "medium",
                    value=gap,
                    threshold=0.03,
                ))

        # RSI extreme
        if indicators.rsi is not None:
            if indicators.rsi > 80:
                anomalies.append(AnomalyResult(
                    symbol=symbol,
                    anomaly_type="rsi_overbought",
                    severity="medium",
                    value=indicators.rsi,
                    threshold=80.0,
                ))
            elif indicators.rsi < 20:
                anomalies.append(AnomalyResult(
                    symbol=symbol,
                    anomaly_type="rsi_oversold",
                    severity="medium",
                    value=indicators.rsi,
                    threshold=20.0,
                ))

        return anomalies

    def validate_data(
        self,
        symbol: str,
        candles: list[dict] | None = None,
    ) -> DataQuality:
        """Validate data quality for a symbol.

        Returns:
            DataQuality with level, staleness, gaps.
        """
        if candles is None:
            candles = self._fetch_candles(symbol, "1h")

        if not candles:
            return DataQuality(level="LOW", is_stale=True, gaps=100, timestamp=time.time())

        now = time.time()
        last_timestamp = candles[-1].get("timestamp", 0)
        if isinstance(last_timestamp, str):
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(last_timestamp)
                last_timestamp = dt.timestamp()
            except (ValueError, AttributeError):
                last_timestamp = 0

        age = now - float(last_timestamp) if last_timestamp else 99999
        is_stale = age > 3600  # > 1 hour

        # Check for gaps
        gaps = 0
        for i in range(1, len(candles)):
            curr_ts = candles[i].get("timestamp", 0)
            prev_ts = candles[i - 1].get("timestamp", 0)
            if isinstance(curr_ts, str) and isinstance(prev_ts, str):
                try:
                    from datetime import datetime
                    curr = datetime.fromisoformat(curr_ts).timestamp()
                    prev = datetime.fromisoformat(prev_ts).timestamp()
                    if curr - prev > 7200:  # > 2h gap
                        gaps += 1
                except (ValueError, AttributeError):
                    pass

        if is_stale or gaps > 5:
            level = "LOW"
        elif gaps > 2 or len(candles) < 50:
            level = "MEDIUM"
        else:
            level = "HIGH"

        return DataQuality(level=level, is_stale=is_stale, gaps=gaps, timestamp=now)

    def get_all_indicators(
        self,
        symbols: list[str],
        timeframe: str = "1h",
    ) -> dict[str, IndicatorResult]:
        """Compute indicators for multiple symbols."""
        return {
            sym: self.compute_indicators(sym, timeframe)
            for sym in symbols
        }

    def clear_cache(self) -> None:
        """Clear all cached data."""
        with self._lock:
            self._indicator_cache.clear()
            self._liquidity_cache.clear()
            self._correlation_cache = None

    # --- Private computation methods ---

    def _compute_rsi(self, closes: list[float], period: int = 14) -> float | None:
        if len(closes) < period + 1:
            return None
        gains = []
        losses = []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _compute_macd(
        self,
        closes: list[float],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> tuple[float | None, float | None, float | None]:
        if len(closes) < slow + signal:
            return None, None, None

        ema_fast = self._compute_ema(closes, fast)
        ema_slow = self._compute_ema(closes, slow)
        if ema_fast is None or ema_slow is None:
            return None, None, None

        macd = ema_fast - ema_slow

        # Compute signal line (EMA of MACD values)
        macd_values = []
        for i in range(slow, len(closes)):
            ef = self._compute_ema(closes[:i + 1], fast)
            es = self._compute_ema(closes[:i + 1], slow)
            if ef is not None and es is not None:
                macd_values.append(ef - es)

        if len(macd_values) < signal:
            return macd, None, None

        signal_line = sum(macd_values[-signal:]) / signal
        histogram = macd - signal_line
        return macd, signal_line, histogram

    def _compute_ema(self, values: list[float], period: int) -> float | None:
        if len(values) < period:
            return None
        multiplier = 2 / (period + 1)
        ema = sum(values[:period]) / period
        for val in values[period:]:
            ema = (val - ema) * multiplier + ema
        return ema

    def _compute_atr(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int = 14,
    ) -> float | None:
        if len(closes) < period + 1:
            return None
        true_ranges = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            true_ranges.append(tr)
        return sum(true_ranges[-period:]) / period

    def _compute_volatility(self, closes: list[float]) -> float | None:
        if len(closes) < 20:
            return None
        returns = [
            (closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(1, len(closes))
            if closes[i - 1] > 0
        ]
        if len(returns) < 10:
            return None
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        return variance ** 0.5

    def _compute_volume_relative(self, volumes: list[float]) -> float | None:
        if len(volumes) < 20:
            return None
        avg = sum(volumes[-20:-1]) / 19
        if avg == 0:
            return None
        return volumes[-1] / avg

    def _determine_trend(self, closes: list[float]) -> str:
        if len(closes) < 50:
            return "unknown"
        ema_20 = self._compute_ema(closes, 20)
        ema_50 = self._compute_ema(closes, 50)
        if ema_20 is None or ema_50 is None:
            return "unknown"
        if ema_20 > ema_50 * 1.001:
            return "bullish"
        if ema_20 < ema_50 * 0.999:
            return "bearish"
        return "neutral"

    def _find_support_levels(
        self,
        lows: list[float],
        closes: list[float],
        lookback: int = 50,
    ) -> list[float]:
        lookback = min(lookback, len(lows))
        recent_lows = lows[-lookback:]
        sorted_lows = sorted(recent_lows)
        # Return bottom 3 unique levels
        levels = []
        for low in sorted_lows:
            if not levels or abs(low - levels[-1]) / levels[-1] > 0.005:
                levels.append(low)
            if len(levels) >= 3:
                break
        return levels

    def _find_resistance_levels(
        self,
        highs: list[float],
        closes: list[float],
        lookback: int = 50,
    ) -> list[float]:
        lookback = min(lookback, len(highs))
        recent_highs = highs[-lookback:]
        sorted_highs = sorted(recent_highs, reverse=True)
        levels = []
        for high in sorted_highs:
            if not levels or abs(high - levels[-1]) / levels[-1] > 0.005:
                levels.append(high)
            if len(levels) >= 3:
                break
        return levels

    def _pearson_correlation(
        self,
        x: list[float],
        y: list[float],
    ) -> float:
        n = min(len(x), len(y))
        if n < 2:
            return 0.0
        x = x[:n]
        y = y[:n]
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        denom_x = sum((xi - mean_x) ** 2 for xi in x) ** 0.5
        denom_y = sum((yi - mean_y) ** 2 for yi in y) ** 0.5
        if denom_x == 0 or denom_y == 0:
            return 0.0
        return numerator / (denom_x * denom_y)

    # --- Data fetching (delegated to data_provider) ---

    def _fetch_candles(self, symbol: str, timeframe: str) -> list[dict]:
        if self.data_provider and hasattr(self.data_provider, "get_candles"):
            try:
                return self.data_provider.get_candles(symbol, timeframe)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to fetch candles for %s: %s", symbol, exc)
        return []

    def _fetch_order_book(self, symbol: str) -> dict:
        if self.data_provider and hasattr(self.data_provider, "get_order_book"):
            try:
                return self.data_provider.get_order_book(symbol)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to fetch order book for %s: %s", symbol, exc)
        return {}


# Singleton instance
_engine_instance: MarketDataEngine | None = None
_engine_lock = threading.Lock()


def get_market_data_engine() -> MarketDataEngine:
    """Get or create the singleton MarketDataEngine instance."""
    global _engine_instance
    with _engine_lock:
        if _engine_instance is None:
            _engine_instance = MarketDataEngine()
        return _engine_instance
