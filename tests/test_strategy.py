"""Pruebas de la estrategia TrendMomentumStrategy."""

from datetime import date
from decimal import Decimal

import pandas as pd

from app.data import MarketDataService, MockDataSource
from app.models.signal import SignalCreate
from app.strategies import TrendMomentumConfig, TrendMomentumStrategy


class TestTrendMomentumStrategy:
    def _make_strategy(self) -> TrendMomentumStrategy:
        return TrendMomentumStrategy(
            TrendMomentumConfig(
                fast_ema=10,
                slow_ema=30,
                rsi_period=14,
                rsi_lower=40,
                rsi_upper=70,
                volume_lookback=20,
                volume_threshold=1.2,
                atr_period=14,
                stop_loss_percent=2.0,
                take_profit_percent=4.0,
                max_hold_bars=20,
            )
        )

    def _build_indicator_df(
        self,
        rows: int = 60,
        last_ema_fast: float = 105.0,
        last_ema_slow: float = 100.0,
        prev_ema_fast: float = 99.0,
        prev_ema_slow: float = 100.0,
        rsi: float = 55.0,
        volume_rel: float = 1.5,
        close: float = 100.0,
        ema_trend: float = 95.0,
    ) -> pd.DataFrame:
        dates = pd.date_range("2024-01-01", periods=rows, freq="D", tz="UTC")
        data = {
            "open": [close] * rows,
            "high": [close + 1] * rows,
            "low": [close - 1] * rows,
            "close": [close] * rows,
            "volume": [1_000_000] * rows,
            "ema_fast": [prev_ema_fast] * (rows - 2) + [prev_ema_fast, last_ema_fast],
            "ema_slow": [prev_ema_slow] * (rows - 2) + [prev_ema_slow, last_ema_slow],
            "ema_trend": [ema_trend] * rows,
            "rsi": [rsi] * rows,
            "atr": [1.0] * rows,
            "volume_rel": [volume_rel] * rows,
            "returns": [0.0] * rows,
        }
        return pd.DataFrame(data, index=dates)

    def test_prepare_data_adds_indicators(self) -> None:
        source = MockDataSource(seed=7)
        service = MarketDataService(source)
        df = service.get_historical_bars("TEST", date(2024, 1, 1), date(2024, 3, 1), "1d")
        strategy = self._make_strategy()
        result = strategy.prepare_data(df)
        for col in ["ema_fast", "ema_slow", "ema_trend", "rsi", "atr", "volume_rel"]:
            assert col in result.columns

    def test_signal_hold_when_not_enough_data(self) -> None:
        strategy = self._make_strategy()
        df = pd.DataFrame(
            {
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.0],
                "volume": [1_000_000],
            },
            index=pd.date_range("2024-01-01", periods=1, tz="UTC"),
        )
        signal = strategy.generate_signal("TEST", df)
        assert signal.signal_type == "HOLD"

    def test_buy_when_conditions_met(self) -> None:
        strategy = self._make_strategy()
        custom_df = self._build_indicator_df(
            last_ema_fast=105.0,
            last_ema_slow=100.0,
            prev_ema_fast=99.0,
            prev_ema_slow=100.0,
            rsi=55.0,
            volume_rel=1.5,
            close=100.0,
        )
        strategy.prepare_data = lambda df: custom_df
        signal = strategy.generate_signal("TEST", custom_df)
        assert signal.signal_type == "BUY"
        assert signal.entry_price == Decimal("100")
        assert signal.suggested_stop_loss == Decimal("98")
        assert signal.suggested_take_profit == Decimal("104")
        assert "EMA" in signal.explanation

    def test_sell_on_ema_cross_down(self) -> None:
        strategy = self._make_strategy()
        custom_df = self._build_indicator_df(
            last_ema_fast=95.0,
            last_ema_slow=100.0,
            prev_ema_fast=101.0,
            prev_ema_slow=100.0,
            rsi=55.0,
            volume_rel=1.0,
            close=100.0,
        )
        strategy.prepare_data = lambda df: custom_df
        signal = strategy.generate_signal(
            "TEST", custom_df, has_position=True, position_entry_price=Decimal("100")
        )
        assert signal.signal_type == "SELL"
        assert signal.explanation != ""

    def test_sell_on_stop_loss(self) -> None:
        strategy = self._make_strategy()
        custom_df = self._build_indicator_df(
            last_ema_fast=102.0,
            last_ema_slow=100.0,
            prev_ema_fast=101.0,
            prev_ema_slow=100.0,
            rsi=55.0,
            volume_rel=1.0,
            close=100.0,
        )
        strategy.prepare_data = lambda df: custom_df
        signal = strategy.generate_signal(
            "TEST",
            custom_df,
            current_price=Decimal("98"),
            has_position=True,
            position_entry_price=Decimal("105"),
        )
        assert signal.signal_type == "SELL"
        assert "stop loss" in signal.metadata_json["triggers"]

    def test_sell_on_take_profit(self) -> None:
        strategy = self._make_strategy()
        custom_df = self._build_indicator_df(
            last_ema_fast=102.0,
            last_ema_slow=100.0,
            prev_ema_fast=101.0,
            prev_ema_slow=100.0,
            rsi=55.0,
            volume_rel=1.0,
            close=110.0,
        )
        strategy.prepare_data = lambda df: custom_df
        signal = strategy.generate_signal(
            "TEST",
            custom_df,
            current_price=Decimal("110"),
            has_position=True,
            position_entry_price=Decimal("100"),
        )
        assert signal.signal_type == "SELL"
        assert "take profit" in signal.metadata_json["triggers"]

    def test_sell_on_max_hold_bars(self) -> None:
        strategy = self._make_strategy()
        custom_df = self._build_indicator_df(
            last_ema_fast=102.0,
            last_ema_slow=100.0,
            prev_ema_fast=101.0,
            prev_ema_slow=100.0,
            rsi=55.0,
            volume_rel=1.0,
            close=100.0,
        )
        strategy.prepare_data = lambda df: custom_df
        signal = strategy.generate_signal(
            "TEST",
            custom_df,
            has_position=True,
            position_entry_price=Decimal("100"),
            bars_in_position=strategy.config.max_hold_bars,
        )
        assert signal.signal_type == "SELL"
        assert "tiempo máximo en posición" in signal.metadata_json["triggers"]

    def test_sell_on_trailing_stop(self) -> None:
        strategy = self._make_strategy()
        custom_df = self._build_indicator_df(
            last_ema_fast=102.0,
            last_ema_slow=100.0,
            prev_ema_fast=101.0,
            prev_ema_slow=100.0,
            rsi=55.0,
            volume_rel=1.0,
            close=100.0,
        )
        strategy.prepare_data = lambda df: custom_df
        # Price went up to 110 (highest), then dropped to 107 (below trailing 2% of 110 = 107.8)
        signal = strategy.generate_signal(
            "TEST",
            custom_df,
            current_price=Decimal("107"),
            has_position=True,
            position_entry_price=Decimal("100"),
            position_highest_price=Decimal("110"),
        )
        assert signal.signal_type == "SELL"
        assert "trailing stop" in signal.metadata_json["triggers"]

    def test_no_trailing_stop_when_price_still_high(self) -> None:
        strategy = self._make_strategy()
        custom_df = self._build_indicator_df(
            last_ema_fast=102.0,
            last_ema_slow=100.0,
            prev_ema_fast=101.0,
            prev_ema_slow=100.0,
            rsi=55.0,
            volume_rel=1.0,
            close=100.0,
        )
        strategy.prepare_data = lambda df: custom_df
        # Price at 109, highest 110, trailing 2% = 107.8, 109 > 107.8 so no trailing stop
        signal = strategy.generate_signal(
            "TEST",
            custom_df,
            current_price=Decimal("109"),
            has_position=True,
            position_entry_price=Decimal("100"),
            position_highest_price=Decimal("110"),
        )
        assert "trailing stop" not in signal.metadata_json.get("triggers", [])

    def test_no_buy_when_price_below_ema_trend(self) -> None:
        strategy = self._make_strategy()
        custom_df = self._build_indicator_df(
            last_ema_fast=105.0,
            last_ema_slow=100.0,
            prev_ema_fast=99.0,
            prev_ema_slow=100.0,
            rsi=55.0,
            volume_rel=1.5,
            close=100.0,
            ema_trend=105.0,
        )
        strategy.prepare_data = lambda df: custom_df
        signal = strategy.generate_signal("TEST", custom_df)
        assert signal.signal_type == "HOLD"

    def test_signal_fields_are_valid_pydantic(self) -> None:
        source = MockDataSource(seed=17)
        service = MarketDataService(source)
        df = service.get_historical_bars("SYM", date(2024, 1, 1), date(2024, 9, 1), "1d")
        strategy = TrendMomentumStrategy(
            TrendMomentumConfig(
                rsi_lower=20,
                rsi_upper=80,
                volume_threshold=1.0,
            )
        )
        signal = strategy.generate_signal("SYM", df)
        assert isinstance(signal, SignalCreate)
        assert signal.signal_type in {"BUY", "SELL", "HOLD"}
        assert 0 <= signal.confidence <= 1
