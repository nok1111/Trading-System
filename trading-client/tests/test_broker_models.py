"""Tests para brokers/models.py — todo importe monetario es Decimal, normalizacion de simbolos."""

from decimal import Decimal

import pytest

from app.brokers.models import (
    Balance,
    BrokerCredentials,
    BrokerOrder,
    Candle,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    PortfolioSnapshot,
    Position,
    Ticker,
    denormalize_symbol,
    normalize_symbol,
)


class TestSymbolNormalization:
    def test_btcusdt_to_canonical(self):
        assert normalize_symbol("BTCUSDT") == "BTC/USDT"

    def test_btcusdt_lower_to_canonical(self):
        assert normalize_symbol("btcusdt") == "BTC/USDT"

    def test_already_canonical(self):
        assert normalize_symbol("BTC/USDT") == "BTC/USDT"

    def test_with_dash(self):
        assert normalize_symbol("BTC-USDT") == "BTC/USDT"

    def test_with_underscore(self):
        assert normalize_symbol("BTC_USDT") == "BTC/USDT"

    def test_ethusdt(self):
        assert normalize_symbol("ETHUSDT") == "ETH/USDT"

    def test_busd_pair(self):
        assert normalize_symbol("BTCBUSD") == "BTC/BUSD"

    def test_btc_pair(self):
        assert normalize_symbol("ETHBTC") == "ETH/BTC"

    def test_unknown_suffix(self):
        assert normalize_symbol("FOOBAR") == "FOOBAR"

    def test_denormalize_binance(self):
        assert denormalize_symbol("BTC/USDT", "binance") == "BTCUSDT"

    def test_denormalize_kraken_btc(self):
        assert denormalize_symbol("BTC/USDT", "kraken") == "XBTUSDT"

    def test_denormalize_kraken_eth(self):
        assert denormalize_symbol("ETH/USDT", "kraken") == "ETHUSDT"

    def test_denormalize_with_dash(self):
        assert denormalize_symbol("BTC-USDT", "binance") == "BTCUSDT"


class TestBalanceDecimal:
    def test_free_is_decimal(self):
        b = Balance(asset="BTC", free=Decimal("0.5"), locked=Decimal("0.1"))
        assert isinstance(b.free, Decimal)
        assert isinstance(b.locked, Decimal)

    def test_total(self):
        b = Balance(asset="USDT", free=Decimal("100"), locked=Decimal("50"))
        assert b.total == Decimal("150")

    def test_frozen(self):
        b = Balance(asset="USDT", free=Decimal("100"), locked=Decimal("50"))
        with pytest.raises(AttributeError):
            b.free = Decimal("200")


class TestPortfolioSnapshotDecimal:
    def test_total_usd_is_decimal(self):
        snap = PortfolioSnapshot(
            timestamp=__import__("datetime").datetime.now(),
            balances=(),
            total_usd=Decimal("5000.00"),
        )
        assert isinstance(snap.total_usd, Decimal)

    def test_frozen(self):
        snap = PortfolioSnapshot(
            timestamp=__import__("datetime").datetime.now(),
            balances=(),
            total_usd=Decimal("5000.00"),
        )
        with pytest.raises(AttributeError):
            snap.total_usd = Decimal("6000")


class TestOrderRequestDecimal:
    def test_quantity_is_decimal(self):
        req = OrderRequest(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.1"),
        )
        assert isinstance(req.quantity, Decimal)

    def test_price_is_decimal(self):
        req = OrderRequest(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.1"),
            price=Decimal("45000"),
        )
        assert isinstance(req.price, Decimal)


class TestBrokerOrderDecimal:
    def test_quantities_are_decimal(self):
        order = BrokerOrder(
            broker_order_id="123",
            client_order_id="abc",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.1"),
            filled_quantity=Decimal("0.1"),
            price=Decimal("45000"),
            status=OrderStatus.FILLED,
        )
        assert isinstance(order.quantity, Decimal)
        assert isinstance(order.filled_quantity, Decimal)
        assert isinstance(order.price, Decimal)


class TestTickerDecimal:
    def test_price_is_decimal(self):
        t = Ticker(symbol="BTC/USDT", price=Decimal("45000"))
        assert isinstance(t.price, Decimal)


class TestCandleDecimal:
    def test_all_fields_decimal(self):
        from datetime import datetime

        c = Candle(
            timestamp=datetime.now(),
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("95"),
            close=Decimal("105"),
            volume=Decimal("1000"),
        )
        for field in ("open", "high", "low", "close", "volume"):
            assert isinstance(getattr(c, field), Decimal), f"{field} should be Decimal"


class TestPositionDecimal:
    def test_quantities_are_decimal(self):
        p = Position(
            symbol="BTC/USDT",
            side="long",
            quantity=Decimal("0.1"),
            entry_price=Decimal("45000"),
            current_price=Decimal("46000"),
        )
        assert isinstance(p.quantity, Decimal)
        assert isinstance(p.entry_price, Decimal)
        assert isinstance(p.current_price, Decimal)


class TestBrokerCredentials:
    def test_basic(self):
        creds = BrokerCredentials(
            broker_id="binance",
            api_key="test_key",
            api_secret="test_secret",
        )
        assert creds.broker_id == "binance"
        assert creds.api_key == "test_key"
        assert creds.testnet is False

    def test_testnet(self):
        creds = BrokerCredentials(
            broker_id="binance",
            api_key="test_key",
            api_secret="test_secret",
            testnet=True,
        )
        assert creds.testnet is True

    def test_passphrase_optional(self):
        creds = BrokerCredentials(
            broker_id="okx",
            api_key="k",
            api_secret="s",
            passphrase="p",
        )
        assert creds.passphrase == "p"
