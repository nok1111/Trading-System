"""STUB — NO IMPLEMENTADO. Adaptador de Kraken para Fase 7."""

from __future__ import annotations

from app.brokers.base import BrokerAdapter
from app.brokers.capabilities import BrokerCapabilities
from app.brokers.models import (
    Balance,
    BrokerCredentials,
    BrokerInfo,
    BrokerOrder,
    CancelOrderRequest,
    CredentialValidationResult,
    MarketInfo,
    MarketType,
    OrderCancellationResult,
    OrderExecutionResult,
    OrderRequest,
    PortfolioSnapshot,
    Position,
    Ticker,
)


class KrakenAdapter(BrokerAdapter):
    """STUB — NO IMPLEMENTADO. # TODO(fase-7)"""

    def __init__(self, credentials: BrokerCredentials) -> None:
        self._credentials = credentials

    def get_broker_info(self) -> BrokerInfo:
        return BrokerInfo(
            broker_id="kraken",
            display_name="Kraken",
            supported_markets=(MarketType.SPOT, MarketType.MARGIN),
            website_url="https://www.kraken.com",
            api_docs_url="https://docs.kraken.com",
        )

    def get_capabilities(self) -> BrokerCapabilities:
        return BrokerCapabilities(
            spot=True,
            margin=True,
            staking=True,
            websocket=True,
            market_orders=True,
            limit_orders=True,
            stop_orders=True,
            withdrawals=False,
        )

    def validate_credentials(self) -> CredentialValidationResult:
        raise NotImplementedError("KrakenAdapter no implementado — TODO(fase-7)")

    def get_account_balances(self) -> tuple[Balance, ...]:
        raise NotImplementedError("KrakenAdapter no implementado — TODO(fase-7)")

    def get_portfolio(self) -> PortfolioSnapshot:
        raise NotImplementedError("KrakenAdapter no implementado — TODO(fase-7)")

    def get_open_positions(self) -> tuple[Position, ...]:
        raise NotImplementedError("KrakenAdapter no implementado — TODO(fase-7)")

    def get_order_history(self, symbol: str | None = None, limit: int = 50) -> tuple[BrokerOrder, ...]:
        raise NotImplementedError("KrakenAdapter no implementado — TODO(fase-7)")

    def get_market_info(self, symbol: str) -> MarketInfo:
        raise NotImplementedError("KrakenAdapter no implementado — TODO(fase-7)")

    def get_ticker(self, symbol: str) -> Ticker:
        raise NotImplementedError("KrakenAdapter no implementado — TODO(fase-7)")

    def place_order(self, request: OrderRequest) -> OrderExecutionResult:
        raise NotImplementedError("KrakenAdapter no implementado — TODO(fase-7)")

    def cancel_order(self, request: CancelOrderRequest) -> OrderCancellationResult:
        raise NotImplementedError("KrakenAdapter no implementado — TODO(fase-7)")

    def get_order_status(self, broker_order_id: str, symbol: str | None = None) -> BrokerOrder:
        raise NotImplementedError("KrakenAdapter no implementado — TODO(fase-7)")
