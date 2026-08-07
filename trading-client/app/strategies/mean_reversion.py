"""Estrategia MeanReversion basada en RSI + Bollinger Bands."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import pandas as pd

from app.indicators import indicators as ind
from app.models.signal import SignalCreate
from app.strategies.strategy import Strategy


@dataclass
class MeanReversionConfig:
    """Parámetros configurables de la estrategia Mean Reversion."""

    bb_period: int = 20
    bb_std: float = 2.0
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    volume_lookback: int = 20
    volume_threshold: float = 1.0
    atr_period: int = 14
    stop_loss_percent: float = 2.5
    take_profit_percent: float = 4.0
    max_hold_bars: int = 24
    trailing_stop_percent: float = 1.5
    # Exit when price reverts to the mean (middle band)
    exit_at_mean: bool = True


class MeanReversionStrategy(Strategy):
    """Estrategia de reversión a la media usando RSI + Bollinger Bands.

    Entrada long:  RSI < oversold Y precio toca/cruza banda inferior
    Salida:        RSI > overbought O precio vuelve a la media (SMA) O SL/TP
    Funciona mejor en mercados laterales (ranging).
    """

    def __init__(self, config: MeanReversionConfig | None = None) -> None:
        self.config = config or MeanReversionConfig()

    @property
    def name(self) -> str:
        return "MeanReversionStrategy"

    @property
    def min_bars(self) -> int:
        return max(
            self.config.bb_period,
            self.config.rsi_period,
            self.config.atr_period,
            self.config.volume_lookback,
        ) + 1

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Añade Bollinger Bands, RSI, ATR, volumen relativo."""
        c = self.config
        data = df.copy()
        bb = ind.bollinger_bands(data["close"], c.bb_period, c.bb_std)
        data["bb_upper"] = bb["upper"]
        data["bb_middle"] = bb["middle"]
        data["bb_lower"] = bb["lower"]
        data["bb_width"] = (bb["upper"] - bb["lower"]) / bb["middle"].replace(0, np.nan)
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
            self.config.bb_period,
            self.config.rsi_period,
            self.config.atr_period,
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
            # Entry: RSI oversold + price at/below lower band + volume confirmation
            rsi_oversold = last["rsi"] < self.config.rsi_oversold
            price_at_lower = last["close"] <= last["bb_lower"]
            # Also accept: price crossed below lower band in this candle
            crossed_below = prev["close"] > prev["bb_lower"] and last["close"] <= last["bb_lower"]
            volume_ok = last["volume_rel"] > self.config.volume_threshold

            # Band width filter: avoid trading in very tight bands (low volatility = no edge)
            band_width_ok = last["bb_width"] > 0.02 if not np.isnan(last["bb_width"]) else False

            if rsi_oversold:
                triggers.append(f"RSI oversold ({last['rsi']:.1f} < {self.config.rsi_oversold})")
            if price_at_lower or crossed_below:
                triggers.append("precio en banda inferior de Bollinger")
            if volume_ok:
                triggers.append(f"volumen relativo {last['volume_rel']:.1f}x")
            if band_width_ok:
                triggers.append("ancho de banda adecuado")

            if rsi_oversold and (price_at_lower or crossed_below) and volume_ok and band_width_ok:
                signal_type = "BUY"
        else:
            # Exit conditions
            # 1. RSI overbought
            if last["rsi"] > self.config.rsi_overbought:
                triggers.append(f"RSI overbought ({last['rsi']:.1f} > {self.config.rsi_overbought})")

            # 2. Price reverted to mean (middle band)
            if self.config.exit_at_mean and not np.isnan(last["bb_middle"]):
                if last["close"] >= last["bb_middle"]:
                    triggers.append("precio volvió a la media (banda media)")

            # 3. Stop loss
            if position_entry_price is not None and self.config.stop_loss_percent > 0:
                stop_level = position_entry_price * (
                    Decimal(1) - Decimal(str(self.config.stop_loss_percent)) / Decimal(100)
                )
                if price <= stop_level:
                    triggers.append("stop loss")

            # 4. Take profit
            if position_entry_price is not None and self.config.take_profit_percent > 0:
                take_level = position_entry_price * (
                    Decimal(1) + Decimal(str(self.config.take_profit_percent)) / Decimal(100)
                )
                if price >= take_level:
                    triggers.append("take profit")

            # 5. Max hold time
            if bars_in_position >= self.config.max_hold_bars:
                triggers.append(f"tiempo máximo ({bars_in_position} barras)")

            # 6. Trailing stop
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
            "bb_upper": float(last["bb_upper"]) if not np.isnan(last["bb_upper"]) else 0,
            "bb_middle": float(last["bb_middle"]) if not np.isnan(last["bb_middle"]) else 0,
            "bb_lower": float(last["bb_lower"]) if not np.isnan(last["bb_lower"]) else 0,
            "bb_width": float(last["bb_width"]) if not np.isnan(last["bb_width"]) else 0,
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
        """Confianza basada en qué tan extremo es el RSI y la posición vs bandas."""
        if signal_type == "HOLD":
            return Decimal("0")
        last = df.iloc[-1]
        rsi = last["rsi"]
        close = last["close"]
        bb_lower = last["bb_lower"]
        bb_middle = last["bb_middle"]
        bb_upper = last["bb_upper"]
        vol = last["volume_rel"]

        if signal_type == "BUY":
            # More confidence when RSI is deeply oversold and price far below lower band
            rsi_score = max(0, (self.config.rsi_oversold - rsi) / self.config.rsi_oversold) if not np.isnan(rsi) else 0
            # Distance below lower band as fraction of band width
            band_width = (bb_upper - bb_lower) if not np.isnan(bb_upper) else 0
            band_score = max(0, (bb_lower - close) / band_width) if band_width > 0 and not np.isnan(bb_lower) else 0
            vol_score = min(max(vol - 1, 0), 1) if not np.isnan(vol) else 0
            score = min(1.0, 0.4 * rsi_score + 0.35 * band_score + 0.25 * vol_score)
            return Decimal(str(round(score, 4)))

        # SELL
        if signal_type == "SELL":
            rsi_score = max(0, (rsi - self.config.rsi_overbought) / (100 - self.config.rsi_overbought)) if not np.isnan(rsi) else 0
            # How far above middle band
            band_width = (bb_upper - bb_lower) if not np.isnan(bb_upper) else 0
            band_score = max(0, (close - bb_middle) / band_width) if band_width > 0 and not np.isnan(bb_middle) else 0
            score = min(1.0, 0.5 * rsi_score + 0.3 * band_score + 0.2)
            return Decimal(str(round(score, 4)))

        return Decimal("0")

    def explain_signal(
        self,
        signal_type: str,
        row: pd.Series,
        prev: pd.Series | None = None,
    ) -> str:
        """Explicación legible del motivo de la señal."""
        if signal_type == "HOLD":
            return "Sin condiciones de entrada ni salida"

        rsi_val = float(row["rsi"]) if not np.isnan(row["rsi"]) else 50
        close = float(row["close"])
        bb_lower = float(row["bb_lower"]) if not np.isnan(row["bb_lower"]) else 0
        bb_upper = float(row["bb_upper"]) if not np.isnan(row["bb_upper"]) else 0
        bb_middle = float(row["bb_middle"]) if not np.isnan(row["bb_middle"]) else 0

        if signal_type == "BUY":
            return (
                f"Reversión a la media: RSI {rsi_val:.1f} (oversold < {self.config.rsi_oversold}), "
                f"precio {close:.4f} en/bajo banda inferior {bb_lower:.4f}. "
                f"Objetivo: vuelta a la media {bb_middle:.4f} (+{self.config.take_profit_percent}% TP, "
                f"-{self.config.stop_loss_percent}% SL)."
            )
        # SELL
        return (
            f"Salida de reversión: RSI {rsi_val:.1f}, precio {close:.4f}. "
            f"Banda media {bb_middle:.4f}, superior {bb_upper:.4f}. "
            f"Razón: revertió a la media o señal de overbought."
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
