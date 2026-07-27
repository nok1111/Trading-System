"""Tests para RiskEngine + CircuitBreaker.

Sin red: todo es lógica determinista con Decimal.
"""

from decimal import Decimal

from app.risk.engine import (
    CircuitBreaker,
    CircuitBreakerState,
    RiskEngine,
)


class TestCircuitBreaker:
    def test_starts_normal(self):
        cb = CircuitBreaker(daily_loss_limit=Decimal("100"))
        assert cb.state == CircuitBreakerState.NORMAL

    def test_warning_at_50pct_loss(self):
        cb = CircuitBreaker(daily_loss_limit=Decimal("100"))
        cb.update(daily_pnl=Decimal("-55"), equity=Decimal("10000"))
        assert cb.state == CircuitBreakerState.WARNING

    def test_halt_at_80pct_loss(self):
        cb = CircuitBreaker(daily_loss_limit=Decimal("100"))
        cb.update(daily_pnl=Decimal("-85"), equity=Decimal("10000"))
        assert cb.state == CircuitBreakerState.HALT_TRADING

    def test_emergency_at_100pct_loss(self):
        cb = CircuitBreaker(daily_loss_limit=Decimal("100"))
        cb.update(daily_pnl=Decimal("-105"), equity=Decimal("10000"))
        assert cb.state == CircuitBreakerState.EMERGENCY_HALT

    def test_recovery_to_normal(self):
        cb = CircuitBreaker(daily_loss_limit=Decimal("100"))
        cb.update(daily_pnl=Decimal("-85"), equity=Decimal("10000"))
        assert cb.state == CircuitBreakerState.HALT_TRADING
        cb.update(daily_pnl=Decimal("-25"), equity=Decimal("10000"))
        assert cb.state == CircuitBreakerState.NORMAL

    def test_warning_stays_warning_with_more_loss(self):
        cb = CircuitBreaker(daily_loss_limit=Decimal("100"))
        cb.update(daily_pnl=Decimal("-55"), equity=Decimal("10000"))
        assert cb.state == CircuitBreakerState.WARNING
        cb.update(daily_pnl=Decimal("-60"), equity=Decimal("10000"))
        assert cb.state == CircuitBreakerState.WARNING

    def test_allows_new_orders(self):
        cb = CircuitBreaker(daily_loss_limit=Decimal("100"))
        assert cb.allows_new_orders()
        cb.update(daily_pnl=Decimal("-55"), equity=Decimal("10000"))
        assert cb.allows_new_orders()  # WARNING still allows
        cb.update(daily_pnl=Decimal("-85"), equity=Decimal("10000"))
        assert not cb.allows_new_orders()  # HALT blocks

    def test_allows_closes(self):
        cb = CircuitBreaker(daily_loss_limit=Decimal("100"))
        assert cb.allows_closes()
        cb.update(daily_pnl=Decimal("-85"), equity=Decimal("10000"))
        assert cb.allows_closes()  # HALT still allows closes
        cb.update(daily_pnl=Decimal("-105"), equity=Decimal("10000"))
        assert not cb.allows_closes()  # EMERGENCY blocks all

    def test_position_size_multiplier(self):
        cb = CircuitBreaker(daily_loss_limit=Decimal("100"))
        assert cb.position_size_multiplier() == Decimal("1.0")
        cb.update(daily_pnl=Decimal("-55"), equity=Decimal("10000"))
        assert cb.position_size_multiplier() == Decimal("0.5")

    def test_transition_log(self):
        cb = CircuitBreaker(daily_loss_limit=Decimal("100"))
        cb.update(daily_pnl=Decimal("-55"), equity=Decimal("10000"))
        assert len(cb.transition_log) == 1
        assert cb.transition_log[0]["from"] == "NORMAL"
        assert cb.transition_log[0]["to"] == "WARNING"

    def test_no_loss_stays_normal(self):
        cb = CircuitBreaker(daily_loss_limit=Decimal("100"))
        cb.update(daily_pnl=Decimal("50"), equity=Decimal("10000"))
        assert cb.state == CircuitBreakerState.NORMAL


class TestRiskEngineEvaluateOrder:
    def setup_method(self):
        self.engine = RiskEngine(
            max_position_size_pct=Decimal("10"),
            max_risk_per_trade_pct=Decimal("1"),
            max_daily_loss_pct=Decimal("3"),
            min_cash_reserve_pct=Decimal("20"),
            max_open_positions=20,
            max_order_usd=Decimal("500"),
            daily_loss_limit_usd=Decimal("100"),
        )

    def test_buy_approved(self):
        decision = self.engine.evaluate_order(
            side="buy",
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            account_cash=Decimal("10000"),
            account_equity=Decimal("10000"),
        )
        assert decision.allowed
        assert decision.adjusted_quantity is not None
        assert decision.adjusted_quantity > 0

    def test_buy_blocked_max_positions(self):
        decision = self.engine.evaluate_order(
            side="buy",
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            account_cash=Decimal("10000"),
            account_equity=Decimal("10000"),
            open_positions_count=20,
        )
        assert not decision.allowed
        assert "posiciones" in decision.reason.lower()

    def test_buy_blocked_duplicate_symbol(self):
        decision = self.engine.evaluate_order(
            side="buy",
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            account_cash=Decimal("10000"),
            account_equity=Decimal("10000"),
            open_positions=[{"symbol": "BTCUSDT", "status": "open"}],
        )
        assert not decision.allowed
        assert "BTCUSDT" in decision.reason

    def test_buy_blocked_insufficient_cash(self):
        decision = self.engine.evaluate_order(
            side="buy",
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            account_cash=Decimal("100"),
            account_equity=Decimal("10000"),
        )
        assert not decision.allowed
        assert "reserva" in decision.reason.lower()

    def test_buy_blocked_invalid_price(self):
        decision = self.engine.evaluate_order(
            side="buy",
            symbol="BTCUSDT",
            entry_price=Decimal("0"),
            account_cash=Decimal("10000"),
            account_equity=Decimal("10000"),
        )
        assert not decision.allowed

    def test_sell_always_allowed(self):
        decision = self.engine.evaluate_order(
            side="sell",
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
        )
        assert decision.allowed

    def test_circuit_breaker_halt_blocks_buy(self):
        decision = self.engine.evaluate_order(
            side="buy",
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            account_cash=Decimal("10000"),
            account_equity=Decimal("10000"),
            daily_pnl=Decimal("-85"),
        )
        assert not decision.allowed
        assert "HALT_TRADING" in decision.reason

    def test_circuit_breaker_emergency_blocks_sell(self):
        decision = self.engine.evaluate_order(
            side="sell",
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            daily_pnl=Decimal("-105"),
            account_equity=Decimal("10000"),
        )
        assert not decision.allowed
        assert "EMERGENCY_HALT" in decision.reason

    def test_circuit_breaker_warning_reduces_size(self):
        decision = self.engine.evaluate_order(
            side="buy",
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            account_cash=Decimal("10000"),
            account_equity=Decimal("10000"),
            daily_pnl=Decimal("-55"),
        )
        assert decision.allowed
        assert decision.metadata.get("multiplier") == "0.5"

    def test_max_order_usd_cap(self):
        decision = self.engine.evaluate_order(
            side="buy",
            symbol="BTCUSDT",
            entry_price=Decimal("100"),
            account_cash=Decimal("100000"),
            account_equity=Decimal("100000"),
        )
        assert decision.allowed
        order_value = decision.adjusted_quantity * Decimal("100")
        assert order_value <= Decimal("500")


class TestTrailingStop:
    def setup_method(self):
        self.engine = RiskEngine()

    def test_below_entry_uses_original_sl(self):
        result = self.engine.evaluate_trailing_stop(
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48500"),
            take_profit=Decimal("53000"),
            current_price=Decimal("49000"),
        )
        assert not result.should_close
        assert result.effective_sl == Decimal("48500")

    def test_at_entry_uses_original_sl(self):
        result = self.engine.evaluate_trailing_stop(
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48500"),
            take_profit=Decimal("53000"),
            current_price=Decimal("50000"),
        )
        assert not result.should_close
        assert result.effective_sl == Decimal("48500")

    def test_slightly_above_entry_breakeven(self):
        result = self.engine.evaluate_trailing_stop(
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48500"),
            take_profit=Decimal("53000"),
            current_price=Decimal("50500"),
        )
        assert not result.should_close
        assert result.effective_sl == Decimal("50000")  # breakeven

    def test_clearly_in_profit_trailing(self):
        # First push price up to set peak
        self.engine.evaluate_trailing_stop(
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48500"),
            take_profit=Decimal("53000"),
            current_price=Decimal("52000"),
        )
        # Now price drops but still in profit
        result = self.engine.evaluate_trailing_stop(
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48500"),
            take_profit=Decimal("53000"),
            current_price=Decimal("51000"),
        )
        assert not result.should_close
        # Trailing SL = 52000 * 0.98 = 50960
        assert result.effective_sl == Decimal("50960")
        assert result.peak == Decimal("52000")

    def test_trailing_stop_triggers_close(self):
        # Push peak up
        self.engine.evaluate_trailing_stop(
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48500"),
            take_profit=Decimal("53000"),
            current_price=Decimal("52000"),
        )
        # Price drops below trailing SL
        result = self.engine.evaluate_trailing_stop(
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48500"),
            take_profit=Decimal("53000"),
            current_price=Decimal("50900"),
        )
        assert result.should_close
        assert result.close_type == "trailing"

    def test_stop_loss_triggers_close(self):
        result = self.engine.evaluate_trailing_stop(
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48500"),
            take_profit=Decimal("53000"),
            current_price=Decimal("48000"),
        )
        assert result.should_close
        assert result.close_type == "stop_loss"

    def test_take_profit_triggers_close(self):
        result = self.engine.evaluate_trailing_stop(
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48500"),
            take_profit=Decimal("53000"),
            current_price=Decimal("53100"),
        )
        assert result.should_close
        assert result.close_type == "take_profit"

    def test_breakeven_stop_triggers_close(self):
        # Set peak slightly above entry to activate breakeven
        self.engine.evaluate_trailing_stop(
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48500"),
            take_profit=Decimal("53000"),
            current_price=Decimal("50500"),
        )
        # Price drops below entry (but above original SL)
        result = self.engine.evaluate_trailing_stop(
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48500"),
            take_profit=Decimal("53000"),
            current_price=Decimal("49900"),
        )
        assert result.should_close
        assert result.close_type == "breakeven"

    def test_clear_peak_on_close(self):
        self.engine.evaluate_trailing_stop(
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48500"),
            take_profit=Decimal("53000"),
            current_price=Decimal("52000"),
        )
        assert self.engine.get_position_peak("BTCUSDT") == Decimal("52000")
        self.engine.clear_position_peak("BTCUSDT")
        assert self.engine.get_position_peak("BTCUSDT") is None

    def test_peak_never_goes_down(self):
        self.engine.evaluate_trailing_stop(
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48500"),
            take_profit=Decimal("53000"),
            current_price=Decimal("52000"),
        )
        self.engine.evaluate_trailing_stop(
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48500"),
            take_profit=Decimal("53000"),
            current_price=Decimal("51000"),
        )
        assert self.engine.get_position_peak("BTCUSDT") == Decimal("52000")
