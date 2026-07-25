"""Feature engineering para el módulo de ML."""

import numpy as np
import pandas as pd

from app.indicators import indicators as ind


class FeatureEngineer:
    """Genera features técnicos y etiquetas para entrenamiento de ML."""

    FEATURE_COLUMNS = [
        "ema_fast",
        "ema_slow",
        "rsi",
        "rsi_lag5",
        "atr",
        "volume_rel",
        "returns",
        "returns_lag1",
        "returns_lag3",
        "sma_20",
        "bollinger_width",
        "macd_hist",
        "historical_vol",
        "momentum",
        "momentum_3",
        "momentum_20",
        "price_position",
        "candle_body",
        "upper_shadow",
        "lower_shadow",
        "ema_spread",
        "volatility_lag5",
    ]

    def __init__(
        self,
        fast_ema: int = 10,
        slow_ema: int = 30,
        rsi_period: int = 14,
        atr_period: int = 14,
        volume_lookback: int = 20,
    ) -> None:
        self.fast_ema = fast_ema
        self.slow_ema = slow_ema
        self.rsi_period = rsi_period
        self.atr_period = atr_period
        self.volume_lookback = volume_lookback

    @property
    def min_bars(self) -> int:
        return max(self.slow_ema, self.rsi_period, self.atr_period, self.volume_lookback, 20, 25) + 2

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Añade columnas de features al DataFrame."""
        data = df.copy()
        data["ema_fast"] = ind.ema(data["close"], self.fast_ema)
        data["ema_slow"] = ind.ema(data["close"], self.slow_ema)
        data["rsi"] = ind.rsi(data["close"], self.rsi_period)
        data["atr"] = ind.atr(data, self.atr_period)
        data["volume_rel"] = ind.relative_volume(data["volume"], self.volume_lookback)
        data["returns"] = ind.percent_return(data["close"], 1)
        data["sma_20"] = ind.sma(data["close"], 20)
        bb = ind.bollinger_bands(data["close"], 20)
        data["bollinger_width"] = (bb["upper"] - bb["lower"]) / data["close"]
        macd_df = ind.macd(data["close"], 12, 26, 9)
        data["macd_hist"] = macd_df["histogram"]
        data["historical_vol"] = ind.historical_volatility(data["close"], 20)
        data["momentum"] = data["close"].pct_change(10)
        data["momentum_3"] = data["close"].pct_change(3)
        data["momentum_20"] = data["close"].pct_change(20)
        data["rsi_lag5"] = data["rsi"].shift(5)
        data["returns_lag1"] = data["returns"].shift(1)
        data["returns_lag3"] = data["returns"].shift(3)
        data["ema_spread"] = (data["ema_fast"] - data["ema_slow"]) / data["close"]
        data["volatility_lag5"] = data["historical_vol"].shift(5)
        bb_mid = (bb["upper"] + bb["lower"]) / 2
        bb_range = (bb["upper"] - bb["lower"]).replace(0, np.nan)
        data["price_position"] = ((data["close"] - bb["lower"]) / bb_range).clip(-1, 2)
        candle_range = (data["high"] - data["low"]).replace(0, np.nan)
        data["candle_body"] = (data["close"] - data["open"]) / candle_range
        data["upper_shadow"] = (data["high"] - data[["open", "close"]].max(axis=1)) / candle_range
        data["lower_shadow"] = (data[["open", "close"]].min(axis=1) - data["low"]) / candle_range
        data = data.replace([np.inf, -np.inf], np.nan)
        return data

    def build_training_data(
        self,
        df: pd.DataFrame,
        forward_window: int = 5,
        threshold: float = 0.0,
    ) -> tuple[pd.DataFrame, pd.Series]:
        """Construye X, y para entrenamiento.

        Etiqueta: 1 si el retorno en `forward_window` barras supera `threshold`,
        0 si es menor a -threshold, NaN en caso contrario (se descartan).
        """
        data = self.prepare_features(df)
        data["forward_return"] = data["close"].shift(-forward_window) / data["close"] - 1
        data["label"] = np.where(
            data["forward_return"] > threshold,
            1,
            np.where(data["forward_return"] < -threshold, 0, np.nan),
        )
        data = data.dropna(subset=self.FEATURE_COLUMNS + ["label"])
        data["label"] = data["label"].astype(int)

        x = data[self.FEATURE_COLUMNS]
        y = data["label"]
        return x, y

    def extract_latest_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extrae features de la última barra para predicción."""
        data = self.prepare_features(df)
        return data[self.FEATURE_COLUMNS].iloc[-1:]
