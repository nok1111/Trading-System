"""Tests for Portfolio Matcher + Notification Generator + Pending Queue — Fase D."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.models import PendingNotification
from app.services.notifications import NotificationGenerator, PendingQueue
from app.services.portfolio_matcher import (
    PortfolioMatcher,
    UserPortfolio,
)

# --- Fixtures ---

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine)
    session = session_local()
    yield session
    session.close()


@pytest.fixture
def matcher():
    return PortfolioMatcher()


@pytest.fixture
def notif_gen():
    return NotificationGenerator()


@pytest.fixture
def queue(session):
    return PendingQueue(session)


def _make_portfolio(
    user_id: str = "user123",
    positions: list[dict] | None = None,
    max_alloc: float = 40.0,
    risk_profile: str = "intermediate",
) -> UserPortfolio:
    return UserPortfolio(
        user_id_hash=user_id,
        risk_profile=risk_profile,
        max_allocation_pct=max_alloc,
        positions=positions or [],
        total_portfolio_value=100000.0,
        cash_pct=20.0,
    )


def _make_signal(asset: str = "BTC", decision: str = "BUY", confidence: float = 0.79) -> dict:
    return {
        "asset": asset,
        "decision": decision,
        "confidence": confidence,
        "mainReasons": ["Tendencia alcista"],
        "mainRisks": ["Resistencia cercana"],
    }


# --- Portfolio Matcher Tests ---

class TestPortfolioMatcher:
    def test_buy_no_position(self, matcher):
        portfolio = _make_portfolio(positions=[])
        signal = _make_signal("BTC", "BUY")
        rec = matcher.match_signals_to_user(signal, portfolio)
        assert rec.personal_recommendation == "BUY"
        assert "Sin posición" in rec.reason

    def test_buy_with_small_position(self, matcher):
        portfolio = _make_portfolio(positions=[
            {"symbol": "BTC", "allocation_pct": 10.0},
        ])
        signal = _make_signal("BTC", "BUY")
        rec = matcher.match_signals_to_user(signal, portfolio)
        assert rec.personal_recommendation == "BUY_PARTIAL"

    def test_buy_at_max_allocation(self, matcher):
        portfolio = _make_portfolio(positions=[
            {"symbol": "BTC", "allocation_pct": 40.0},
        ])
        signal = _make_signal("BTC", "BUY")
        rec = matcher.match_signals_to_user(signal, portfolio)
        assert rec.personal_recommendation == "HOLD"
        assert "límite" in rec.reason.lower()

    def test_buy_over_max_allocation(self, matcher):
        portfolio = _make_portfolio(positions=[
            {"symbol": "BTC", "allocation_pct": 65.0},
        ])
        signal = _make_signal("BTC", "BUY")
        rec = matcher.match_signals_to_user(signal, portfolio)
        assert rec.personal_recommendation == "HOLD"
        assert "supera" in rec.reason.lower()

    def test_sell_no_position(self, matcher):
        portfolio = _make_portfolio(positions=[])
        signal = _make_signal("BTC", "SELL")
        rec = matcher.match_signals_to_user(signal, portfolio)
        assert rec.personal_recommendation == "AVOID"

    def test_sell_with_position(self, matcher):
        portfolio = _make_portfolio(positions=[
            {"symbol": "BTC", "allocation_pct": 20.0},
        ])
        signal = _make_signal("BTC", "SELL")
        rec = matcher.match_signals_to_user(signal, portfolio)
        assert rec.personal_recommendation == "TAKE_PARTIAL_PROFIT"

    def test_sell_overexposed(self, matcher):
        portfolio = _make_portfolio(positions=[
            {"symbol": "BTC", "allocation_pct": 60.0},
        ])
        signal = _make_signal("BTC", "SELL")
        rec = matcher.match_signals_to_user(signal, portfolio)
        assert rec.personal_recommendation == "SELL_FULL"

    def test_take_profit_no_position(self, matcher):
        portfolio = _make_portfolio(positions=[])
        signal = _make_signal("BTC", "TAKE_PROFIT")
        rec = matcher.match_signals_to_user(signal, portfolio)
        assert rec.personal_recommendation == "AVOID"

    def test_take_profit_with_position(self, matcher):
        portfolio = _make_portfolio(positions=[
            {"symbol": "BTC", "allocation_pct": 30.0},
        ])
        signal = _make_signal("BTC", "TAKE_PROFIT")
        rec = matcher.match_signals_to_user(signal, portfolio)
        assert rec.personal_recommendation == "TAKE_PARTIAL_PROFIT"

    def test_avoid_signal(self, matcher):
        portfolio = _make_portfolio(positions=[
            {"symbol": "BTC", "allocation_pct": 20.0},
        ])
        signal = _make_signal("BTC", "AVOID")
        rec = matcher.match_signals_to_user(signal, portfolio)
        assert rec.personal_recommendation == "AVOID"

    def test_wait_confirmation(self, matcher):
        portfolio = _make_portfolio()
        signal = _make_signal("BTC", "WAIT_CONFIRMATION")
        rec = matcher.match_signals_to_user(signal, portfolio)
        assert rec.personal_recommendation == "WAIT"

    def test_hold_no_position(self, matcher):
        portfolio = _make_portfolio(positions=[])
        signal = _make_signal("BTC", "HOLD")
        rec = matcher.match_signals_to_user(signal, portfolio)
        assert rec.personal_recommendation == "HOLD"

    def test_hold_overexposed_reduces(self, matcher):
        portfolio = _make_portfolio(positions=[
            {"symbol": "BTC", "allocation_pct": 65.0},
        ])
        signal = _make_signal("BTC", "HOLD")
        rec = matcher.match_signals_to_user(signal, portfolio)
        assert rec.personal_recommendation == "TAKE_PARTIAL_PROFIT"

    def test_passive_profile_downgrades_buy(self, matcher):
        portfolio = _make_portfolio(risk_profile="passive")
        signal = _make_signal("BTC", "BUY")
        rec = matcher.match_signals_to_user(signal, portfolio)
        assert rec.personal_recommendation in ("BUY_PARTIAL", "WAIT")

    def test_suggested_reduction_for_overexposed(self, matcher):
        portfolio = _make_portfolio(positions=[
            {"symbol": "BTC", "allocation_pct": 60.0},
        ])
        signal = _make_signal("BTC", "SELL")
        rec = matcher.match_signals_to_user(signal, portfolio)
        assert "suggestedReductionPercent" in rec.suggested_action

    def test_suggested_allocation_for_buy(self, matcher):
        portfolio = _make_portfolio(positions=[
            {"symbol": "BTC", "allocation_pct": 10.0},
        ])
        signal = _make_signal("BTC", "BUY")
        rec = matcher.match_signals_to_user(signal, portfolio)
        assert "suggestedAllocationPercent" in rec.suggested_action

    def test_match_multiple_signals(self, matcher):
        portfolio = _make_portfolio(positions=[
            {"symbol": "BTC", "allocation_pct": 30.0},
        ])
        signals = [
            _make_signal("BTC", "BUY"),
            _make_signal("ETH", "SELL"),
        ]
        recs = matcher.match_multiple_signals(signals, portfolio)
        assert len(recs) == 2
        assert recs[0].asset == "BTC"
        assert recs[1].asset == "ETH"

    def test_different_users_different_recommendations(self, matcher):
        signal = _make_signal("BTC", "BUY")

        # User A: no position
        portfolio_a = _make_portfolio("userA", positions=[])
        rec_a = matcher.match_signals_to_user(signal, portfolio_a)
        assert rec_a.personal_recommendation == "BUY"

        # User B: at max
        portfolio_b = _make_portfolio("userB", positions=[
            {"symbol": "BTC", "allocation_pct": 40.0},
        ])
        rec_b = matcher.match_signals_to_user(signal, portfolio_b)
        assert rec_b.personal_recommendation == "HOLD"

        # User C: overexposed
        portfolio_c = _make_portfolio("userC", positions=[
            {"symbol": "BTC", "allocation_pct": 70.0},
        ])
        rec_c = matcher.match_signals_to_user(signal, portfolio_c)
        assert rec_c.personal_recommendation == "HOLD"


# --- Notification Generator Tests ---

class TestNotificationGenerator:
    def test_generate_from_recommendation(self, notif_gen):
        rec = {
            "personal_recommendation": "BUY",
            "asset": "BTC",
            "reason": "Sin posición actual",
            "confidence": 0.79,
            "suggested_action": {"suggestedAllocationPercent": 40.0},
        }
        notif = notif_gen.generate_from_recommendation(rec)
        assert "BTC" in notif["message"]
        assert notif["type"] == "recommendation"
        assert notif["asset"] == "BTC"

    def test_generate_from_alert(self, notif_gen):
        alert = {
            "alert_type": "crash_risk",
            "asset": "SOL",
            "message": "Open interest elevado",
            "severity": "high",
        }
        notif = notif_gen.generate_from_alert(alert)
        assert "SOL" in notif["message"]
        assert notif["type"] == "alert"
        assert notif["severity"] == "high"

    def test_generate_from_signal(self, notif_gen):
        signal = {
            "asset": "BTC",
            "decision": "BUY_ON_PULLBACK",
            "confidence": 0.79,
            "main_reasons": ["Tendencia alcista", "Salidas de exchanges"],
        }
        notif = notif_gen.generate_from_signal(signal)
        assert "BTC" in notif["message"]
        assert "BUY_ON_PULLBACK" in notif["message"]
        assert notif["type"] == "signal"

    def test_generate_invalidation(self, notif_gen):
        notif = notif_gen.generate_invalidation("ETH", "Soporte roto")
        assert "ETH" in notif["message"]
        assert "invalidada" in notif["message"].lower()
        assert notif["type"] == "invalidation"


# --- Pending Queue Tests ---

class TestPendingQueue:
    def test_add_and_get_pending(self, queue):
        notif = queue.add_notification(
            user_id_hash="user123",
            notification_type="signal",
            content={"decision": "BUY"},
            asset="BTC",
        )
        assert notif.id is not None
        assert notif.status == "PENDING"

        pending = queue.get_pending("user123")
        assert len(pending) == 1
        assert pending[0].asset == "BTC"

    def test_mark_delivered(self, queue):
        notif = queue.add_notification("user123", "signal", {}, "BTC")
        result = queue.mark_delivered(notif.id)
        assert result is True

    def test_mark_read(self, queue):
        notif = queue.add_notification("user123", "signal", {}, "BTC")
        queue.mark_delivered(notif.id)
        result = queue.mark_read(notif.id)
        assert result is True

    def test_cancel(self, queue):
        notif = queue.add_notification("user123", "signal", {}, "BTC")
        result = queue.cancel(notif.id)
        assert result is True

    def test_expire_stale(self, queue):
        # Add a notification that's already expired
        queue.add_notification(
            "user123", "signal", {}, "BTC",
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        expired_count = queue.expire_stale()
        assert expired_count >= 1

    def test_supersede_auto(self, queue):
        """New notification supersedes pending ones of same type+asset."""
        notif1 = queue.add_notification("user123", "signal", {"decision": "BUY"}, "BTC")
        notif2 = queue.add_notification("user123", "signal", {"decision": "HOLD"}, "BTC")

        # First should be SUPERSEDED
        session = queue.session
        old = session.get(PendingNotification, notif1.id)
        assert old.status == "SUPERSEDED"

        # Second should be PENDING
        new = session.get(PendingNotification, notif2.id)
        assert new.status == "PENDING"

    def test_supersede_with_id(self, queue):
        notif1 = queue.add_notification("user123", "signal", {}, "BTC")
        notif2 = queue.add_notification(
            "user123", "signal", {}, "BTC",
            supersedes_id=notif1.id,
        )
        assert notif2.supersedes_id == notif1.id

    def test_pending_summary(self, queue):
        queue.add_notification("user123", "signal", {}, "BTC")
        queue.add_notification("user123", "alert", {}, "SOL")
        queue.add_notification("user123", "signal", {}, "ETH")

        summary = queue.get_pending_summary("user123")
        assert summary["signal"] == 2
        assert summary["alert"] == 1

    def test_different_users_isolated(self, queue):
        queue.add_notification("userA", "signal", {}, "BTC")
        queue.add_notification("userB", "signal", {}, "BTC")

        pending_a = queue.get_pending("userA")
        pending_b = queue.get_pending("userB")
        assert len(pending_a) == 1
        assert len(pending_b) == 1
