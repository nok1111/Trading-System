"""Estrategia MACD Momentum — cruce de MACD con señal + histograma."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import pandas as pd

from app.indicators import indicators as ind
from app.models.signal import SignalCreate
from app.strategies.strategy import Strategy


@dataclass
class MACDMomentumConfig:
    """Parámetros configurables de MACD Momentum."""

    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9
    atr_period: int = 14
    rsi_period: int = 14
    rsi_min: float = 45.0  # confirm momentum, not oversold bounce
    stop_loss_percent: float = 3.0
    take_profit_percent: float = 7.0
    max_hold_bars: int = 48
    trailing_stop_percent: float = 2.5
    # Require histogram to be rising for entry
    require_rising_histogram: bool = True


class MACDMomentumStrategy(Strategy):
    """Estrategia basada en MACD.

    Entrada long:  MACD cruza arriba de la señal + histograma positivo + RSI > 45
    Salida:        MACD cruza abajo de la señal, o SL/TP/trailing
    Funciona mejor en mercados con momentum direccional.
    Detecta cambios de tendencia antes que EMA crossover.
    """

    def __init__(self, config: MACDMomentumConfig | None = None) -> None:
        self.config = config or MACDMomentumConfig()

    @property
    def name(self) -> str:
        return "MACDMomentumStrategy"

    @property
    def min_bars(self) -> int:
        return max(self.config.slow_period + self.config.signal_period, 30) + 1

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        c = self.config
        data = df.copy()
        macd_df = ind.macd(data["close"], c.fast_period, c.slow_period, c.signal_period)
        data["macd"] = macd_df["macd"]
        data["macd_signal"] = macd_df["signal"]
        data["macd_hist"] = macd_df["histogram"]
        data["rsi"] = ind.rsi(data["close"], c.rsi_period)
        data["atr"] = ind.atr(data, c.atr_period)
        data["returns"] = ind.percent_return(data["close"], 1)
        return data

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
        min_bars = self.config.slow_period + self.config.signal_period + 1
        if len(data) < min_bars:
            return self._build_signal(symbol, data, "HOLD", "Datos insuficientes")

        last = data.iloc[-1]
        prev = data.iloc[-2]
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
            macd_val = float(last["macd"]) if not np.isnan(last["macd"]) else 0
            signal_val = float(last["macd_signal"]) if not np.isnan(last["macd_signal"]) else 0
            prev_macd = float(prev["macd"]) if not np.isnan(prev["macd"]) else 0
            prev_signal = float(prev["macd_signal"]) if not np.isnan(prev["macd_signal"]) else 0
            hist = float(last["macd_hist"]) if not np.isnan(last["macd_hist"]) else 0
            prev_hist = float(prev["macd_hist"]) if not np.isnan(prev["macd_hist"]) else 0
            rsi_val = float(last["rsi"]) if not np.isnan(last["rsi"]) else 50

            # Bullish crossover: MACD crosses above signal
            crossover_up = prev_macd <= prev_signal and macd_val > signal_val
            histogram_positive = hist > 0
            histogram_rising = hist > prev_hist if self.config.require_rising_histogram else True
            rsi_ok = rsi_val > self.config.rsi_min

            if crossover_up:
                triggers.append(f"MACD {macd_val:.4f} cruzo arriba señal {signal_val:.4f}")
            if histogram_positive:
                triggers.append(f"histograma positivo {hist:.4f}")
            if histogram_rising:
                triggers.append("histograma creciente")
            if rsi_ok:
                triggers.append(f"RSI {rsi_val:.1f} > {self.config.rsi_min}")

            if crossover_up and histogram_positive and rsi_ok:
                signal_type = "BUY"
        else:
            macd_val = float(last["macd"]) if not np.isnan(last["macd"]) else 0
            signal_val = float(last["macd_signal"]) if not np.isnan(last["macd_signal"]) else 0
            prev_macd = float(prev["macd"]) if not np.isnan(prev["macd"]) else 0
            prev_signal = float(prev["macd_signal"]) if not np.isnan(prev["macd_signal"]) else 0

            # Bearish crossover: MACD crosses below signal
            crossover_down = prev_macd >= prev_signal and macd_val < signal_val
            if crossover_down:
                triggers.append("MACD cruzo abajo señal")

            if position_entry_price is not None and self.config.stop_loss_percent > 0:
                stop_level = position_entry_price * (Decimal(1) - Decimal(str(self.config.stop_loss_percent)) / Decimal(100))
                if price <= stop_level:
                    triggers.append("stop loss")

            if position_entry_price is not None and self.config.take_profit_percent > 0:
                take_level = position_entry_price * (Decimal(1) + Decimal(str(self.config.take_profit_percent)) / Decimal(100))
                if price >= take_level:
                    triggers.append("take profit")

            if bars_in_position >= self.config.max_hold_bars:
                triggers.append(f"tiempo maximo ({bars_in_position} barras)")

            if position_highest_price is not None and self.config.trailing_stop_percent > 0:
                trailing_level = position_highest_price * (Decimal(1) - Decimal(str(self.config.trailing_stop_percent)) / Decimal(100))
                if price <= trailing_level and position_highest_price > position_entry_price:
                    triggers.append("trailing stop")

            if triggers:
                signal_type = "SELL"

        explanation = self.explain_signal(signal_type, last, prev)
        confidence = self.calculate_confidence(data, signal_type)

        entry_price = price if signal_type != "HOLD" else None
        stop_loss = None
        take_profit = None
        if signal_type == "BUY":
            stop_loss = price * (Decimal(1) - Decimal(str(self.config.stop_loss_percent)) / Decimal(100))
            take_profit = price * (Decimal(1) + Decimal(str(self.config.take_profit_percent)) / Decimal(100))
        elif signal_type == "SELL":
            stop_loss = Decimal("0")
            take_profit = Decimal("0")

        metadata = {
            "macd": float(last["macd"]) if not np.isnan(last["macd"]) else 0,
            "macd_signal": float(last["macd_signal"]) if not np.isnan(last["macd_signal"]) else 0,
            "macd_hist": float(last["macd_hist"]) if not np.isnan(last["macd_hist"]) else 0,
            "rsi": float(last["rsi"]) if not np.isnan(last["rsi"]) else 50,
            "atr": float(last["atr"]) if not np.isnan(last["atr"]) else 0,
            "close": float(last["close"]),
            "triggers": triggers,
        }

        return SignalCreate(
            timestamp=timestamp, symbol=symbol, signal_type=signal_type,  # type: ignore[arg-type]
            confidence=confidence, entry_price=entry_price,
            suggested_stop_loss=stop_loss, suggested_take_profit=take_profit,
            strategy_name=self.name, explanation=explanation, metadata_json=metadata,
        )

    def calculate_confidence(self, df: pd.DataFrame, signal_type: str) -> Decimal:
        if signal_type == "HOLD":
            return Decimal("0")
        last = df.iloc[-1]
        prev = df.iloc[-2]
        hist = float(last["macd_hist"]) if not np.isnan(last["macd_hist"]) else 0
        prev_hist = float(prev["macd_hist"]) if not np.isnan(prev["macd_hist"]) else 0
        rsi = float(last["rsi"]) if not np.isnan(last["rsi"]) else 50

        if signal_type == "BUY":
            hist_strength = min(abs(hist) * 100, 1.0)
            hist_rising = 1.0 if hist > prev_hist else 0.3
            rsi_score = min(max(rsi - 40, 0) / 30, 1.0)
            score = min(1.0, 0.40 * hist_strength + 0.30 * hist_rising + 0.30 * rsi_score)
            return Decimal(str(round(score, 4)))
        return Decimal("0.7")

    def explain_signal(self, signal_type: str, row: pd.Series, prev: pd.Series | None = None) -> str:
        if signal_type == "HOLD":
            return "Sin cruce MACD ni condiciones de salida"
        macd_val = float(row["macd"]) if not np.isnan(row["macd"]) else 0
        signal_val = float(row["macd_signal"]) if not np.isnan(row["macd_signal"]) else 0
        hist = float(row["macd_hist"]) if not np.isnan(row["macd_hist"]) else 0
        close = float(row["close"])
        if signal_type == "BUY":
            return (
                f"MACD bullish: MACD {macd_val:.4f} > señal {signal_val:.4f}, "
                f"histograma {hist:.4f}. Precio {close:.4f}. "
                f"TP +{self.config.take_profit_percent}%, SL -{self.config.stop_loss_percent}%."
            )
        return f"MACD bearish: MACD {macd_val:.4f} < señal {signal_val:.4f}. Salida."

    def _build_signal(self, symbol: str, data: pd.DataFrame, signal_type: str, reason: str) -> SignalCreate:
        timestamp = data.index[-1] if len(data) > 0 else datetime.now(tz=UTC)
        if isinstance(timestamp, pd.Timestamp):
            timestamp = timestamp.to_pydatetime()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        return SignalCreate(
            timestamp=timestamp, symbol=symbol, signal_type=signal_type,  # type: ignore[arg-type]
            confidence=Decimal("0"), entry_price=None, suggested_stop_loss=None,
            suggested_take_profit=None, strategy_name=self.name,
            explanation=reason, metadata_json={"triggers": [], "reason": reason},
        )
