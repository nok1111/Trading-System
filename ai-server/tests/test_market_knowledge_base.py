"""Tests for Market Knowledge Base models — Fase C."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
from app.database.models import (
    MarketAlert,
    MarketReport,
    MarketScenario,
    MarketSignal,
    PendingNotification,
    SignalInvalidation,
)


@pytest.fixture
def session():
    """In-memory SQLite session for tests."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine)
    session = session_local()
    yield session
    session.close()


class TestMarketSignal:
    def test_create_signal(self, session):
        signal = MarketSignal(
            asset="BTC",
            signal_type="BUY",
            decision="BUY_ON_PULLBACK",
            confidence=0.79,
            agreement_positive=5,
            agreement_neutral=2,
            agreement_negative=1,
            main_reasons=["Tendencia diaria alcista", "Salidas de exchanges"],
            main_risks=["Resistencia cercana"],
            consensus_data={"agents": ["technical", "onchain"]},
            status="ACTIVE",
            expires_at=datetime.now() + timedelta(hours=24),
        )
        session.add(signal)
        session.commit()
        assert signal.id is not None
        assert signal.asset == "BTC"
        assert signal.confidence == 0.79
        assert len(signal.main_reasons) == 2

    def test_signal_states(self, session):
        signal = MarketSignal(
            asset="ETH",
            signal_type="HOLD",
            decision="HOLD",
            confidence=0.5,
        )
        session.add(signal)
        session.commit()
        assert signal.status == "ACTIVE"


class TestMarketAlert:
    def test_create_alert(self, session):
        alert = MarketAlert(
            asset="SOL",
            alert_type="crash_risk",
            severity="high",
            message="Open interest demasiado elevado",
            details={"crash_risk": 0.68},
        )
        session.add(alert)
        session.commit()
        assert alert.id is not None
        assert alert.severity == "high"


class TestMarketScenario:
    def test_create_scenario(self, session):
        scenario = MarketScenario(
            asset="BTC",
            horizon="7d",
            current_price=105000,
            scenarios=[
                {"name": "bullish", "probability": 0.25, "range": [111000, 118000]},
                {"name": "base", "probability": 0.50, "range": [102000, 110000]},
                {"name": "bearish", "probability": 0.25, "range": [93000, 101000]},
            ],
            invalidation_conditions=["Soporte 101000 roto"],
        )
        session.add(scenario)
        session.commit()
        assert scenario.id is not None
        assert len(scenario.scenarios) == 3
        assert scenario.scenarios[1]["probability"] == 0.50


class TestMarketReport:
    def test_create_report(self, session):
        report = MarketReport(
            asset="BTC",
            report_type="daily",
            content={"summary": "Market bullish", "key_events": []},
            period="2025-07-27",
        )
        session.add(report)
        session.commit()
        assert report.id is not None
        assert report.report_type == "daily"


class TestSignalInvalidation:
    def test_create_invalidation(self, session):
        signal = MarketSignal(
            asset="ETH",
            signal_type="BUY",
            decision="BUY",
            confidence=0.7,
        )
        session.add(signal)
        session.flush()
        inv = SignalInvalidation(
            signal_id=signal.id,
            reason="Soporte principal roto",
        )
        session.add(inv)
        session.commit()
        assert inv.id is not None
        assert inv.signal_id == signal.id


class TestPendingNotification:
    def test_create_pending(self, session):
        notif = PendingNotification(
            user_id_hash="user123hash",
            notification_type="signal",
            asset="BTC",
            content={"decision": "BUY_ON_PULLBACK", "confidence": 0.79},
            status="PENDING",
        )
        session.add(notif)
        session.commit()
        assert notif.id is not None
        assert notif.status == "PENDING"
        assert notif.delivered_at is None
        assert notif.read_at is None

    def test_notification_with_supersedes(self, session):
        notif1 = PendingNotification(
            user_id_hash="user123hash",
            notification_type="signal",
            asset="BTC",
            content={"decision": "BUY"},
        )
        session.add(notif1)
        session.flush()
        notif2 = PendingNotification(
            user_id_hash="user123hash",
            notification_type="signal",
            asset="BTC",
            content={"decision": "HOLD"},
            supersedes_id=notif1.id,
        )
        session.add(notif2)
        session.commit()
        assert notif2.supersedes_id == notif1.id

    def test_notification_states(self, session):
        notif = PendingNotification(
            user_id_hash="user123hash",
            notification_type="alert",
            asset="SOL",
            content={"alert_type": "crash_risk"},
            status="PENDING",
        )
        session.add(notif)
        session.commit()
        # Simulate delivery
        notif.status = "DELIVERED"
        notif.delivered_at = datetime.now()
        session.commit()
        assert notif.status == "DELIVERED"
        assert notif.delivered_at is not None

        # Simulate read
        notif.status = "READ"
        notif.read_at = datetime.now()
        session.commit()
        assert notif.status == "READ"
        assert notif.read_at is not None
