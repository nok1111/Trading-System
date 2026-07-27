"""Interfaz abstracta BrokerAdapter y excepciones tipadas.

Toda la base de codigo es sincrona (httpx en modo sync), por lo que
esta interfaz es sincrona. Los adaptadores implementan estos metodos
traduciendo a/desde los modelos normalizados de brokers/models.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from app.brokers.capabilities import BrokerCapabilities
from app.brokers.models import (
    Balance,
    BrokerInfo,
    BrokerOrder,
    CancelOrderRequest,
    CredentialValidationResult,
    MarketInfo,
    OrderCancellationResult,
    OrderExecutionResult,
    OrderRequest,
    PortfolioSnapshot,
    Position,
    Ticker,
)


class BrokerError(Exception):
    """Error base de broker."""


class BrokerAuthError(BrokerError):
    """Error de autenticacion con el broker (API key invalida, etc.)."""


class BrokerRateLimitError(BrokerError):
    """El broker ha aplicado rate limiting (429)."""


class BrokerTimeoutError(BrokerError):
    """Timeout al conectar con el broker."""


class InvalidSymbolError(BrokerError):
    """El simbolo no existe en el broker."""


class InsufficientBalanceError(BrokerError):
    """Saldo insuficiente para ejecutar la orden."""


class MinNotionalError(BrokerError):
    """El valor de la orden es menor al minimo notional del broker."""


class DuplicateOrderError(BrokerError):
    """Orden duplicada (client_order_id ya existe)."""


class BrokerAdapter(ABC):
    """Adaptador de broker con modelos de dominio normalizados.

    Metodos de solo lectura: get_broker_info, validate_credentials,
    get_account_balances, get_portfolio, get_open_positions,
    get_order_history, get_market_info, get_ticker, get_order_status.

    Metodos de escritura: place_order, cancel_order.

    Metodo opcional: subscribe_market_data.
    """

    @abstractmethod
    def get_broker_info(self) -> BrokerInfo:
        """Devuelve metadatos estaticos del broker."""

    @abstractmethod
    def get_capabilities(self) -> BrokerCapabilities:
        """Devuelve las capacidades declaradas del broker."""

    @abstractmethod
    def validate_credentials(self) -> CredentialValidationResult:
        """Valida que las credenciales configuradas funcionen."""

    @abstractmethod
    def get_account_balances(self) -> tuple[Balance, ...]:
        """Devuelve los saldos de todos los activos con balance > 0."""

    @abstractmethod
    def get_portfolio(self) -> PortfolioSnapshot:
        """Devuelve un snapshot del portfolio con valor total en USD."""

    @abstractmethod
    def get_open_positions(self) -> tuple[Position, ...]:
        """Devuelve las posiciones abiertas."""

    @abstractmethod
    def get_order_history(self, symbol: str | None = None, limit: int = 50) -> tuple[BrokerOrder, ...]:
        """Devuelve el historial de ordenes."""

    @abstractmethod
    def get_market_info(self, symbol: str) -> MarketInfo:
        """Devuelve informacion de mercado (filtros, precisiones) para un simbolo."""

    @abstractmethod
    def get_ticker(self, symbol: str) -> Ticker:
        """Devuelve la cotizacion en tiempo real de un simbolo."""

    @abstractmethod
    def place_order(self, request: OrderRequest) -> OrderExecutionResult:
        """Envia una orden al broker y devuelve el resultado."""

    @abstractmethod
    def cancel_order(self, request: CancelOrderRequest) -> OrderCancellationResult:
        """Cancela una orden pendiente en el broker."""

    @abstractmethod
    def get_order_status(self, broker_order_id: str, symbol: str | None = None) -> BrokerOrder:
        """Consulta el estado de una orden en el broker."""

    def subscribe_market_data(
        self,
        symbols: list[str],
        on_ticker: Callable[[Ticker], None] | None = None,
    ) -> None:
        """Suscribe a actualizaciones de mercado en tiempo real.

        Implementacion opcional. Por defecto no hace nada.
        Los adaptadores que soportan WebSocket deben override este metodo.
        """
        raise NotImplementedError("Este broker no soporta subscribe_market_data")
