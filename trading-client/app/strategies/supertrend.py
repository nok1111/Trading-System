"""Estrategia Supertrend — ATR-based trend following."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import pandas as pd

from app.indicators import indicators as ind
from app.models.signal import SignalCreate
from app.strategies.strategy import Strategy


@dataclass
class SupertrendConfig:
    """Parámetros configurables de Supertrend."""

    atr_period: int = 10
    multiplier: float = 3.0
    rsi_period: int = 14
    rsi_min: float = 45.0
    volume_lookback: int = 20
    volume_threshold: float = 0.8  # lower than breakout — trend doesn't need huge volume
    stop_loss_percent: float = 4.0  # wider — supertrend is more patient
    take_profit_percent: float = 12.0  # bigger — trends run further
    max_hold_bars: int = 72
    trailing_stop_percent: float = 3.5


class SupertrendStrategy(Strategy):
    """Estrategia basada en Supertrend (ATR trend following).

    Entrada long:  Supertrend cambia a direccion alcista (1) + RSI > 45 + volumen
    Salida:        Supertrend cambia a bajista (-1), o SL/TP/trailing
    Funciona mejor en tendencias sostenidas — el ATR multiplier filtra ruido.
    Más paciente que Trend Momentum (EMA) — menos whipsaws.
    """

    def __init__(self, config: SupertrendConfig | None = None) -> None:
        self.config = config or SupertrendConfig()

    @property
    def name(self) -> str:
        return "SupertrendStrategy"

    @property
    def min_bars(self) -> int:
        return max(self.config.atr_period * 2, 30) + 1

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        c = self.config
        data = df.copy()
        st = ind.supertrend(data, c.atr_period, c.multiplier)
        data["supertrend"] = st["supertrend"]
        data["st_direction"] = st["direction"]
        data["rsi"] = ind.rsi(data["close"], c.rsi_period)
        data["atr"] = ind.atr(data, c.atr_period)
        data["volume_rel"] = ind.relative_volume(data["volume"], c.volume_lookback)
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
        min_bars = self.config.atr_period * 2 + 1
        if len(data) < min_bars + 1:
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

        st_dir = float(last["st_direction"]) if not np.isnan(last["st_direction"]) else 0
        prev_st_dir = float(prev["st_direction"]) if not np.isnan(prev["st_direction"]) else 0
        st_val = float(last["supertrend"]) if not np.isnan(last["supertrend"]) else 0

        if not has_position:
            rsi_val = float(last["rsi"]) if not np.isnan(last["rsi"]) else 50
            vr = float(last["volume_rel"]) if not np.isnan(last["volume_rel"]) else 1.0

            # Supertrend flipped to uptrend
            trend_up = prev_st_dir == -1 and st_dir == 1
            price_above_st = last["close"] > st_val

            if trend_up:
                triggers.append(f"Supertrend cambio a alcista (ST {st_val:.4f})")
            if price_above_st:
                triggers.append(f"precio {last['close']:.4f} sobre Supertrend")
            if rsi_val > self.config.rsi_min:
                triggers.append(f"RSI {rsi_val:.1f} > {self.config.rsi_min}")
            if vr > self.config.volume_threshold:
                triggers.append(f"volumen {vr:.1f}x")

            if trend_up and price_above_st and rsi_val > self.config.rsi_min:
                signal_type = "BUY"
        else:
            # Exit: Supertrend flips to downtrend
            trend_down = prev_st_dir == 1 and st_dir == -1
            if trend_down:
                triggers.append("Supertrend cambio a bajista")

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
            "supertrend": st_val,
            "st_direction": st_dir,
            "rsi": float(last["rsi"]) if not np.isnan(last["rsi"]) else 50,
            "atr": float(last["atr"]) if not np.isnan(last["atr"]) else 0,
            "volume_rel": float(last["volume_rel"]) if not np.isnan(last["volume_rel"]) else 1,
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
        rsi = float(last["rsi"]) if not np.isnan(last["rsi"]) else 50
        vr = float(last["volume_rel"]) if not np.isnan(last["volume_rel"]) else 1
        atr = float(last["atr"]) if not np.isnan(last["atr"]) else 0
        close = float(last["close"])

        if signal_type == "BUY":
            rsi_score = min(max(rsi - 40, 0) / 30, 1.0)
            vol_score = min(max(vr - 0.5, 0) / 1.5, 1.0)
            atr_score = min(atr / close, 0.03) / 0.03 if close else 0
            score = min(1.0, 0.40 * rsi_score + 0.30 * vol_score + 0.30 * atr_score)
            return Decimal(str(round(score, 4)))
        return Decimal("0.7")

    def explain_signal(self, signal_type: str, row: pd.Series, prev: pd.Series | None = None) -> str:
        if signal_type == "HOLD":
            return "Supertrend sin cambio de direccion"
        st_val = float(row["supertrend"]) if not np.isnan(row["supertrend"]) else 0
        close = float(row["close"])
        rsi_val = float(row["rsi"]) if not np.isnan(row["rsi"]) else 50
        if signal_type == "BUY":
            return (
                f"Supertrend bullish: ST {st_val:.4f}, precio {close:.4f} sobre linea. "
                f"RSI {rsi_val:.1f}. TP +{self.config.take_profit_percent}%, SL -{self.config.stop_loss_percent}%."
            )
        return f"Supertrend bearish: ST {st_val:.4f}. Salida de tendencia."

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
