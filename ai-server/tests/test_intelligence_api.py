"""Tests for intelligence API endpoints — Fase F."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.database.base import Base
from app.database.models import (
    MarketAlert,
    MarketScenario,
    MarketSignal,
    PendingNotification,
)
from app.main import app


@pytest.fixture
def test_db():
    """In-memory SQLite for integration tests — StaticPool for TestClient thread safety."""
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
def client():
    return TestClient(app)


def _seed_signal(db: Session, asset: str = "BTC", decision: str = "BUY_ON_PULLBACK") -> MarketSignal:
    signal = MarketSignal(
        asset=asset,
        signal_type="BUY",
        decision=decision,
        confidence=0.79,
        agreement_positive=5,
        agreement_neutral=2,
        agreement_negative=1,
        main_reasons=["Tendencia alcista"],
        main_risks=["Resistencia cercana"],
        status="ACTIVE",
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db.add(signal)
    db.commit()
    return signal


def _seed_alert(db: Session, asset: str = "SOL") -> MarketAlert:
    alert = MarketAlert(
        asset=asset,
        alert_type="crash_risk",
        severity="high",
        message="Open interest elevado",
        details={"crash_risk": 0.68},
        status="ACTIVE",
    )
    db.add(alert)
    db.commit()
    return alert


def _seed_scenario(db: Session, asset: str = "BTC") -> MarketScenario:
    scenario = MarketScenario(
        asset=asset,
        horizon="7d",
        current_price=105000,
        scenarios=[
            {"name": "bullish", "probability": 0.25, "range": [111000, 118000]},
            {"name": "base", "probability": 0.50, "range": [102000, 110000]},
            {"name": "bearish", "probability": 0.25, "range": [93000, 101000]},
        ],
        invalidation_conditions=["Soporte 101000 roto"],
    )
    db.add(scenario)
    db.commit()
    return scenario


# --- Tests ---

class TestSignalsEndpoint:
    def test_get_signals_empty(self, client, test_db):
        resp = client.get("/v1/intelligence/signals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["signals"] == []

    def test_get_signals_with_data(self, client, test_db):
        _seed_signal(test_db, "BTC")
        _seed_signal(test_db, "ETH")
        resp = client.get("/v1/intelligence/signals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2

    def test_get_signals_by_asset(self, client, test_db):
        _seed_signal(test_db, "BTC")
        _seed_signal(test_db, "ETH")
        resp = client.get("/v1/intelligence/signals", params={"asset": "BTC"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["signals"][0]["asset"] == "BTC"


class TestAlertsEndpoint:
    def test_get_alerts_empty(self, client, test_db):
        resp = client.get("/v1/intelligence/alerts")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_get_alerts_with_data(self, client, test_db):
        _seed_alert(test_db, "SOL")
        resp = client.get("/v1/intelligence/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["alerts"][0]["asset"] == "SOL"

    def test_get_alerts_by_severity(self, client, test_db):
        _seed_alert(test_db, "SOL")
        resp = client.get("/v1/intelligence/alerts", params={"severity": "high"})
        assert resp.status_code == 200
        assert resp.json()["count"] == 1


class TestScenariosEndpoint:
    def test_get_scenarios_empty(self, client, test_db):
        resp = client.get("/v1/intelligence/scenarios/BTC")
        assert resp.status_code == 200
        assert resp.json()["scenarios"] == []

    def test_get_scenarios_with_data(self, client, test_db):
        _seed_scenario(test_db, "BTC")
        resp = client.get("/v1/intelligence/scenarios/BTC")
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset"] == "BTC"
        assert len(data["scenarios"]) == 1
        assert len(data["scenarios"][0]["scenarios"]) == 3


class TestPendingEndpoint:
    def test_get_pending_empty(self, client, test_db):
        resp = client.get("/v1/intelligence/pending", params={"user_id_hash": "user123hash"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["notifications"] == []
        assert data["summary"] == {}

    def test_get_pending_with_data(self, client, test_db):
        notif = PendingNotification(
            user_id_hash="user123hash",
            notification_type="signal",
            asset="BTC",
            content={"decision": "BUY"},
            status="PENDING",
        )
        test_db.add(notif)
        test_db.commit()

        resp = client.get("/v1/intelligence/pending", params={"user_id_hash": "user123hash"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["notifications"]) == 1
        assert data["summary"]["signal"] == 1


class TestMarkReadEndpoint:
    def test_mark_read_success(self, client, test_db):
        notif = PendingNotification(
            user_id_hash="user123hash",
            notification_type="signal",
            asset="BTC",
            content={},
            status="PENDING",
        )
        test_db.add(notif)
        test_db.commit()
        test_db.refresh(notif)

        resp = client.post(
            f"/v1/intelligence/pending/{notif.id}/read",
            params={"user_id_hash": "user123hash"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "read"

    def test_mark_read_not_found(self, client, test_db):
        resp = client.post(
            "/v1/intelligence/pending/9999/read",
            params={"user_id_hash": "user123hash"},
        )
        assert resp.status_code == 404

    def test_mark_read_wrong_user(self, client, test_db):
        notif = PendingNotification(
            user_id_hash="user123hash",
            notification_type="signal",
            asset="BTC",
            content={},
            status="PENDING",
        )
        test_db.add(notif)
        test_db.commit()
        test_db.refresh(notif)

        resp = client.post(
            f"/v1/intelligence/pending/{notif.id}/read",
            params={"user_id_hash": "wronguser"},
        )
        assert resp.status_code == 403


class TestPortfolioMatchEndpoint:
    def test_portfolio_match_buy_no_position(self, client, test_db):
        resp = client.post(
            "/v1/intelligence/portfolio-match",
            json={
                "user_id_hash": "user123hash123",
                "signal": {
                    "asset": "BTC",
                    "decision": "BUY",
                    "confidence": 0.79,
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
        data = resp.json()
        assert data["personal_recommendation"] == "BUY"
        assert data["notification"]["type"] == "recommendation"

    def test_portfolio_match_hold_at_max(self, client, test_db):
        resp = client.post(
            "/v1/intelligence/portfolio-match",
            json={
                "user_id_hash": "user123hash123",
                "signal": {
                    "asset": "BTC",
                    "decision": "BUY",
                    "confidence": 0.79,
                },
                "portfolio": {
                    "positions": [{"symbol": "BTC", "allocation_pct": 40.0}],
                },
            },
        )
        assert resp.status_code == 200
        assert resp.json()["personal_recommendation"] == "HOLD"

    def test_portfolio_match_sell_overexposed(self, client, test_db):
        resp = client.post(
            "/v1/intelligence/portfolio-match",
            json={
                "user_id_hash": "user123hash123",
                "signal": {
                    "asset": "BTC",
                    "decision": "SELL",
                    "confidence": 0.65,
                },
                "portfolio": {
                    "positions": [{"symbol": "BTC", "allocation_pct": 60.0}],
                },
            },
        )
        assert resp.status_code == 200
        assert resp.json()["personal_recommendation"] == "SELL_FULL"


class TestAgentsEndpoint:
    def test_list_agents(self, client, test_db):
        resp = client.get("/v1/intelligence/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["agents"]) == 9


class TestSchedulerEndpoints:
    def test_scheduler_status(self, client, test_db):
        resp = client.get("/v1/intelligence/scheduler/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "running" in data
        assert "symbols" in data

    def test_scheduler_stop_when_not_running(self, client, test_db):
        resp = client.post("/v1/intelligence/scheduler/stop")
        assert resp.status_code == 400


class TestReportsEndpoint:
    def test_get_reports_empty(self, client, test_db):
        resp = client.get("/v1/intelligence/reports/BTC")
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset"] == "BTC"
        assert data["reports"] == []

    def test_get_reports_with_data(self, client, test_db):
        from app.database.models import MarketReport
        report = MarketReport(
            asset="BTC",
            report_type="daily",
            content={"summary": "Market bullish"},
            period="2025-07-27",
        )
        test_db.add(report)
        test_db.commit()

        resp = client.get("/v1/intelligence/reports/BTC")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["reports"]) == 1
        assert data["reports"][0]["report_type"] == "daily"


class TestCreateSignalEndpoint:
    def test_create_signal(self, client, test_db):
        resp = client.post(
            "/v1/intelligence/signals",
            json={
                "asset": "BTC",
                "signal_type": "BUY",
                "decision": "BUY_ON_PULLBACK",
                "confidence": 0.79,
                "agreement_positive": 5,
                "agreement_neutral": 2,
                "agreement_negative": 1,
                "main_reasons": ["Tendencia alcista"],
                "main_risks": ["Resistencia cercana"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "created"
        assert data["asset"] == "BTC"
        assert data["id"] is not None

    def test_create_signal_supersedes_old(self, client, test_db):
        # Create first signal
        resp1 = client.post(
            "/v1/intelligence/signals",
            json={
                "asset": "ETH",
                "signal_type": "BUY",
                "decision": "BUY",
                "confidence": 0.70,
            },
        )
        assert resp1.status_code == 201

        # Create second signal for same asset
        resp2 = client.post(
            "/v1/intelligence/signals",
            json={
                "asset": "ETH",
                "signal_type": "HOLD",
                "decision": "HOLD",
                "confidence": 0.50,
            },
        )
        assert resp2.status_code == 201

        # Verify only 1 ACTIVE signal
        resp3 = client.get("/v1/intelligence/signals", params={"asset": "ETH"})
        data = resp3.json()
        assert data["count"] == 1
        assert data["signals"][0]["decision"] == "HOLD"


class TestCreateAlertEndpoint:
    def test_create_alert(self, client, test_db):
        resp = client.post(
            "/v1/intelligence/alerts",
            json={
                "asset": "SOL",
                "alert_type": "crash_risk",
                "severity": "high",
                "message": "Open interest elevado",
                "details": {"crash_risk": 0.68},
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "created"
        assert data["asset"] == "SOL"

    def test_create_alert_invalid_severity(self, client, test_db):
        resp = client.post(
            "/v1/intelligence/alerts",
            json={
                "asset": "SOL",
                "alert_type": "crash_risk",
                "severity": "critical",
                "message": "Test",
            },
        )
        assert resp.status_code == 422


class TestJWTEnforcement:
    """Tests that JWT is enforced when INTELLIGENCE_REQUIRE_JWT=True."""

    @pytest.fixture
    def jwt_enabled(self):
        """Temporarily enable JWT requirement."""
        from app.routes.intelligence import settings as route_settings
        original = route_settings.INTELLIGENCE_REQUIRE_JWT
        route_settings.INTELLIGENCE_REQUIRE_JWT = True
        yield
        route_settings.INTELLIGENCE_REQUIRE_JWT = original

    def test_signals_requires_jwt(self, client, test_db, jwt_enabled):
        resp = client.get("/v1/intelligence/signals")
        assert resp.status_code == 401

    def test_alerts_requires_jwt(self, client, test_db, jwt_enabled):
        resp = client.get("/v1/intelligence/alerts")
        assert resp.status_code == 401

    def test_pending_requires_jwt(self, client, test_db, jwt_enabled):
        resp = client.get("/v1/intelligence/pending", params={"user_id_hash": "test123hash"})
        assert resp.status_code == 401

    def test_portfolio_match_requires_jwt(self, client, test_db, jwt_enabled):
        resp = client.post(
            "/v1/intelligence/portfolio-match",
            json={
                "user_id_hash": "user123hash123",
                "signal": {"asset": "BTC", "decision": "BUY", "confidence": 0.79},
                "portfolio": {"positions": []},
            },
        )
        assert resp.status_code == 401

    def test_scheduler_endpoints_no_jwt_required(self, client, test_db, jwt_enabled):
        """Scheduler control endpoints should NOT require JWT (internal)."""
        resp = client.get("/v1/intelligence/scheduler/status")
        assert resp.status_code == 200

    def test_create_signal_no_jwt_required(self, client, test_db, jwt_enabled):
        """Scheduler POST endpoints should NOT require JWT (internal)."""
        resp = client.post(
            "/v1/intelligence/signals",
            json={
                "asset": "BTC",
                "signal_type": "BUY",
                "decision": "BUY",
                "confidence": 0.70,
            },
        )
        assert resp.status_code == 201
