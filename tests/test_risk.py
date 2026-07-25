"""Pruebas del RiskManager."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.config import Settings
from app.database.models.account_snapshot import AccountSnapshot
from app.database.models.position import Position
from app.models.signal import SignalCreate
from app.risk import RiskManager


@pytest.fixture
def risk_settings() -> Settings:
    return Settings(
        _env_file=None,
        APP_ENV="testing",
        DATABASE_URL="sqlite:///./test.db",
        TRADING_MODE="backtest",
        LIVE_TRADING_ENABLED=False,
        MAX_OPEN_POSITIONS=2,
        MAX_POSITION_SIZE_PERCENT=10.0,
        MAX_RISK_PER_TRADE_PERCENT=1.0,
        MAX_DAILY_LOSS_PERCENT=3.0,
        MIN_CASH_RESERVE_PERCENT=20.0,
    )


@pytest.fixture
def sample_account() -> AccountSnapshot:
    return AccountSnapshot(
        timestamp=datetime.now(tz=UTC),
        cash=Decimal("100000"),
        equity=Decimal("100000"),
        buying_power=Decimal("100000"),
        margin_used=Decimal("0"),
        daily_pnl=Decimal("0"),
        total_pnl=Decimal("0"),
        open_positions_count=0,
        strategy_run_id=None,
    )


def _buy_signal(symbol: str = "AAPL") -> SignalCreate:
    return SignalCreate(
        timestamp=datetime.now(tz=UTC),
        symbol=symbol,
        signal_type="BUY",
        confidence=Decimal("0.8"),
        entry_price=Decimal("100"),
        suggested_stop_loss=Decimal("98"),
        strategy_name="TestStrategy",
        explanation="test",
    )


class TestRiskManager:
    def test_allow_valid_buy(
        self, risk_settings: Settings, sample_account: AccountSnapshot
    ) -> None:
        rm = RiskManager(risk_settings)
        result = rm.evaluate_signal(_buy_signal(), sample_account, [])
        assert result.allowed
        assert result.reason is None

    def test_reject_hold_signal(
        self, risk_settings: Settings, sample_account: AccountSnapshot
    ) -> None:
        signal = _buy_signal()
        signal.signal_type = "HOLD"
        rm = RiskManager(risk_settings)
        result = rm.evaluate_signal(signal, sample_account, [])
        assert not result.allowed
        assert "HOLD" in (result.reason or "")

    def test_reject_when_max_positions_reached(
        self,
        risk_settings: Settings,
        sample_account: AccountSnapshot,
    ) -> None:
        positions = [
            Position(
                symbol="MSFT",
                opened_at=datetime.now(tz=UTC),
                side="long",
                quantity=Decimal("10"),
                entry_price=Decimal("200"),
                unrealized_pnl=Decimal("0"),
                realized_pnl=Decimal("0"),
                status="open",
                strategy_name="Test",
                metadata_json={},
            ),
            Position(
                symbol="TSLA",
                opened_at=datetime.now(tz=UTC),
                side="long",
                quantity=Decimal("5"),
                entry_price=Decimal("300"),
                unrealized_pnl=Decimal("0"),
                realized_pnl=Decimal("0"),
                status="open",
                strategy_name="Test",
                metadata_json={},
            ),
        ]
        rm = RiskManager(risk_settings)
        result = rm.evaluate_signal(_buy_signal(), sample_account, positions)
        assert not result.allowed
        assert "posiciones" in (result.reason or "").lower()

    def test_reject_sell_without_position(
        self,
        risk_settings: Settings,
        sample_account: AccountSnapshot,
    ) -> None:
        signal = SignalCreate(
            timestamp=datetime.now(tz=UTC),
            symbol="AAPL",
            signal_type="SELL",
            confidence=Decimal("0.8"),
            entry_price=Decimal("100"),
            strategy_name="TestStrategy",
            explanation="test",
        )
        rm = RiskManager(risk_settings)
        result = rm.evaluate_signal(signal, sample_account, [])
        assert not result.allowed
        assert "posición" in (result.reason or "").lower()

    def test_calculate_position_size_respects_both_limits(
        self,
        risk_settings: Settings,
        sample_account: AccountSnapshot,
    ) -> None:
        rm = RiskManager(risk_settings)
        signal = _buy_signal()
        qty = rm.calculate_position_size(signal, sample_account)
        # El límite de tamaño (10% de 100k / 100 = 100) es más restrictivo
        # que el límite de riesgo (1% / 2% de stop = 500 acciones).
        assert qty == Decimal("100")

    def test_calculate_position_size_without_stop(
        self,
        risk_settings: Settings,
        sample_account: AccountSnapshot,
    ) -> None:
        rm = RiskManager(risk_settings)
        signal = _buy_signal()
        signal.suggested_stop_loss = None
        qty = rm.calculate_position_size(signal, sample_account)
        # 10% de 100k = 10k / 100 = 100 acciones
        assert qty == Decimal("100")

    def test_reject_daily_loss_limit(
        self,
        risk_settings: Settings,
        sample_account: AccountSnapshot,
    ) -> None:
        sample_account.daily_pnl = Decimal("-5000")
        rm = RiskManager(risk_settings)
        result = rm.evaluate_signal(_buy_signal(), sample_account, [])
        assert not result.allowed
        assert "diario" in (result.reason or "").lower()

    def test_reject_live_without_enable_flag(
        self,
        risk_settings: Settings,
        sample_account: AccountSnapshot,
    ) -> None:
        risk_settings.TRADING_MODE = "live"
        rm = RiskManager(risk_settings)
        result = rm.evaluate_signal(_buy_signal(), sample_account, [])
        assert not result.allowed

    def test_reject_buy_when_cash_below_reserve(
        self,
        risk_settings: Settings,
    ) -> None:
        account = AccountSnapshot(
            timestamp=datetime.now(tz=UTC),
            cash=Decimal("15"),
            equity=Decimal("100"),
            buying_power=Decimal("15"),
            margin_used=Decimal("0"),
            daily_pnl=Decimal("0"),
            total_pnl=Decimal("0"),
            open_positions_count=0,
            strategy_run_id=None,
        )
        rm = RiskManager(risk_settings)
        result = rm.evaluate_signal(_buy_signal(), account, [])
        assert not result.allowed
        assert "reserva" in (result.reason or "").lower()

    def test_position_size_limited_by_cash_reserve(
        self,
        risk_settings: Settings,
    ) -> None:
        account = AccountSnapshot(
            timestamp=datetime.now(tz=UTC),
            cash=Decimal("5000"),
            equity=Decimal("100000"),
            buying_power=Decimal("5000"),
            margin_used=Decimal("0"),
            daily_pnl=Decimal("0"),
            total_pnl=Decimal("0"),
            open_positions_count=0,
            strategy_run_id=None,
        )
        rm = RiskManager(risk_settings)
        signal = _buy_signal()
        qty = rm.calculate_position_size(signal, account)
        available = Decimal("5000") - Decimal("20000")
        available = max(available, Decimal("0"))
        max_value = min(Decimal("10000"), available)
        expected_qty = max_value / Decimal("100")
        assert qty == expected_qty.quantize(Decimal("0.00000001"))
