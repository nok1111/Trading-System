"""Tests for the portfolio aggregator service."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestPortfolioAggregator:
    """Unit tests for the portfolio aggregator."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Clear cache before each test."""
        from app.services import portfolio_aggregator as agg
        agg._cache.clear()
        yield
        agg._cache.clear()

    def test_get_unified_balances_no_brokers(self):
        """Should return empty portfolio when no brokers connected."""
        from app.services import portfolio_aggregator as agg

        with patch.object(agg, "_get_connected_brokers", return_value=[]):
            result = agg.get_unified_balances(user_id=999)
            assert result["total_usd"] == 0
            assert result["by_broker"] == []
            assert result["by_asset"] == []
            assert result["broker_count"] == 0

    def test_get_unified_balances_with_mock_broker(self):
        """Should aggregate balances from a mock broker."""
        from app.services import portfolio_aggregator as agg

        # Mock broker account
        mock_account = MagicMock()
        mock_account.broker_id = "binance"
        mock_account.display_name = "Binance"
        mock_account.environment = "live"
        mock_account.api_key_enc = "encrypted"
        mock_account.api_secret_enc = "encrypted"
        mock_account.passphrase_enc = None

        # Mock adapter
        mock_adapter = MagicMock()
        mock_balance_btc = MagicMock()
        mock_balance_btc.asset = "BTC"
        mock_balance_btc.free = 0.5
        mock_balance_btc.locked = 0.0

        mock_balance_usdt = MagicMock()
        mock_balance_usdt.asset = "USDT"
        mock_balance_usdt.free = 10000.0
        mock_balance_usdt.locked = 0.0

        mock_adapter.get_account_balances.return_value = (mock_balance_btc, mock_balance_usdt)

        # Mock ticker for BTC (returns price only for BTC pairs, not USDT)
        mock_ticker = MagicMock()
        mock_ticker.price = 50000.0

        def mock_get_ticker(symbol):
            if symbol.startswith("BTC/"):
                return mock_ticker
            raise Exception(f"No ticker for {symbol}")

        mock_adapter.get_ticker.side_effect = mock_get_ticker

        with patch.object(agg, "_get_connected_brokers", return_value=[mock_account]):
            with patch.object(agg, "_get_adapter_for_account", return_value=mock_adapter):
                result = agg.get_unified_balances(user_id=1)

                assert result["broker_count"] == 1
                assert result["total_usd"] == 35000.0  # 0.5 BTC * 50000 + 10000 USDT
                assert len(result["by_broker"]) == 1
                assert result["by_broker"][0]["broker_id"] == "binance"
                assert result["by_broker"][0]["total_usd"] == 35000.0

                # By asset: BTC should be 25000, USDT should be 10000
                assets = {a["asset"]: a for a in result["by_asset"]}
                assert "BTC" in assets
                assert "USDT" in assets
                assert assets["BTC"]["usd_value"] == 25000.0
                assert assets["USDT"]["usd_value"] == 10000.0

    def test_get_unified_balances_broker_error(self):
        """Should handle broker errors gracefully."""
        from app.services import portfolio_aggregator as agg

        mock_account = MagicMock()
        mock_account.broker_id = "binance"
        mock_account.display_name = "Binance"
        mock_account.environment = "live"
        mock_account.api_key_enc = "encrypted"
        mock_account.api_secret_enc = "encrypted"
        mock_account.passphrase_enc = None

        mock_adapter = MagicMock()
        mock_adapter.get_account_balances.side_effect = Exception("Connection refused")

        with patch.object(agg, "_get_connected_brokers", return_value=[mock_account]):
            with patch.object(agg, "_get_adapter_for_account", return_value=mock_adapter):
                result = agg.get_unified_balances(user_id=1)

                assert result["total_usd"] == 0
                assert len(result["errors"]) == 1
                assert result["errors"][0]["broker_id"] == "binance"
                assert "Connection refused" in result["errors"][0]["error"]

    def test_get_unified_positions_no_brokers(self):
        """Should return empty positions when no brokers connected."""
        from app.services import portfolio_aggregator as agg

        with patch.object(agg, "_get_connected_brokers", return_value=[]):
            result = agg.get_unified_positions(user_id=999)
            assert result["positions"] == []
            assert result["total_unrealized_pnl"] == 0
            assert result["position_count"] == 0

    def test_cache_works(self):
        """Should cache results and return cached data on second call."""
        from app.services import portfolio_aggregator as agg

        with patch.object(agg, "_get_connected_brokers", return_value=[]):
            # First call
            result1 = agg.get_unified_balances(user_id=42)
            assert result1["total_usd"] == 0

            # Second call should return cached data (no broker query)
            with patch.object(agg, "_get_connected_brokers", side_effect=Exception("Should not be called")):
                result2 = agg.get_unified_balances(user_id=42)
                assert result2["total_usd"] == 0

    def test_invalidate_cache(self):
        """Should invalidate cache when requested."""
        from app.services import portfolio_aggregator as agg

        with patch.object(agg, "_get_connected_brokers", return_value=[]):
            agg.get_unified_balances(user_id=42)
            assert 42 in agg._cache

            agg.invalidate_cache(42)
            assert 42 not in agg._cache

    def test_net_exposure_empty(self):
        """Should return empty exposure when no positions."""
        from app.services import portfolio_aggregator as agg

        with patch.object(agg, "_get_connected_brokers", return_value=[]):
            result = agg.get_net_exposure(user_id=999)
            assert result["by_asset"] == []
            assert result["total_long_usd"] == 0
            assert result["total_short_usd"] == 0

    def test_concentration_analysis_empty(self):
        """Should return empty concentration when no balances."""
        from app.services import portfolio_aggregator as agg

        with patch.object(agg, "_get_connected_brokers", return_value=[]):
            result = agg.get_concentration_analysis(user_id=999)
            assert result["total_usd"] == 0
            assert result["by_asset"] == []
            assert result["by_broker"] == []
            assert result["warnings"] == []
