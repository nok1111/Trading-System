"""Tests para AI Server — HMAC, level router, agents, validator, cache, orchestrator.

Sin red: monkeypatch de httpx.post/get.
"""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

from app.services.agents import AGENTS, get_agent, list_agents
from app.services.cache import cache_size, clear_cache, get_cached_analysis, set_cached_analysis
from app.services.hmac import (
    compute_signature,
    verify_nonce,
    verify_signature,
    verify_timestamp,
)
from app.services.level_router import get_model_for_plan
from app.services.orchestrator import orchestrate_analysis
from app.services.token_accounting import get_all_usage, get_user_usage, record_tokens
from app.services.validator import validate_analysis_response


class TestHMAC:
    def test_compute_and_verify_signature(self):
        secret = "test-secret"
        timestamp = str(int(time.time()))
        nonce = "abc123"
        body = '{"test": true}'
        sig = compute_signature(timestamp, nonce, body, secret)
        assert verify_signature(timestamp, nonce, body, sig, secret)

    def test_wrong_secret_fails(self):
        sig = compute_signature("123", "nonce", "body", "secret1")
        assert not verify_signature("123", "nonce", "body", sig, "secret2")

    def test_wrong_body_fails(self):
        sig = compute_signature("123", "nonce", "body1", "secret")
        assert not verify_signature("123", "nonce", "body2", sig, "secret")

    def test_timestamp_valid(self):
        ts = str(int(time.time()))
        assert verify_timestamp(ts, 300)

    def test_timestamp_expired(self):
        ts = str(int(time.time()) - 600)
        assert not verify_timestamp(ts, 300)

    def test_timestamp_invalid(self):
        assert not verify_timestamp("not-a-number", 300)

    def test_nonce_unique(self):
        clear_nonce_test = "test-nonce-unique"
        assert verify_nonce(clear_nonce_test, 300)
        assert not verify_nonce(clear_nonce_test, 300)


class TestLevelRouter:
    def test_free_gets_economic(self):
        config = get_model_for_plan("free")
        assert config.level == "economic"
        assert config.max_tokens == 1000

    def test_pro_gets_medium(self):
        config = get_model_for_plan("pro")
        assert config.level == "medium"
        assert config.max_tokens == 1500

    def test_premium_gets_advanced(self):
        config = get_model_for_plan("premium")
        assert config.level == "advanced"
        assert config.max_tokens == 2000

    def test_unknown_plan_defaults_to_free(self):
        config = get_model_for_plan("unknown")
        assert config.level == "economic"


class TestAgents:
    def test_all_8_agents_exist(self):
        assert len(AGENTS) == 8

    def test_agent_ids(self):
        expected = {
            "market_analyst", "risk_analyst", "strategy_selector",
            "entry_strategist", "exit_strategist", "portfolio_manager",
            "sentiment_analyst", "performance_monitor",
        }
        assert set(AGENTS.keys()) == expected

    def test_get_agent(self):
        agent = get_agent("market_analyst")
        assert agent is not None
        assert agent.name == "Market Analyst"

    def test_get_agent_unknown(self):
        assert get_agent("unknown") is None

    def test_list_agents(self):
        agents = list_agents()
        assert len(agents) == 8
        assert "id" in agents[0]
        assert "name" in agents[0]
        assert "role" in agents[0]

    def test_all_agents_have_prompts(self):
        for aid, agent in AGENTS.items():
            assert agent.system_prompt, f"Agent {aid} has empty prompt"
            assert len(agent.system_prompt) > 50


class TestValidator:
    def test_valid_response(self):
        response = {
            "version": "1",
            "analysis_id": "test-uuid",
            "market_overview": "Bull market",
            "actions": [{"type": "buy", "symbol": "BTC/USDT", "confidence": 0.8}],
            "risk_assessment": "Low risk",
        }
        valid, error = validate_analysis_response(response)
        assert valid
        assert error is None

    def test_missing_required_field(self):
        response = {
            "version": "1",
            "analysis_id": "test-uuid",
            "market_overview": "Bull market",
            "actions": [],
        }
        valid, error = validate_analysis_response(response)
        assert not valid
        assert error is not None

    def test_invalid_action_type(self):
        response = {
            "version": "1",
            "analysis_id": "test-uuid",
            "market_overview": "Bull",
            "actions": [{"type": "invalid", "symbol": "BTC", "confidence": 0.5}],
            "risk_assessment": "Low",
        }
        valid, _error = validate_analysis_response(response)
        assert not valid

    def test_confidence_out_of_range(self):
        response = {
            "version": "1",
            "analysis_id": "test-uuid",
            "market_overview": "Bull",
            "actions": [{"type": "buy", "symbol": "BTC", "confidence": 1.5}],
            "risk_assessment": "Low",
        }
        valid, _error = validate_analysis_response(response)
        assert not valid


class TestCache:
    def setup_method(self):
        clear_cache()

    def test_set_and_get(self):
        set_cached_analysis("binance", "spot", "BTC", "1m", "v1", {"test": True})
        result = get_cached_analysis("binance", "spot", "BTC", "1m", "v1")
        assert result == {"test": True}

    def test_cache_miss(self):
        result = get_cached_analysis("binance", "spot", "ETH", "1m", "v1")
        assert result is None

    def test_cache_size(self):
        set_cached_analysis("binance", "spot", "BTC", "1m", "v1", {"a": 1})
        set_cached_analysis("binance", "spot", "ETH", "1m", "v1", {"b": 2})
        assert cache_size() == 2


class TestTokenAccounting:
    def test_record_and_get(self):
        record_tokens("user-hash-123", 100, "market_analyst", "llama-3.1-8b")
        record_tokens("user-hash-123", 50, "risk_analyst", "llama-3.1-8b")
        usage = get_user_usage("user-hash-123")
        assert usage["total_tokens"] == 150
        assert usage["request_count"] == 2

    def test_get_all_usage(self):
        record_tokens("user-a", 100, "market_analyst", "model-x")
        record_tokens("user-b", 200, "risk_analyst", "model-y")
        all_usage = get_all_usage()
        assert "user-a" in all_usage
        assert "user-b" in all_usage
        assert all_usage["user-a"]["total_tokens"] == 100
        assert all_usage["user-b"]["total_tokens"] == 200


class TestOrchestrator:
    def test_orchestrate_with_mocked_llm(self):
        mock_responses = {
            "market_analyst": json.dumps({"trend": "bull", "momentum": "strong", "volume_assessment": "high", "key_levels": []}),
            "risk_analyst": json.dumps({"overall_risk": 3, "concentration": "low", "exposure": "moderate", "recommendations": ["hold"]}),
            "strategy_selector": json.dumps({"strategy": "swing", "timeframe": "1h", "reason": "trending", "default_sl_pct": 3, "default_tp_pct": 8}),
            "entry_strategist": json.dumps({"entries": [{"symbol": "BTC/USDT", "confidence": 0.8, "sl_pct": 3, "tp_pct": 8, "reason": "momentum"}]}),
            "portfolio_manager": json.dumps({"diversification_score": 7, "capital_allocation": "balanced", "rebalance": []}),
            "sentiment_analyst": json.dumps({"sentiment": "greedy", "fear_greed_index": 72, "signals": ["bullish"]}),
            "performance_monitor": json.dumps({"pnl_trend": "up", "efficiency": "good", "suggestions": ["increase size"]}),
        }

        def mock_post(url, **kwargs):
            messages = kwargs.get("json", {}).get("messages", [])
            system_msg = messages[0]["content"] if messages else ""
            # Match agent by system prompt
            for agent_id, agent in AGENTS.items():
                if agent.system_prompt in system_msg or system_msg in agent.system_prompt:
                    content = mock_responses.get(agent_id, "{}")
                    mock = MagicMock()
                    mock.status_code = 200
                    mock.json.return_value = {
                        "choices": [{"message": {"content": content}}],
                        "usage": {"total_tokens": 100},
                    }
                    mock.raise_for_status = MagicMock()
                    return mock
            mock = MagicMock()
            mock.status_code = 200
            mock.json.return_value = {
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"total_tokens": 50},
            }
            mock.raise_for_status = MagicMock()
            return mock

        with patch("app.services.orchestrator.httpx.post", side_effect=mock_post):
            with patch("app.services.orchestrator.get_settings") as mock_settings:
                mock = MagicMock()
                mock.AI_PROVIDER = "groq"
                mock.GROQ_API_KEY = "test-key"
                mock.GROQ_MODEL_ECONOMIC = "llama-3.1-8b"
                mock.GROQ_MODEL_MEDIUM = "llama-3.3-70b"
                mock.GROQ_MODEL_ADVANCED = "llama-3.3-70b"
                mock_settings.return_value = mock
                result = orchestrate_analysis(
                    context={"acc": {"cash": 5000}},
                    plan="premium",
                    user_id_hash="test-hash",
                )

        assert result is not None
        assert result["version"] == "1"
        assert "analysis_id" in result
        assert isinstance(result["actions"], list)
        assert len(result["actions"]) > 0
        assert result["actions"][0]["symbol"] == "BTC/USDT"
        assert result["tokens_used"] > 0

    def test_orchestrate_no_llm_available(self):
        with patch("app.services.orchestrator.get_settings") as mock_settings:
            mock = MagicMock()
            mock.AI_PROVIDER = "groq"
            mock.GROQ_API_KEY = None
            mock_settings.return_value = mock
            result = orchestrate_analysis(
                context={},
                plan="free",
                user_id_hash="test-hash",
            )
        # Without LLM, agents return None, but the orchestrator still builds a valid response
        # with empty actions and default values
        assert result is not None
        assert result["actions"] == []
