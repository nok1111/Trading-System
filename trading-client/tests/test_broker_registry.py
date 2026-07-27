"""Tests para brokers/registry.py — resolucion de adaptadores, stubs, withdrawals siempre False."""

from decimal import Decimal

import pytest

from app.brokers.base import BrokerAdapter, BrokerError
from app.brokers.capabilities import BrokerCapabilities
from app.brokers.models import BrokerCredentials
from app.brokers.registry import (
    get_adapter,
    get_available_broker_ids,
    get_capabilities,
    list_brokers,
)


class TestListBrokers:
    def test_returns_all_brokers(self):
        brokers = list_brokers()
        ids = [b.broker_id for b in brokers]
        assert "binance" in ids
        assert "bybit" in ids
        assert "coinbase" in ids
        assert "kraken" in ids
        assert "okx" in ids
        assert len(brokers) == 5

    def test_broker_info_has_display_name(self):
        brokers = list_brokers()
        for b in brokers:
            assert b.display_name
            assert b.broker_id


class TestGetCapabilities:
    def test_binance_capabilities(self):
        caps = get_capabilities("binance")
        assert isinstance(caps, BrokerCapabilities)
        assert caps.spot is True
        assert caps.withdrawals is False

    def test_bybit_capabilities(self):
        caps = get_capabilities("bybit")
        assert caps.spot is True
        assert caps.futures is True
        assert caps.withdrawals is False

    def test_coinbase_capabilities(self):
        caps = get_capabilities("coinbase")
        assert caps.spot is True
        assert caps.withdrawals is False

    def test_kraken_capabilities(self):
        caps = get_capabilities("kraken")
        assert caps.spot is True
        assert caps.withdrawals is False

    def test_okx_capabilities(self):
        caps = get_capabilities("okx")
        assert caps.spot is True
        assert caps.withdrawals is False

    def test_unknown_broker(self):
        with pytest.raises(BrokerError):
            get_capabilities("nonexistent")


class TestGetAdapter:
    def test_binance_adapter(self):
        creds = BrokerCredentials(
            broker_id="binance",
            api_key="k",
            api_secret="s",
        )
        adapter = get_adapter("binance", creds)
        assert isinstance(adapter, BrokerAdapter)
        assert adapter.get_broker_info().broker_id == "binance"

    def test_non_binance_blocked_without_flag(self):
        creds = BrokerCredentials(
            broker_id="bybit",
            api_key="k",
            api_secret="s",
        )
        with pytest.raises(BrokerError, match="Multi-broker deshabilitado"):
            get_adapter("bybit", creds)

    def test_unknown_broker(self):
        creds = BrokerCredentials(
            broker_id="nonexistent",
            api_key="k",
            api_secret="s",
        )
        with pytest.raises(BrokerError, match="Multi-broker deshabilitado"):
            get_adapter("nonexistent", creds)


class TestStubsNotImplemented:
    """Los stubs deben lanzar NotImplementedError en todos los metodos excepto get_broker_info y get_capabilities."""

    def _make_stub(self, broker_id: str) -> BrokerAdapter:
        creds = BrokerCredentials(broker_id=broker_id, api_key="k", api_secret="s")
        from app.brokers.registry import _register_adapters
        _register_adapters()
        from app.brokers.registry import _ADAPTER_CLASSES
        cls = _ADAPTER_CLASSES[broker_id]
        return cls(creds)

    def test_bybit_validate_credentials(self):
        adapter = self._make_stub("bybit")
        with pytest.raises(NotImplementedError):
            adapter.validate_credentials()

    def test_bybit_get_account_balances(self):
        adapter = self._make_stub("bybit")
        with pytest.raises(NotImplementedError):
            adapter.get_account_balances()

    def test_bybit_get_ticker(self):
        adapter = self._make_stub("bybit")
        with pytest.raises(NotImplementedError):
            adapter.get_ticker("BTC/USDT")

    def test_bybit_place_order(self):
        adapter = self._make_stub("bybit")
        from app.brokers.models import OrderRequest, OrderSide, OrderType

        with pytest.raises(NotImplementedError):
            adapter.place_order(
                OrderRequest(
                    symbol="BTC/USDT",
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=Decimal("0.1"),
                )
            )

    def test_coinbase_validate_credentials(self):
        adapter = self._make_stub("coinbase")
        with pytest.raises(NotImplementedError):
            adapter.validate_credentials()

    def test_kraken_validate_credentials(self):
        adapter = self._make_stub("kraken")
        with pytest.raises(NotImplementedError):
            adapter.validate_credentials()

    def test_okx_validate_credentials(self):
        adapter = self._make_stub("okx")
        with pytest.raises(NotImplementedError):
            adapter.validate_credentials()

    def test_bybit_get_broker_info_works(self):
        adapter = self._make_stub("bybit")
        info = adapter.get_broker_info()
        assert info.broker_id == "bybit"

    def test_bybit_get_capabilities_works(self):
        adapter = self._make_stub("bybit")
        caps = adapter.get_capabilities()
        assert caps.withdrawals is False


class TestWithdrawalsAlwaysFalse:
    """withdrawals debe ser False en todos los brokers, sin excepcion."""

    def test_all_brokers_withdrawals_false(self):
        for broker_id in ("binance", "bybit", "coinbase", "kraken", "okx"):
            caps = get_capabilities(broker_id)
            assert caps.withdrawals is False, f"{broker_id} should have withdrawals=False"


class TestGetAvailableBrokerIds:
    def test_only_binance_by_default(self):
        ids = get_available_broker_ids()
        assert ids == ("binance",)
