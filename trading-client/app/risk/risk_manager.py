"""Gestión de riesgo para señales de trading."""

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from app.config import Settings
from app.database.models.account_snapshot import AccountSnapshot
from app.database.models.position import Position
from app.models.signal import SignalCreate

if TYPE_CHECKING:
    pass


@dataclass
class RiskResult:
    """Resultado de la evaluación de riesgo de una señal."""

    allowed: bool
    reason: str | None = None


class RiskManager:
    """Evalúa si una señal cumple las reglas de riesgo configuradas."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def evaluate_signal(
        self,
        signal: SignalCreate,
        account: AccountSnapshot,
        open_positions: list[Position],
    ) -> RiskResult:
        """Determina si se puede actuar sobre una señal."""
        if signal.signal_type == "HOLD":
            return RiskResult(allowed=False, reason="Señal HOLD, no se ejecuta")

        if self.settings.TRADING_MODE == "live" and not self.settings.LIVE_TRADING_ENABLED:
            return RiskResult(
                allowed=False,
                reason="Trading live deshabilitado por configuración",
            )

        if signal.signal_type == "BUY":
            return self._evaluate_buy(signal, account, open_positions)
        if signal.signal_type == "SELL":
            return self._evaluate_sell(signal, account, open_positions)

        return RiskResult(allowed=False, reason=f"Tipo de señal desconocido: {signal.signal_type}")

    def _evaluate_buy(
        self,
        signal: SignalCreate,
        account: AccountSnapshot,
        open_positions: list[Position],
    ) -> RiskResult:
        # Max positions limit removed per user request — no cap on open positions
        pass

        if signal.entry_price is None or signal.entry_price <= 0:
            return RiskResult(allowed=False, reason="Precio de entrada inválido")

        # Reserva mínima de cash: no operar si el cash disponible es menor al reserve
        min_reserve = (
            account.equity * Decimal(str(self.settings.MIN_CASH_RESERVE_PERCENT)) / Decimal(100)
        )
        if account.cash - min_reserve <= 0:
            return RiskResult(
                allowed=False,
                reason=f"Cash disponible ({account.cash}) no supera la reserva mínima ({min_reserve})",
            )

        # Tamaño máximo permitido por la regla de posición
        max_position_value = (
            account.equity * Decimal(str(self.settings.MAX_POSITION_SIZE_PERCENT)) / Decimal(100)
        )
        # No exceder el cash disponible menos la reserva mínima
        available_for_trade = account.cash - min_reserve
        max_position_value = min(max_position_value, available_for_trade)
        max_qty_by_size = max_position_value / signal.entry_price

        # Si hay stop loss, verificar riesgo por trade
        if signal.suggested_stop_loss is not None and signal.suggested_stop_loss > 0:
            risk_per_share = signal.entry_price - signal.suggested_stop_loss
            if risk_per_share <= 0:
                return RiskResult(
                    allowed=False,
                    reason="Stop loss igual o mayor que el precio de entrada",
                )
            max_risk_amount = (
                account.equity
                * Decimal(str(self.settings.MAX_RISK_PER_TRADE_PERCENT))
                / Decimal(100)
            )
            max_qty_by_risk = max_risk_amount / risk_per_share
            max_qty = min(max_qty_by_size, max_qty_by_risk)
        else:
            max_qty = max_qty_by_size

        if max_qty <= 0:
            return RiskResult(allowed=False, reason="Tamaño de posición calculado es cero")

        # Límite diario de pérdida
        daily_loss_limit = (
            account.equity * Decimal(str(self.settings.MAX_DAILY_LOSS_PERCENT)) / Decimal(100)
        )
        if account.daily_pnl <= -daily_loss_limit:
            return RiskResult(
                allowed=False,
                reason="Límite diario de pérdida alcanzado",
            )

        # Verificación de exposición simple: no se permite comprar el mismo símbolo dos veces
        if any(p.symbol == signal.symbol and p.status == "open" for p in open_positions):
            return RiskResult(
                allowed=False,
                reason=f"Ya existe una posición abierta en {signal.symbol}",
            )

        return RiskResult(allowed=True)

    def _evaluate_sell(
        self,
        signal: SignalCreate,
        account: AccountSnapshot,
        open_positions: list[Position],
    ) -> RiskResult:
        position = next(
            (p for p in open_positions if p.symbol == signal.symbol and p.status == "open"),
            None,
        )
        if position is None:
            return RiskResult(
                allowed=False,
                reason=f"No hay posición abierta en {signal.symbol} para vender",
            )
        return RiskResult(allowed=True)

    def calculate_position_size(
        self,
        signal: SignalCreate,
        account: AccountSnapshot,
    ) -> Decimal:
        """Calcula la cantidad a comprar respetando riesgo y tamaño máximo."""
        if signal.entry_price is None or signal.entry_price <= 0:
            return Decimal("0")

        min_reserve = (
            account.equity * Decimal(str(self.settings.MIN_CASH_RESERVE_PERCENT)) / Decimal(100)
        )
        available_for_trade = max(account.cash - min_reserve, Decimal("0"))

        max_position_value = (
            account.equity * Decimal(str(self.settings.MAX_POSITION_SIZE_PERCENT)) / Decimal(100)
        )
        max_position_value = min(max_position_value, available_for_trade)
        max_qty_by_size = max_position_value / signal.entry_price

        if signal.suggested_stop_loss is not None and signal.suggested_stop_loss > 0:
            risk_per_share = signal.entry_price - signal.suggested_stop_loss
            if risk_per_share > 0:
                max_risk_amount = (
                    account.equity
                    * Decimal(str(self.settings.MAX_RISK_PER_TRADE_PERCENT))
                    / Decimal(100)
                )
                max_qty_by_risk = max_risk_amount / risk_per_share
                return min(max_qty_by_size, max_qty_by_risk).quantize(Decimal("0.00000001"))

        return max_qty_by_size.quantize(Decimal("0.00000001"))
