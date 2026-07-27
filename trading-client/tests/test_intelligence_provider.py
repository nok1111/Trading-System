"""Tests for IntelligenceProvider — trading-client integration with ai-server."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.ai.intelligence_provider import (
    IntelligenceProvider,
    create_intelligence_provider,
)


@pytest.fixture
def provider():
    return IntelligenceProvider(
        base_url="http://localhost:8000",
        token="test-token",
        timeout=5.0,
    )


def _mock_response(status_code=200, json_data=None):
    """Create a mock httpx.Response."""
    class MockResp:
        def __init__(self):
            self.status_code = status_code
            self._json = json_data or {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise Exception(f"HTTP {self.status_code}")

        def json(self):
            return self._json
    return MockResp()


class TestGetSignals:
    def test_get_signals_success(self, provider):
        mock_data = {
            "signals": [
                {
                    "id": 1,
                    "asset": "BTC",
                    "signal_type": "BUY",
                    "decision": "BUY_ON_PULLBACK",
                    "confidence": 0.79,
                    "agreement": {"positive": 5, "neutral": 2, "negative": 1},
                    "main_reasons": ["Tendencia alcista"],
                    "main_risks": ["Resistencia cercana"],
                    "timestamp": "2025-07-27T10:00:00Z",
                    "expires_at": "2025-07-28T10:00:00Z",
                },
            ],
            "count": 1,
        }
        with patch("httpx.get", return_value=_mock_response(200, mock_data)):
            signals = provider.get_signals()
        assert len(signals) == 1
        assert signals[0].asset == "BTC"
        assert signals[0].decision == "BUY_ON_PULLBACK"
        assert signals[0].confidence == 0.79

    def test_get_signals_by_asset(self, provider):
        mock_data = {"signals": [], "count": 0}
        with patch("httpx.get", return_value=_mock_response(200, mock_data)) as mock_get:
            provider.get_signals(asset="ETH")
        params = mock_get.call_args.kwargs.get("params", {})
        assert params.get("asset") == "ETH"

    def test_get_signals_failure_returns_empty(self, provider):
        with patch("httpx.get", side_effect=Exception("Connection error")):
            signals = provider.get_signals()
        assert signals == []


class TestGetAlerts:
    def test_get_alerts_success(self, provider):
        mock_data = {
            "alerts": [
                {
                    "id": 1,
                    "asset": "SOL",
                    "alert_type": "crash_risk",
                    "severity": "high",
                    "message": "Open interest elevado",
                    "details": {"crash_risk": 0.68},
                    "timestamp": "2025-07-27T10:00:00Z",
                },
            ],
            "count": 1,
        }
        with patch("httpx.get", return_value=_mock_response(200, mock_data)):
            alerts = provider.get_alerts()
        assert len(alerts) == 1
        assert alerts[0].asset == "SOL"
        assert alerts[0].severity == "high"

    def test_get_alerts_failure_returns_empty(self, provider):
        with patch("httpx.get", side_effect=Exception("Connection error")):
            alerts = provider.get_alerts()
        assert alerts == []


class TestGetPendingNotifications:
    def test_get_pending_success(self, provider):
        mock_data = {
            "notifications": [
                {
                    "id": 1,
                    "notification_type": "signal",
                    "asset": "BTC",
                    "content": {"decision": "BUY"},
                    "created_at": "2025-07-27T10:00:00Z",
                    "expires_at": "2025-07-29T10:00:00Z",
                },
            ],
            "summary": {"signal": 1},
        }
        with patch("httpx.get", return_value=_mock_response(200, mock_data)):
            notifs = provider.get_pending_notifications("user123hash")
        assert len(notifs) == 1
        assert notifs[0].notification_type == "signal"
        assert notifs[0].asset == "BTC"

    def test_get_pending_failure_returns_empty(self, provider):
        with patch("httpx.get", side_effect=Exception("Connection error")):
            notifs = provider.get_pending_notifications("user123hash")
        assert notifs == []


class TestMarkNotificationRead:
    def test_mark_read_success(self, provider):
        with patch("httpx.post", return_value=_mock_response(200, {"status": "read"})):
            result = provider.mark_notification_read(1, "user123hash")
        assert result is True

    def test_mark_read_failure(self, provider):
        with patch("httpx.post", return_value=_mock_response(404, {})):
            result = provider.mark_notification_read(999, "user123hash")
        assert result is False


class TestPortfolioMatch:
    def test_portfolio_match_success(self, provider):
        mock_data = {
            "asset": "BTC",
            "market_decision": "BUY",
            "personal_recommendation": "BUY",
            "reason": "Sin posición actual",
            "suggested_action": {"suggestedAllocationPercent": 40.0},
            "confidence": 0.79,
            "notification": {"type": "recommendation", "message": "Oportunidad de compra"},
        }
        with patch("httpx.post", return_value=_mock_response(200, mock_data)):
            rec = provider.portfolio_match(
                "user123hash",
                {"asset": "BTC", "decision": "BUY", "confidence": 0.79},
                {"positions": []},
            )
        assert rec is not None
        assert rec.personal_recommendation == "BUY"
        assert rec.asset == "BTC"

    def test_portfolio_match_failure_returns_none(self, provider):
        with patch("httpx.post", side_effect=Exception("Connection error")):
            rec = provider.portfolio_match("user123hash", {}, {})
        assert rec is None


class TestGetScenarios:
    def test_get_scenarios_success(self, provider):
        mock_data = {
            "asset": "BTC",
            "scenarios": [
                {"id": 1, "horizon": "7d", "scenarios": [{"name": "bullish", "probability": 0.25}]},
            ],
        }
        with patch("httpx.get", return_value=_mock_response(200, mock_data)):
            scenarios = provider.get_scenarios("BTC")
        assert len(scenarios) == 1

    def test_get_scenarios_failure(self, provider):
        with patch("httpx.get", side_effect=Exception("Connection error")):
            scenarios = provider.get_scenarios("BTC")
        assert scenarios == []


class TestGetSchedulerStatus:
    def test_scheduler_status_success(self, provider):
        mock_data = {"running": True, "symbols": ["BTCUSDT"], "interval_seconds": 60}
        with patch("httpx.get", return_value=_mock_response(200, mock_data)):
            status = provider.get_scheduler_status()
        assert status is not None
        assert status["running"] is True

    def test_scheduler_status_failure(self, provider):
        with patch("httpx.get", side_effect=Exception("Connection error")):
            status = provider.get_scheduler_status()
        assert status is None


class TestCreateIntelligenceProvider:
    def test_create_when_disabled(self):
        from types import SimpleNamespace
        settings = SimpleNamespace(USE_INTELLIGENCE_API=False)
        result = create_intelligence_provider(settings)
        assert result is None

    def test_create_when_enabled_with_url(self):
        from types import SimpleNamespace
        settings = SimpleNamespace(
            USE_INTELLIGENCE_API=True,
            REMOTE_AI_URL="http://localhost:8000",
            REMOTE_AI_TOKEN="test-token",
        )
        result = create_intelligence_provider(settings)
        assert result is not None
        assert result._base_url == "http://localhost:8000"

    def test_create_when_enabled_without_url(self):
        from types import SimpleNamespace
        settings = SimpleNamespace(
            USE_INTELLIGENCE_API=True,
            REMOTE_AI_URL=None,
            REMOTE_AI_TOKEN=None,
        )
        result = create_intelligence_provider(settings)
        assert result is None
