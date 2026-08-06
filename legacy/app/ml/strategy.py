"""Estrategia de trading basada en ML (FASE 7)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import pandas as pd

from app.ml.feature_engineering import FeatureEngineer
from app.ml.model import MLModel
from app.models.signal import SignalCreate
from app.strategies.strategy import Strategy


@dataclass
class MLStrategyConfig:
    """Parámetros configurables de la estrategia ML."""

    buy_threshold: float = 0.6
    sell_threshold: float = 0.4
    stop_loss_percent: float = 3.0
    take_profit_percent: float = 6.0
    max_hold_bars: int = 36
    trailing_stop_percent: float = 2.0


class MLStrategy(Strategy):
    """Estrategia que usa un modelo ML para generar señales."""

    def __init__(
        self,
        model: MLModel,
        feature_engineer: FeatureEngineer | None = None,
        config: MLStrategyConfig | None = None,
    ) -> None:
        self.model = model
        self.feature_engineer = feature_engineer or FeatureEngineer()
        self.config = config or MLStrategyConfig()

    @property
    def name(self) -> str:
        return "MLStrategy"

    @property
    def min_bars(self) -> int:
        return self.feature_engineer.min_bars

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        return self.feature_engineer.prepare_features(df)

    def generate_signal(
        self,
        symbol: str,
        df: pd.DataFrame,
        current_price: Decimal | None = None,
        has_position: bool = False,
        position_entry_price: Decimal | None = None,
        bars_in_position: int = 0,
        position_highest_price: Decimal | None = None,
    ) -> SignalCreate:
        data = self.prepare_data(df)
        if len(data) < self.min_bars or not self.model.is_trained:
            return self._build_signal(symbol, data, "HOLD", "Datos insuficientes o modelo no entrenado")

        last = data.iloc[-1]
        features = data[self.feature_engineer.FEATURE_COLUMNS].iloc[-1:]
        x_arr = features.to_numpy(dtype=np.float64)
        proba = float(self.model.predict_proba(x_arr)[0])

        close = Decimal(str(last["close"]))
        price = current_price if current_price is not None else close
        timestamp = data.index[-1]
        if isinstance(timestamp, pd.Timestamp):
            timestamp = timestamp.to_pydatetime()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)

        signal_type = "HOLD"
        triggers: list[str] = []

        if not has_position:
            if proba >= self.config.buy_threshold:
                signal_type = "BUY"
                triggers.append(f"ML probabilidad={proba:.4f} >= {self.config.buy_threshold}")
        else:
            if proba <= self.config.sell_threshold:
                signal_type = "SELL"
                triggers.append(f"ML probabilidad={proba:.4f} <= {self.config.sell_threshold}")
            if position_entry_price is not None and self.config.stop_loss_percent > 0:
                stop_level = position_entry_price * (
                    Decimal(1) - Decimal(str(self.config.stop_loss_percent)) / Decimal(100)
                )
                if price <= stop_level:
                    signal_type = "SELL"
                    triggers.append("stop loss")
            if position_entry_price is not None and self.config.take_profit_percent > 0:
                take_level = position_entry_price * (
                    Decimal(1) + Decimal(str(self.config.take_profit_percent)) / Decimal(100)
                )
                if price >= take_level:
                    signal_type = "SELL"
                    triggers.append("take profit")
            if bars_in_position >= self.config.max_hold_bars:
                signal_type = "SELL"
                triggers.append("tiempo máximo en posición")
            if position_highest_price is not None and self.config.trailing_stop_percent > 0:
                trailing_level = position_highest_price * (
                    Decimal(1) - Decimal(str(self.config.trailing_stop_percent)) / Decimal(100)
                )
                if price <= trailing_level and position_highest_price > position_entry_price:
                    signal_type = "SELL"
                    triggers.append("trailing stop")

        explanation = self.explain_signal(signal_type, last)
        confidence = self.calculate_confidence(data, signal_type)

        entry_price = price if signal_type != "HOLD" else None
        stop_loss = None
        take_profit = None
        if signal_type == "BUY":
            stop_loss = price * (
                Decimal(1) - Decimal(str(self.config.stop_loss_percent)) / Decimal(100)
            )
            take_profit = price * (
                Decimal(1) + Decimal(str(self.config.take_profit_percent)) / Decimal(100)
            )
        elif signal_type == "SELL":
            stop_loss = Decimal("0")
            take_profit = Decimal("0")

        metadata = {
            "ml_probability": proba,
            "close": float(last["close"]),
            "rsi": float(last["rsi"]),
            "triggers": triggers,
        }

        return SignalCreate(
            timestamp=timestamp,
            symbol=symbol,
            signal_type=signal_type,  # type: ignore[arg-type]
            confidence=confidence,
            entry_price=entry_price,
            suggested_stop_loss=stop_loss,
            suggested_take_profit=take_profit,
            strategy_name=self.name,
            explanation=explanation,
            metadata_json=metadata,
        )

    def calculate_confidence(self, df: pd.DataFrame, signal_type: str) -> Decimal:
        if signal_type == "HOLD":
            return Decimal("0")
        last = df.iloc[-1]
        features = last[self.feature_engineer.FEATURE_COLUMNS].to_numpy(dtype=np.float64)
        proba = float(self.model.predict_proba(features.reshape(1, -1))[0])
        return Decimal(str(round(proba, 4)))

    def explain_signal(self, signal_type: str, row: pd.Series) -> str:
        if signal_type == "HOLD":
            return "No se cumplen las condiciones del modelo ML."
        proba = row.get("ml_probability", None) if hasattr(row, "get") else None
        proba_str = f"{proba:.4f}" if proba is not None else "N/A"
        return (
            f"Señal ML {signal_type}: probabilidad={proba_str}, "
            f"RSI={row['rsi']:.2f}, ATR={row['atr']:.4f}."
        )

    def _build_signal(
        self,
        symbol: str,
        df: pd.DataFrame,
        signal_type: str,
        reason: str,
    ) -> SignalCreate:
        timestamp = df.index[-1].to_pydatetime() if not df.empty else datetime.now(tz=UTC)
        if isinstance(timestamp, pd.Timestamp):
            timestamp = timestamp.to_pydatetime()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        return SignalCreate(
            timestamp=timestamp,
            symbol=symbol,
            signal_type=signal_type,  # type: ignore[arg-type]
            confidence=Decimal("0"),
            entry_price=None,
            suggested_stop_loss=None,
            suggested_take_profit=None,
            strategy_name=self.name,
            explanation=reason,
            metadata_json={},
        )
