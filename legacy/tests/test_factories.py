"""Tests de la fábrica de data sources y brokers."""

from decimal import Decimal
from unittest.mock import patch

import pytest

from app.brokers.binance_broker import BinanceBroker
from app.brokers.mock_broker import MockBroker
from app.config import Settings
from app.data.binance_source import BinanceDataSource
from app.data.mock_data_source import MockDataSource
from app.data.yahoo_finance_source import YahooFinanceDataSource
from app.factories import create_broker, create_data_source


class TestCreateDataSource:
    def test_mock_provider_returns_mock(self):
        settings = Settings(BROKER_PROVIDER="mock", DEFAULT_SYMBOLS="AAPL")
        ds = create_data_source(settings)
        assert isinstance(ds, MockDataSource)

    def test_binance_provider_returns_binance(self):
        settings = Settings(BROKER_PROVIDER="binance", DEFAULT_SYMBOLS="BTCUSDT")
        ds = create_data_source(settings)
        assert isinstance(ds, BinanceDataSource)

    def test_alpaca_provider_returns_yahoo(self):
        settings = Settings(BROKER_PROVIDER="alpaca", DEFAULT_SYMBOLS="AAPL")
        ds = create_data_source(settings)
        assert isinstance(ds, YahooFinanceDataSource)

    def test_ibkr_provider_returns_yahoo(self):
        settings = Settings(BROKER_PROVIDER="ibkr", DEFAULT_SYMBOLS="AAPL")
        ds = create_data_source(settings)
        assert isinstance(ds, YahooFinanceDataSource)


class TestCreateBroker:
    def test_mock_provider_returns_mock(self):
        settings = Settings(
            BROKER_PROVIDER="mock",
            DEFAULT_SYMBOLS="AAPL",
            PAPER_TRADING_INITIAL_CASH=Decimal("50000"),
        )
        broker = create_broker(settings)
        assert isinstance(broker, MockBroker)
        assert broker._cash == Decimal("50000")

    def test_binance_provider_returns_binance(self):
        settings = Settings(
            BROKER_PROVIDER="binance",
            BROKER_API_KEY="test_key",
            BROKER_API_SECRET="test_secret",
            DEFAULT_SYMBOLS="BTCUSDT",
            BINANCE_TESTNET=True,
        )
        broker = create_broker(settings)
        assert isinstance(broker, BinanceBroker)
        assert broker._base_url == "https://testnet.binance.vision"

    def test_binance_provider_without_keys_returns_mock(self):
        settings = Settings(
            BROKER_PROVIDER="binance",
            BROKER_API_KEY=None,
            BROKER_API_SECRET=None,
            DEFAULT_SYMBOLS="BTCUSDT",
            PAPER_TRADING_INITIAL_CASH=Decimal("100000"),
        )
        broker = create_broker(settings)
        assert isinstance(broker, MockBroker)
        assert broker._cash == Decimal("100000")

    def test_binance_provider_testnet_false_uses_production_url(self):
        settings = Settings(
            BROKER_PROVIDER="binance",
            BROKER_API_KEY="test_key",
            BROKER_API_SECRET="test_secret",
            DEFAULT_SYMBOLS="BTCUSDT",
            BINANCE_TESTNET=False,
        )
        broker = create_broker(settings)
        assert isinstance(broker, BinanceBroker)
        assert broker._base_url == "https://api.binance.com"
