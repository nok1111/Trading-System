"""Tests for the Smart Alerts service."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestSmartAlerts:
    """Tests for generate_smart_alerts."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Clear cache before each test."""
        from app.services import portfolio_aggregator as agg
        agg._cache.clear()
        yield
        agg._cache.clear()

    def test_alerts_no_brokers(self):
        """Should return minimal alerts when no brokers connected."""
        from app.services.smart_alerts import generate_smart_alerts

        with patch("app.services.portfolio_aggregator._get_connected_brokers", return_value=[]):
            with patch("app.services.smart_alerts._check_stop_loss_coverage", return_value=[]):
                with patch("app.services.smart_alerts._check_market_regime", return_value=[]):
                    result = generate_smart_alerts(user_id=999)

                    assert "alerts" in result
                    assert "count" in result
                    assert "high_urgency_count" in result
                    assert "generated_at" in result
                    assert isinstance(result["alerts"], list)

    def test_alerts_high_loss_position(self):
        """Should generate high-loss alert with high urgency."""
        from app.services.smart_alerts import generate_smart_alerts

        mock_overview = {
            "total_usd": 5000.0,
            "position_count": 1,
            "broker_count": 1,
            "balances": {
                "total_usd": 5000.0,
                "by_broker": [],
                "by_asset": [],
                "errors": [],
                "broker_count": 1,
            },
            "positions": {
                "positions": [
                    {
                        "symbol": "BTC/USDT",
                        "broker_id": "binance",
                        "broker_name": "Binance",
                        "side": "long",
                        "quantity": 0.1,
                        "entry_price": 60000,
                        "current_price": 45000,
                        "unrealized_pnl": -1500,
                        "unrealized_pnl_pct": -25,
                        "leverage": 1,
                        "liquidation_price": None,
                        "market_type": "spot",
                    }
                ],
                "total_unrealized_pnl": -1500,
                "position_count": 1,
                "errors": [],
            },
            "exposure": {"by_asset": [], "total_long_usd": 0, "total_short_usd": 0, "net_usd": 0},
            "concentration": {
                "total_usd": 5000.0,
                "by_asset": [],
                "by_broker": [],
                "by_venue": {"spot": 5000, "futures": 0, "stablecoins": 0},
                "warnings": [],
            },
        }

        with patch("app.services.portfolio_aggregator.get_unified_portfolio_overview", return_value=mock_overview):
            with patch("app.services.portfolio_aggregator.get_concentration_analysis", return_value=mock_overview["concentration"]):
                with patch("app.services.portfolio_aggregator.get_unified_positions", return_value=mock_overview["positions"]):
                    with patch("app.services.smart_alerts._check_stop_loss_coverage", return_value=[]):
                        with patch("app.services.smart_alerts._check_market_regime", return_value=[]):
                            result = generate_smart_alerts(user_id=1)

                            high_loss_alerts = [a for a in result["alerts"] if a["type"] == "high_loss"]
                            assert len(high_loss_alerts) > 0
                            assert high_loss_alerts[0]["urgency"] >= 60  # -25% should be high urgency

    def test_alerts_high_gain_position(self):
        """Should generate high-gain alert."""
        from app.services.smart_alerts import generate_smart_alerts

        mock_overview = {
            "total_usd": 10000.0,
            "position_count": 1,
            "broker_count": 1,
            "balances": {
                "total_usd": 10000.0,
                "by_broker": [],
                "by_asset": [],
                "errors": [],
                "broker_count": 1,
            },
            "positions": {
                "positions": [
                    {
                        "symbol": "ETH/USDT",
                        "broker_id": "binance",
                        "broker_name": "Binance",
                        "side": "long",
                        "quantity": 2,
                        "entry_price": 2000,
                        "current_price": 2800,
                        "unrealized_pnl": 1600,
                        "unrealized_pnl_pct": 40,
                        "leverage": 1,
                        "liquidation_price": None,
                        "market_type": "spot",
                    }
                ],
                "total_unrealized_pnl": 1600,
                "position_count": 1,
                "errors": [],
            },
            "exposure": {"by_asset": [], "total_long_usd": 0, "total_short_usd": 0, "net_usd": 0},
            "concentration": {
                "total_usd": 10000.0,
                "by_asset": [],
                "by_broker": [],
                "by_venue": {"spot": 10000, "futures": 0, "stablecoins": 0},
                "warnings": [],
            },
        }

        with patch("app.services.portfolio_aggregator.get_unified_portfolio_overview", return_value=mock_overview):
            with patch("app.services.portfolio_aggregator.get_concentration_analysis", return_value=mock_overview["concentration"]):
                with patch("app.services.portfolio_aggregator.get_unified_positions", return_value=mock_overview["positions"]):
                    with patch("app.services.smart_alerts._check_stop_loss_coverage", return_value=[]):
                        with patch("app.services.smart_alerts._check_market_regime", return_value=[]):
                            result = generate_smart_alerts(user_id=1)

                            gain_alerts = [a for a in result["alerts"] if a["type"] == "high_gain"]
                            assert len(gain_alerts) > 0

    def test_alerts_broker_error(self):
        """Should generate broker_error alert when broker fails."""
        from app.services.smart_alerts import generate_smart_alerts

        mock_overview = {
            "total_usd": 0,
            "position_count": 0,
            "broker_count": 1,
            "balances": {
                "total_usd": 0,
                "by_broker": [],
                "by_asset": [],
                "errors": [{"broker_id": "binance", "error": "Connection refused"}],
                "broker_count": 1,
            },
            "positions": {"positions": [], "total_unrealized_pnl": 0, "position_count": 0, "errors": []},
            "exposure": {"by_asset": [], "total_long_usd": 0, "total_short_usd": 0, "net_usd": 0},
            "concentration": {
                "total_usd": 0,
                "by_asset": [],
                "by_broker": [],
                "by_venue": {"spot": 0, "futures": 0, "stablecoins": 0},
                "warnings": [],
            },
        }

        with patch("app.services.portfolio_aggregator.get_unified_portfolio_overview", return_value=mock_overview):
            with patch("app.services.portfolio_aggregator.get_concentration_analysis", return_value=mock_overview["concentration"]):
                with patch("app.services.portfolio_aggregator.get_unified_positions", return_value=mock_overview["positions"]):
                    with patch("app.services.smart_alerts._check_stop_loss_coverage", return_value=[]):
                        with patch("app.services.smart_alerts._check_market_regime", return_value=[]):
                            result = generate_smart_alerts(user_id=1)

                            error_alerts = [a for a in result["alerts"] if a["type"] == "broker_error"]
                            assert len(error_alerts) > 0
                            assert "binance" in error_alerts[0]["title"]

    def test_alerts_sorted_by_urgency(self):
        """Alerts should be sorted by urgency descending."""
        from app.services.smart_alerts import generate_smart_alerts

        mock_overview = {
            "total_usd": 10000.0,
            "position_count": 2,
            "broker_count": 1,
            "balances": {
                "total_usd": 10000.0,
                "by_broker": [],
                "by_asset": [],
                "errors": [],
                "broker_count": 1,
            },
            "positions": {
                "positions": [
                    {
                        "symbol": "BTC/USDT",
                        "broker_id": "binance",
                        "broker_name": "Binance",
                        "side": "long",
                        "quantity": 0.1,
                        "entry_price": 60000,
                        "current_price": 45000,
                        "unrealized_pnl": -1500,
                        "unrealized_pnl_pct": -25,
                        "leverage": 1,
                        "liquidation_price": None,
                        "market_type": "spot",
                    },
                    {
                        "symbol": "ETH/USDT",
                        "broker_id": "binance",
                        "broker_name": "Binance",
                        "side": "long",
                        "quantity": 1,
                        "entry_price": 2000,
                        "current_price": 2100,
                        "unrealized_pnl": 100,
                        "unrealized_pnl_pct": 5,
                        "leverage": 1,
                        "liquidation_price": None,
                        "market_type": "spot",
                    },
                ],
                "total_unrealized_pnl": -1400,
                "position_count": 2,
                "errors": [],
            },
            "exposure": {"by_asset": [], "total_long_usd": 0, "total_short_usd": 0, "net_usd": 0},
            "concentration": {
                "total_usd": 10000.0,
                "by_asset": [],
                "by_broker": [],
                "by_venue": {"spot": 10000, "futures": 0, "stablecoins": 0},
                "warnings": [],
            },
        }

        with patch("app.services.portfolio_aggregator.get_unified_portfolio_overview", return_value=mock_overview):
            with patch("app.services.portfolio_aggregator.get_concentration_analysis", return_value=mock_overview["concentration"]):
                with patch("app.services.portfolio_aggregator.get_unified_positions", return_value=mock_overview["positions"]):
                    with patch("app.services.smart_alerts._check_stop_loss_coverage", return_value=[]):
                        with patch("app.services.smart_alerts._check_market_regime", return_value=[]):
                            result = generate_smart_alerts(user_id=1)

                            if len(result["alerts"]) > 1:
                                urgencies = [a["urgency"] for a in result["alerts"]]
                                assert urgencies == sorted(urgencies, reverse=True)

    def test_dismiss_alert(self):
        """Should return ok when dismissing an alert."""
        from app.services.smart_alerts import dismiss_alert

        result = dismiss_alert(user_id=1, alert_id="test-alert-1")
        assert result["ok"] is True
        assert result["alert_id"] == "test-alert-1"
        assert "dismissed_at" in result
