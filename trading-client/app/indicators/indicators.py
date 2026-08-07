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


def donchian_channels(
    df: pd.DataFrame,
    window: int = 20,
) -> pd.DataFrame:
    """Donchian Channels — highest high and lowest low over N periods.

    Returns DataFrame with 'upper', 'lower', and 'middle' columns.
    The upper band is the highest high, lower is the lowest low,
    and middle is the average of the two.
    """
    upper = df["high"].rolling(window=window, min_periods=window).max()
    lower = df["low"].rolling(window=window, min_periods=window).min()
    middle = (upper + lower) / 2
    return pd.DataFrame({"upper": upper, "lower": lower, "middle": middle})


def stochastic(
    df: pd.DataFrame,
    k_window: int = 14,
    d_window: int = 3,
) -> pd.DataFrame:
    """Stochastic Oscillator (%K and %D).

    %K = (Close - Lowest Low) / (Highest High - Lowest Low) * 100
    %D = SMA of %K over d_window periods.
    """
    lowest = df["low"].rolling(window=k_window, min_periods=k_window).min()
    highest = df["high"].rolling(window=k_window, min_periods=k_window).max()
    k = (df["close"] - lowest) / (highest - lowest).replace(0, np.nan) * 100
    d = k.rolling(window=d_window, min_periods=d_window).mean()
    return pd.DataFrame({"k": k, "d": d})


def supertrend(
    df: pd.DataFrame,
    atr_period: int = 10,
    multiplier: float = 3.0,
) -> pd.DataFrame:
    """Supertrend indicator — ATR-based trend following.

    Returns DataFrame with 'supertrend' (the trend line) and 'direction'
    (1 for uptrend, -1 for downtrend).
    """
    atr_val = atr(df, atr_period)
    hl2 = (df["high"] + df["low"]) / 2

    upper_band = hl2 + multiplier * atr_val
    lower_band = hl2 - multiplier * atr_val

    st = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=float)

    close = df["close"].values
    upper = upper_band.values.copy()
    lower = lower_band.values.copy()
    st_vals = np.full(len(df), np.nan)
    dir_vals = np.full(len(df), 1.0)

    for i in range(1, len(df)):
        if np.isnan(upper[i]) or np.isnan(lower[i]):
            continue

        # Final upper band: if upper < prev_upper OR close > prev_upper
        if i > 0 and not np.isnan(st_vals[i - 1]):
            prev_st = st_vals[i - 1]
            if close[i - 1] <= prev_st:  # was in downtrend
                upper[i] = min(upper[i], upper[i - 1]) if not np.isnan(upper[i - 1]) else upper[i]
            else:  # was in uptrend
                lower[i] = max(lower[i], lower[i - 1]) if not np.isnan(lower[i - 1]) else lower[i]

        # Determine direction
        if dir_vals[i - 1] == 1:  # was uptrend
            if close[i] < lower[i]:
                dir_vals[i] = -1
                st_vals[i] = upper[i]
            else:
                dir_vals[i] = 1
                st_vals[i] = lower[i]
        else:  # was downtrend
            if close[i] > upper[i]:
                dir_vals[i] = 1
                st_vals[i] = lower[i]
            else:
                dir_vals[i] = -1
                st_vals[i] = upper[i]

    return pd.DataFrame({
        "supertrend": pd.Series(st_vals, index=df.index),
        "direction": pd.Series(dir_vals, index=df.index),
    })


def atr_percentile(df: pd.DataFrame, atr_period: int = 14, lookback: int = 50) -> pd.Series:
    """ATR percentile — used to detect volatility squeeze.

    Returns a Series with values 0-100 representing where current ATR
    falls relative to the last N periods. Low percentile = squeeze.
    """
    atr_val = atr(df, atr_period)
    return atr_val.rolling(window=lookback, min_periods=atr_period).rank(pct=True) * 100


def rate_of_change(series: pd.Series, period: int = 12) -> pd.Series:
    """Rate of Change (ROC) — percentage change over N periods.

    ROC = (Current Price - Price N periods ago) / Price N periods ago * 100
    """
    shifted = series.shift(period)
    return ((series - shifted) / shifted.replace(0, np.nan)) * 100


def williams_r(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Williams %R — momentum oscillator (similar to stochastic but inverted).

    %R = (Highest High - Close) / (Highest High - Lowest Low) * -100
    Range: -100 to 0. Oversold < -80, Overbought > -20.
    """
    highest = df["high"].rolling(window=period, min_periods=period).max()
    lowest = df["low"].rolling(window=period, min_periods=period).min()
    wr = (highest - df["close"]) / (highest - lowest).replace(0, np.nan) * -100
    return wr
