"""Interfaz abstracta para fuentes de datos de mercado."""

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd


class DataSourceError(Exception):
    """Error al obtener datos de una fuente externa."""


class DataSource(ABC):
    """Adaptador para descargar OHLCV desde un proveedor de datos."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre identificador de la fuente."""

    @abstractmethod
    def fetch_bars(
        self,
        symbol: str,
        start: date,
        end: date,
        timeframe: str,
    ) -> pd.DataFrame:
        """Descarga velas OHLCV para un símbolo y rango de fechas.

        Args:
            symbol: Símbolo del activo.
            start: Fecha inicial.
            end: Fecha final.
            timeframe: Intervalo de las velas (ej. '1d', '1h').

        Returns:
            DataFrame con columnas 'open', 'high', 'low', 'close', 'volume'
            e índice DatetimeIndex.
        """
