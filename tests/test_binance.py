"""Pruebas de los adaptadores de Binance (data source y broker)."""

import hashlib
import hmac
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock

import httpx
import pandas as pd
import pytest

from app.brokers.binance_broker import BinanceBroker, BinanceBrokerError
from app.data.binance_source import BinanceDataSource
from app.data.data_source import DataSourceError
from app.database.models.order import Order


# ---------------------------------------------------------------------------
# BinanceDataSource
# ---------------------------------------------------------------------------


def _make_klines_response(n: int = 10, interval_ms: int = 86_400_000) -> list[list]:
    """Genera una respuesta simulada de klines de Binance."""
    base_ts = 1_700_000_000_000
    return [
        [
            base_ts + i * interval_ms,
            f"{100 + i}.50",      # open
            f"{105 + i}.00",      # high
            f"{95 + i}.00",       # low
            f"{102 + i}.30",      # close
            f"{1_000_000 + i * 10000}",  # volume
            base_ts + i * interval_ms + 3600000,  # close time
            "50000000",           # quote asset volume
            1000,                 # number of trades
            None,                 # taker buy base volume
            None,                 # taker buy quote volume
            "0",                  # ignore
        ]
        for i in range(n)
    ]


class TestBinanceDataSource:
    def test_name(self):
        ds = BinanceDataSource()
        assert ds.name == "binance"

    def test_fetch_bars_success(self):
        klines = _make_klines_response(n=5)
        mock_resp = MagicMock()
        mock_resp.json.return_value = klines
        mock_resp.raise_for_status = MagicMock()

        ds = BinanceDataSource()
        with patch("httpx.get", return_value=mock_resp):
            df = ds.fetch_bars("BTCUSDT", date(2024, 1, 1), date(2024, 1, 6), "1d")

        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert len(df) == 5
        assert df.index.name == "timestamp"
        assert df.index.tz is not None

    def test_fetch_bars_empty_raises(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status = MagicMock()

        ds = BinanceDataSource()
        with patch("httpx.get", return_value=mock_resp):
            with pytest.raises(DataSourceError, match="no devolvió datos"):
                ds.fetch_bars("FAKEUSDT", date(2024, 1, 1), date(2024, 1, 6), "1d")

    def test_fetch_bars_http_error_raises(self):
        ds = BinanceDataSource()
        with patch("httpx.get", side_effect=httpx.ConnectError("connection refused")):
            with pytest.raises(DataSourceError, match="Error al consultar klines"):
                ds.fetch_bars("BTCUSDT", date(2024, 1, 1), date(2024, 1, 6), "1d")

    def test_unsupported_timeframe_raises(self):
        ds = BinanceDataSource()
        with pytest.raises(DataSourceError, match="Timeframe no soportado"):
            ds.fetch_bars("BTCUSDT", date(2024, 1, 1), date(2024, 1, 6), "2d")

    def test_pagination(self):
        """Verifica que se hacen múltiples requests cuando hay >1000 velas."""
        interval_ms = 86_400_000
        base_ts = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)

        klines_page1 = [
            [base_ts + i * interval_ms, "100.0", "105.0", "95.0", "102.0", "1000000"]
            + [None] * 6
            for i in range(1000)
        ]
        klines_page2 = [
            [base_ts + (1000 + i) * interval_ms, "200.0", "205.0", "195.0", "202.0", "2000000"]
            + [None] * 6
            for i in range(5)
        ]
        mock_resp1 = MagicMock()
        mock_resp1.json.return_value = klines_page1
        mock_resp1.raise_for_status = MagicMock()
        mock_resp2 = MagicMock()
        mock_resp2.json.return_value = klines_page2
        mock_resp2.raise_for_status = MagicMock()

        ds = BinanceDataSource()
        with patch("httpx.get", side_effect=[mock_resp1, mock_resp2]):
            df = ds.fetch_bars("BTCUSDT", date(2020, 1, 1), date(2024, 1, 1), "1d")

        assert len(df) == 1005


# ---------------------------------------------------------------------------
# BinanceBroker
# ---------------------------------------------------------------------------


def _make_order(symbol="BTCUSDT", side="buy", qty=Decimal("0.001"), order_type="market"):
    return Order(
        client_order_id="test-001",
        broker_order_id=None,
        timestamp=datetime.now(tz=UTC),
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=qty,
        filled_quantity=Decimal("0"),
        price=Decimal("50000") if order_type == "limit" else None,
        status="submitted",
    )


class TestBinanceBroker:
    def test_name(self):
        broker = BinanceBroker("key", "secret")
        assert broker.name == "binance"

    def test_testnet_url(self):
        broker = BinanceBroker("key", "secret", testnet=True)
        assert broker._base_url == "https://testnet.binance.vision"

    def test_place_order_market(self):
        resp_data = {
            "orderId": 123456,
            "status": "FILLED",
            "executedQty": "0.001",
            "avgPrice": "50000.00",
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = resp_data
        mock_resp.raise_for_status = MagicMock()

        broker = BinanceBroker("test_key", "test_secret")
        order = _make_order()
        with patch("httpx.post", return_value=mock_resp):
            result = broker.place_order(order)

        assert result.broker_order_id == "123456"
        assert result.status == "filled"
        assert result.filled_quantity == Decimal("0.001")
        assert result.price == Decimal("50000.00")

    def test_place_order_limit(self):
        resp_data = {
            "orderId": 789,
            "status": "NEW",
            "executedQty": "0",
            "price": "50000.00",
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = resp_data
        mock_resp.raise_for_status = MagicMock()

        broker = BinanceBroker("test_key", "test_secret")
        order = _make_order(order_type="limit", qty=Decimal("0.01"))
        with patch("httpx.post", return_value=mock_resp):
            result = broker.place_order(order)

        assert result.status == "pending"
        assert result.broker_order_id == "789"

    def test_cancel_order_success(self):
        resp_data = {
            "symbol": "BTCUSDT",
            "orderId": 123,
            "status": "CANCELED",
            "side": "BUY",
            "type": "MARKET",
            "origQty": "0.001",
            "executedQty": "0",
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = resp_data
        mock_resp.raise_for_status = MagicMock()

        broker = BinanceBroker("test_key", "test_secret")
        with patch("httpx.delete", return_value=mock_resp):
            result = broker.cancel_order("123")

        assert result is not None
        assert result.status == "cancelled"

    def test_cancel_order_not_found(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPError("not found")

        broker = BinanceBroker("test_key", "test_secret")
        with patch("httpx.delete", return_value=mock_resp):
            result = broker.cancel_order("999")

        assert result is None

    def test_get_order_success(self):
        resp_data = {
            "symbol": "BTCUSDT",
            "orderId": 123,
            "status": "FILLED",
            "side": "BUY",
            "type": "MARKET",
            "origQty": "0.001",
            "executedQty": "0.001",
            "price": "0",
            "clientOrderId": "test-001",
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = resp_data
        mock_resp.raise_for_status = MagicMock()

        broker = BinanceBroker("test_key", "test_secret")
        with patch("httpx.get", return_value=mock_resp):
            result = broker.get_order("123")

        assert result is not None
        assert result.status == "filled"
        assert result.symbol == "BTCUSDT"

    def test_get_quote(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"price": "51234.56"}
        mock_resp.raise_for_status = MagicMock()

        broker = BinanceBroker("test_key", "test_secret")
        with patch("httpx.get", return_value=mock_resp):
            price = broker.get_quote("BTCUSDT")

        assert price == Decimal("51234.56")

    def test_get_quote_error(self):
        broker = BinanceBroker("test_key", "test_secret")
        with patch("httpx.get", side_effect=httpx.ConnectError("no connection")):
            with pytest.raises(BinanceBrokerError, match="No se pudo obtener precio"):
                broker.get_quote("BTCUSDT")

    def test_signed_request_includes_signature(self):
        """Verifica que la firma HMAC-SHA256 se añade a los parámetros."""
        resp_data = {"balances": []}
        mock_resp = MagicMock()
        mock_resp.json.return_value = resp_data
        mock_resp.raise_for_status = MagicMock()

        broker = BinanceBroker("test_key", "test_secret")
        with patch("httpx.get", return_value=mock_resp) as mock_get:
            broker._signed_request("GET", "/api/v3/account", {})

            call_params = mock_get.call_args.kwargs.get("params", {})
            assert "signature" in call_params
            assert "timestamp" in call_params
            assert call_params["signature"] != ""

    def test_signed_request_api_error_raises(self):
        error_data = {"code": -2010, "msg": "insufficient balance"}
        mock_resp = MagicMock()
        mock_resp.json.return_value = error_data
        mock_resp.raise_for_status = MagicMock()

        broker = BinanceBroker("test_key", "test_secret")
        with patch("httpx.get", return_value=mock_resp):
            with pytest.raises(BinanceBrokerError, match="insufficient balance"):
                broker._signed_request("GET", "/api/v3/account", {})

    def test_map_status(self):
        assert BinanceBroker._map_status("NEW") == "pending"
        assert BinanceBroker._map_status("FILLED") == "filled"
        assert BinanceBroker._map_status("CANCELED") == "cancelled"
        assert BinanceBroker._map_status("REJECTED") == "rejected"
        assert BinanceBroker._map_status("EXPIRED") == "rejected"

    def test_format_quantity(self):
        assert BinanceBroker._format_quantity(Decimal("0.00100000")) == "0.001"
        assert BinanceBroker._format_quantity(Decimal("1.50000000")) == "1.5"
        assert BinanceBroker._format_quantity(Decimal("0")) == "0"

    def test_format_price(self):
        assert BinanceBroker._format_price(Decimal("50000.00000000")) == "50000"
        assert BinanceBroker._format_price(Decimal("50000.50000000")) == "50000.5"
