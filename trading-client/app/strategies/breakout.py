"""Estrategia Breakout basada en Donchian Channels + volumen."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import pandas as pd

from app.indicators import indicators as ind
from app.models.signal import SignalCreate
from app.strategies.strategy import Strategy


@dataclass
class BreakoutConfig:
    """Parámetros configurables de la estrategia Breakout."""

    donchian_period: int = 20
    volume_lookback: int = 20
    volume_threshold: float = 1.5
    atr_period: int = 14
    rsi_period: int = 14
    rsi_min: float = 40.0  # avoid buying in oversold (likely fakeout)
    stop_loss_percent: float = 3.0
    take_profit_percent: float = 8.0
    max_hold_bars: int = 48
    trailing_stop_percent: float = 2.5
    # Confirmation: price must close above the channel (not just wick)
    confirm_close: bool = True


class BreakoutStrategy(Strategy):
    """Estrategia de breakout de Donchian Channels + volumen.

    Entrada long:  Precio cierra arriba del canal superior de Donchian + volumen alto
    Salida:        Precio cae abajo del canal medio, o SL/TP/trailing
    Funciona mejor en mercados con volatilidad creciente o tras consolidaciones.
    """

    def __init__(self, config: BreakoutConfig | None = None) -> None:
        self.config = config or BreakoutConfig()

    @property
    def name(self) -> str:
        return "BreakoutStrategy"

    @property
    def min_bars(self) -> int:
        return max(
            self.config.donchian_period,
            self.config.atr_period,
            self.config.rsi_period,
            self.config.volume_lookback,
        ) + 1

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Añade Donchian Channels, RSI, ATR, volumen relativo."""
        c = self.config
        data = df.copy()
        dc = ind.donchian_channels(data, c.donchian_period)
        data["dc_upper"] = dc["upper"]
        data["dc_lower"] = dc["lower"]
        data["dc_middle"] = dc["middle"]
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
            self.config.donchian_period,
            self.config.atr_period,
            self.config.rsi_period,
            self.config.volume_lookback,
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
            # Entry: price breaks above upper Donchian channel + volume confirmation
            # Use the PREVIOUS candle's channel as the breakout level (avoid lookahead)
            prev_upper = prev["dc_upper"] if not np.isnan(prev["dc_upper"]) else 0
            breakout_level = prev_upper
            price_above = last["close"] > breakout_level
            volume_ok = last["volume_rel"] > self.config.volume_threshold
            rsi_ok = last["rsi"] > self.config.rsi_min if not np.isnan(last["rsi"]) else True

            if price_above:
                triggers.append(f"precio {last['close']:.4f} rompio canal superior {breakout_level:.4f}")
            if volume_ok:
                triggers.append(f"volumen {last['volume_rel']:.1f}x > {self.config.volume_threshold}x")
            if rsi_ok:
                triggers.append(f"RSI {last['rsi']:.1f} > {self.config.rsi_min}")

            if price_above and volume_ok and rsi_ok:
                signal_type = "BUY"
        else:
            # Exit conditions
            # 1. Price falls below middle channel (breakout failed)
            if not np.isnan(last["dc_middle"]) and last["close"] < last["dc_middle"]:
                triggers.append(f"precio cayo bajo canal medio {last['dc_middle']:.4f}")

            # 2. Stop loss
            if position_entry_price is not None and self.config.stop_loss_percent > 0:
                stop_level = position_entry_price * (
                    Decimal(1) - Decimal(str(self.config.stop_loss_percent)) / Decimal(100)
                )
                if price <= stop_level:
                    triggers.append("stop loss")

            # 3. Take profit
            if position_entry_price is not None and self.config.take_profit_percent > 0:
                take_level = position_entry_price * (
                    Decimal(1) + Decimal(str(self.config.take_profit_percent)) / Decimal(100)
                )
                if price >= take_level:
                    triggers.append("take profit")

            # 4. Max hold
            if bars_in_position >= self.config.max_hold_bars:
                triggers.append(f"tiempo maximo ({bars_in_position} barras)")

            # 5. Trailing stop
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
            "dc_upper": float(last["dc_upper"]) if not np.isnan(last["dc_upper"]) else 0,
            "dc_middle": float(last["dc_middle"]) if not np.isnan(last["dc_middle"]) else 0,
            "dc_lower": float(last["dc_lower"]) if not np.isnan(last["dc_lower"]) else 0,
            "rsi": float(last["rsi"]) if not np.isnan(last["rsi"]) else 50,
            "atr": float(last["atr"]) if not np.isnan(last["atr"]) else 0,
            "volume_rel": float(last["volume_rel"]) if not np.isnan(last["volume_rel"]) else 1,
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
        """Confianza basada en la fuerza del breakout y volumen."""
        if signal_type == "HOLD":
            return Decimal("0")
        last = df.iloc[-1]
        prev = df.iloc[-2]
        close = last["close"]
        prev_upper = prev["dc_upper"] if not np.isnan(prev["dc_upper"]) else close
        vol = last["volume_rel"]
        atr = last["atr"]
        rsi = last["rsi"]

        if signal_type == "BUY":
            # How far above the channel (breakout strength)
            breakout_strength = (close - prev_upper) / prev_upper if prev_upper > 0 else 0
            breakout_score = min(breakout_strength * 20, 1.0)  # 5% breakout = max score
            vol_score = min(max(vol - 1, 0) / 2, 1.0) if not np.isnan(vol) else 0  # 3x volume = max
            rsi_score = min(max(rsi - 40, 0) / 30, 1.0) if not np.isnan(rsi) else 0  # RSI 70 = max
            atr_score = min(atr / close, 0.05) / 0.05 if close and not np.isnan(atr) else 0
            score = min(1.0, 0.35 * breakout_score + 0.30 * vol_score + 0.20 * rsi_score + 0.15 * atr_score)
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
        """Explicación legible del motivo de la señal."""
        if signal_type == "HOLD":
            return "Sin condiciones de entrada ni salida"

        close = float(row["close"])
        dc_upper = float(row["dc_upper"]) if not np.isnan(row["dc_upper"]) else 0
        dc_middle = float(row["dc_middle"]) if not np.isnan(row["dc_middle"]) else 0
        vol = float(row["volume_rel"]) if not np.isnan(row["volume_rel"]) else 1
        rsi_val = float(row["rsi"]) if not np.isnan(row["rsi"]) else 50

        if signal_type == "BUY":
            prev_upper = float(prev["dc_upper"]) if prev is not None and not np.isnan(prev["dc_upper"]) else dc_upper
            return (
                f"Breakout: precio {close:.4f} rompio canal superior {prev_upper:.4f} "
                f"con volumen {vol:.1f}x y RSI {rsi_val:.1f}. "
                f"Objetivo: +{self.config.take_profit_percent}% (TP), "
                f"-{self.config.stop_loss_percent}% (SL)."
            )
        return (
            f"Salida de breakout: precio {close:.4f}, canal medio {dc_middle:.4f}. "
            f"El breakout fallo o se alcanzo SL/TP."
        )

    def _build_signal(
        self,
        symbol: str,
        data: pd.DataFrame,
        signal_type: str,
        reason: str,
    ) -> SignalCreate:
        """Construye una señal HOLD con metadata mínima."""
        last = data.iloc[-1] if len(data) > 0 else pd.Series()
        timestamp = data.index[-1] if len(data) > 0 else datetime.now(tz=UTC)
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
            metadata_json={"triggers": [], "reason": reason},
        )
