"""Pruebas de indicadores técnicos."""

import pandas as pd
import pytest

from app.indicators import indicators as ind


def _series(values: list[float]) -> pd.Series:
    return pd.Series(values, dtype=float)


class TestIndicators:
    def test_sma_basic(self) -> None:
        series = _series([1, 2, 3, 4, 5])
        result = ind.sma(series, 3)
        assert pd.isna(result.iloc[1])
        assert result.iloc[-1] == pytest.approx(4.0)

    def test_ema_rises_with_uptrend(self) -> None:
        series = _series([1, 2, 3, 4, 5])
        result = ind.ema(series, 3)
        assert result.iloc[-1] > result.iloc[-2]

    def test_rsi_high_in_strong_uptrend(self) -> None:
        series = _series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15])
        result = ind.rsi(series, 14)
        assert result.iloc[-1] > 60

    def test_rsi_is_fifty_when_constant(self) -> None:
        series = _series([10.0] * 30)
        result = ind.rsi(series, 14)
        assert result.iloc[-1] == pytest.approx(50.0)

    def test_macd_columns(self) -> None:
        series = _series([10 + i for i in range(50)])
        result = ind.macd(series)
        assert set(result.columns) == {"macd", "signal", "histogram"}

    def test_atr_positive(self) -> None:
        df = pd.DataFrame({"high": [10, 11, 12], "low": [8, 9, 9], "close": [9, 10, 11]})
        result = ind.atr(df, 2)
        assert result.iloc[-1] > 0

    def test_bollinger_bands_order(self) -> None:
        series = _series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10] * 2)
        result = ind.bollinger_bands(series, 5, 2)
        assert result["upper"].iloc[-1] > result["middle"].iloc[-1]
        assert result["middle"].iloc[-1] > result["lower"].iloc[-1]

    def test_percent_return(self) -> None:
        series = _series([100, 110, 99])
        result = ind.percent_return(series, 1)
        assert result.iloc[1] == pytest.approx(10.0)
        assert result.iloc[2] == pytest.approx(-10.0)

    def test_historical_volatility_positive(self) -> None:
        series = _series([100 - i for i in range(30)])
        result = ind.historical_volatility(series, 20, 252)
        assert result.iloc[-1] > 0

    def test_relative_volume(self) -> None:
        volume = _series([10.0, 15.0])
        result = ind.relative_volume(volume, 2)
        assert result.iloc[-1] == pytest.approx(1.2)

    def test_vwap(self) -> None:
        df = pd.DataFrame(
            {
                "high": [10, 11],
                "low": [9, 10],
                "close": [9.5, 10.5],
                "volume": [100, 200],
            }
        )
        result = ind.vwap(df)
        assert result.iloc[-1] > 0

    def test_crossover_up(self) -> None:
        fast = _series([1, 2, 3, 4, 5])
        slow = _series([2, 2, 3, 3, 3])
        result = ind.crossover(fast, slow, "up")
        assert result.iloc[3]
        assert not result.iloc[4]

    def test_crossover_down(self) -> None:
        fast = _series([5, 4, 3, 2, 1])
        slow = _series([3, 3, 3, 4, 4])
        result = ind.crossover(fast, slow, "down")
        assert result.iloc[3]
