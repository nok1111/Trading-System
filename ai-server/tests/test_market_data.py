"""Tests for Market Data Engine — deterministic indicator computation."""

from __future__ import annotations

import time

import pytest

from app.services.market_data import (
    MarketDataEngine,
)


def _make_candles(n: int = 100, base_price: float = 50000.0, trend: float = 0.0) -> list[dict]:
    """Generate n synthetic candles with optional upward trend."""
    candles = []
    price = base_price
    base_ts = time.time() - n * 3600  # n hours ago
    for i in range(n):
        vol = 1000 + (i % 10) * 50
        high = price + 100 + (i % 5) * 20
        low = price - 80 - (i % 3) * 15
        candles.append({
            "open": price,
            "high": high,
            "low": low,
            "close": price + trend,
            "volume": vol,
            "timestamp": base_ts + i * 3600,  # epoch seconds, 1h apart
        })
        price = price + trend
    return candles


def _make_order_book() -> dict:
    """Generate a synthetic order book with a spread."""
    bids = [[49995 - i * 5, 10 - i * 0.3] for i in range(20)]
    asks = [[50005 + i * 5, 10 - i * 0.3] for i in range(20)]
    return {"bids": bids, "asks": asks}


class TestIndicatorComputation:
    def test_rsi_computation(self):
        engine = MarketDataEngine()
        candles = _make_candles(100, trend=10)
        result = engine.compute_indicators("BTCUSDT", "1h", candles)
        assert result.rsi is not None
        assert 0 <= result.rsi <= 100

    def test_rsi_insufficient_data(self):
        engine = MarketDataEngine()
        candles = _make_candles(10)
        result = engine.compute_indicators("BTCUSDT", "1h", candles)
        assert result.rsi is None

    def test_macd_computation(self):
        engine = MarketDataEngine()
        candles = _make_candles(100, trend=5)
        result = engine.compute_indicators("BTCUSDT", "1h", candles)
        assert result.macd is not None
        assert result.macd_signal is not None
        assert result.macd_histogram is not None

    def test_ema_computation(self):
        engine = MarketDataEngine()
        candles = _make_candles(100, trend=2)
        result = engine.compute_indicators("BTCUSDT", "1h", candles)
        assert result.ema_20 is not None
        assert result.ema_50 is not None

    def test_ema_200_requires_200_candles(self):
        engine = MarketDataEngine()
        candles = _make_candles(100)
        result = engine.compute_indicators("BTCUSDT", "1h", candles)
        assert result.ema_200 is None

    def test_ema_200_with_enough_data(self):
        engine = MarketDataEngine()
        candles = _make_candles(250, trend=1)
        result = engine.compute_indicators("BTCUSDT", "1h", candles)
        assert result.ema_200 is not None

    def test_atr_computation(self):
        engine = MarketDataEngine()
        candles = _make_candles(100)
        result = engine.compute_indicators("BTCUSDT", "1h", candles)
        assert result.atr is not None
        assert result.atr > 0

    def test_volatility_computation(self):
        engine = MarketDataEngine()
        candles = _make_candles(100, trend=5)
        result = engine.compute_indicators("BTCUSDT", "1h", candles)
        assert result.volatility is not None
        assert result.volatility > 0

    def test_volume_relative(self):
        engine = MarketDataEngine()
        candles = _make_candles(50)
        result = engine.compute_indicators("BTCUSDT", "1h", candles)
        assert result.volume_relative is not None
        assert result.volume_relative > 0

    def test_trend_bullish(self):
        engine = MarketDataEngine()
        candles = _make_candles(100, trend=10)
        result = engine.compute_indicators("BTCUSDT", "1h", candles)
        assert result.trend == "bullish"

    def test_trend_bearish(self):
        engine = MarketDataEngine()
        candles = _make_candles(100, trend=-10)
        result = engine.compute_indicators("BTCUSDT", "1h", candles)
        assert result.trend == "bearish"

    def test_trend_neutral(self):
        engine = MarketDataEngine()
        candles = _make_candles(100, trend=0)
        result = engine.compute_indicators("BTCUSDT", "1h", candles)
        assert result.trend == "neutral"

    def test_support_resistance_levels(self):
        engine = MarketDataEngine()
        candles = _make_candles(100, trend=1)
        result = engine.compute_indicators("BTCUSDT", "1h", candles)
        assert len(result.support_levels) > 0
        assert len(result.resistance_levels) > 0

    def test_insufficient_candles_returns_unknown(self):
        engine = MarketDataEngine()
        result = engine.compute_indicators("BTCUSDT", "1h", [])
        assert result.trend == "unknown"
        assert result.rsi is None


class TestLiquidityComputation:
    def test_spread_computation(self):
        engine = MarketDataEngine()
        ob = _make_order_book()
        result = engine.compute_liquidity("BTCUSDT", ob)
        assert result.spread is not None
        assert result.spread > 0

    def test_depth_computation(self):
        engine = MarketDataEngine()
        ob = _make_order_book()
        result = engine.compute_liquidity("BTCUSDT", ob)
        assert result.bid_depth is not None
        assert result.ask_depth is not None
        assert result.bid_depth > 0
        assert result.ask_depth > 0

    def test_order_book_imbalance(self):
        engine = MarketDataEngine()
        ob = _make_order_book()
        result = engine.compute_liquidity("BTCUSDT", ob)
        assert result.order_book_imbalance is not None
        assert -1 <= result.order_book_imbalance <= 1

    def test_empty_order_book(self):
        engine = MarketDataEngine()
        result = engine.compute_liquidity("BTCUSDT", {"bids": [], "asks": []})
        assert result.spread is None


class TestCorrelations:
    def test_correlation_identity(self):
        engine = MarketDataEngine()
        returns = {"BTC": [0.01, -0.02, 0.03, 0.01, -0.01]}
        corr = engine.compute_correlations(["BTC"], returns)
        assert corr["BTC"]["BTC"] == 1.0

    def test_correlation_perfect_positive(self):
        engine = MarketDataEngine()
        returns = {
            "BTC": [0.01, -0.02, 0.03, 0.01],
            "ETH": [0.01, -0.02, 0.03, 0.01],
        }
        corr = engine.compute_correlations(["BTC", "ETH"], returns)
        assert corr["BTC"]["ETH"] == pytest.approx(1.0, abs=0.01)

    def test_correlation_perfect_negative(self):
        engine = MarketDataEngine()
        returns = {
            "BTC": [0.01, -0.02, 0.03, 0.01],
            "ETH": [-0.01, 0.02, -0.03, -0.01],
        }
        corr = engine.compute_correlations(["BTC", "ETH"], returns)
        assert corr["BTC"]["ETH"] == pytest.approx(-1.0, abs=0.01)


class TestAnomalyDetection:
    def test_volatility_spike(self):
        engine = MarketDataEngine()
        # Create candles with extreme alternating volatility in the last portion
        candles = []
        price = 50000
        base_ts = time.time() - 50 * 3600
        for i in range(50):
            if i > 40:
                # Alternate large up and down swings to create high variance
                swing = price * 0.15 * (1 if i % 2 == 0 else -1)
            else:
                swing = 50
            close = price + swing
            candles.append({
                "open": price,
                "high": max(price, close) + 50,
                "low": min(price, close) - 50,
                "close": close,
                "volume": 1000,
                "timestamp": base_ts + i * 3600,
            })
            price = close
        anomalies = engine.detect_anomalies("BTCUSDT", candles)
        vol_anomalies = [a for a in anomalies if a.anomaly_type == "volatility_spike"]
        assert len(vol_anomalies) > 0

    def test_volume_spike(self):
        engine = MarketDataEngine()
        candles = _make_candles(50)
        # Last candle has 10x volume
        candles[-1]["volume"] = 10000
        anomalies = engine.detect_anomalies("BTCUSDT", candles)
        vol_anomalies = [a for a in anomalies if a.anomaly_type == "volume_spike"]
        assert len(vol_anomalies) > 0

    def test_price_gap(self):
        engine = MarketDataEngine()
        candles = _make_candles(50)
        # Create a 5% gap
        candles[-1]["close"] = candles[-2]["close"] * 1.06
        anomalies = engine.detect_anomalies("BTCUSDT", candles)
        gap_anomalies = [a for a in anomalies if a.anomaly_type == "price_gap"]
        assert len(gap_anomalies) > 0

    def test_rsi_overbought(self):
        engine = MarketDataEngine()
        candles = _make_candles(50, trend=200)
        anomalies = engine.detect_anomalies("BTCUSDT", candles)
        rsi_anomalies = [a for a in anomalies if a.anomaly_type == "rsi_overbought"]
        assert len(rsi_anomalies) > 0

    def test_no_anomalies_in_normal_market(self):
        engine = MarketDataEngine()
        candles = _make_candles(100, trend=1)
        anomalies = engine.detect_anomalies("BTCUSDT", candles)
        # Normal market should have few or no anomalies
        high_severity = [a for a in anomalies if a.severity == "high"]
        assert len(high_severity) == 0


class TestDataValidation:
    def test_high_quality_data(self):
        engine = MarketDataEngine()
        candles = _make_candles(100)
        quality = engine.validate_data("BTCUSDT", candles)
        assert quality.level in ("HIGH", "MEDIUM")

    def test_stale_data(self):
        engine = MarketDataEngine()
        candles = _make_candles(50)
        # Make timestamps very old (2020)
        for i, c in enumerate(candles):
            c["timestamp"] = 1577836800 + i * 3600  # Jan 1, 2020
        quality = engine.validate_data("BTCUSDT", candles)
        assert quality.is_stale

    def test_empty_data(self):
        engine = MarketDataEngine()
        quality = engine.validate_data("BTCUSDT", [])
        assert quality.level == "LOW"
        assert quality.is_stale


class TestCaching:
    def test_indicator_cache_hit(self):
        engine = MarketDataEngine()
        candles = _make_candles(100)
        r1 = engine.compute_indicators("BTCUSDT", "1h", candles)
        r2 = engine.compute_indicators("BTCUSDT", "1h")  # Should hit cache
        assert r1.rsi == r2.rsi

    def test_clear_cache(self):
        engine = MarketDataEngine()
        candles = _make_candles(100)
        engine.compute_indicators("BTCUSDT", "1h", candles)
        engine.clear_cache()
        # After clear, should recompute (not crash)
        r = engine.compute_indicators("BTCUSDT", "1h", candles)
        assert r.rsi is not None


class TestGetAllIndicators:
    def test_multiple_symbols(self):
        engine = MarketDataEngine()
        _make_candles(100)
        results = engine.get_all_indicators(["BTCUSDT", "ETHUSDT"], "1h")
        assert "BTCUSDT" in results
        assert "ETHUSDT" in results
