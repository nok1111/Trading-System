"""Tests para AI Server — HMAC, level router, intelligence agents, validator, cache.

Sin red: monkeypatch de httpx.post/get.
"""

from __future__ import annotations

import time

from app.services.cache import cache_size, clear_cache, get_cached_analysis, set_cached_analysis
from app.services.hmac import (
    compute_signature,
    verify_nonce,
    verify_signature,
    verify_timestamp,
)
from app.services.intelligence_agents import (
    INTELLIGENCE_AGENTS,
    get_core_intelligence_agents,
    get_intelligence_agent,
    get_optional_intelligence_agents,
    list_intelligence_agents,
)
from app.services.level_router import get_model_for_plan
from app.services.token_accounting import get_all_usage, get_user_usage, record_tokens
from app.services.validator import (
    validate_agent_response,
    validate_analysis_response,
    validate_envelope,
)


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


class TestIntelligenceAgents:
    def test_all_9_agents_exist(self):
        assert len(INTELLIGENCE_AGENTS) == 9

    def test_agent_ids(self):
        expected = {
            "technical_analyst", "news_analyst", "sentiment_analyst",
            "onchain_analyst", "macro_analyst", "crash_detector",
            "opportunity_detector", "contrarian_agent", "consensus_agent",
        }
        assert set(INTELLIGENCE_AGENTS.keys()) == expected

    def test_get_agent(self):
        agent = get_intelligence_agent("technical_analyst")
        assert agent is not None
        assert agent.name == "Technical Market Analyst"

    def test_get_agent_unknown(self):
        assert get_intelligence_agent("unknown") is None

    def test_list_agents(self):
        agents = list_intelligence_agents()
        assert len(agents) == 9
        assert "id" in agents[0]
        assert "name" in agents[0]
        assert "role" in agents[0]
        assert "interval_minutes" in agents[0]
        assert "is_optional" in agents[0]

    def test_all_agents_have_prompts(self):
        for aid, agent in INTELLIGENCE_AGENTS.items():
            assert agent.system_prompt, f"Agent {aid} has empty prompt"
            assert len(agent.system_prompt) > 50

    def test_all_agents_have_schemas(self):
        for aid, agent in INTELLIGENCE_AGENTS.items():
            assert agent.output_schema, f"Agent {aid} has empty schema"
            assert agent.output_schema.get("type") == "object"

    def test_core_agents_count(self):
        core = get_core_intelligence_agents()
        assert len(core) == 5

    def test_optional_agents_count(self):
        optional = get_optional_intelligence_agents()
        assert len(optional) == 4
        assert "news_analyst" in optional
        assert "sentiment_analyst" in optional
        assert "onchain_analyst" in optional
        assert "macro_analyst" in optional


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

    def test_validate_agent_response_technical_analyst(self):
        data = {"asset": "BTCUSDT", "technicalBias": "BUY", "confidence": 0.8}
        valid, error = validate_agent_response("technical_analyst", data)
        assert valid
        assert error is None

    def test_validate_agent_response_crash_detector(self):
        data = {"asset": "BTCUSDT", "crashRisk": 0.3, "riskLevel": "low"}
        valid, _error = validate_agent_response("crash_detector", data)
        assert valid

    def test_validate_agent_response_consensus(self):
        data = {
            "asset": "BTCUSDT", "decision": "BUY", "confidence": 0.75,
            "riskLevel": "MEDIUM",
            "agentVotes": {"technical": "BUY", "news": "NEUTRAL"},
        }
        valid, _error = validate_agent_response("consensus_agent", data)
        assert valid

    def test_validate_agent_response_unknown_agent(self):
        valid, error = validate_agent_response("unknown_agent", {})
        assert not valid
        assert "unknown" in error.lower()

    def test_validate_agent_response_invalid_schema(self):
        data = {"technicalBias": "INVALID_BIAS"}
        valid, _error = validate_agent_response("technical_analyst", data)
        assert not valid

    def test_validate_envelope_valid(self):
        data = {
            "agent": "MARKET_ANALYST",
            "version": "1.0.0",
            "request_id": "uuid-123",
            "timestamp": "2025-01-01T00:00:00Z",
            "status": "OK",
            "payload": {},
        }
        valid, error = validate_envelope(data)
        assert valid
        assert error is None

    def test_validate_envelope_missing_required(self):
        data = {"agent": "TEST", "version": "1.0.0"}
        valid, _error = validate_envelope(data)
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
