"""Interfaz abstracta para brokers."""

from abc import ABC, abstractmethod
from decimal import Decimal

from app.database.models.account_snapshot import AccountSnapshot
from app.database.models.order import Order


class Broker(ABC):
    """Adaptador para enviar órdenes a un broker real o simulado."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre del broker."""

    @abstractmethod
    def place_order(self, order: Order) -> Order:
        """Envía una orden y devuelve la orden actualizada."""

    @abstractmethod
    def cancel_order(self, broker_order_id: str) -> Order | None:
        """Cancela una orden pendiente."""

    @abstractmethod
    def get_order(self, broker_order_id: str) -> Order | None:
        """Consulta el estado de una orden."""

    @abstractmethod
    def get_account(self) -> AccountSnapshot:
        """Devuelve el estado actual de la cuenta."""

    @abstractmethod
    def get_quote(self, symbol: str) -> Decimal:
        """Devuelve el precio actual del símbolo."""
