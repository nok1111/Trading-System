"""Tests para brokers/registry.py — resolucion de adaptadores, withdrawals siempre False.

Estado actual: Binance usa adapter nativo, el resto usa CCXTAdapter (20+ exchanges).
No hay stubs NotImplementedError — CCXTAdapter cubre todos los exchanges no-Binance.
"""

from decimal import Decimal
from unittest.mock import patch

import pytest

from app.brokers.base import BrokerAdapter, BrokerError
from app.brokers.capabilities import BrokerCapabilities
from app.brokers.models import BrokerCredentials
from app.brokers.registry import (
    get_adapter,
    get_available_broker_ids,
    get_capabilities,
    is_implemented,
    list_brokers,
)

# Brokers que el usuario decidio soportar explicitamente
_REQUIRED_BROKERS = ("binance", "bybit", "coinbase", "kraken", "okx")


def _creds(broker_id: str) -> BrokerCredentials:
    return BrokerCredentials(broker_id=broker_id, api_key="k", api_secret="s")


class TestListBrokers:
    def test_returns_all_required_brokers(self):
        brokers = list_brokers()
        ids = [b.broker_id for b in brokers]
        for required in _REQUIRED_BROKERS:
            assert required in ids, f"{required} should be registered"

    def test_returns_at_least_5_brokers(self):
        brokers = list_brokers()
        assert len(brokers) >= 5

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
        adapter = get_adapter("binance", _creds("binance"))
        assert isinstance(adapter, BrokerAdapter)
        assert adapter.get_broker_info().broker_id == "binance"

    def test_non_binance_blocked_without_flag(self):
        with patch("app.brokers.registry.get_settings") as mock_settings:
            mock_settings.return_value.ENABLE_MULTI_BROKER = False
            with pytest.raises(BrokerError, match="Multi-broker deshabilitado"):
                get_adapter("bybit", _creds("bybit"))

    def test_non_binance_allowed_with_flag(self):
        with patch("app.brokers.registry.get_settings") as mock_settings:
            mock_settings.return_value.ENABLE_MULTI_BROKER = True
            adapter = get_adapter("bybit", _creds("bybit"))
            assert isinstance(adapter, BrokerAdapter)

    def test_unknown_broker_raises(self):
        with patch("app.brokers.registry.get_settings") as mock_settings:
            mock_settings.return_value.ENABLE_MULTI_BROKER = True
            with pytest.raises(BrokerError, match="Broker desconocido"):
                get_adapter("nonexistent", _creds("nonexistent"))


class TestWithdrawalsAlwaysFalse:
    """withdrawals debe ser False en todos los brokers, sin excepcion."""

    def test_all_required_brokers_withdrawals_false(self):
        for broker_id in _REQUIRED_BROKERS:
            caps = get_capabilities(broker_id)
            assert caps.withdrawals is False, f"{broker_id} should have withdrawals=False"


class TestGetAvailableBrokerIds:
    def test_only_binance_by_default(self):
        with patch("app.brokers.registry.get_settings") as mock_settings:
            mock_settings.return_value.ENABLE_MULTI_BROKER = False
            ids = get_available_broker_ids()
            assert ids == ("binance",)

    def test_all_brokers_when_flag_enabled(self):
        with patch("app.brokers.registry.get_settings") as mock_settings:
            mock_settings.return_value.ENABLE_MULTI_BROKER = True
            ids = get_available_broker_ids()
            assert "binance" in ids
            assert "bybit" in ids
            assert len(ids) >= 5


class TestIsImplemented:
    def test_required_brokers_are_implemented(self):
        for broker_id in _REQUIRED_BROKERS:
            assert is_implemented(broker_id), f"{broker_id} should be implemented"

    def test_unknown_broker_not_implemented(self):
        assert not is_implemented("nonexistent")
