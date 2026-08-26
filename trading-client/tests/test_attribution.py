"""Tests for performance attribution service."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestPerformanceAttribution:
    """Tests for performance attribution."""

    def test_empty_attribution(self):
        """Should return empty attribution when no portfolio."""
        from app.services.performance_attribution import get_performance_attribution

        with patch("app.services.portfolio_aggregator.get_unified_portfolio_overview", return_value={"total_usd": 0}):
            with patch("app.services.portfolio_aggregator.get_unified_positions", return_value={"positions": []}):
                result = get_performance_attribution(user_id=1)

                assert result["total_return_pct"] == 0
                assert result["by_asset"] == []
                assert result["by_broker"] == []
                assert result["summary"]["total_positions"] == 0

    def test_attribution_with_positions(self):
        """Should calculate attribution with positions."""
        from app.services.performance_attribution import get_performance_attribution

        mock_overview = {"total_usd": 10000.0}
        mock_positions = {
            "positions": [
                {
                    "symbol": "BTC/USDT",
                    "broker_id": "binance",
                    "broker_name": "Binance",
                    "unrealized_pnl": 500,
                    "current_value": 5000,
                    "entry_price": 40000,
                    "current_price": 45000,
                    "quantity": 0.1,
                },
                {
                    "symbol": "ETH/USDT",
                    "broker_id": "bybit",
                    "broker_name": "Bybit",
                    "unrealized_pnl": -200,
                    "current_value": 3000,
                    "entry_price": 2500,
                    "current_price": 2000,
                    "quantity": 1.5,
                },
            ]
        }

        with patch("app.services.portfolio_aggregator.get_unified_portfolio_overview", return_value=mock_overview):
            with patch("app.services.portfolio_aggregator.get_unified_positions", return_value=mock_positions):
                with patch("app.services.performance_attribution._attribute_by_strategy", return_value=[]):
                    result = get_performance_attribution(user_id=1)

                    assert result["total_return_pct"] == 3.0  # (500-200)/10000*100
                    assert len(result["by_asset"]) == 2
                    assert len(result["by_broker"]) == 2
                    assert result["summary"]["total_positions"] == 2
                    assert result["summary"]["winning_positions"] == 1
                    assert result["summary"]["losing_positions"] == 1

    def test_attribution_by_asset(self):
        """Should attribute returns by asset correctly."""
        from app.services.performance_attribution import _attribute_by_asset

        positions = [
            {"symbol": "BTC/USDT", "unrealized_pnl": 500, "current_value": 5000, "entry_price": 40000, "quantity": 0.1},
            {"symbol": "ETH/USDT", "unrealized_pnl": -200, "current_value": 3000, "entry_price": 2500, "quantity": 1.5},
        ]

        result = _attribute_by_asset(positions, total_usd=10000)

        assert len(result) == 2
        # BTC should have positive contribution
        btc = next(r for r in result if r["symbol"] == "BTC/USDT")
        assert btc["contribution_pct"] == 5.0  # 500/10000*100
        assert btc["pnl_usd"] == 500

    def test_benchmark_calculation(self):
        """Should calculate equal-weight benchmark."""
        from app.services.performance_attribution import _calculate_benchmark

        positions = [
            {"entry_price": 100, "current_price": 110},  # +10%
            {"entry_price": 200, "current_price": 180},  # -10%
        ]

        benchmark = _calculate_benchmark(positions)
        assert benchmark == 0.0  # average of +10% and -10%

    def test_attribution_summary(self):
        """Should identify best and worst performers."""
        from app.services.performance_attribution import get_performance_attribution

        mock_overview = {"total_usd": 10000.0}
        mock_positions = {
            "positions": [
                {"symbol": "BTC/USDT", "broker_name": "Binance", "unrealized_pnl": 500, "current_value": 5000, "entry_price": 40000, "current_price": 45000, "quantity": 0.1},
                {"symbol": "ETH/USDT", "broker_name": "Bybit", "unrealized_pnl": -200, "current_value": 3000, "entry_price": 2500, "current_price": 2000, "quantity": 1.5},
            ]
        }

        with patch("app.services.portfolio_aggregator.get_unified_portfolio_overview", return_value=mock_overview):
            with patch("app.services.portfolio_aggregator.get_unified_positions", return_value=mock_positions):
                with patch("app.services.performance_attribution._attribute_by_strategy", return_value=[]):
                    result = get_performance_attribution(user_id=1)

                    # Best performer should be BTC (positive contribution)
                    assert result["summary"]["best_performer"]["symbol"] == "BTC/USDT"
                    # Worst should be ETH
                    assert result["summary"]["worst_performer"]["symbol"] == "ETH/USDT"
