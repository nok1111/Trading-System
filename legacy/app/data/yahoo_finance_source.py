"""Adaptador de Yahoo Finance usando yfinance."""

from datetime import date

import pandas as pd
import yfinance as yf

from app.data.data_source import DataSource, DataSourceError


class YahooFinanceDataSource(DataSource):
    """Adaptador real para Yahoo Finance.

    Requiere conexión a Internet. No se usa en tests unitarios.
    """

    @property
    def name(self) -> str:
        return "yahoo_finance"

    def fetch_bars(
        self,
        symbol: str,
        start: date,
        end: date,
        timeframe: str = "1d",
    ) -> pd.DataFrame:
        interval = self._timeframe_to_interval(timeframe)
        ticker = yf.Ticker(symbol)
        hist = ticker.history(start=start, end=end, interval=interval)
        if hist.empty:
            raise DataSourceError(
                f"Yahoo Finance no devolvió datos para {symbol} entre {start} y {end} ({timeframe})"
            )
        hist = hist.rename(columns=str.lower)
        for col in ["open", "high", "low", "close", "volume"]:
            if col not in hist.columns:
                raise DataSourceError(f"Columna {col} no encontrada en datos de {symbol}")
        hist = hist[["open", "high", "low", "close", "volume"]]
        if hist.index.tz is None:
            hist.index = hist.index.tz_localize("UTC")
        else:
            hist.index = hist.index.tz_convert("UTC")
        hist.index.name = "timestamp"
        return hist

    def _timeframe_to_interval(self, timeframe: str) -> str:
        mapping = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "1d": "1d",
            "1wk": "1wk",
            "1mo": "1mo",
        }
        if timeframe not in mapping:
            raise DataSourceError(f"Timeframe no soportado: {timeframe}")
        return mapping[timeframe]
