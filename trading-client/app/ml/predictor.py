"""Predictor que combina FeatureEngineer + MLModel."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.ml.feature_engineering import FeatureEngineer
from app.ml.model import MLModel


class MLPredictor:
    """Encapsula feature engineering + modelo ML para entrenar y predecir."""

    def __init__(
        self,
        feature_engineer: FeatureEngineer | None = None,
        model: MLModel | None = None,
    ) -> None:
        self.feature_engineer = feature_engineer or FeatureEngineer()
        self.model = model or MLModel()

    def train(self, df: pd.DataFrame, forward_window: int = 5, threshold: float = 0.0) -> dict:
        """Entrena el modelo a partir de un DataFrame OHLCV."""
        x, y = self.feature_engineer.build_training_data(df, forward_window, threshold)
        if len(x) == 0:
            raise ValueError("No hay datos suficientes para entrenar")
        x_arr = x.to_numpy(dtype=np.float64)
        y_arr = y.to_numpy()
        metrics = self.model.fit(x_arr, y_arr, list(x.columns))
        metrics["forward_window"] = forward_window
        metrics["threshold"] = threshold
        return metrics

    def predict(self, df: pd.DataFrame) -> dict:
        """Predice la probabilidad de subida para la última barra."""
        if not self.model.is_trained:
            raise RuntimeError("Modelo no entrenado")
        features = self.feature_engineer.extract_latest_features(df)
        x_arr = features.to_numpy(dtype=np.float64)
        proba = float(self.model.predict_proba(x_arr)[0])
        label = int(proba >= 0.5)
        return {
            "probability": proba,
            "prediction": label,
            "features": features.iloc[0].to_dict(),
        }

    def save(self, path: str | Path) -> None:
        """Guarda el modelo a disco como JSON."""
        data = {
            "feature_engineer": {
                "fast_ema": self.feature_engineer.fast_ema,
                "slow_ema": self.feature_engineer.slow_ema,
                "rsi_period": self.feature_engineer.rsi_period,
                "atr_period": self.feature_engineer.atr_period,
                "volume_lookback": self.feature_engineer.volume_lookback,
            },
            "model": self.model.to_dict(),
        }
        Path(path).write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: str | Path) -> "MLPredictor":
        """Carga el modelo desde disco."""
        data = json.loads(Path(path).read_text())
        fe = FeatureEngineer(**data["feature_engineer"])
        model = MLModel.from_dict(data["model"])
        return cls(feature_engineer=fe, model=model)
