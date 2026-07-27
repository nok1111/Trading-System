"""STUB — NO IMPLEMENTADO. Adaptador de Coinbase para Fase 7."""

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


class CoinbaseAdapter(BrokerAdapter):
    """STUB — NO IMPLEMENTADO. # TODO(fase-7)"""

    def __init__(self, credentials: BrokerCredentials) -> None:
        self._credentials = credentials

    def get_broker_info(self) -> BrokerInfo:
        return BrokerInfo(
            broker_id="coinbase",
            display_name="Coinbase",
            supported_markets=(MarketType.SPOT, MarketType.FUTURES),
            website_url="https://www.coinbase.com",
            api_docs_url="https://docs.cloud.coinbase.com",
        )

    def get_capabilities(self) -> BrokerCapabilities:
        return BrokerCapabilities(
            spot=True,
            futures=True,
            staking=True,
            earn=True,
            websocket=True,
            market_orders=True,
            limit_orders=True,
            stop_orders=False,
            withdrawals=False,
        )

    def validate_credentials(self) -> CredentialValidationResult:
        raise NotImplementedError("CoinbaseAdapter no implementado — TODO(fase-7)")

    def get_account_balances(self) -> tuple[Balance, ...]:
        raise NotImplementedError("CoinbaseAdapter no implementado — TODO(fase-7)")

    def get_portfolio(self) -> PortfolioSnapshot:
        raise NotImplementedError("CoinbaseAdapter no implementado — TODO(fase-7)")

    def get_open_positions(self) -> tuple[Position, ...]:
        raise NotImplementedError("CoinbaseAdapter no implementado — TODO(fase-7)")

    def get_order_history(self, symbol: str | None = None, limit: int = 50) -> tuple[BrokerOrder, ...]:
        raise NotImplementedError("CoinbaseAdapter no implementado — TODO(fase-7)")

    def get_market_info(self, symbol: str) -> MarketInfo:
        raise NotImplementedError("CoinbaseAdapter no implementado — TODO(fase-7)")

    def get_ticker(self, symbol: str) -> Ticker:
        raise NotImplementedError("CoinbaseAdapter no implementado — TODO(fase-7)")

    def place_order(self, request: OrderRequest) -> OrderExecutionResult:
        raise NotImplementedError("CoinbaseAdapter no implementado — TODO(fase-7)")

    def cancel_order(self, request: CancelOrderRequest) -> OrderCancellationResult:
        raise NotImplementedError("CoinbaseAdapter no implementado — TODO(fase-7)")

    def get_order_status(self, broker_order_id: str, symbol: str | None = None) -> BrokerOrder:
        raise NotImplementedError("CoinbaseAdapter no implementado — TODO(fase-7)")
