import pytest
from pydantic import ValidationError

from app.config import Settings


class TestSettingsValidation:
    def test_default_settings_are_safe(self) -> None:
        settings = Settings(_env_file=None)
        assert settings.TRADING_MODE == "backtest"
        assert settings.LIVE_TRADING_ENABLED is False
        assert settings.BROKER_PROVIDER == "mock"
        assert settings.symbols_list == ["SPY", "AAPL", "MSFT"]

    def test_symbols_are_normalized(self) -> None:
        settings = Settings(
            _env_file=None,
            DEFAULT_SYMBOLS=" aapl , spy , msft ",
        )
        assert settings.DEFAULT_SYMBOLS == "AAPL,SPY,MSFT"

    def test_empty_symbols_raise(self) -> None:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, DEFAULT_SYMBOLS="")

    def test_invalid_trading_mode_raises(self) -> None:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, TRADING_MODE="invalid")

    def test_live_mode_requires_enabled_flag(self) -> None:
        with pytest.raises(ValidationError) as exc:
            Settings(
                _env_file=None,
                TRADING_MODE="live",
                LIVE_TRADING_ENABLED=False,
                BROKER_API_KEY="key",
            )
        assert "LIVE_TRADING_ENABLED" in str(exc.value)

    def test_live_mode_requires_api_key(self) -> None:
        with pytest.raises(ValidationError) as exc:
            Settings(
                _env_file=None,
                TRADING_MODE="live",
                LIVE_TRADING_ENABLED=True,
            )
        assert "BROKER_API_KEY" in str(exc.value)

    def test_live_mode_accepts_when_explicitly_enabled(self) -> None:
        settings = Settings(
            _env_file=None,
            TRADING_MODE="live",
            LIVE_TRADING_ENABLED=True,
            BROKER_API_KEY="secret",
            BROKER_API_SECRET="secret",
        )
        assert settings.TRADING_MODE == "live"
        assert settings.LIVE_TRADING_ENABLED is True

    def test_safe_dict_hides_secrets(self) -> None:
        settings = Settings(
            _env_file=None,
            BROKER_API_KEY="super-secret-key",
            BROKER_API_SECRET="super-secret-secret",
        )
        safe = settings.to_safe_dict()
        assert safe["BROKER_API_KEY"] == "***REDACTED***"
        assert safe["BROKER_API_SECRET"] == "***REDACTED***"

    def test_risk_limits_are_within_bounds(self) -> None:
        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                MAX_POSITION_SIZE_PERCENT=150.0,
            )
        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                MAX_RISK_PER_TRADE_PERCENT=-1.0,
            )

    def test_live_trading_remains_disabled_by_default(self) -> None:
        settings = Settings(_env_file=None)
        assert settings.LIVE_TRADING_ENABLED is False
        assert settings.TRADING_MODE != "live"
