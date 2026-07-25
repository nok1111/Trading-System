"""Servicio de obtención, validación y almacenamiento de datos de mercado."""

from datetime import date

import pandas as pd

from app.data.data_source import DataSource
from app.data.repository import BarRepository


class DataValidationError(Exception):
    """Datos OHLCV inválidos."""


class MarketDataService:
    """Coordina la descarga desde una fuente y la persistencia en DB."""

    def __init__(
        self,
        data_source: DataSource,
        repository: BarRepository | None = None,
    ) -> None:
        self.data_source = data_source
        self.repository = repository

    def get_historical_bars(
        self,
        symbol: str,
        start: date,
        end: date,
        timeframe: str = "1d",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Devuelve velas OHLCV, usando caché DB cuando esté disponible."""
        if use_cache and self.repository is not None:
            cached = self.repository.get_bars(symbol, start, end, timeframe)
            if not cached.empty and self._covers_range(cached, start, end):
                return cached

        df = self.data_source.fetch_bars(symbol, start, end, timeframe)
        df = self._validate_and_normalize(df)

        if self.repository is not None:
            self.repository.upsert_bars(df, symbol, timeframe, self.data_source.name)

        return df

    def _covers_range(
        self,
        df: pd.DataFrame,
        start: date,
        end: date,
    ) -> bool:
        if df.empty:
            return False
        return df.index[0].date() <= start and df.index[-1].date() >= end

    def _validate_and_normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(df.index, pd.DatetimeIndex):
            raise DataValidationError("El índice debe ser un DatetimeIndex")

        df = df.copy()
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")

        required = ["open", "high", "low", "close", "volume"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise DataValidationError(f"Faltan columnas: {missing}")

        df = df[required]
        for col in required:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        if df.isna().any().any():
            raise DataValidationError("Datos con valores faltantes")

        if df.index.duplicated().any():
            raise DataValidationError("Timestamps duplicados detectados")

        if (df["high"] < df["low"]).any():
            raise DataValidationError("Existen filas donde high < low")

        return df
