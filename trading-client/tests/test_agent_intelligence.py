"""Tests for AITradingAgent intelligence mode — _tick_intelligence, portfolio matching, recommendation conversion."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.ai.agent import AITradingAgent
from app.ai.intelligence_provider import (
    IntelligenceProvider,
    IntelligenceSignal,
    PersonalRecommendation,
)


@pytest.fixture
def agent_with_intelligence():
    """Agent with IntelligenceProvider mock and no real LLM."""
    mock_provider = MagicMock(spec=IntelligenceProvider)
    agent = AITradingAgent(
        provider="groq",
        groq_api_key="fake",
        auto_trade=False,
    )
    agent._intelligence_provider = mock_provider
    return agent, mock_provider


class TestGetIntelligenceMode:
    def test_status_shows_intelligence_mode_off(self):
        agent = AITradingAgent(provider="groq", groq_api_key="fake")
        agent._intelligence_provider = None
        status = agent.get_status()
        assert status["intelligence_mode"] is False

    def test_status_shows_intelligence_mode_on(self, agent_with_intelligence):
        agent, _ = agent_with_intelligence
        status = agent.get_status()
        assert status["intelligence_mode"] is True


class TestRecommendationToAction:
    def test_buy_recommendation(self, agent_with_intelligence):
        agent, _ = agent_with_intelligence
        rec = PersonalRecommendation(
            asset="BTC",
            market_decision="BUY",
            personal_recommendation="BUY",
            reason="Sin posición actual",
            confidence=0.79,
        )
        action = agent._recommendation_to_action(rec)
        assert action is not None
        assert action["type"] == "buy"
        assert action["symbol"] == "BTCUSDT"
        assert action["confidence"] == 0.79

    def test_sell_full_recommendation(self, agent_with_intelligence):
        agent, _ = agent_with_intelligence
        rec = PersonalRecommendation(
            asset="ETH",
            market_decision="SELL",
            personal_recommendation="SELL_FULL",
            reason="Sobreexpuesto",
            confidence=0.65,
        )
        action = agent._recommendation_to_action(rec)
        assert action is not None
        assert action["type"] == "sell"
        assert action["symbol"] == "ETHUSDT"

    def test_take_partial_profit(self, agent_with_intelligence):
        agent, _ = agent_with_intelligence
        rec = PersonalRecommendation(
            asset="SOL",
            market_decision="SELL",
            personal_recommendation="TAKE_PARTIAL_PROFIT",
            reason="Tomar ganancias parciales",
            confidence=0.60,
        )
        action = agent._recommendation_to_action(rec)
        assert action is not None
        assert action["type"] == "sell"

    def test_hold_returns_none(self, agent_with_intelligence):
        agent, _ = agent_with_intelligence
        rec = PersonalRecommendation(
            asset="BTC",
            market_decision="BUY",
            personal_recommendation="HOLD",
            reason="Ya en posición máxima",
            confidence=0.50,
        )
        action = agent._recommendation_to_action(rec)
        assert action is None

    def test_avoid_returns_none(self, agent_with_intelligence):
        agent, _ = agent_with_intelligence
        rec = PersonalRecommendation(
            asset="BTC",
            market_decision="SELL",
            personal_recommendation="AVOID",
            reason="No hay posición",
            confidence=0.30,
        )
        action = agent._recommendation_to_action(rec)
        assert action is None

    def test_symbol_already_has_usdt(self, agent_with_intelligence):
        agent, _ = agent_with_intelligence
        rec = PersonalRecommendation(
            asset="BTCUSDT",
            market_decision="BUY",
            personal_recommendation="BUY",
            reason="Test",
            confidence=0.70,
        )
        action = agent._recommendation_to_action(rec)
        assert action["symbol"] == "BTCUSDT"


class TestBuildPortfolioForMatch:
    def test_empty_positions(self, agent_with_intelligence):
        agent, _ = agent_with_intelligence
        with patch.object(agent, "_api_get", return_value=[]):
            portfolio = agent._build_portfolio_for_match([])
        assert portfolio["positions"] == []
        assert portfolio["cash_pct"] == 100.0

    def test_with_positions(self, agent_with_intelligence):
        agent, _ = agent_with_intelligence
        positions = [
            {"symbol": "BTCUSDT", "quantity": 0.5, "entry_price": 100000, "current_price": 105000},
            {"symbol": "ETHUSDT", "quantity": 2.0, "entry_price": 3000, "current_price": 3500},
        ]
        snapshots = [{"equity": 60000, "cash": 20000}]
        with patch.object(agent, "_api_get", side_effect=[snapshots]):
            portfolio = agent._build_portfolio_for_match(positions)
        assert len(portfolio["positions"]) == 2
        assert portfolio["total_portfolio_value"] == 60000
        assert portfolio["cash_pct"] == pytest.approx(33.33, rel=0.01)
        # Check allocation percentages
        btc_value = 0.5 * 105000
        total = btc_value + 2.0 * 3500
        assert portfolio["positions"][0]["allocation_pct"] == pytest.approx((btc_value / total) * 100, rel=0.01)


class TestGetUserHash:
    def test_with_jwt_token(self, agent_with_intelligence):
        agent, _ = agent_with_intelligence
        agent._jwt_token = "test-jwt-token"
        user_hash = agent._get_user_hash()
        assert len(user_hash) == 32
        assert user_hash != "anonymous_user_hash_000000"

    def test_without_jwt_token(self, agent_with_intelligence):
        agent, _ = agent_with_intelligence
        agent._jwt_token = None
        user_hash = agent._get_user_hash()
        assert user_hash == "anonymous_user_hash_000000"


class TestTickIntelligence:
    def test_no_signals(self, agent_with_intelligence):
        agent, mock_provider = agent_with_intelligence
        mock_provider.get_signals.return_value = []
        mock_provider.get_alerts.return_value = []
        with patch.object(agent, "_gather_context", return_value={"positions": []}), \
             patch.object(agent, "_ask_llm", return_value=None), \
             patch.object(agent, "_handle_llm_failure", return_value=False):
            agent._tick_intelligence()
        # Should increment hold streak
        assert agent._hold_streak >= 1

    def test_with_buy_signal(self, agent_with_intelligence):
        agent, mock_provider = agent_with_intelligence
        signal = IntelligenceSignal(
            id=1, asset="BTC", signal_type="BUY",
            decision="BUY", confidence=0.79,
        )
        mock_provider.get_signals.return_value = [signal]
        mock_provider.get_alerts.return_value = []
        mock_provider.portfolio_match.return_value = PersonalRecommendation(
            asset="BTC",
            market_decision="BUY",
            personal_recommendation="BUY",
            reason="Sin posición",
            confidence=0.79,
        )
        with patch.object(agent, "_api_get", return_value=[]):
            agent._tick_intelligence()
        # auto_trade=False so no execution, but hold streak should be 0
        assert agent._hold_streak == 0

    def test_with_hold_recommendation(self, agent_with_intelligence):
        agent, mock_provider = agent_with_intelligence
        signal = IntelligenceSignal(
            id=1, asset="BTC", signal_type="BUY",
            decision="BUY", confidence=0.79,
        )
        mock_provider.get_signals.return_value = [signal]
        mock_provider.get_alerts.return_value = []
        mock_provider.portfolio_match.return_value = PersonalRecommendation(
            asset="BTC",
            market_decision="BUY",
            personal_recommendation="HOLD",
            reason="Ya en posición máxima",
            confidence=0.50,
        )
        with patch.object(agent, "_gather_context", return_value={"positions": []}), \
             patch.object(agent, "_ask_llm", return_value=None), \
             patch.object(agent, "_handle_llm_failure", return_value=False), \
             patch.object(agent, "_api_get", return_value=[]):
            agent._tick_intelligence()
        # HOLD → no actions → hold streak increases
        assert agent._hold_streak >= 1

    def test_alerts_logged(self, agent_with_intelligence):
        from app.ai.intelligence_provider import IntelligenceAlert
        agent, mock_provider = agent_with_intelligence
        mock_provider.get_signals.return_value = []
        mock_provider.get_alerts.return_value = [
            IntelligenceAlert(
                id=1, asset="SOL", alert_type="crash_risk",
                severity="high", message="Open interest elevado",
            ),
        ]
        agent._tick_intelligence()
        # Check that alert was logged
        logs = agent.get_log()
        alert_logs = [entry for entry in logs if "Alerta" in entry.get("message", "")]
        assert len(alert_logs) > 0
