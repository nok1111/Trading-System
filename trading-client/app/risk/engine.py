"""Risk Engine determinista con circuit breakers y trailing stop en Decimal.

Reemplaza la lógica de auto-close que estaba en agent.py con un motor
determinista que tiene poder de veto sobre toda orden.

Circuit breakers: 4 estados
- NORMAL: operación normal
- WARNING: reduce position size al 50%
- HALT_TRADING: bloquea nuevas compras, permite closes
- EMERGENCY_HALT: bloquea todo excepto cancelaciones

Trailing stop con Decimal:
1. Below entry: usa stop-loss original
2. Above entry (< 2% up): stop en breakeven (entry)
3. Clearly in profit: trail at 2% below peak, nunca below entry
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

from app.config import get_settings as _get_settings

_settings = _get_settings()
TRAILING_STOP_PCT = Decimal(str(_settings.TRAILING_STOP_PCT / 100))  # configurable, stored as percentage
BREAKEVEN_THRESHOLD = Decimal(str(1 + _settings.BREAKEVEN_THRESHOLD_PCT / 100))  # configurable


class CircuitBreakerState(StrEnum):
    """Estados del circuit breaker."""

    NORMAL = "NORMAL"
    WARNING = "WARNING"
    HALT_TRADING = "HALT_TRADING"
    EMERGENCY_HALT = "EMERGENCY_HALT"


@dataclass
class RiskDecision:
    """Decisión del Risk Engine para una orden propuesta."""

    allowed: bool
    reason: str
    severity: str = "info"  # info, warning, block, kill
    circuit_breaker_state: CircuitBreakerState = CircuitBreakerState.NORMAL
    adjusted_quantity: Decimal | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TrailingStopResult:
    """Resultado de evaluar el trailing stop para una posición."""

    should_close: bool
    reason: str
    effective_sl: Decimal
    peak: Decimal
    close_type: str = ""  # stop_loss, breakeven, trailing, take_profit


@dataclass
class TechnicalExitResult:
    """Resultado de evaluar criterios técnicos de salida."""

    should_close: bool
    reason: str
    indicator: str = ""  # rsi, macd, time, volume
    value: float = 0.0


@dataclass
class AutoSellConfig:
    """Configuración de umbrales para auto-sell técnico."""

    rsi_overbought: float = 70.0
    max_position_hours: float = 24.0
    min_volume_relative: float = 0.5
    macd_bearish_enabled: bool = True
    rsi_enabled: bool = True
    time_enabled: bool = True
    volume_enabled: bool = True


class CircuitBreaker:
    """Circuit breaker con 4 estados y transiciones deterministas.

    Transiciones:
    - NORMAL → WARNING: daily loss > 50% del límite
    - WARNING → HALT_TRADING: daily loss > 80% del límite
    - HALT_TRADING → EMERGENCY_HALT: daily loss > 100% del límite
    - Cualquiera → NORMAL: daily loss recupera a < 30% del límite
    """

    def __init__(
        self,
        daily_loss_limit: Decimal,
        warning_threshold: Decimal = Decimal("0.5"),
        halt_threshold: Decimal = Decimal("0.8"),
        emergency_threshold: Decimal = Decimal("1.0"),
        recovery_threshold: Decimal = Decimal("0.3"),
    ) -> None:
        self._state = CircuitBreakerState.NORMAL
        self._daily_loss_limit = daily_loss_limit
        self._warning_threshold = warning_threshold
        self._halt_threshold = halt_threshold
        self._emergency_threshold = emergency_threshold
        self._recovery_threshold = recovery_threshold
        self._transition_log: list[dict[str, Any]] = []

    @property
    def state(self) -> CircuitBreakerState:
        return self._state

    @property
    def transition_log(self) -> list[dict[str, Any]]:
        return list(self._transition_log)

    def update(self, daily_pnl: Decimal, equity: Decimal) -> CircuitBreakerState:
        """Actualiza el estado del circuit breaker basado en el PnL diario."""
        if equity <= 0:
            return self._state

        loss_ratio = abs(min(daily_pnl, Decimal("0"))) / self._daily_loss_limit

        prev_state = self._state

        if loss_ratio >= self._emergency_threshold:
            self._state = CircuitBreakerState.EMERGENCY_HALT
        elif loss_ratio >= self._halt_threshold:
            self._state = CircuitBreakerState.HALT_TRADING
        elif loss_ratio >= self._warning_threshold:
            if self._state == CircuitBreakerState.NORMAL:
                self._state = CircuitBreakerState.WARNING
        elif loss_ratio <= self._recovery_threshold:
            self._state = CircuitBreakerState.NORMAL

        if prev_state != self._state:
            self._transition_log.append({
                "timestamp": datetime.now(UTC).isoformat(),
                "from": prev_state.value,
                "to": self._state.value,
                "loss_ratio": str(loss_ratio),
            })
            logger.warning(
                f"Circuit breaker: {prev_state.value} → {self._state.value} "
                f"(loss_ratio={loss_ratio:.2%})"
            )

        return self._state

    def allows_new_orders(self) -> bool:
        """Whether new buy orders are allowed."""
        return self._state in (CircuitBreakerState.NORMAL, CircuitBreakerState.WARNING)

    def allows_closes(self) -> bool:
        """Whether close/sell orders are allowed."""
        return self._state != CircuitBreakerState.EMERGENCY_HALT

    def position_size_multiplier(self) -> Decimal:
        """Multiplier for position size based on current state."""
        if self._state == CircuitBreakerState.WARNING:
            return Decimal("0.5")
        return Decimal("1.0")


class RiskEngine:
    """Risk Engine determinista con poder de veto sobre toda orden.

    Reglas:
    - Max position size (configurable)
    - Max open positions
    - Daily loss limit con circuit breaker
    - Diversificación (no mismo símbolo dos veces)
    - Trailing stop con Decimal
    - Take-profit check
    """

    def __init__(
        self,
        max_position_size_pct: Decimal = Decimal("10"),
        max_risk_per_trade_pct: Decimal = Decimal("1"),
        max_daily_loss_pct: Decimal = Decimal("3"),
        min_cash_reserve_pct: Decimal = Decimal("20"),
        max_open_positions: int = 20,
        max_order_usd: Decimal = Decimal("500"),
        daily_loss_limit_usd: Decimal = Decimal("100"),
    ) -> None:
        self._max_position_size_pct = max_position_size_pct
        self._max_risk_per_trade_pct = max_risk_per_trade_pct
        self._max_daily_loss_pct = max_daily_loss_pct
        self._min_cash_reserve_pct = min_cash_reserve_pct
        self._max_open_positions = max_open_positions
        self._max_order_usd = max_order_usd
        self._daily_loss_limit_usd = daily_loss_limit_usd
        self._circuit_breaker = CircuitBreaker(daily_loss_limit_usd)
        self._position_peaks: dict[str, Decimal] = {}
        self._peaks_lock = threading.Lock()

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        return self._circuit_breaker

    def evaluate_order(
        self,
        side: str,  # "buy" or "sell"
        symbol: str,
        entry_price: Decimal,
        stop_loss: Decimal | None = None,
        account_cash: Decimal = Decimal("0"),
        account_equity: Decimal = Decimal("0"),
        daily_pnl: Decimal = Decimal("0"),
        open_positions: list[dict] | None = None,
        open_positions_count: int = 0,
    ) -> RiskDecision:
        """Evalúa si una orden puede ejecutarse. Tiene poder de veto."""
        open_positions = open_positions or []

        # Update circuit breaker
        self._circuit_breaker.update(daily_pnl, account_equity)
        cb_state = self._circuit_breaker.state

        # EMERGENCY_HALT: bloquea todo excepto cancelaciones
        if cb_state == CircuitBreakerState.EMERGENCY_HALT:
            return RiskDecision(
                allowed=False,
                reason="EMERGENCY_HALT: bloqueo total por pérdida diaria excedida",
                severity="kill",
                circuit_breaker_state=cb_state,
            )

        if side.lower() == "buy":
            # HALT_TRADING: bloquea nuevas compras
            if cb_state == CircuitBreakerState.HALT_TRADING:
                return RiskDecision(
                    allowed=False,
                    reason="HALT_TRADING: nuevas compras bloqueadas por circuit breaker",
                    severity="block",
                    circuit_breaker_state=cb_state,
                )

            # Max open positions
            if open_positions_count >= self._max_open_positions:
                return RiskDecision(
                    allowed=False,
                    reason=f"Máximo de posiciones abiertas alcanzado ({self._max_open_positions})",
                    severity="block",
                    circuit_breaker_state=cb_state,
                )

            # Diversificación: no mismo símbolo
            if any(p.get("symbol") == symbol and p.get("status") == "open" for p in open_positions):
                return RiskDecision(
                    allowed=False,
                    reason=f"Ya existe posición abierta en {symbol}",
                    severity="block",
                    circuit_breaker_state=cb_state,
                )

            # Precio inválido
            if entry_price <= 0:
                return RiskDecision(
                    allowed=False,
                    reason="Precio de entrada inválido",
                    severity="block",
                    circuit_breaker_state=cb_state,
                )

            # Reserva mínima de cash
            min_reserve = account_equity * self._min_cash_reserve_pct / Decimal("100")
            available = account_cash - min_reserve
            if available <= 0:
                return RiskDecision(
                    allowed=False,
                    reason=f"Cash disponible ({account_cash}) no supera reserva mínima ({min_reserve})",
                    severity="block",
                    circuit_breaker_state=cb_state,
                )

            # Tamaño máximo de posición
            max_value = account_equity * self._max_position_size_pct / Decimal("100")
            max_value = min(max_value, available)
            max_qty = max_value / entry_price

            # Risk per trade
            if stop_loss and stop_loss > 0 and stop_loss < entry_price:
                risk_per_share = entry_price - stop_loss
                max_risk_amount = account_equity * self._max_risk_per_trade_pct / Decimal("100")
                max_qty_by_risk = max_risk_amount / risk_per_share
                max_qty = min(max_qty, max_qty_by_risk)

            # Max order USD
            order_value = max_qty * entry_price
            if order_value > self._max_order_usd:
                max_qty = self._max_order_usd / entry_price

            # Circuit breaker WARNING: reduce al 50%
            multiplier = self._circuit_breaker.position_size_multiplier()
            if multiplier < Decimal("1"):
                max_qty = max_qty * multiplier

            if max_qty <= 0:
                return RiskDecision(
                    allowed=False,
                    reason="Tamaño de posición calculado es cero",
                    severity="block",
                    circuit_breaker_state=cb_state,
                )

            return RiskDecision(
                allowed=True,
                reason="Orden aprobada",
                circuit_breaker_state=cb_state,
                adjusted_quantity=max_qty.quantize(Decimal("0.00000001")),
                metadata={"max_value": str(max_value), "multiplier": str(multiplier)},
            )

        elif side.lower() == "sell":
            # HALT_TRADING y EMERGENCY_HALT ya filtrados arriba para EMERGENCY
            # Sells siempre permitidos (excepto EMERGENCY_HALT)
            return RiskDecision(
                allowed=True,
                reason="Venta aprobada",
                circuit_breaker_state=cb_state,
            )

        return RiskDecision(
            allowed=False,
            reason=f"Side desconocido: {side}",
            severity="block",
            circuit_breaker_state=cb_state,
        )

    def evaluate_trailing_stop(
        self,
        symbol: str,
        entry_price: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
        current_price: Decimal,
    ) -> TrailingStopResult:
        """Evalúa el trailing stop para una posición abierta.

        Lógica migrada de agent.py _check_auto_close, ahora con Decimal:
        1. Below entry: usa stop-loss original
        2. Above entry (< 2% up): stop en breakeven
        3. Clearly in profit: trail at 2% below peak, nunca below entry
        """
        # Track peak
        with self._peaks_lock:
            peak = self._position_peaks.get(symbol, entry_price)
            if current_price > peak:
                peak = current_price
                self._position_peaks[symbol] = peak

        # Determine effective stop-loss based on peak (highest price seen)
        # This ensures the stop never goes backwards even if price drops
        if peak > entry_price * BREAKEVEN_THRESHOLD:
            # Position was clearly in profit: trail at 2% below peak, never below entry
            trailing_sl = peak * (Decimal("1") - TRAILING_STOP_PCT)
            effective_sl = max(entry_price, trailing_sl)
        elif peak > entry_price:
            # Position was barely in profit (< 2% up): breakeven stop
            effective_sl = entry_price
        else:
            # Never been in profit: use original stop-loss
            effective_sl = stop_loss

        # Check if should close
        if current_price <= effective_sl:
            if effective_sl == entry_price and current_price < entry_price:
                return TrailingStopResult(
                    should_close=True,
                    reason=f"Breakeven stop: precio {current_price} bajó hacia entry {entry_price}",
                    effective_sl=effective_sl,
                    peak=peak,
                    close_type="breakeven",
                )
            elif effective_sl > entry_price:
                return TrailingStopResult(
                    should_close=True,
                    reason=f"Trailing stop: peak fue {peak}, vendiendo a {current_price}",
                    effective_sl=effective_sl,
                    peak=peak,
                    close_type="trailing",
                )
            else:
                return TrailingStopResult(
                    should_close=True,
                    reason=f"Stop-loss: precio {current_price} <= SL {effective_sl}",
                    effective_sl=effective_sl,
                    peak=peak,
                    close_type="stop_loss",
                )

        if current_price >= take_profit:
            return TrailingStopResult(
                should_close=True,
                reason=f"Take-profit: precio {current_price} >= TP {take_profit}",
                effective_sl=effective_sl,
                peak=peak,
                close_type="take_profit",
            )

        return TrailingStopResult(
            should_close=False,
            reason="Posición dentro de rangos",
            effective_sl=effective_sl,
            peak=peak,
        )

    def clear_position_peak(self, symbol: str) -> None:
        """Limpia el peak tracking después de cerrar una posición."""
        with self._peaks_lock:
            self._position_peaks.pop(symbol, None)

    def evaluate_trailing_stop_short(
        self,
        symbol: str,
        entry_price: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
        current_price: Decimal,
    ) -> TrailingStopResult:
        """Evalúa el trailing stop para una posición SHORT (inverted logic).

        For shorts:
        - Profit when price goes DOWN
        - SL is ABOVE entry price
        - TP is BELOW entry price
        - Track lowest price (trough) instead of peak
        1. Above entry: use original stop-loss
        2. Below entry (< 2% down): stop at breakeven
        3. Clearly in profit: trail at 2% above trough, never above entry
        """
        # Track trough (lowest price seen)
        with self._peaks_lock:
            trough = self._position_peaks.get(symbol, entry_price)
            if current_price < trough:
                trough = current_price
                self._position_peaks[symbol] = trough

        # Determine effective stop-loss based on trough (lowest price seen)
        if trough < entry_price * (Decimal("1") - BREAKEVEN_THRESHOLD):
            # Position was clearly in profit: trail at 2% above trough, never above entry
            trailing_sl = trough * (Decimal("1") + TRAILING_STOP_PCT)
            effective_sl = min(entry_price, trailing_sl)
        elif trough < entry_price:
            # Position was barely in profit (< 2% down): breakeven stop
            effective_sl = entry_price
        else:
            # Never been in profit: use original stop-loss
            effective_sl = stop_loss

        # Check if should close (price goes UP for shorts = bad)
        if current_price >= effective_sl:
            if effective_sl == entry_price and current_price > entry_price:
                return TrailingStopResult(
                    should_close=True,
                    reason=f"Breakeven stop (short): precio {current_price} subió hacia entry {entry_price}",
                    effective_sl=effective_sl,
                    peak=trough,
                    close_type="breakeven",
                )
            elif effective_sl < entry_price:
                return TrailingStopResult(
                    should_close=True,
                    reason=f"Trailing stop (short): trough fue {trough}, comprando a {current_price}",
                    effective_sl=effective_sl,
                    peak=trough,
                    close_type="trailing",
                )
            else:
                return TrailingStopResult(
                    should_close=True,
                    reason=f"Stop-loss (short): precio {current_price} >= SL {effective_sl}",
                    effective_sl=effective_sl,
                    peak=trough,
                    close_type="stop_loss",
                )

        # TP for shorts: price goes DOWN to TP
        if current_price <= take_profit:
            return TrailingStopResult(
                should_close=True,
                reason=f"Take-profit (short): precio {current_price} <= TP {take_profit}",
                effective_sl=effective_sl,
                peak=trough,
                close_type="take_profit",
            )

        return TrailingStopResult(
            should_close=False,
            reason="Posición short dentro de rangos",
            effective_sl=effective_sl,
            peak=trough,
        )

    def get_position_peak(self, symbol: str) -> Decimal | None:
        """Devuelve el peak tracking para un símbolo."""
        with self._peaks_lock:
            return self._position_peaks.get(symbol)

    def evaluate_technical_exit(
        self,
        symbol: str,
        entry_price: Decimal,
        current_price: Decimal,
        opened_at: datetime,
        config: AutoSellConfig | None = None,
    ) -> TechnicalExitResult:
        """Evalúa criterios técnicos adicionales para salir de una posición.

        Criterios (todos configurables):
        - RSI overbought: RSI > threshold → vender
        - MACD bearish cross: MACD line cruza bajo signal line → vender
        - Tiempo máximo: posición abierta > max_hours → vender
        - Caída de volumen: volume_relative < threshold → vender
        """
        if config is None:
            config = AutoSellConfig()

        import httpx

        # 1. Time-based exit
        if config.time_enabled and config.max_position_hours > 0:
            now = datetime.now(UTC)
            if opened_at.tzinfo is None:
                from datetime import timezone
                opened_at = opened_at.replace(tzinfo=timezone.utc)
            elapsed_hours = (now - opened_at).total_seconds() / 3600
            if elapsed_hours >= config.max_position_hours:
                return TechnicalExitResult(
                    should_close=True,
                    reason=f"Tiempo máximo: {elapsed_hours:.1f}h >= {config.max_position_hours}h",
                    indicator="time",
                    value=elapsed_hours,
                )

        # Fetch klines for technical indicators
        try:
            from app.brokers.models import normalize_symbol, denormalize_symbol
            from app.config import get_settings
            settings = get_settings()
            canonical = normalize_symbol(symbol)
            native = denormalize_symbol(canonical, settings.DEFAULT_BROKER_ID)
            base_url = settings.PUBLIC_MARKET_DATA_URL
            resp = httpx.get(
                f"{base_url}/api/v3/klines",
                params={"symbol": native, "interval": "1h", "limit": 50},
                timeout=10.0,
            )
            if resp.status_code != 200:
                return TechnicalExitResult(should_close=False, reason="No klines")
            klines = resp.json()
        except Exception:
            return TechnicalExitResult(should_close=False, reason="klines fetch failed")

        closes = [float(k[4]) for k in klines]
        volumes = [float(k[5]) for k in klines]
        if len(closes) < 26:
            return TechnicalExitResult(should_close=False, reason="Insufficient data")

        # 2. RSI overbought
        if config.rsi_enabled and config.rsi_overbought > 0:
            rsi = self._calc_rsi(closes, period=14)
            if rsi >= config.rsi_overbought:
                return TechnicalExitResult(
                    should_close=True,
                    reason=f"RSI overbought: {rsi:.1f} >= {config.rsi_overbought}",
                    indicator="rsi",
                    value=rsi,
                )

        # 3. MACD bearish cross
        if config.macd_bearish_enabled:
            macd_line, signal_line = self._calc_macd(closes)
            if macd_line is not None and signal_line is not None:
                prev_macd, prev_signal = self._calc_macd(closes[:-1])
                if prev_macd is not None and prev_signal is not None:
                    if prev_macd >= prev_signal and macd_line < signal_line:
                        return TechnicalExitResult(
                            should_close=True,
                            reason=f"MACD bearish cross: MACD {macd_line:.6f} < Signal {signal_line:.6f}",
                            indicator="macd",
                            value=macd_line,
                        )

        # 4. Volume drop
        if config.volume_enabled and config.min_volume_relative > 0 and len(volumes) >= 20:
            avg_vol = sum(volumes[-20:]) / 20
            current_vol = volumes[-1]
            vol_relative = current_vol / avg_vol if avg_vol > 0 else 1.0
            if vol_relative < config.min_volume_relative:
                return TechnicalExitResult(
                    should_close=True,
                    reason=f"Caída de volumen: {vol_relative:.2f}x < {config.min_volume_relative}x",
                    indicator="volume",
                    value=vol_relative,
                )

        return TechnicalExitResult(should_close=False, reason="Indicadores OK")

    @staticmethod
    def _calc_rsi(closes: list[float], period: int = 14) -> float:
        """Calculate RSI from close prices."""
        if len(closes) < period + 1:
            return 50.0
        gains = []
        losses = []
        for i in range(1, len(closes)):
            change = closes[i] - closes[i - 1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _calc_macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[float | None, float | None]:
        """Calculate MACD line and signal line."""
        if len(closes) < slow + signal:
            return None, None

        def ema(data: list[float], period: int) -> list[float]:
            multiplier = 2 / (period + 1)
            ema_values = [data[0]]
            for i in range(1, len(data)):
                ema_values.append(data[i] * multiplier + ema_values[-1] * (1 - multiplier))
            return ema_values

        ema_fast = ema(closes, fast)
        ema_slow = ema(closes, slow)
        macd_values = [f - s for f, s in zip(ema_fast, ema_slow)]
        signal_values = ema(macd_values[-(signal + len(macd_values) - len(macd_values)):], signal)
        if len(signal_values) == 0:
            return macd_values[-1], None
        return macd_values[-1], signal_values[-1]
