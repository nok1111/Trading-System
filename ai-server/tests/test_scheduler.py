"""Tests for Event-Driven Scheduler — Fase E."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from app.services.market_data import MarketDataEngine
from app.services.scheduler import (
    EVENT_AGENT_MAP,
    AgentExecutionResult,
    EventScheduler,
    EventType,
    SchedulerEvent,
)


@pytest.fixture
def engine_with_data():
    """MarketDataEngine with mock data provider."""
    def _make_candles(n=100, base_price=50000.0, trend=0.0):
        candles = []
        price = base_price
        base_ts = time.time() - n * 3600
        for i in range(n):
            candles.append({
                "open": price, "high": price + 100,
                "low": price - 80, "close": price + trend,
                "volume": 1000 + i * 10,
                "timestamp": base_ts + i * 3600,
            })
            price = price + trend
        return candles

    provider = MagicMock()
    provider.get_candles = MagicMock(return_value=_make_candles(100, trend=5))
    provider.get_order_book = MagicMock(return_value={
        "bids": [[49995, 10], [49990, 5]],
        "asks": [[50005, 10], [50010, 5]],
    })
    return MarketDataEngine(data_provider=provider)


@pytest.fixture
def scheduler(engine_with_data):
    return EventScheduler(
        market_data_engine=engine_with_data,
        symbols=["BTCUSDT"],
    )


class TestEventType:
    def test_event_types_exist(self):
        assert EventType.SUPPORT_BREAK
        assert EventType.NEWS_CRITICAL
        assert EventType.SCHEDULED

    def test_event_agent_map_has_all_types(self):
        for et in EventType:
            assert et in EVENT_AGENT_MAP
            assert len(EVENT_AGENT_MAP[et]) > 0

    def test_all_event_mappings_include_consensus(self):
        for et, agents in EVENT_AGENT_MAP.items():
            assert "consensus_agent" in agents, f"{et} missing consensus_agent"


class TestSchedulerEvent:
    def test_event_creation(self):
        event = SchedulerEvent(
            event_type=EventType.SUPPORT_BREAK,
            asset="BTCUSDT",
            data={"price": 49000, "broken_level": 50000},
        )
        assert event.event_type == EventType.SUPPORT_BREAK
        assert event.asset == "BTCUSDT"
        assert event.timestamp is not None

    def test_event_default_data(self):
        event = SchedulerEvent(
            event_type=EventType.SCHEDULED,
            asset="ETHUSDT",
        )
        assert event.data == {}


class TestSchedulerLifecycle:
    def test_start_when_disabled(self, scheduler):
        with patch.object(scheduler, "_run_loop"):
            # SCHEDULER_ENABLED is False by default
            result = scheduler.start()
            assert result is False
            assert not scheduler.is_running

    def test_start_when_enabled(self, scheduler):
        with patch("app.services.scheduler.settings") as mock_settings:
            mock_settings.SCHEDULER_ENABLED = True
            mock_settings.SCHEDULER_INTERVAL_SECONDS = 1
            with patch.object(scheduler, "_run_loop"):
                result = scheduler.start()
                assert result is True
                assert scheduler.is_running
                scheduler.stop()

    def test_stop_when_not_running(self, scheduler):
        result = scheduler.stop()
        assert result is False

    def test_status(self, scheduler):
        status = scheduler.status()
        assert "running" in status
        assert "symbols" in status
        assert "BTCUSDT" in status["symbols"]
        assert "interval_seconds" in status


class TestShouldRunAgent:
    def test_first_run_always_allowed(self, scheduler):
        assert scheduler.should_run_agent("technical_analyst") is True

    def test_within_interval_not_allowed(self, scheduler):
        scheduler._last_run["technical_analyst"] = time.time()
        assert scheduler.should_run_agent("technical_analyst") is False

    def test_after_interval_allowed(self, scheduler):
        scheduler._last_run["technical_analyst"] = time.time() - 16 * 60  # 16 min ago
        assert scheduler.should_run_agent("technical_analyst") is True

    def test_unknown_agent(self, scheduler):
        assert scheduler.should_run_agent("nonexistent") is False


class TestDetectEvents:
    def test_no_events_on_first_run(self, scheduler):
        events = scheduler.detect_events("BTCUSDT")
        # First run has no previous data, should not detect support/resistance breaks
        # But may detect anomalies from indicators
        break_events = [e for e in events if e.event_type in (EventType.SUPPORT_BREAK, EventType.RESISTANCE_BREAK)]
        assert len(break_events) == 0

    def test_support_break_detected(self, scheduler):
        # First run to establish baseline
        scheduler.detect_events("BTCUSDT")
        # Manually set previous indicators with higher support
        scheduler._last_indicators["BTCUSDT"] = {
            "trend": "bullish",
            "rsi": 55.0,
            "volatility": 0.02,
            "volume_relative": 1.0,
            "support_levels": [60000.0],  # High support that will be "broken"
            "resistance_levels": [65000.0],
        }
        # Current price (ema_20) will be ~50000 from mock data, below 60000
        events = scheduler.detect_events("BTCUSDT")
        support_breaks = [e for e in events if e.event_type == EventType.SUPPORT_BREAK]
        assert len(support_breaks) > 0

    def test_resistance_break_detected(self, scheduler):
        scheduler.detect_events("BTCUSDT")
        scheduler._last_indicators["BTCUSDT"] = {
            "trend": "bearish",
            "rsi": 45.0,
            "volatility": 0.02,
            "volume_relative": 1.0,
            "support_levels": [10000.0],
            "resistance_levels": [1000.0],  # Very low resistance that will be "broken"
        }
        events = scheduler.detect_events("BTCUSDT")
        resistance_breaks = [e for e in events if e.event_type == EventType.RESISTANCE_BREAK]
        assert len(resistance_breaks) > 0


class TestProcessEvent:
    def test_process_manual_event(self, scheduler):
        event = SchedulerEvent(
            event_type=EventType.MANUAL,
            asset="BTCUSDT",
        )
        # Mock the LLM call to avoid real API calls
        with patch("app.services.consensus._call_llm") as mock_llm:
            mock_llm.return_value = (None, 0)
            results = scheduler.process_event(event)
        # All agents should be attempted (even if LLM fails)
        assert len(results) > 0
        # Results should include agent_ids
        agent_ids = [r.agent_id for r in results]
        assert "consensus_agent" in agent_ids

    def test_process_support_break_event(self, scheduler):
        event = SchedulerEvent(
            event_type=EventType.SUPPORT_BREAK,
            asset="BTCUSDT",
            data={"price": 49000, "broken_level": 50000},
        )
        with patch("app.services.consensus._call_llm") as mock_llm:
            mock_llm.return_value = (None, 0)
            results = scheduler.process_event(event)
        agent_ids = [r.agent_id for r in results]
        assert "technical_analyst" in agent_ids
        assert "crash_detector" in agent_ids
        assert "consensus_agent" in agent_ids

    def test_process_news_event(self, scheduler):
        event = SchedulerEvent(
            event_type=EventType.NEWS_CRITICAL,
            asset="BTCUSDT",
            data={"headline": "New regulation", "severity": "high"},
        )
        with patch("app.services.consensus._call_llm") as mock_llm:
            mock_llm.return_value = (None, 0)
            results = scheduler.process_event(event)
        agent_ids = [r.agent_id for r in results]
        assert "news_analyst" in agent_ids
        assert "macro_analyst" in agent_ids

    def test_process_updates_last_run(self, scheduler):
        event = SchedulerEvent(
            event_type=EventType.MANUAL,
            asset="BTCUSDT",
        )
        with patch("app.services.consensus._call_llm") as mock_llm:
            mock_llm.return_value = (None, 0)
            scheduler.process_event(event)
        assert "technical_analyst" in scheduler._last_run
        assert "consensus_agent" in scheduler._last_run

    def test_failed_agent_returns_error(self, scheduler):
        event = SchedulerEvent(
            event_type=EventType.MANUAL,
            asset="BTCUSDT",
        )
        with patch("app.services.consensus._call_llm") as mock_llm:
            mock_llm.return_value = (None, 0)
            results = scheduler.process_event(event)
        # At least some agents should have success=False (no LLM available)
        failed = [r for r in results if not r.success]
        assert len(failed) > 0


class TestAgentExecutionResult:
    def test_success_result(self):
        result = AgentExecutionResult(
            agent_id="technical_analyst",
            success=True,
            result={"asset": "BTC", "technicalBias": "BUY"},
            tokens_used=150,
            duration_seconds=0.5,
        )
        assert result.success is True
        assert result.tokens_used == 150

    def test_failure_result(self):
        result = AgentExecutionResult(
            agent_id="technical_analyst",
            success=False,
            error="LLM unavailable",
        )
        assert result.success is False
        assert result.result is None


class TestSchedulerPersistence:
    """Tests that scheduler persists results to the Knowledge Base."""

    @pytest.fixture
    def db_session(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        from app.database.base import Base

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        session_local = sessionmaker(bind=engine)
        session = session_local()
        yield session
        session.close()

    def test_persist_signal(self, scheduler, db_session):
        consensus_result = {
            "asset": "BTC",
            "decision": "BUY_ON_PULLBACK",
            "confidence": 0.79,
            "agreement": {"positive": 5, "neutral": 2, "negative": 1},
            "mainReasons": ["Tendencia alcista"],
            "mainRisks": ["Resistencia cercana"],
            "scenarios": [],
        }
        signal = scheduler._persist_signal(db_session, consensus_result, {})
        assert signal is not None
        assert signal.asset == "BTC"
        assert signal.decision == "BUY_ON_PULLBACK"
        assert signal.confidence == 0.79
        assert signal.status == "ACTIVE"

    def test_persist_signal_supersedes_old(self, scheduler, db_session):
        from app.database.models import MarketSignal

        # First signal
        result1 = {"asset": "BTC", "decision": "BUY", "confidence": 0.70, "agreement": {}}
        scheduler._persist_signal(db_session, result1, {})

        # Second signal for same asset
        result2 = {"asset": "BTC", "decision": "HOLD", "confidence": 0.50, "agreement": {}}
        scheduler._persist_signal(db_session, result2, {})

        # Verify only 1 ACTIVE
        from sqlalchemy import select
        active = db_session.execute(
            select(MarketSignal).where(MarketSignal.asset == "BTC", MarketSignal.status == "ACTIVE")
        ).scalars().all()
        assert len(active) == 1
        assert active[0].decision == "HOLD"

    def test_persist_alert(self, scheduler, db_session):
        crash_result = {
            "asset": "SOL",
            "crashRisk": 0.68,
            "riskLevel": "high",
            "reasons": ["Open interest elevado", "Funding extremo"],
        }
        alert = scheduler._persist_alert(db_session, crash_result)
        assert alert is not None
        assert alert.asset == "SOL"
        assert alert.severity == "high"
        assert alert.status == "ACTIVE"

    def test_persist_signal_with_session_none(self, scheduler):
        """process_event with session=None should not crash."""
        event = SchedulerEvent(
            event_type=EventType.MANUAL,
            asset="BTCUSDT",
        )
        with patch("app.services.consensus._call_llm") as mock_llm:
            mock_llm.return_value = (None, 0)
            results = scheduler.process_event(event, session=None)
        # Should still return results, just not persist
        assert len(results) > 0
