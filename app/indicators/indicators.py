"""Indicadores técnicos implementados desde cero con pandas/numpy."""

from typing import Literal

import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    """Media móvil simple."""
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, window: int) -> pd.Series:
    """Media móvil exponencial."""
    return series.ewm(span=window, adjust=False, min_periods=window).mean()


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """Relative Strength Index usando media móvil simple de ganancias/pérdidas."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=window, min_periods=window).mean()
    avg_loss = loss.rolling(window=window, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_value = 100 - (100 / (1 + rs))
    # Cuando no hay pérdidas, RSI es 100; sin movimiento, 50
    loss_zero = avg_loss == 0
    gain_zero = avg_gain == 0
    rsi_value = rsi_value.where(~(loss_zero & ~gain_zero), 100.0)
    return rsi_value.where(~(loss_zero & gain_zero), 50.0)


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """MACD con línea de señal e histograma."""
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "histogram": histogram})


def atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """Average True Range."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.rolling(window=window, min_periods=window).mean()


def vwap(df: pd.DataFrame) -> pd.Series:
    """Volume Weighted Average Price acumulado."""
    typical = (df["high"] + df["low"] + df["close"]) / 3
    cumulative_tp_vol = (typical * df["volume"]).cumsum()
    cumulative_volume = df["volume"].cumsum()
    return cumulative_tp_vol / cumulative_volume.replace(0, np.nan)


def bollinger_bands(
    series: pd.Series,
    window: int = 20,
    num_std: float = 2.0,
) -> pd.DataFrame:
    """Bandas de Bollinger."""
    middle = sma(series, window)
    std = series.rolling(window=window, min_periods=window).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    return pd.DataFrame({"middle": middle, "upper": upper, "lower": lower})


def percent_return(series: pd.Series, periods: int = 1) -> pd.Series:
    """Retorno porcentual respecto a N períodos previos."""
    return (series / series.shift(periods) - 1) * 100


def historical_volatility(
    series: pd.Series,
    window: int = 20,
    periods: int = 252,
) -> pd.Series:
    """Volatilidad histórica anualizada en porcentaje."""
    log_returns = np.log(series / series.shift(1))
    std = log_returns.rolling(window=window, min_periods=window).std()
    return std * np.sqrt(periods) * 100


def relative_volume(volume: pd.Series, window: int = 20) -> pd.Series:
    """Volumen actual dividido por el volumen promedio reciente."""
    avg_volume = volume.rolling(window=window, min_periods=window).mean()
    return volume / avg_volume.replace(0, np.nan)


def crossover(
    fast: pd.Series,
    slow: pd.Series,
    direction: Literal["up", "down"] = "up",
) -> pd.Series:
    """Detecta cruces entre dos series.

    Devuelve una Serie booleana con True en el índice donde ocurre el cruce.
    """
    if direction == "up":
        return (fast.shift(1) <= slow.shift(1)) & (fast > slow)
    return (fast.shift(1) >= slow.shift(1)) & (fast < slow)
