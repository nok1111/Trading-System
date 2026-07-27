"""STUB — NO IMPLEMENTADO. Adaptador de Bybit para Fase 7."""

from __future__ import annotations

from app.brokers.base import BrokerAdapter
from app.brokers.capabilities import BrokerCapabilities
from app.brokers.models import (
    Balance,
    BrokerCredentials,
    BrokerInfo,
    BrokerOrder,
    CancelOrderRequest,
    Candle,
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


class BybitAdapter(BrokerAdapter):
    """STUB — NO IMPLEMENTADO. # TODO(fase-7)"""

    def __init__(self, credentials: BrokerCredentials) -> None:
        self._credentials = credentials

    def get_broker_info(self) -> BrokerInfo:
        return BrokerInfo(
            broker_id="bybit",
            display_name="Bybit",
            supported_markets=(MarketType.SPOT, MarketType.FUTURES),
            website_url="https://www.bybit.com",
            api_docs_url="https://bybit-exchange.github.io/docs/v5/intro",
        )

    def get_capabilities(self) -> BrokerCapabilities:
        return BrokerCapabilities(
            spot=True,
            margin=True,
            futures=True,
            websocket=True,
            market_orders=True,
            limit_orders=True,
            stop_orders=True,
            withdrawals=False,
        )

    def validate_credentials(self) -> CredentialValidationResult:
        raise NotImplementedError("BybitAdapter no implementado — TODO(fase-7)")

    def get_account_balances(self) -> tuple[Balance, ...]:
        raise NotImplementedError("BybitAdapter no implementado — TODO(fase-7)")

    def get_portfolio(self) -> PortfolioSnapshot:
        raise NotImplementedError("BybitAdapter no implementado — TODO(fase-7)")

    def get_open_positions(self) -> tuple[Position, ...]:
        raise NotImplementedError("BybitAdapter no implementado — TODO(fase-7)")

    def get_order_history(self, symbol: str | None = None, limit: int = 50) -> tuple[BrokerOrder, ...]:
        raise NotImplementedError("BybitAdapter no implementado — TODO(fase-7)")

    def get_market_info(self, symbol: str) -> MarketInfo:
        raise NotImplementedError("BybitAdapter no implementado — TODO(fase-7)")

    def get_ticker(self, symbol: str) -> Ticker:
        raise NotImplementedError("BybitAdapter no implementado — TODO(fase-7)")

    def place_order(self, request: OrderRequest) -> OrderExecutionResult:
        raise NotImplementedError("BybitAdapter no implementado — TODO(fase-7)")

    def cancel_order(self, request: CancelOrderRequest) -> OrderCancellationResult:
        raise NotImplementedError("BybitAdapter no implementado — TODO(fase-7)")

    def get_order_status(self, broker_order_id: str, symbol: str | None = None) -> BrokerOrder:
        raise NotImplementedError("BybitAdapter no implementado — TODO(fase-7)")

    def get_klines(self, symbol: str, interval: str, limit: int = 200) -> list[Candle]:
        raise NotImplementedError("BybitAdapter no implementado — TODO(fase-7)")

    def get_market_movers(self, market: str = "spot", limit: int = 20, quote: str = "USDT") -> dict:
        raise NotImplementedError("BybitAdapter no implementado — TODO(fase-7)")
