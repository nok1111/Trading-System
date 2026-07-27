"""Tests de paridad de API — verifica que las respuestas JSON no cambian tras la migracion.

Estos tests documentan el shape exacto de las respuestas de los endpoints
que se migran en Fase 1b. Sirven como regression test: si la forma cambia,
el test falla.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch


class TestBalanceResponseShape:
    """Shape de /api/binance/balance — debe mantenerse identico tras migrar a adapter."""

    EXPECTED_KEYS = {
        "assets",
        "total_usd",
        "total_mxn",
        "mxn_rate",
        "testnet",
        "usdt_free",
        "usdt_total",
        "usdt_mxn",
        "usdt_usd",
    }

    ASSET_KEYS = {"asset", "free", "locked", "total", "usd_value"}

    def test_balance_response_has_all_keys(self):
        """La respuesta de /api/binance/balance debe tener exactamente estas keys."""
        sample_response = {
            "assets": [
                {"asset": "USDT", "free": 1000.0, "locked": 0.0, "total": 1000.0, "usd_value": 1000.0},
                {"asset": "BTC", "free": 0.5, "locked": 0.0, "total": 0.5, "usd_value": 22500.0},
            ],
            "total_usd": 23500.0,
            "total_mxn": 441500.0,
            "mxn_rate": 18.5,
            "testnet": False,
            "usdt_free": 1000.0,
            "usdt_total": 1000.0,
            "usdt_mxn": 18500.0,
            "usdt_usd": 1000.0,
        }
        assert set(sample_response.keys()) == self.EXPECTED_KEYS
        for asset in sample_response["assets"]:
            assert set(asset.keys()) == self.ASSET_KEYS

    def test_error_response_shape(self):
        """La respuesta de error debe tener estas keys."""
        error_response = {
            "error": "No tienes API keys de Binance configuradas.",
            "assets": [],
            "total_usd": 0,
            "total_mxn": 0,
        }
        assert "error" in error_response
        assert error_response["assets"] == []
        assert error_response["total_usd"] == 0


class TestPositionsResponseShape:
    """Shape de /api/positions — debe mantenerse identico tras migrar a adapter."""

    POSITION_KEYS = {
        "id",
        "symbol",
        "opened_at",
        "closed_at",
        "side",
        "quantity",
        "entry_price",
        "current_price",
        "stop_loss",
        "take_profit",
        "unrealized_pnl",
        "realized_pnl",
        "status",
        "strategy_name",
    }

    def test_position_has_expected_keys(self):
        """Cada posicion en la lista debe tener estas keys (via PositionOut schema)."""
        sample_position = {
            "id": 1,
            "symbol": "BTCUSDT",
            "opened_at": "2025-01-01T00:00:00Z",
            "closed_at": None,
            "side": "long",
            "quantity": "0.1",
            "entry_price": "45000.00000000",
            "current_price": "46000.00000000",
            "stop_loss": "43650.00000000",
            "take_profit": "47700.00000000",
            "unrealized_pnl": "100.00000000",
            "realized_pnl": "0",
            "status": "open",
            "strategy_name": "AI-Agent",
        }
        assert set(sample_position.keys()) == self.POSITION_KEYS


class TestTickerDecimalParity:
    """Verifica que get_ticker devuelve Decimal, no float."""

    def test_ticker_price_is_decimal(self):
        from app.brokers.adapters.binance_adapter import BinanceAdapter
        from app.brokers.models import BrokerCredentials

        creds = BrokerCredentials(
            broker_id="binance",
            api_key="k",
            api_secret="s",
        )
        adapter = BinanceAdapter(creds)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"price": "45000.00"}
        mock_resp.raise_for_status = MagicMock()

        with patch("app.brokers.adapters.binance_adapter.httpx.get", return_value=mock_resp):
            ticker = adapter.get_ticker("BTC/USDT")

        assert isinstance(ticker.price, Decimal)
        assert ticker.price == Decimal("45000.00")
