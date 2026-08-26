"""Tests for the Copilot service."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestCopilotSuggest:
    """Tests for copilot_suggest."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Clear cache before each test."""
        from app.services import portfolio_aggregator as agg
        agg._cache.clear()
        yield
        agg._cache.clear()

    def test_suggest_no_brokers(self):
        """Should return minimal suggestions when no brokers connected."""
        from app.ai.copilot import copilot_suggest

        with patch("app.services.portfolio_aggregator._get_connected_brokers", return_value=[]):
            result = copilot_suggest(user_id=999)

            assert "suggestions" in result
            assert "count" in result
            assert "generated_at" in result
            assert isinstance(result["suggestions"], list)

    def test_suggest_with_concentration_warning(self):
        """Should generate concentration warning suggestions."""
        from app.ai.copilot import copilot_suggest

        # Mock the portfolio aggregator functions
        mock_overview = {
            "total_usd": 10000.0,
            "position_count": 0,
            "broker_count": 1,
            "balances": {
                "total_usd": 10000.0,
                "by_broker": [],
                "by_asset": [],
                "errors": [],
                "broker_count": 1,
            },
            "positions": {"positions": [], "total_unrealized_pnl": 0, "position_count": 0, "errors": []},
            "exposure": {"by_asset": [], "total_long_usd": 0, "total_short_usd": 0, "net_usd": 0},
            "concentration": {
                "total_usd": 10000.0,
                "by_asset": [],
                "by_broker": [],
                "by_venue": {"spot": 0, "futures": 0, "stablecoins": 10000.0},
                "warnings": [
                    {"type": "asset_concentration", "level": "high", "message": "BTC representa 50% del portfolio"},
                ],
            },
        }

        with patch("app.services.portfolio_aggregator.get_unified_portfolio_overview", return_value=mock_overview):
            with patch("app.services.portfolio_aggregator.get_concentration_analysis", return_value=mock_overview["concentration"]):
                result = copilot_suggest(user_id=1)

                assert result["count"] > 0
                # Should have the concentration warning
                risk_warnings = [s for s in result["suggestions"] if s["type"] == "risk_warning"]
                assert len(risk_warnings) > 0

    def test_suggest_high_loss_position(self):
        """Should generate close_position suggestion for high-loss positions."""
        from app.ai.copilot import copilot_suggest

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
                        "current_price": 48000,
                        "unrealized_pnl": -1200,
                        "unrealized_pnl_pct": -20,
                        "leverage": 1,
                        "liquidation_price": None,
                        "market_type": "spot",
                    }
                ],
                "total_unrealized_pnl": -1200,
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
                result = copilot_suggest(user_id=1)

                close_suggestions = [s for s in result["suggestions"] if s["type"] == "close_position"]
                assert len(close_suggestions) > 0
                assert close_suggestions[0]["priority"] == "medium"  # -20% is medium (< -20 is high)

    def test_suggest_high_gain_position(self):
        """Should generate adjust_sl_tp suggestion for high-gain positions."""
        from app.ai.copilot import copilot_suggest

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
                        "current_price": 2600,
                        "unrealized_pnl": 1200,
                        "unrealized_pnl_pct": 30,
                        "leverage": 1,
                        "liquidation_price": None,
                        "market_type": "spot",
                    }
                ],
                "total_unrealized_pnl": 1200,
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
                result = copilot_suggest(user_id=1)

                gain_suggestions = [s for s in result["suggestions"] if s["type"] == "adjust_sl_tp"]
                assert len(gain_suggestions) > 0

    def test_suggest_stablecoin_excess(self):
        """Should suggest deploying capital when stablecoin-heavy."""
        from app.ai.copilot import copilot_suggest

        mock_overview = {
            "total_usd": 10000.0,
            "position_count": 0,
            "broker_count": 1,
            "balances": {
                "total_usd": 10000.0,
                "by_broker": [],
                "by_asset": [],
                "errors": [],
                "broker_count": 1,
            },
            "positions": {"positions": [], "total_unrealized_pnl": 0, "position_count": 0, "errors": []},
            "exposure": {"by_asset": [], "total_long_usd": 0, "total_short_usd": 0, "net_usd": 0},
            "concentration": {
                "total_usd": 10000.0,
                "by_asset": [],
                "by_broker": [],
                "by_venue": {"spot": 0, "futures": 0, "stablecoins": 8000.0},
                "warnings": [],
            },
        }

        with patch("app.services.portfolio_aggregator.get_unified_portfolio_overview", return_value=mock_overview):
            with patch("app.services.portfolio_aggregator.get_concentration_analysis", return_value=mock_overview["concentration"]):
                result = copilot_suggest(user_id=1)

                opp_suggestions = [s for s in result["suggestions"] if s["type"] == "opportunity"]
                assert len(opp_suggestions) > 0

    def test_suggest_sorted_by_priority(self):
        """Suggestions should be sorted by priority (high first)."""
        from app.ai.copilot import copilot_suggest

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
                        "symbol": "BTC/USDT",
                        "broker_id": "binance",
                        "broker_name": "Binance",
                        "side": "long",
                        "quantity": 0.1,
                        "entry_price": 60000,
                        "current_price": 48000,
                        "unrealized_pnl": -1200,
                        "unrealized_pnl_pct": -20,
                        "leverage": 1,
                        "liquidation_price": None,
                        "market_type": "spot",
                    }
                ],
                "total_unrealized_pnl": -1200,
                "position_count": 1,
                "errors": [],
            },
            "exposure": {"by_asset": [], "total_long_usd": 0, "total_short_usd": 0, "net_usd": 0},
            "concentration": {
                "total_usd": 10000.0,
                "by_asset": [],
                "by_broker": [],
                "by_venue": {"spot": 10000, "futures": 0, "stablecoins": 0},
                "warnings": [
                    {"type": "asset_concentration", "level": "medium", "message": "Concentración media"},
                ],
            },
        }

        with patch("app.services.portfolio_aggregator.get_unified_portfolio_overview", return_value=mock_overview):
            with patch("app.services.portfolio_aggregator.get_concentration_analysis", return_value=mock_overview["concentration"]):
                result = copilot_suggest(user_id=1)

                priorities = [s["priority"] for s in result["suggestions"]]
                # high should come before medium
                if "high" in priorities and "medium" in priorities:
                    assert priorities.index("high") < priorities.index("medium")


class TestCopilotQuickAction:
    """Tests for copilot_quick_action."""

    def test_unknown_action(self):
        """Should return error for unknown action."""
        from app.ai.copilot import copilot_quick_action

        result = copilot_quick_action(user_id=1, action="unknown")
        assert "error" in result

    def test_valid_action_delegates_to_alvora(self):
        """Should delegate to alvora_chat for valid actions."""
        from app.ai.copilot import copilot_quick_action

        with patch("app.ai.copilot.alvora_chat", return_value={"reply": "test", "actions": []}) as mock:
            result = copilot_quick_action(user_id=1, action="rebalance")
            assert result == {"reply": "test", "actions": []}
            assert mock.call_count == 1
            # Check the prompt was passed
            args = mock.call_args
            assert "rebalance" in args[0][1].lower() or "rebalanceo" in args[0][1].lower()
