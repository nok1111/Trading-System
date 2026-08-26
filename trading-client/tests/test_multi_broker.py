"""Tests for OKX and Bybit adapter wrappers."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestOKXAdapter:
    """Tests for OKXAdapter."""

    def test_okx_adapter_instantiation(self):
        """Should create OKXAdapter with correct exchange_id."""
        from app.brokers.adapters.okx_adapter import OKXAdapter
        from app.brokers.models import BrokerCredentials

        creds = BrokerCredentials(
            broker_id="okx",
            api_key="test-key",
            api_secret="test-secret",
            passphrase="test-passphrase",
            testnet=False,
        )

        adapter = OKXAdapter(creds)
        assert adapter._exchange_id == "okx"
        assert adapter._market_type == "spot"

    def test_okx_adapter_testnet_mode(self):
        """Should enable sandbox mode for testnet."""
        from app.brokers.adapters.okx_adapter import OKXAdapter
        from app.brokers.models import BrokerCredentials

        creds = BrokerCredentials(
            broker_id="okx",
            api_key="test-key",
            api_secret="test-secret",
            passphrase="test-passphrase",
            testnet=True,
        )

        adapter = OKXAdapter(creds)
        assert adapter._credentials.testnet is True

    def test_okx_validate_credentials_without_passphrase(self):
        """Should fail validation if passphrase is missing."""
        from app.brokers.adapters.okx_adapter import OKXAdapter
        from app.brokers.models import BrokerCredentials, BrokerAccountStatus

        creds = BrokerCredentials(
            broker_id="bybit",
            api_key="test-key",
            api_secret="test-secret",
            passphrase=None,
            testnet=False,
        )

        adapter = OKXAdapter(creds)
        result = adapter.validate_credentials()
        assert result.valid is False
        assert "passphrase" in (result.error_message or "").lower()

    def test_okx_get_broker_info(self):
        """Should return OKX broker info."""
        from app.brokers.adapters.okx_adapter import OKXAdapter
        from app.brokers.models import BrokerCredentials

        creds = BrokerCredentials(
            broker_id="okx",
            api_key="test-key",
            api_secret="test-secret",
            passphrase="test-passphrase",
            testnet=False,
        )

        adapter = OKXAdapter(creds)
        info = adapter.get_broker_info()
        assert info.broker_id == "okx"
        assert info.display_name == "OKX"

    def test_okx_get_capabilities(self):
        """Should return OKX capabilities (spot + futures)."""
        from app.brokers.adapters.okx_adapter import OKXAdapter
        from app.brokers.models import BrokerCredentials

        creds = BrokerCredentials(
            broker_id="okx",
            api_key="test-key",
            api_secret="test-secret",
            passphrase="test-passphrase",
            testnet=False,
        )

        adapter = OKXAdapter(creds)
        caps = adapter.get_capabilities()
        assert caps.spot is True
        assert caps.futures is True


class TestBybitAdapter:
    """Tests for BybitAdapter."""

    def test_bybit_adapter_instantiation(self):
        """Should create BybitAdapter with correct exchange_id."""
        from app.brokers.adapters.bybit_adapter import BybitAdapter
        from app.brokers.models import BrokerCredentials

        creds = BrokerCredentials(
            broker_id="bybit",
            api_key="test-key",
            api_secret="test-secret",
            passphrase=None,
            testnet=False,
        )

        adapter = BybitAdapter(creds)
        assert adapter._exchange_id == "bybit"
        assert adapter._market_type == "spot"

    def test_bybit_adapter_testnet_mode(self):
        """Should work in testnet mode."""
        from app.brokers.adapters.bybit_adapter import BybitAdapter
        from app.brokers.models import BrokerCredentials

        creds = BrokerCredentials(
            broker_id="bybit",
            api_key="test-key",
            api_secret="test-secret",
            passphrase=None,
            testnet=True,
        )

        adapter = BybitAdapter(creds)
        assert adapter._credentials.testnet is True

    def test_bybit_get_broker_info(self):
        """Should return Bybit broker info."""
        from app.brokers.adapters.bybit_adapter import BybitAdapter
        from app.brokers.models import BrokerCredentials

        creds = BrokerCredentials(
            broker_id="bybit",
            api_key="test-key",
            api_secret="test-secret",
            passphrase=None,
            testnet=False,
        )

        adapter = BybitAdapter(creds)
        info = adapter.get_broker_info()
        assert info.broker_id == "bybit"
        assert info.display_name == "Bybit"

    def test_bybit_get_capabilities(self):
        """Should return Bybit capabilities (spot + futures)."""
        from app.brokers.adapters.bybit_adapter import BybitAdapter
        from app.brokers.models import BrokerCredentials

        creds = BrokerCredentials(
            broker_id="bybit",
            api_key="test-key",
            api_secret="test-secret",
            passphrase=None,
            testnet=False,
        )

        adapter = BybitAdapter(creds)
        caps = adapter.get_capabilities()
        assert caps.spot is True
        assert caps.futures is True


class TestRegistryMultiBroker:
    """Tests for the broker registry with OKX and Bybit."""

    def test_registry_includes_okx_and_bybit(self):
        """Registry should include OKX and Bybit."""
        from app.brokers.registry import _BROKER_IDS

        assert "okx" in _BROKER_IDS
        assert "bybit" in _BROKER_IDS
        assert "binance" in _BROKER_IDS

    def test_registry_uses_okx_adapter(self):
        """Registry should use OKXAdapter for okx."""
        from app.brokers.registry import _register_adapters, _ADAPTER_CLASSES
        from app.brokers.adapters.okx_adapter import OKXAdapter

        _register_adapters()
        assert _ADAPTER_CLASSES["okx"] is OKXAdapter

    def test_registry_uses_bybit_adapter(self):
        """Registry should use BybitAdapter for bybit."""
        from app.brokers.registry import _register_adapters, _ADAPTER_CLASSES
        from app.brokers.adapters.bybit_adapter import BybitAdapter

        _register_adapters()
        assert _ADAPTER_CLASSES["bybit"] is BybitAdapter

    def test_get_adapter_okx(self):
        """get_adapter should return OKXAdapter for okx."""
        from app.brokers.registry import get_adapter
        from app.brokers.adapters.okx_adapter import OKXAdapter
        from app.brokers.models import BrokerCredentials

        creds = BrokerCredentials(
            broker_id="okx",
            api_key="test-key",
            api_secret="test-secret",
            passphrase="test-pass",
            testnet=False,
        )
        adapter = get_adapter("okx", creds)
        assert isinstance(adapter, OKXAdapter)

    def test_get_adapter_bybit(self):
        """get_adapter should return BybitAdapter for bybit."""
        from app.brokers.registry import get_adapter
        from app.brokers.adapters.bybit_adapter import BybitAdapter
        from app.brokers.models import BrokerCredentials

        creds = BrokerCredentials(
            broker_id="bybit",
            api_key="test-key",
            api_secret="test-secret",
            passphrase=None,
            testnet=False,
        )
        adapter = get_adapter("bybit", creds)
        assert isinstance(adapter, BybitAdapter)

    def test_list_brokers_includes_all(self):
        """list_brokers should include Binance, OKX, Bybit, and others."""
        from app.brokers.registry import list_brokers

        brokers = list_brokers()
        broker_ids = [b.broker_id for b in brokers]
        assert "binance" in broker_ids
        assert "okx" in broker_ids
        assert "bybit" in broker_ids


