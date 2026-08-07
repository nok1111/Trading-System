"""Fábrica centralizada para crear data sources y brokers según la configuración."""

from app.brokers.broker import Broker
from app.brokers.binance_broker import BinanceBroker
from app.brokers.mock_broker import MockBroker
from app.config import Settings
from app.data.binance_source import BinanceDataSource
from app.data.data_source import DataSource
from app.data.mock_data_source import MockDataSource
from app.data.yahoo_finance_source import YahooFinanceDataSource


def create_data_source(settings: Settings) -> DataSource:
    """Crea la fuente de datos adecuada según BROKER_PROVIDER."""
    provider = settings.BROKER_PROVIDER.lower()
    if provider == "binance":
        return BinanceDataSource()
    if provider in ("alpaca", "ibkr"):
        return YahooFinanceDataSource()
    return MockDataSource()


def create_broker(settings: Settings) -> Broker:
    """Crea el broker adecuado según BROKER_PROVIDER y TRADING_MODE.

    - Paper mode: siempre MockBroker (usa datos reales de Binance pero sin órdenes reales).
    - Live mode: BinanceBroker con API keys reales.
    - Testnet: BinanceBroker apuntando a testnet.binance.vision.
    - Futures: se maneja via CCXTAdapter en la capa de adapters, no aquí.
    """
    provider = settings.BROKER_PROVIDER.lower()
    is_live = settings.TRADING_MODE == "live" and settings.LIVE_TRADING_ENABLED

    if provider == "binance" and is_live:
        if not settings.BROKER_API_KEY or not settings.BROKER_API_SECRET:
            # No keys in .env — fall back to MockBroker (user keys resolved at API layer)
            return MockBroker(initial_cash=settings.PAPER_TRADING_INITIAL_CASH)
        return BinanceBroker(
            api_key=settings.BROKER_API_KEY,
            api_secret=settings.BROKER_API_SECRET,
            testnet=settings.BINANCE_TESTNET,
        )

    # Paper mode o cualquier otro caso: MockBroker
    return MockBroker(initial_cash=settings.PAPER_TRADING_INITIAL_CASH)
