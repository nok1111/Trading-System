"""Pruebas del servicio de datos de mercado."""

from datetime import date

import pandas as pd
import pytest
from sqlalchemy.orm import Session

from app.data import (
    BarRepository,
    DataValidationError,
    MarketDataService,
    MockDataSource,
)
from app.database.models.market_bar import MarketBar


@pytest.fixture
def market_service(db_session: Session) -> MarketDataService:
    source = MockDataSource(seed=123)
    repository = BarRepository(db_session)
    return MarketDataService(source, repository)


class TestMarketDataService:
    def test_fetch_and_cache(
        self,
        market_service: MarketDataService,
        db_session: Session,
    ) -> None:
        df = market_service.get_historical_bars(
            "AAPL",
            date(2024, 1, 1),
            date(2024, 1, 10),
            "1d",
        )
        assert not df.empty
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert df.index.tz is not None

        bars = db_session.query(MarketBar).all()
        assert len(bars) == len(df)

        # Segunda llamada debe usar caché y devolver los mismos datos
        df2 = market_service.get_historical_bars(
            "AAPL",
            date(2024, 1, 1),
            date(2024, 1, 10),
            "1d",
        )
        pd.testing.assert_frame_equal(df, df2)

    def test_validation_missing_column(self) -> None:
        df = pd.DataFrame(
            {"open": [1], "high": [2], "low": [1], "close": [1.5]},
            index=pd.date_range("2024-01-01", periods=1, tz="UTC"),
        )
        service = MarketDataService(MockDataSource())
        with pytest.raises(DataValidationError):
            service._validate_and_normalize(df)

    def test_validation_duplicate_index(self) -> None:
        dates = pd.DatetimeIndex(
            ["2024-01-01", "2024-01-01"],
            tz="UTC",
        )
        df = pd.DataFrame(
            {
                "open": [1, 1],
                "high": [2, 2],
                "low": [1, 1],
                "close": [1.5, 1.5],
                "volume": [100, 200],
            },
            index=dates,
        )
        service = MarketDataService(MockDataSource())
        with pytest.raises(DataValidationError):
            service._validate_and_normalize(df)

    def test_validation_high_lower_than_low(self) -> None:
        df = pd.DataFrame(
            {
                "open": [1],
                "high": [0.5],
                "low": [1.5],
                "close": [1],
                "volume": [100],
            },
            index=pd.date_range("2024-01-01", periods=1, tz="UTC"),
        )
        service = MarketDataService(MockDataSource())
        with pytest.raises(DataValidationError):
            service._validate_and_normalize(df)

    def test_timezone_normalization_naive_index(self) -> None:
        df = pd.DataFrame(
            {
                "open": [1],
                "high": [2],
                "low": [1],
                "close": [1.5],
                "volume": [100],
            },
            index=pd.date_range("2024-01-01", periods=1),
        )
        service = MarketDataService(MockDataSource())
        result = service._validate_and_normalize(df)
        assert result.index.tz is not None
