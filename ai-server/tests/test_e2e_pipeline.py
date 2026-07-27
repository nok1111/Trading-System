"""E2E integration test — full pipeline: scheduler → persist → API → consume.

Validates the autonomous flow:
1. Scheduler processes an event with a session
2. Consensus result is persisted as MarketSignal
3. PendingNotification is auto-generated
4. GET /signals returns the new signal
5. GET /pending returns the notification
6. POST /portfolio-match personalizes the signal
7. _expire_stale cleans up expired items
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.database.base import Base
from app.database.models import MarketSignal, PendingNotification
from app.main import app
from app.services.scheduler import EventScheduler, EventType, SchedulerEvent


@pytest.fixture
def e2e_db():
    """Shared in-memory SQLite for scheduler + API."""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine)
    session = session_local()

    def _override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    yield session
    app.dependency_overrides.clear()
    session.close()


@pytest.fixture
def e2e_client(e2e_db):
    return TestClient(app)


@pytest.fixture
def e2e_scheduler():
    """Scheduler with mocked LLM."""
    scheduler = EventScheduler(symbols=["BTCUSDT"])
    return scheduler


class TestE2EPipeline:
    """Full pipeline: scheduler → persist → API → consume."""

    def test_full_pipeline_signal_to_portfolio_match(self, e2e_db, e2e_client, e2e_scheduler):
        """E2E: Scheduler persists signal → API exposes it → portfolio-match personalizes."""
        # 1. Simulate consensus result and persist directly
        consensus_result = {
            "asset": "BTC",
            "decision": "BUY_ON_PULLBACK",
            "confidence": 0.82,
            "agreement": {"positive": 6, "neutral": 1, "negative": 1},
            "mainReasons": ["Tendencia alcista confirmada", "Volumen creciente"],
            "mainRisks": ["Resistencia en 105k"],
            "scenarios": [],
        }
        signal = e2e_scheduler._persist_signal(e2e_db, consensus_result, {})
        assert signal is not None
        assert signal.status == "ACTIVE"

        # 2. Verify GET /signals returns the signal
        resp = e2e_client.get("/v1/intelligence/signals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["signals"][0]["asset"] == "BTC"
        assert data["signals"][0]["decision"] == "BUY_ON_PULLBACK"
        assert data["signals"][0]["confidence"] == 0.82

        # 3. Verify GET /pending returns the broadcast notification
        resp = e2e_client.get("/v1/intelligence/pending", params={"user_id_hash": "broadcast"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["notifications"]) == 1
        assert data["notifications"][0]["notification_type"] == "signal"
        assert data["notifications"][0]["asset"] == "BTC"
        assert data["notifications"][0]["content"]["signal_id"] == signal.id

        # 4. Verify POST /portfolio-match personalizes the signal
        resp = e2e_client.post(
            "/v1/intelligence/portfolio-match",
            json={
                "user_id_hash": "user123hash123",
                "signal": {
                    "asset": "BTC",
                    "decision": "BUY_ON_PULLBACK",
                    "confidence": 0.82,
                },
                "portfolio": {
                    "broker": "binance",
                    "risk_profile": "intermediate",
                    "max_allocation_pct": 40.0,
                    "positions": [],
                    "total_portfolio_value": 100000,
                },
            },
        )
        assert resp.status_code == 200
        rec = resp.json()
        assert rec["asset"] == "BTC"
        assert rec["market_decision"] == "BUY_ON_PULLBACK"
        assert rec["personal_recommendation"] == "BUY"
        assert rec["notification"]["type"] == "recommendation"

    def test_full_pipeline_alert_persisted_and_visible(self, e2e_db, e2e_client, e2e_scheduler):
        """E2E: Scheduler persists alert → API exposes it."""
        crash_result = {
            "asset": "SOL",
            "crashRisk": 0.72,
            "riskLevel": "high",
            "reasons": ["Open interest extremo", "Funding rate negativo"],
        }
        alert = e2e_scheduler._persist_alert(e2e_db, crash_result)
        assert alert is not None

        # Verify GET /alerts returns it
        resp = e2e_client.get("/v1/intelligence/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["alerts"][0]["asset"] == "SOL"
        assert data["alerts"][0]["severity"] == "high"

    def test_full_pipeline_supersede_and_notification(self, e2e_db, e2e_client, e2e_scheduler):
        """E2E: Second signal supersedes first, new notification generated."""
        # First signal
        result1 = {"asset": "BTC", "decision": "BUY", "confidence": 0.70, "agreement": {}}
        signal1 = e2e_scheduler._persist_signal(e2e_db, result1, {})
        assert signal1 is not None

        # Second signal for same asset
        result2 = {"asset": "BTC", "decision": "HOLD", "confidence": 0.50, "agreement": {}}
        signal2 = e2e_scheduler._persist_signal(e2e_db, result2, {})
        assert signal2 is not None

        # Only 1 ACTIVE signal
        resp = e2e_client.get("/v1/intelligence/signals")
        data = resp.json()
        assert data["count"] == 1
        assert data["signals"][0]["decision"] == "HOLD"

        # 2 pending notifications (one per signal)
        resp = e2e_client.get("/v1/intelligence/pending", params={"user_id_hash": "broadcast"})
        data = resp.json()
        assert len(data["notifications"]) == 2

    def test_full_pipeline_expire_stale(self, e2e_db, e2e_client, e2e_scheduler):
        """E2E: Expired signals are cleaned up and no longer visible via API."""
        # Create an already-expired signal directly
        expired_signal = MarketSignal(
            asset="ETH",
            signal_type="BUY",
            decision="BUY",
            confidence=0.65,
            status="ACTIVE",
            expires_at=datetime.now(UTC) - timedelta(hours=2),
        )
        e2e_db.add(expired_signal)
        e2e_db.commit()

        # Run expire
        e2e_scheduler._expire_stale(e2e_db)

        # Signal should not appear in GET /signals
        resp = e2e_client.get("/v1/intelligence/signals")
        data = resp.json()
        assert data["count"] == 0

    def test_full_pipeline_mark_notification_read(self, e2e_db, e2e_client, e2e_scheduler):
        """E2E: Notification can be marked as read via API."""
        # Create signal (generates notification)
        result = {"asset": "BTC", "decision": "BUY", "confidence": 0.75, "agreement": {}}
        e2e_scheduler._persist_signal(e2e_db, result, {})

        # Get pending
        resp = e2e_client.get("/v1/intelligence/pending", params={"user_id_hash": "broadcast"})
        notif_id = resp.json()["notifications"][0]["id"]

        # Mark as read
        resp = e2e_client.post(
            f"/v1/intelligence/pending/{notif_id}/read",
            params={"user_id_hash": "broadcast"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "read"

        # Should no longer appear in pending
        resp = e2e_client.get("/v1/intelligence/pending", params={"user_id_hash": "broadcast"})
        data = resp.json()
        assert len(data["notifications"]) == 0

    def test_full_pipeline_process_event_with_session(self, e2e_db, e2e_client, e2e_scheduler):
        """E2E: process_event with session persists results end-to-end."""
        event = SchedulerEvent(
            event_type=EventType.MANUAL,
            asset="BTCUSDT",
        )

        # Mock LLM to return valid consensus-like result
        mock_consensus = {
            "asset": "BTC",
            "decision": "BUY",
            "confidence": 0.78,
            "agreement": {"positive": 5, "neutral": 2, "negative": 1},
            "mainReasons": ["Bullish"],
            "mainRisks": ["Volatility"],
            "scenarios": [],
        }

        with patch("app.services.consensus._call_llm") as mock_llm, \
             patch("app.services.scheduler.validate_agent_response", return_value=(True, None)):
            mock_llm.return_value = ('{"decision": "BUY", "confidence": 0.78}', 100)
            # Patch _execute_consensus to return a valid result
            with patch.object(e2e_scheduler, "_execute_consensus") as mock_cons:
                from app.services.scheduler import AgentExecutionResult
                mock_cons.return_value = AgentExecutionResult(
                    agent_id="consensus_agent",
                    success=True,
                    result=mock_consensus,
                    tokens_used=100,
                    duration_seconds=0.5,
                )
                e2e_scheduler.process_event(event, session=e2e_db)

        # Verify signal was persisted
        signals = e2e_db.execute(
            select(MarketSignal).where(MarketSignal.asset == "BTC")
        ).scalars().all()
        assert len(signals) == 1
        assert signals[0].status == "ACTIVE"

        # Verify notification was generated
        notifs = e2e_db.execute(
            select(PendingNotification).where(PendingNotification.user_id_hash == "broadcast")
        ).scalars().all()
        assert len(notifs) == 1

        # Verify API exposes the signal
        resp = e2e_client.get("/v1/intelligence/signals")
        assert resp.json()["count"] == 1
