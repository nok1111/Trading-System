"""Unit tests for scalp engine scoring, AI JSON parse and heartbeat."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.scalp_engine import atr_from_ohlc, heartbeat_expired, parse_ai_pick, score_symbol, _entry_signal


class TestAtrAndScore:
    def test_atr_insufficient_bars(self):
        assert atr_from_ohlc([1, 2], [1, 2], [1, 2], 14) == 0.0

    def test_atr_positive_on_range(self):
        highs = [10 + i * 0.1 for i in range(30)]
        lows = [9 + i * 0.1 for i in range(30)]
        closes = [9.5 + i * 0.1 for i in range(30)]
        atr = atr_from_ohlc(highs, lows, closes, 14)
        assert atr > 0

    def test_score_zero_on_dead_market(self):
        assert score_symbol(0, 1_000_000, 0.5) == 0.0
        assert score_symbol(1.2, 0, 0.5) == 0.0

    def test_score_higher_with_more_vol_and_move(self):
        a = score_symbol(1.0, 1_000_000, 0.2, 1.0)
        b = score_symbol(1.5, 5_000_000, 0.8, 2.0)
        assert b > a


class TestParseAiPick:
    def test_clean_json(self):
        r = parse_ai_pick('{"pick":"SOLUSDT","side":"long","conf":0.7}')
        assert r is not None
        assert r["pick"] == "SOLUSDT"
        assert r["side"] == "long"
        assert r["conf"] == 0.7

    def test_wrapped_text(self):
        r = parse_ai_pick('Sure.\n{"pick":"DOGEUSDT","side":"short","conf":0.4}\n')
        assert r["pick"] == "DOGEUSDT"
        assert r["side"] == "short"

    def test_invalid_side_becomes_skip(self):
        r = parse_ai_pick('{"pick":"BTCUSDT","side":"maybe","conf":1}')
        assert r["side"] == "skip"

    def test_garbage_returns_none(self):
        assert parse_ai_pick("no json here") is None
        assert parse_ai_pick("") is None


class TestEntrySignal:
    def test_rejects_low_volume(self):
        ok, reason = _entry_signal({"vol_ratio": 0.8, "symbol": "BTCUSDT"}, "long")
        assert ok is False
        assert "volumen" in reason


class TestHeartbeat:
    def test_none_is_expired(self):
        assert heartbeat_expired(None) is True

    def test_fresh_heartbeat(self):
        now = datetime.now(tz=UTC)
        assert heartbeat_expired(now, now, timeout_sec=20) is False

    def test_stale_heartbeat(self):
        now = datetime.now(tz=UTC)
        stale = now - timedelta(seconds=21)
        assert heartbeat_expired(stale, now, timeout_sec=20) is True
