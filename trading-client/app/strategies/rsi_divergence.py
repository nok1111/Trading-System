"""Estrategia RSI Divergence — detecta reverses cuando precio y RSI divergen."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import pandas as pd

from app.indicators import indicators as ind
from app.models.signal import SignalCreate
from app.strategies.strategy import Strategy


@dataclass
class RSIDivergenceConfig:
    """Parámetros configurables de RSI Divergence."""

    rsi_period: int = 14
    divergence_lookback: int = 20  # bars to look back for divergence
    rsi_oversold: float = 35.0  # RSI must be oversold for bullish divergence
    rsi_overbought: float = 65.0  # RSI must be overbought for bearish divergence
    atr_period: int = 14
    stop_loss_percent: float = 3.0
    take_profit_percent: float = 6.0
    max_hold_bars: int = 36
    trailing_stop_percent: float = 2.0
    # Require at least N bars between pivots
    min_pivot_distance: int = 5


class RSIDivergenceStrategy(Strategy):
    """Estrategia basada en divergencia de RSI.

    Bullish divergence: precio hace un low más bajo, pero RSI hace un low más alto.
    Bearish divergence: precio hace un high más alto, pero RSI hace un high más bajo.

    Entrada long:  Bullish divergence + RSI < 35 (oversold)
    Salida:        RSI overbought, o SL/TP/trailing
    Funciona mejor para detectar reverses antes que otros indicadores.
    """

    def __init__(self, config: RSIDivergenceConfig | None = None) -> None:
        self.config = config or RSIDivergenceConfig()

    @property
    def name(self) -> str:
        return "RSIDivergenceStrategy"

    @property
    def min_bars(self) -> int:
        return max(self.config.divergence_lookback + 10, self.config.rsi_period + 10, 30)

    def _find_pivots(self, series: pd.Series, lookback: int) -> list[tuple[int, float]]:
        """Find local minima/maxima in the last N bars."""
        pivots: list[tuple[int, float]] = []
        vals = series.values
        for i in range(2, len(vals) - 2):
            if i < len(vals) - lookback:
                continue
            if np.isnan(vals[i]):
                continue
            # Simple pivot: lower than neighbors
            if vals[i] < vals[i - 1] and vals[i] < vals[i + 1] and vals[i] < vals[i - 2] and vals[i] < vals[i + 2]:
                pivots.append((i, float(vals[i])))
        return pivots

    def _find_pivot_highs(self, series: pd.Series, lookback: int) -> list[tuple[int, float]]:
        """Find local maxima in the last N bars."""
        pivots: list[tuple[int, float]] = []
        vals = series.values
        for i in range(2, len(vals) - 2):
            if i < len(vals) - lookback:
                continue
            if np.isnan(vals[i]):
                continue
            if vals[i] > vals[i - 1] and vals[i] > vals[i + 1] and vals[i] > vals[i - 2] and vals[i] > vals[i + 2]:
                pivots.append((i, float(vals[i])))
        return pivots

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        c = self.config
        data = df.copy()
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
        if len(data) < self.min_bars + 1:
            return self._build_signal(symbol, data, "HOLD", "Datos insuficientes")

        last = data.iloc[-1]
        close = Decimal(str(last["close"]))
        price = current_price if current_price is not None else close
        timestamp = data.index[-1]
        if isinstance(timestamp, pd.Timestamp):
            timestamp = timestamp.to_pydatetime()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)

        signal_type = "HOLD"
        triggers: list[str] = []
        rsi_val = float(last["rsi"]) if not np.isnan(last["rsi"]) else 50

        if not has_position:
            # Detect bullish divergence: price lower low, RSI higher low
            price_lows = self._find_pivots(data["close"], self.config.divergence_lookback)
            rsi_lows = self._find_pivots(data["rsi"], self.config.divergence_lookback)

            bullish_div = False
            if len(price_lows) >= 2 and len(rsi_lows) >= 2:
                p1_idx, p1_val = price_lows[-2]
                p2_idx, p2_val = price_lows[-1]
                r1_idx, r1_val = rsi_lows[-2]
                r2_idx, r2_val = rsi_lows[-1]

                # Price lower low, RSI higher low
                if p2_val < p1_val and r2_val > r1_val and rsi_val < self.config.rsi_oversold:
                    bullish_div = True
                    triggers.append(
                        f"divergencia bullish: precio {p2_val:.4f} < {p1_val:.4f}, "
                        f"RSI {r2_val:.1f} > {r1_val:.1f}"
                    )
                    triggers.append(f"RSI {rsi_val:.1f} < {self.config.rsi_oversold} (oversold)")

            if bullish_div:
                signal_type = "BUY"
        else:
            # Exit: RSI overbought or divergence exhausted
            if rsi_val > self.config.rsi_overbought:
                triggers.append(f"RSI {rsi_val:.1f} > {self.config.rsi_overbought} (overbought)")

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

        explanation = self.explain_signal(signal_type, last, None)
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
            "rsi": rsi_val,
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
        rsi = float(last["rsi"]) if not np.isnan(last["rsi"]) else 50

        if signal_type == "BUY":
            # Deeper oversold = higher confidence
            rsi_score = 1.0 - min(rsi / self.config.rsi_oversold, 1.0)
            return Decimal(str(round(min(rsi_score, 1.0), 4)))
        return Decimal("0.7")

    def explain_signal(self, signal_type: str, row: pd.Series, prev: pd.Series | None = None) -> str:
        if signal_type == "HOLD":
            return "Sin divergencia RSI detectada"
        rsi_val = float(row["rsi"]) if not np.isnan(row["rsi"]) else 50
        close = float(row["close"])
        if signal_type == "BUY":
            return (
                f"RSI Divergence bullish: RSI {rsi_val:.1f} (oversold) con divergencia positiva. "
                f"Precio {close:.4f}. TP +{self.config.take_profit_percent}%, SL -{self.config.stop_loss_percent}%."
            )
        return f"RSI overbought {rsi_val:.1f}. Salida de divergencia."

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
