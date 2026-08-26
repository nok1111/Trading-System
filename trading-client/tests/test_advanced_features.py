"""Tests for DCA Bot service and auto-copy trading."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestDCABotService:
    """Tests for DCA Bot service."""

    def test_create_dca_bot(self):
        """Should create a DCA bot."""
        from app.services.dca_bot_service import create_dca_bot

        mock_db = MagicMock()
        mock_bot = MagicMock()
        mock_bot.id = 1
        mock_bot.name = "Test DCA"
        mock_bot.buy_amount_usd = 100
        mock_bot.interval_minutes = 1440
        mock_bot.is_active = True
        mock_bot.status = "running"
        mock_bot.buys_executed = 0
        mock_bot.total_invested = 0
        mock_bot.total_quantity = 0
        mock_bot.avg_entry_price = 0
        mock_bot.realized_pnl = 0
        mock_bot.last_buy_at = None
        mock_bot.created_at = None
        mock_bot.user_id = 1
        mock_bot.broker_id = "binance"
        mock_bot.symbol = "BTC/USDT"
        mock_bot.market_type = "spot"
        mock_bot.max_buys = 0

        with patch("app.services.dca_bot_service.SessionLocal", return_value=mock_db):
            with patch("app.services.dca_bot_service.DCABot", return_value=mock_bot):
                result = create_dca_bot(
                    user_id=1,
                    name="Test DCA",
                    broker_id="binance",
                    symbol="BTC/USDT",
                    investment_usd=100,
                    interval_hours=24,
                )

                assert result["name"] == "Test DCA"
                assert mock_db.add.called
                assert mock_db.commit.called

    def test_list_dca_bots(self):
        """Should list DCA bots for a user."""
        from app.services.dca_bot_service import list_dca_bots

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        with patch("app.services.dca_bot_service.SessionLocal", return_value=mock_db):
            result = list_dca_bots(user_id=1)
            assert result == []

    def test_stop_dca_bot(self):
        """Should stop a DCA bot."""
        from app.services.dca_bot_service import stop_dca_bot

        mock_db = MagicMock()
        mock_bot = MagicMock()
        mock_bot.id = 1
        mock_bot.user_id = 1

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_bot

        with patch("app.services.dca_bot_service.SessionLocal", return_value=mock_db):
            result = stop_dca_bot(user_id=1, bot_id=1)
            assert result["ok"] is True
            assert result["status"] == "stopped"
            assert mock_bot.is_active is False

    def test_stop_nonexistent_bot(self):
        """Should return error for nonexistent bot."""
        from app.services.dca_bot_service import stop_dca_bot

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        with patch("app.services.dca_bot_service.SessionLocal", return_value=mock_db):
            result = stop_dca_bot(user_id=1, bot_id=999)
            assert result["ok"] is False

    def test_delete_dca_bot(self):
        """Should delete a DCA bot."""
        from app.services.dca_bot_service import delete_dca_bot

        mock_db = MagicMock()
        mock_bot = MagicMock()
        mock_bot.id = 1
        mock_bot.user_id = 1

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_bot

        with patch("app.services.dca_bot_service.SessionLocal", return_value=mock_db):
            result = delete_dca_bot(user_id=1, bot_id=1)
            assert result["ok"] is True
            assert mock_db.delete.called


class TestAutoCopyService:
    """Tests for auto-copy trading service."""

    def test_get_auto_copy_stats_empty(self):
        """Should return zero stats when no copies exist."""
        from app.services.auto_copy import get_auto_copy_stats

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        with patch("app.services.auto_copy.SessionLocal", return_value=mock_db):
            result = get_auto_copy_stats(user_id=1)
            assert result["total_copies"] == 0
            assert result["win_rate"] == 0

    def test_process_new_signal_no_followers(self):
        """Should return empty list when no auto-copy followers."""
        from app.services.auto_copy import process_new_signal

        mock_signal = MagicMock()
        mock_signal.id = 1
        mock_signal.leader_id = 1

        with patch("app.services.auto_copy.get_auto_copy_followers", return_value=[]):
            result = process_new_signal(mock_signal)
            assert result == []
