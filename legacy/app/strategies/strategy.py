"""Interfaz base para estrategias de trading."""

from abc import ABC, abstractmethod
from decimal import Decimal

import pandas as pd

from app.models.signal import SignalCreate


class Strategy(ABC):
    """Contrato que debe cumplir toda estrategia del sistema."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre identificador de la estrategia."""

    @property
    @abstractmethod
    def min_bars(self) -> int:
        """Mínimo de barras históricas necesarias para generar una señal."""

    @abstractmethod
    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Añade columnas de indicadores al DataFrame de precios."""

    @abstractmethod
    def generate_signal(
        self,
        symbol: str,
        df: pd.DataFrame,
        current_price: Decimal | None = None,
        has_position: bool = False,
        position_entry_price: Decimal | None = None,
        bars_in_position: int = 0,
        position_highest_price: Decimal | None = None,
    ) -> SignalCreate:
        """Genera una señal para la última vela disponible."""

    @abstractmethod
    def calculate_confidence(
        self,
        df: pd.DataFrame,
        signal_type: str,
    ) -> Decimal:
        """Calcula un nivel de confianza entre 0 y 1."""

    @abstractmethod
    def explain_signal(
        self,
        signal_type: str,
        row: pd.Series,
        prev: pd.Series | None = None,
    ) -> str:
        """Genera una explicación legible del motivo de la señal."""
