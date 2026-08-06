"""Fuente de datos sintética para pruebas y desarrollo."""

from datetime import date

import numpy as np
import pandas as pd

from app.data.data_source import DataSource


class MockDataSource(DataSource):
    """Genera datos OHLCV deterministas para un símbolo dado."""

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed

    @property
    def name(self) -> str:
        return "mock"

    def fetch_bars(
        self,
        symbol: str,
        start: date,
        end: date,
        timeframe: str = "1d",
    ) -> pd.DataFrame:
        freq = "D" if timeframe == "1d" else "B"
        dates = pd.date_range(start=start, end=end, freq=freq, tz="UTC")
        if len(dates) == 0:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"]).set_axis(
                pd.DatetimeIndex([], name="timestamp")
            )

        rng = np.random.default_rng(self.seed + hash(symbol) % 2**31)
        n = len(dates)

        trend = np.cumsum(rng.normal(0, 0.5, n))
        close = 100.0 + trend
        open_ = close + rng.normal(0, 0.2, n)
        high = np.maximum(open_, close) + rng.uniform(0, 0.5, n)
        low = np.minimum(open_, close) - rng.uniform(0, 0.5, n)
        volume = rng.integers(1_000_000, 10_000_000, n)

        df = pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
            index=dates,
        )
        df.index.name = "timestamp"
        return df
