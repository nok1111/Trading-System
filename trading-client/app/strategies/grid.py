"""Estrategia Grid Trading — compra baja, vende alta en rangos automáticos."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import pandas as pd

from app.indicators import indicators as ind
from app.models.signal import SignalCreate
from app.strategies.strategy import Strategy


@dataclass
class GridConfig:
    """Parámetros configurables de la estrategia Grid."""

    # Range detection: use ATR or recent high/low to set grid bounds
    atr_period: int = 14
    atr_multiplier: float = 2.0  # grid range = price ± ATR * multiplier
    grid_levels: int = 5  # number of grid levels (buys below, sells above)
    rsi_period: int = 14
    rsi_mid: float = 50.0  # only activate grid when RSI near middle (ranging market)
    rsi_range: float = 25.0  # RSI must be within 50 ± 25 (25-75) to confirm range
    volume_lookback: int = 20
    stop_loss_percent: float = 4.0  # if price breaks below grid range
    max_hold_bars: int = 72
    # Grid spacing: dynamic based on ATR or fixed percentage
    use_atr_spacing: bool = True
    grid_spacing_pct: float = 1.0  # 1% between levels if not using ATR


class GridStrategy(Strategy):
    """Estrategia Grid Trading para mercados laterales.

    Detecta un rango de trading usando ATR. Coloca niveles de compra
    debajo del precio actual y niveles de venta arriba. Cuando el precio
    cae a un nivel de compra, compra. Cuando sube a un nivel de venta, vende.

    Funciona mejor en mercados laterales (ranging) donde el precio oscila.
    NO funciona en tendencias fuertes — el stop loss protege contra eso.
    """

    def __init__(self, config: GridConfig | None = None) -> None:
        self.config = config or GridConfig()

    @property
    def name(self) -> str:
        return "GridStrategy"

    @property
    def min_bars(self) -> int:
        return max(
            self.config.atr_period,
            self.config.rsi_period,
            self.config.volume_lookback,
        ) + 1

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Añade ATR, RSI, volumen relativo, y bandas del grid."""
        c = self.config
        data = df.copy()
        data["atr"] = ind.atr(data, c.atr_period)
        data["rsi"] = ind.rsi(data["close"], c.rsi_period)
        data["volume_rel"] = ind.relative_volume(data["volume"], c.volume_lookback)

        # Calculate grid levels dynamically based on ATR
        atr_val = data["atr"].iloc[-1] if not np.isnan(data["atr"].iloc[-1]) else data["close"].iloc[-1] * 0.02
        mid_price = data["close"].iloc[-1]
        grid_range = atr_val * c.atr_multiplier

        if c.use_atr_spacing:
            spacing = grid_range / c.grid_levels
        else:
            spacing = mid_price * c.grid_spacing_pct / 100

        # Grid levels: buys below, sells above
        data["grid_upper"] = mid_price + grid_range
        data["grid_lower"] = mid_price - grid_range
        data["grid_spacing"] = spacing
        for i in range(c.grid_levels):
            data[f"grid_buy_{i}"] = mid_price - spacing * (i + 1)
            data[f"grid_sell_{i}"] = mid_price + spacing * (i + 1)

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

        # Check if market is ranging (RSI near middle)
        rsi_val = last["rsi"] if not np.isnan(last["rsi"]) else 50
        is_ranging = abs(rsi_val - self.config.rsi_mid) < self.config.rsi_range

        # Grid levels
        spacing = float(last["grid_spacing"]) if not np.isnan(last["grid_spacing"]) else float(close) * 0.01
        mid_price = float(last["close"])
        grid_lower = mid_price - spacing * self.config.grid_levels
        grid_upper = mid_price + spacing * self.config.grid_levels

        if not has_position:
            # Buy when price touches the lowest grid level (bottom of range)
            buy_level = mid_price - spacing
            price_at_buy = last["close"] <= buy_level

            # Only buy if ranging and price is near the bottom of the grid
            if is_ranging and price_at_buy:
                triggers.append(f"precio {last['close']:.4f} en nivel de compra grid {buy_level:.4f}")
                triggers.append(f"RSI {rsi_val:.1f} en rango lateral")
                signal_type = "BUY"
            elif not is_ranging:
                triggers.append(f"RSI {rsi_val:.1f} fuera de rango lateral — grid inactivo")
        else:
            # Sell when price reaches the sell level (top of grid)
            sell_level = mid_price + spacing
            if last["close"] >= sell_level:
                triggers.append(f"precio {last['close']:.4f} en nivel de venta grid {sell_level:.4f}")

            # Stop loss: price broke below grid range
            if position_entry_price is not None and self.config.stop_loss_percent > 0:
                stop_level = position_entry_price * (
                    Decimal(1) - Decimal(str(self.config.stop_loss_percent)) / Decimal(100)
                )
                if price <= stop_level:
                    triggers.append("stop loss — precio rompio el rango del grid")

            # Max hold
            if bars_in_position >= self.config.max_hold_bars:
                triggers.append(f"tiempo maximo ({bars_in_position} barras)")

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
            # Take profit = next grid level up
            take_profit = price + Decimal(str(spacing))
        elif signal_type == "SELL":
            stop_loss = Decimal("0")
            take_profit = Decimal("0")

        metadata = {
            "grid_upper": grid_upper,
            "grid_lower": grid_lower,
            "grid_spacing": spacing,
            "rsi": float(rsi_val),
            "atr": float(last["atr"]) if not np.isnan(last["atr"]) else 0,
            "volume_rel": float(last["volume_rel"]) if not np.isnan(last["volume_rel"]) else 1,
            "close": float(last["close"]),
            "is_ranging": is_ranging,
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
        """Confianza basada en qué tan cerca está el precio del nivel del grid."""
        if signal_type == "HOLD":
            return Decimal("0")
        last = df.iloc[-1]
        rsi = last["rsi"] if not np.isnan(last["rsi"]) else 50
        vol = last["volume_rel"] if not np.isnan(last["volume_rel"]) else 1

        if signal_type == "BUY":
            # More confidence when RSI is close to 50 (ranging) and volume is low
            rsi_score = 1 - abs(rsi - 50) / 50
            vol_score = 1 - min(max(vol - 1, 0), 1)  # lower volume = more confidence in range
            score = min(1.0, 0.6 * rsi_score + 0.4 * vol_score)
            return Decimal(str(round(score, 4)))

        # SELL
        return Decimal("0.7")

    def explain_signal(
        self,
        signal_type: str,
        row: pd.Series,
        prev: pd.Series | None = None,
    ) -> str:
        """Explicación legible del motivo de la señal."""
        if signal_type == "HOLD":
            return "Grid inactivo — precio fuera de niveles o mercado no lateral"

        close = float(row["close"])
        rsi_val = float(row["rsi"]) if not np.isnan(row["rsi"]) else 50
        spacing = float(row["grid_spacing"]) if not np.isnan(row["grid_spacing"]) else 0

        if signal_type == "BUY":
            buy_level = close - spacing if spacing else close
            return (
                f"Grid buy: precio {close:.4f} cerca del nivel inferior {buy_level:.4f}. "
                f"RSI {rsi_val:.1f} confirma mercado lateral. "
                f"Objetivo: vender en siguiente nivel grid (+{spacing:.4f})."
            )
        return (
            f"Grid sell: precio {close:.4f} alcanzo nivel superior. "
            f"RSI {rsi_val:.1f}. Venta del grid level."
        )

    def _build_signal(
        self,
        symbol: str,
        data: pd.DataFrame,
        signal_type: str,
        reason: str,
    ) -> SignalCreate:
        """Construye una señal HOLD con metadata mínima."""
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
