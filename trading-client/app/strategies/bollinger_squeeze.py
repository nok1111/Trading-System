"""Estrategia Bollinger Squeeze — tradea la expansión de volatilidad tras compresión."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import pandas as pd

from app.indicators import indicators as ind
from app.models.signal import SignalCreate
from app.strategies.strategy import Strategy


@dataclass
class BollingerSqueezeConfig:
    """Parámetros configurables de Bollinger Squeeze."""

    bb_period: int = 20
    bb_std: float = 2.0
    atr_period: int = 14
    atr_lookback: int = 50  # for percentile calculation
    squeeze_threshold: float = 20.0  # ATR percentile below this = squeeze
    rsi_period: int = 14
    stop_loss_percent: float = 3.0
    take_profit_percent: float = 10.0  # bigger TP — breakouts can be large
    max_hold_bars: int = 60
    trailing_stop_percent: float = 3.0


class BollingerSqueezeStrategy(Strategy):
    """Estrategia de expansión de volatilidad (Bollinger Squeeze).

    Detecta cuando la volatilidad es muy baja (squeeze) y entra cuando
    el precio rompe fuera de las Bollinger Bands con dirección clara.

    Entrada long:  ATR percentile < 20 (squeeze) + precio rompe arriba BB superior
    Salida:        Precio vuelve al centro de las bands, o SL/TP/trailing
    Funciona mejor tras consolidaciones largas que preceden movimientos grandes.
    Diferente a Breakout: este espera a que la volatilidad se comprima primero.
    """

    def __init__(self, config: BollingerSqueezeConfig | None = None) -> None:
        self.config = config or BollingerSqueezeConfig()

    @property
    def name(self) -> str:
        return "BollingerSqueezeStrategy"

    @property
    def min_bars(self) -> int:
        return max(self.config.bb_period, self.config.atr_lookback, 30) + 1

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        c = self.config
        data = df.copy()
        bb = ind.bollinger_bands(data["close"], c.bb_period, c.bb_std)
        data["bb_upper"] = bb["upper"]
        data["bb_middle"] = bb["middle"]
        data["bb_lower"] = bb["lower"]
        data["bb_width"] = (bb["upper"] - bb["lower"]) / bb["middle"].replace(0, np.nan)
        data["atr"] = ind.atr(data, c.atr_period)
        data["atr_pct"] = ind.atr_percentile(data, c.atr_period, c.atr_lookback)
        data["rsi"] = ind.rsi(data["close"], c.rsi_period)
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
        min_bars = max(self.config.bb_period, self.config.atr_lookback, 30)
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
            # Check for squeeze (low volatility)
            atr_pct = float(last["atr_pct"]) if not np.isnan(last["atr_pct"]) else 50
            in_squeeze = atr_pct < self.config.squeeze_threshold

            # Price breaks above upper BB
            prev_upper = float(prev["bb_upper"]) if not np.isnan(prev["bb_upper"]) else 0
            price_breakout = last["close"] > prev_upper

            # BB width should be expanding
            bw = float(last["bb_width"]) if not np.isnan(last["bb_width"]) else 0
            prev_bw = float(prev["bb_width"]) if not np.isnan(prev["bb_width"]) else 0
            width_expanding = bw > prev_bw

            rsi_val = float(last["rsi"]) if not np.isnan(last["rsi"]) else 50

            if in_squeeze:
                triggers.append(f"squeeze activo (ATR percentile {atr_pct:.0f} < {self.config.squeeze_threshold})")
            if price_breakout:
                triggers.append(f"precio {last['close']:.4f} rompio BB superior {prev_upper:.4f}")
            if width_expanding:
                triggers.append("ancho de bands expandiendo")
            if rsi_val > 50:
                triggers.append(f"RSI {rsi_val:.1f} confirma direccion")

            if in_squeeze and price_breakout and width_expanding:
                signal_type = "BUY"
        else:
            # Exit conditions
            bb_mid = float(last["bb_middle"]) if not np.isnan(last["bb_middle"]) else price

            if last["close"] < bb_mid:
                triggers.append(f"precio cayo bajo BB media {bb_mid:.4f}")

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
            "bb_upper": float(last["bb_upper"]) if not np.isnan(last["bb_upper"]) else 0,
            "bb_middle": float(last["bb_middle"]) if not np.isnan(last["bb_middle"]) else 0,
            "bb_lower": float(last["bb_lower"]) if not np.isnan(last["bb_lower"]) else 0,
            "bb_width": float(last["bb_width"]) if not np.isnan(last["bb_width"]) else 0,
            "atr_pct": float(last["atr_pct"]) if not np.isnan(last["atr_pct"]) else 50,
            "rsi": float(last["rsi"]) if not np.isnan(last["rsi"]) else 50,
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
        atr_pct = float(last["atr_pct"]) if not np.isnan(last["atr_pct"]) else 50
        bw = float(last["bb_width"]) if not np.isnan(last["bb_width"]) else 0
        rsi = float(last["rsi"]) if not np.isnan(last["rsi"]) else 50

        if signal_type == "BUY":
            # Tighter squeeze = higher confidence
            squeeze_score = 1.0 - min(atr_pct / 100, 1.0)
            rsi_score = min(max(rsi - 50, 0) / 25, 1.0)
            score = min(1.0, 0.50 * squeeze_score + 0.50 * rsi_score)
            return Decimal(str(round(score, 4)))
        return Decimal("0.7")

    def explain_signal(self, signal_type: str, row: pd.Series, prev: pd.Series | None = None) -> str:
        if signal_type == "HOLD":
            return "Sin squeeze ni breakout"
        close = float(row["close"])
        atr_pct = float(row["atr_pct"]) if not np.isnan(row["atr_pct"]) else 50
        bb_upper = float(row["bb_upper"]) if not np.isnan(row["bb_upper"]) else 0
        if signal_type == "BUY":
            return (
                f"Bollinger Squeeze: ATR percentile {atr_pct:.0f} (compresion), "
                f"precio {close:.4f} rompio BB superior {bb_upper:.4f}. "
                f"TP +{self.config.take_profit_percent}%, SL -{self.config.stop_loss_percent}%."
            )
        return f"Salida squeeze: precio {close:.4f} volvio a BB media."

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
