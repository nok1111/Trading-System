"""Estrategia TrendMomentumStrategy configurable."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import pandas as pd

from app.indicators import indicators as ind
from app.models.signal import SignalCreate
from app.strategies.strategy import Strategy


@dataclass
class TrendMomentumConfig:
    """Parámetros configurables de la estrategia."""

    fast_ema: int = 9
    slow_ema: int = 21
    rsi_period: int = 14
    rsi_lower: float = 35.0
    rsi_upper: float = 60.0
    volume_lookback: int = 20
    volume_threshold: float = 1.5
    atr_period: int = 14
    stop_loss_percent: float = 3.0
    take_profit_percent: float = 6.0
    max_hold_bars: int = 36
    trend_ema: int = 50
    trailing_stop_percent: float = 2.0


class TrendMomentumStrategy(Strategy):
    """Estrategia de cruce de EMAs + RSI + volumen relativo + ATR."""

    def __init__(self, config: TrendMomentumConfig | None = None) -> None:
        self.config = config or TrendMomentumConfig()

    @property
    def name(self) -> str:
        return "TrendMomentumStrategy"

    @property
    def min_bars(self) -> int:
        return (
            max(
                self.config.slow_ema,
                self.config.rsi_period,
                self.config.atr_period,
                self.config.volume_lookback,
                self.config.trend_ema,
            )
            + 1
        )

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Añade EMAs, RSI, ATR, volumen relativo y otras columnas útiles."""
        c = self.config
        data = df.copy()
        data["ema_fast"] = ind.ema(data["close"], c.fast_ema)
        data["ema_slow"] = ind.ema(data["close"], c.slow_ema)
        data["ema_trend"] = ind.ema(data["close"], c.trend_ema)
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
        """Genera señal BUY, SELL o HOLD para la última vela."""
        data = self.prepare_data(df)
        min_bars = max(
            self.config.slow_ema,
            self.config.rsi_period,
            self.config.atr_period,
            self.config.volume_lookback,
            self.config.trend_ema,
        )
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

        if not has_position:
            cross_up = prev["ema_fast"] <= prev["ema_slow"] and last["ema_fast"] > last["ema_slow"]
            rsi_ok = self.config.rsi_lower < last["rsi"] < self.config.rsi_upper
            volume_ok = last["volume_rel"] > self.config.volume_threshold
            if cross_up:
                triggers.append("cruce EMA alcista")
            if rsi_ok:
                triggers.append("RSI en zona configurable")
            if volume_ok:
                triggers.append("volumen relativo elevado")
            trend_ok = True
            if "ema_trend" in last.index and not np.isnan(last["ema_trend"]):
                trend_ok = last["close"] > last["ema_trend"]
            if trend_ok:
                triggers.append("precio sobre EMA tendencia")
            if cross_up and rsi_ok and volume_ok and trend_ok:
                signal_type = "BUY"
        else:
            cross_down = (
                prev["ema_fast"] >= prev["ema_slow"] and last["ema_fast"] < last["ema_slow"]
            )
            if cross_down:
                triggers.append("cruce EMA bajista")
            if position_entry_price is not None and self.config.stop_loss_percent > 0:
                stop_level = position_entry_price * (
                    Decimal(1) - Decimal(str(self.config.stop_loss_percent)) / Decimal(100)
                )
                if price <= stop_level:
                    triggers.append("stop loss")
            if position_entry_price is not None and self.config.take_profit_percent > 0:
                take_level = position_entry_price * (
                    Decimal(1) + Decimal(str(self.config.take_profit_percent)) / Decimal(100)
                )
                if price >= take_level:
                    triggers.append("take profit")
            if bars_in_position >= self.config.max_hold_bars:
                triggers.append("tiempo máximo en posición")
            if position_highest_price is not None and self.config.trailing_stop_percent > 0:
                trailing_level = position_highest_price * (
                    Decimal(1) - Decimal(str(self.config.trailing_stop_percent)) / Decimal(100)
                )
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
            "ema_fast": float(last["ema_fast"]),
            "ema_slow": float(last["ema_slow"]),
            "ema_trend": float(last.get("ema_trend", 0)) if "ema_trend" in last.index else 0,
            "rsi": float(last["rsi"]),
            "atr": float(last["atr"]),
            "volume_rel": float(last["volume_rel"]),
            "close": float(last["close"]),
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
        """Devuelve una confianza simple basada en la fuerza de la señal."""
        if signal_type == "HOLD":
            return Decimal("0")
        last = df.iloc[-1]
        fast = last["ema_fast"]
        slow = last["ema_slow"]
        rsi = last["rsi"]
        vol = last["volume_rel"]
        atr = last["atr"]
        close = last["close"]

        if signal_type == "BUY":
            ema_diff = abs(fast - slow) / close if close else 0
            rsi_score = 1 - abs(rsi - 55) / 55 if not np.isnan(rsi) else 0
            vol_score = min(max(vol - 1, 0), 1) if not np.isnan(vol) else 0
            atr_score = min(atr / close, 0.2) / 0.2 if close and not np.isnan(atr) else 0
            score = min(1.0, 0.3 * ema_diff + 0.3 * rsi_score + 0.25 * vol_score + 0.15 * atr_score)
            return Decimal(str(round(score, 4)))
        # SELL
        score = min(1.0, 0.5 + 0.05 * len(df))
        return Decimal(str(round(score, 4)))

    def explain_signal(
        self,
        signal_type: str,
        row: pd.Series,
        prev: pd.Series | None = None,
    ) -> str:
        """Genera una explicación legible en español."""
        if signal_type == "HOLD":
            return "No se cumplieron las condiciones de entrada ni de salida."
        if signal_type == "BUY":
            return (
                f"Cruce alcista de EMA{self.config.fast_ema} sobre EMA{self.config.slow_ema}, "
                f"RSI={row['rsi']:.2f} (rango {self.config.rsi_lower}-{self.config.rsi_upper}), "
                f"volumen relativo={row['volume_rel']:.2f}, "
                f"ATR={row['atr']:.4f}."
            )
        # SELL
        prev_text = ""
        if prev is not None:
            prev_text = (
                f" EMA rápida pasó de {prev['ema_fast']:.4f} a {row['ema_fast']:.4f} "
                f"y lenta de {prev['ema_slow']:.4f} a {row['ema_slow']:.4f}."
            )
        return (
            f"Señal de salida: RSI={row['rsi']:.2f}, "
            f"volumen relativo={row['volume_rel']:.2f}, ATR={row['atr']:.4f}.{prev_text}"
        )

    def _build_signal(
        self,
        symbol: str,
        df: pd.DataFrame,
        signal_type: str,
        reason: str,
    ) -> SignalCreate:
        timestamp = df.index[-1].to_pydatetime() if not df.empty else datetime.now(tz=UTC)
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
