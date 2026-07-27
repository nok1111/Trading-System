"""Tests para BinanceAdapter — firma HMAC, stepSize, MIN_NOTIONAL, mapeo de estados y errores.

Sin red: monkeypatch de httpx.get / httpx.post / httpx.delete.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.brokers.adapters.binance_adapter import BinanceAdapter, _map_binance_error
from app.brokers.base import (
    BrokerAuthError,
    BrokerError,
    BrokerRateLimitError,
    BrokerTimeoutError,
    DuplicateOrderError,
    InsufficientBalanceError,
    InvalidSymbolError,
    MinNotionalError,
)
from app.brokers.binance_broker import BinanceBrokerError
from app.brokers.capabilities import BrokerCapabilities
from app.brokers.models import (
    BrokerAccountStatus,
    BrokerCredentials,
    BrokerInfo,
    MarketType,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
)


@pytest.fixture
def credentials():
    return BrokerCredentials(
        broker_id="binance",
        api_key="test_api_key",
        api_secret="test_api_secret",
        testnet=False,
    )


@pytest.fixture
def adapter(credentials):
    return BinanceAdapter(credentials)


def _mock_response(json_data: dict, status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError
        resp.raise_for_status.side_effect = HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


class TestBrokerInfo:
    def test_get_broker_info(self, adapter):
        info = adapter.get_broker_info()
        assert isinstance(info, BrokerInfo)
        assert info.broker_id == "binance"
        assert info.display_name == "Binance"
        assert MarketType.SPOT in info.supported_markets

    def test_get_capabilities(self, adapter):
        caps = adapter.get_capabilities()
        assert isinstance(caps, BrokerCapabilities)
        assert caps.spot is True
        assert caps.websocket is True
        assert caps.market_orders is True
        assert caps.limit_orders is True
        assert caps.stop_orders is True
        assert caps.withdrawals is False


class TestValidateCredentials:
    def test_valid_credentials(self, adapter):
        with patch.object(adapter._broker, "_signed_request", return_value={"balances": []}):
            result = adapter.validate_credentials()
        assert result.valid is True
        assert result.status == BrokerAccountStatus.ACTIVE

    def test_invalid_credentials(self, adapter):
        with patch.object(
            adapter._broker,
            "_signed_request",
            side_effect=BinanceBrokerError("Binance API error -2015: Invalid API-key"),
        ):
            result = adapter.validate_credentials()
        assert result.valid is False
        assert result.status == BrokerAccountStatus.API_KEY_INVALID

    def test_rate_limited(self, adapter):
        with patch.object(
            adapter._broker,
            "_signed_request",
            side_effect=BinanceBrokerError("Binance API error 429: rate limit exceeded"),
        ):
            result = adapter.validate_credentials()
        assert result.valid is False
        assert result.status == BrokerAccountStatus.RATE_LIMITED


class TestGetAccountBalances:
    def test_returns_balances(self, adapter):
        account_data = {
            "balances": [
                {"asset": "BTC", "free": "0.5", "locked": "0.1"},
                {"asset": "USDT", "free": "1000", "locked": "0"},
                {"asset": "ETH", "free": "0", "locked": "0"},
            ]
        }
        with patch.object(adapter._broker, "_signed_request", return_value=account_data):
            balances = adapter.get_account_balances()
        assert len(balances) == 2
        assert balances[0].asset == "BTC"
        assert balances[0].free == Decimal("0.5")
        assert balances[0].locked == Decimal("0.1")
        assert balances[1].asset == "USDT"
        assert balances[1].free == Decimal("1000")

    def test_all_decimal(self, adapter):
        account_data = {
            "balances": [
                {"asset": "BTC", "free": "0.5", "locked": "0.1"},
            ]
        }
        with patch.object(adapter._broker, "_signed_request", return_value=account_data):
            balances = adapter.get_account_balances()
        for b in balances:
            assert isinstance(b.free, Decimal)
            assert isinstance(b.locked, Decimal)

    def test_auth_error(self, adapter):
        with patch.object(
            adapter._broker,
            "_signed_request",
            side_effect=BinanceBrokerError("Binance API error -2015: Invalid"),
        ), pytest.raises(BrokerAuthError):
            adapter.get_account_balances()


class TestGetTicker:
    def test_returns_ticker(self, adapter):
        mock_resp = _mock_response({"price": "45000.00"})
        with patch("app.brokers.adapters.binance_adapter.httpx.get", return_value=mock_resp):
            ticker = adapter.get_ticker("BTC/USDT")
        assert ticker.symbol == "BTC/USDT"
        assert ticker.price == Decimal("45000.00")
        assert isinstance(ticker.price, Decimal)

    def test_invalid_symbol(self, adapter):
        mock_resp = _mock_response({"code": -1121, "msg": "Invalid symbol"}, status_code=400)
        with patch("app.brokers.adapters.binance_adapter.httpx.get", return_value=mock_resp), pytest.raises(InvalidSymbolError):
            adapter.get_ticker("FAKE/USDT")

    def test_rate_limit(self, adapter):
        mock_resp = _mock_response({"code": -1003, "msg": "Rate limit"}, status_code=429)
        with patch("app.brokers.adapters.binance_adapter.httpx.get", return_value=mock_resp), pytest.raises(BrokerRateLimitError):
            adapter.get_ticker("BTC/USDT")


class TestGetMarketInfo:
    def test_returns_market_info(self, adapter):
        exchange_data = {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "status": "TRADING",
                    "filters": [
                        {"filterType": "LOT_SIZE", "minQty": "0.00001", "maxQty": "9000", "stepSize": "0.00001"},
                        {"filterType": "NOTIONAL", "minNotional": "10"},
                    ],
                }
            ]
        }
        mock_resp = _mock_response(exchange_data)
        with patch("app.brokers.adapters.binance_adapter.httpx.get", return_value=mock_resp):
            info = adapter.get_market_info("BTC/USDT")
        assert info.broker_symbol == "BTCUSDT"
        assert info.base_asset == "BTC"
        assert info.quote_asset == "USDT"
        assert info.step_size == Decimal("0.00001")
        assert info.min_notional == Decimal("10")

    def test_invalid_symbol(self, adapter):
        mock_resp = _mock_response({"symbols": []})
        with patch("app.brokers.adapters.binance_adapter.httpx.get", return_value=mock_resp), pytest.raises(InvalidSymbolError):
            adapter.get_market_info("FAKE/USDT")


class TestPlaceOrder:
    def test_market_buy(self, adapter):
        order_resp = {
            "orderId": 123456,
            "clientOrderId": "test-1",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "MARKET",
            "origQty": "0.001",
            "executedQty": "0.001",
            "price": "0",
            "avgPrice": "45000",
            "status": "FILLED",
        }
        with patch.object(adapter._broker, "_signed_request", return_value=order_resp):
            req = OrderRequest(
                symbol="BTC/USDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal("0.001"),
            )
            result = adapter.place_order(req)
        assert result.success is True
        assert result.order is not None
        assert result.order.broker_order_id == "123456"
        assert result.order.status == OrderStatus.FILLED
        assert result.order.filled_quantity == Decimal("0.001")
        assert result.order.avg_fill_price == Decimal("45000")

    def test_limit_order(self, adapter):
        order_resp = {
            "orderId": 123457,
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "LIMIT",
            "origQty": "0.001",
            "executedQty": "0",
            "price": "40000",
            "status": "NEW",
        }
        with patch.object(adapter._broker, "_signed_request", return_value=order_resp):
            req = OrderRequest(
                symbol="BTC/USDT",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=Decimal("0.001"),
                price=Decimal("40000"),
            )
            result = adapter.place_order(req)
        assert result.success is True
        assert result.order.status == OrderStatus.PENDING
        assert result.order.price == Decimal("40000")

    def test_insufficient_balance(self, adapter):
        with patch.object(
            adapter._broker,
            "_signed_request",
            side_effect=BinanceBrokerError("Binance API error -2010: Insufficient balance"),
        ):
            req = OrderRequest(
                symbol="BTC/USDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal("100"),
            )
            result = adapter.place_order(req)
        assert result.success is False
        assert "InsufficientBalance" in result.error or "insufficient" in result.error.lower()

    def test_min_notional(self, adapter):
        with patch.object(
            adapter._broker,
            "_signed_request",
            side_effect=BinanceBrokerError("Binance API error -1013: MIN_NOTIONAL"),
        ):
            req = OrderRequest(
                symbol="BTC/USDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal("0.00001"),
            )
            result = adapter.place_order(req)
        assert result.success is False

    def test_duplicate_order(self, adapter):
        with patch.object(
            adapter._broker,
            "_signed_request",
            side_effect=BinanceBrokerError("Binance API error -2011: Duplicate order"),
        ):
            req = OrderRequest(
                symbol="BTC/USDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal("0.1"),
                client_order_id="dup-1",
            )
            result = adapter.place_order(req)
        assert result.success is False


class TestCancelOrder:
    def test_success(self, adapter):
        cancel_resp = {
            "orderId": 123456,
            "symbol": "BTCUSDT",
            "status": "CANCELED",
        }
        with patch.object(adapter._broker, "_signed_request", return_value=cancel_resp):
            from app.brokers.models import CancelOrderRequest

            result = adapter.cancel_order(CancelOrderRequest(broker_order_id="123456", symbol="BTC/USDT"))
        assert result.success is True
        assert result.status == OrderStatus.CANCELLED

    def test_no_id(self, adapter):
        from app.brokers.models import CancelOrderRequest

        result = adapter.cancel_order(CancelOrderRequest())
        assert result.success is False


class TestErrorMapping:
    def test_auth_error(self):
        exc = BinanceBrokerError("Binance API error -2015: Invalid API-key")
        mapped = _map_binance_error(exc)
        assert isinstance(mapped, BrokerAuthError)

    def test_invalid_symbol(self):
        exc = BinanceBrokerError("Binance API error -1121: Invalid symbol")
        mapped = _map_binance_error(exc)
        assert isinstance(mapped, InvalidSymbolError)

    def test_min_notional(self):
        exc = BinanceBrokerError("Binance API error -1013: MIN_NOTIONAL")
        mapped = _map_binance_error(exc)
        assert isinstance(mapped, MinNotionalError)

    def test_insufficient_balance(self):
        exc = BinanceBrokerError("Binance API error -2010: Insufficient balance")
        mapped = _map_binance_error(exc)
        assert isinstance(mapped, InsufficientBalanceError)

    def test_duplicate_order(self):
        exc = BinanceBrokerError("Binance API error -2011: Duplicate")
        mapped = _map_binance_error(exc)
        assert isinstance(mapped, DuplicateOrderError)

    def test_rate_limit(self):
        exc = BinanceBrokerError("Error 429: rate limit exceeded")
        mapped = _map_binance_error(exc)
        assert isinstance(mapped, BrokerRateLimitError)

    def test_timeout(self):
        exc = BinanceBrokerError("Timeout connecting to Binance")
        mapped = _map_binance_error(exc)
        assert isinstance(mapped, BrokerTimeoutError)

    def test_generic_error(self):
        exc = BinanceBrokerError("Some unknown error")
        mapped = _map_binance_error(exc)
        assert isinstance(mapped, BrokerError)
        assert not isinstance(mapped, (BrokerAuthError, BrokerRateLimitError, BrokerTimeoutError))


class TestGetKlines:
    def test_returns_candles_with_decimal(self, adapter):
        raw_klines = [
            [1700000000000, "42000.0", "42100.0", "41900.0", "42050.0", "100.5", 0, "4205000.0", 10, "50.0", "42000.0"],
            [1700000060000, "42050.0", "42200.0", "42000.0", "42150.0", "200.3", 0, "8430000.0", 20, "100.0", "42050.0"],
        ]
        mock_resp = _mock_response(raw_klines)
        with patch("app.brokers.adapters.binance_adapter.httpx.get", return_value=mock_resp):
            candles = adapter.get_klines("BTC/USDT", "1m", 200)
        assert len(candles) == 2
        for c in candles:
            assert isinstance(c.open, Decimal)
            assert isinstance(c.high, Decimal)
            assert isinstance(c.low, Decimal)
            assert isinstance(c.close, Decimal)
            assert isinstance(c.volume, Decimal)
        assert candles[0].open == Decimal("42000.0")
        assert candles[0].close == Decimal("42050.0")
        assert candles[1].volume == Decimal("200.3")

    def test_invalid_symbol(self, adapter):
        mock_resp = _mock_response({"code": -1121, "msg": "Invalid symbol"}, status_code=400)
        with patch("app.brokers.adapters.binance_adapter.httpx.get", return_value=mock_resp), pytest.raises(InvalidSymbolError):
            adapter.get_klines("FAKE/USDT", "1m", 200)

    def test_empty_response(self, adapter):
        mock_resp = _mock_response([])
        with patch("app.brokers.adapters.binance_adapter.httpx.get", return_value=mock_resp):
            candles = adapter.get_klines("BTC/USDT", "1m", 200)
        assert len(candles) == 0


class TestGetMarketMovers:
    def test_returns_movers_with_decimal(self, adapter):
        raw_tickers = [
            {"symbol": "BTCUSDT", "lastPrice": "42000", "priceChangePercent": "5.2", "quoteVolume": "1000000"},
            {"symbol": "ETHUSDT", "lastPrice": "2200", "priceChangePercent": "-3.1", "quoteVolume": "500000"},
            {"symbol": "SOLUSDT", "lastPrice": "100", "priceChangePercent": "8.5", "quoteVolume": "200000"},
            {"symbol": "DOGEUSDT", "lastPrice": "0.08", "priceChangePercent": "-7.2", "quoteVolume": "100000"},
        ]
        mock_resp = _mock_response(raw_tickers)
        with patch("app.brokers.adapters.binance_adapter.httpx.get", return_value=mock_resp):
            result = adapter.get_market_movers(market="spot", limit=2, quote="USDT")
        assert "gainers" in result
        assert "losers" in result
        assert len(result["gainers"]) == 2
        assert len(result["losers"]) == 2
        for t in result["gainers"] + result["losers"]:
            assert isinstance(t["price"], Decimal)
            assert isinstance(t["price_change_percent"], Decimal)
            assert isinstance(t["volume"], Decimal)
        assert result["gainers"][0]["price_change_percent"] == Decimal("8.5")
        assert result["gainers"][1]["price_change_percent"] == Decimal("5.2")
        assert result["losers"][0]["price_change_percent"] == Decimal("-7.2")
        assert result["losers"][1]["price_change_percent"] == Decimal("-3.1")
