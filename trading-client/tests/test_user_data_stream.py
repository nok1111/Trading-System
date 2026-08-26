"""Tests for the Binance user-data stream message parsing."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestUserDataStreamParsing:
    """Tests for message parsing in BinanceUserDataStream."""

    @pytest.fixture
    def stream(self):
        """Create a BinanceUserDataStream instance for testing."""
        from app.data.user_data_stream import BinanceUserDataStream

        return BinanceUserDataStream(
            api_key="test-key",
            api_secret="test-secret",
            testnet=True,
        )

    def test_parse_order_event(self, stream):
        """Test parsing an executionReport event."""
        raw_event = {
            "e": "executionReport",
            "E": 1234567890,
            "s": "BTCUSDT",
            "S": "BUY",
            "o": "LIMIT",
            "i": 123456,
            "c": "client-order-1",
            "X": "FILLED",
            "q": "0.10000000",
            "z": "0.10000000",
            "p": "50000.00000000",
            "Z": "49999.50000000",
            "n": "0.01000000",
            "N": "BNB",
            "T": 1234567890,
            "t": 789,
            "m": False,
        }

        result = stream._parse_order_event(raw_event)
        assert result["event_type"] == "order_update"
        assert result["order_id"] == 123456
        assert result["client_order_id"] == "client-order-1"
        assert result["symbol"] == "BTCUSDT"
        assert result["side"] == "BUY"
        assert result["order_type"] == "LIMIT"
        assert result["order_status"] == "FILLED"
        assert result["quantity"] == 0.1
        assert result["filled_quantity"] == 0.1
        assert result["price"] == 50000.0
        assert result["avg_fill_price"] == 49999.5
        assert result["commission"] == 0.01
        assert result["commission_asset"] == "BNB"
        assert result["is_maker"] is False

    def test_parse_balance_event(self, stream):
        """Test parsing an outboundAccountPosition event."""
        raw_event = {
            "e": "outboundAccountPosition",
            "E": 1234567890,
            "u": 1234567890,
            "B": [
                {"a": "BTC", "f": "0.50000000", "l": "0.00000000"},
                {"a": "USDT", "f": "10000.00000000", "l": "500.00000000"},
            ],
        }

        result = stream._parse_balance_event(raw_event)
        assert result["event_type"] == "balance_update"
        assert len(result["balances"]) == 2
        assert result["balances"][0]["asset"] == "BTC"
        assert result["balances"][0]["free"] == 0.5
        assert result["balances"][0]["locked"] == 0.0
        assert result["balances"][1]["asset"] == "USDT"
        assert result["balances"][1]["free"] == 10000.0
        assert result["balances"][1]["locked"] == 500.0

    def test_parse_account_update(self, stream):
        """Test parsing a futures ACCOUNT_UPDATE event."""
        raw_event = {
            "e": "ACCOUNT_UPDATE",
            "E": 1234567890,
            "a": {
                "P": [
                    {
                        "s": "BTCUSDT",
                        "pa": "0.500",
                        "ep": "50000.0",
                        "up": "100.0",
                        "mt": "cross",
                        "l": 10,
                    }
                ],
                "B": [
                    {
                        "a": "USDT",
                        "wb": "50000.0",
                        "cw": "5000.0",
                    }
                ],
            },
        }

        result = stream._parse_account_update(raw_event)
        assert result["event_type"] == "account_update"
        assert len(result["positions"]) == 1
        assert result["positions"][0]["symbol"] == "BTCUSDT"
        assert result["positions"][0]["position_amount"] == 0.5
        assert result["positions"][0]["entry_price"] == 50000.0
        assert result["positions"][0]["unrealized_pnl"] == 100.0
        assert result["positions"][0]["leverage"] == 10
        assert len(result["balances"]) == 1
        assert result["balances"][0]["asset"] == "USDT"
        assert result["balances"][0]["balance"] == 50000.0

    def test_handle_message_dispatches_to_callbacks(self, stream):
        """Test that _handle_message dispatches to the correct callback."""
        order_callback = MagicMock()
        balance_callback = MagicMock()
        position_callback = MagicMock()

        stream._on_order_update = order_callback
        stream._on_balance_update = balance_callback
        stream._on_position_update = position_callback

        # Order event
        order_msg = json.dumps({
            "e": "executionReport",
            "s": "BTCUSDT",
            "S": "BUY",
            "X": "FILLED",
            "q": "0.1",
            "z": "0.1",
            "i": 123,
        })
        stream._handle_message(order_msg)
        assert order_callback.call_count == 1
        assert balance_callback.call_count == 0
        assert position_callback.call_count == 0

        # Balance event
        balance_msg = json.dumps({
            "e": "outboundAccountPosition",
            "B": [{"a": "BTC", "f": "0.5", "l": "0"}],
        })
        stream._handle_message(balance_msg)
        assert order_callback.call_count == 1
        assert balance_callback.call_count == 1
        assert position_callback.call_count == 0

        # Position event
        position_msg = json.dumps({
            "e": "ACCOUNT_UPDATE",
            "a": {
                "P": [{"s": "BTCUSDT", "pa": "0.5", "ep": "50000", "up": "100"}],
                "B": [],
            },
        })
        stream._handle_message(position_msg)
        assert order_callback.call_count == 1
        assert balance_callback.call_count == 1
        assert position_callback.call_count == 1

    def test_handle_unknown_event(self, stream):
        """Test that unknown events are handled gracefully."""
        # Should not raise
        stream._handle_message(json.dumps({"e": "unknownEvent", "data": "test"}))

    def test_handle_invalid_json(self, stream):
        """Test that invalid JSON is handled gracefully."""
        # Should not raise
        stream._handle_message("not valid json")


class TestUserDataStreamManager:
    """Tests for the stream manager functions."""

    def test_get_user_data_stream_none(self):
        """Should return None when no stream exists for user."""
        from app.data.user_data_stream import get_user_data_stream, _streams

        _streams.clear()
        assert get_user_data_stream(user_id=999) is None

    def test_stop_user_data_stream_nonexistent(self):
        """Should not raise when stopping a non-existent stream."""
        from app.data.user_data_stream import stop_user_data_stream

        # Should not raise
        stop_user_data_stream(user_id=999)
