"""Tests para AI Server — HMAC, level router, agents, validator, cache, orchestrator.

Sin red: monkeypatch de httpx.post/get.
"""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

from app.services.agents import (
    AGENTS,
    get_agent,
    get_core_agents,
    get_optional_agents,
    get_veto_agents,
    list_agents,
)
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


class TestAgents:
    def test_all_10_agents_exist(self):
        assert len(AGENTS) == 10

    def test_agent_ids(self):
        expected = {
            "orchestrator", "user_profile_manager", "market_analyst",
            "risk_manager", "portfolio_manager", "execution_manager",
            "advisor_explainer", "auditor_guardian",
            "news_sentiment_analyst", "onchain_analyst",
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
        assert len(agents) == 10
        assert "id" in agents[0]
        assert "name" in agents[0]
        assert "role" in agents[0]
        assert "has_veto" in agents[0]
        assert "is_optional" in agents[0]

    def test_all_agents_have_prompts(self):
        for aid, agent in AGENTS.items():
            assert agent.system_prompt, f"Agent {aid} has empty prompt"
            assert len(agent.system_prompt) > 50

    def test_all_agents_have_schemas(self):
        for aid, agent in AGENTS.items():
            assert agent.output_schema, f"Agent {aid} has empty schema"
            assert agent.output_schema.get("type") == "object"

    def test_core_agents_count(self):
        core = get_core_agents()
        assert len(core) == 8

    def test_optional_agents_count(self):
        optional = get_optional_agents()
        assert len(optional) == 2
        assert "news_sentiment_analyst" in optional
        assert "onchain_analyst" in optional

    def test_veto_agents(self):
        veto = get_veto_agents()
        assert len(veto) == 2
        assert "risk_manager" in veto
        assert "auditor_guardian" in veto

    def test_risk_manager_has_veto(self):
        agent = get_agent("risk_manager")
        assert agent.has_veto is True

    def test_auditor_has_veto(self):
        agent = get_agent("auditor_guardian")
        assert agent.has_veto is True


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

    def test_validate_agent_response_risk_manager_approved(self):
        data = {"risk_status": "APPROVED", "max_position_value": 1000}
        valid, error = validate_agent_response("risk_manager", data)
        assert valid
        assert error is None

    def test_validate_agent_response_risk_manager_rejected(self):
        data = {"risk_status": "REJECTED", "rejection_reasons": ["too risky"]}
        valid, _error = validate_agent_response("risk_manager", data)
        assert valid

    def test_validate_agent_response_market_analyst(self):
        data = {"analysis_status": "VALID", "bias": "BULLISH_BIAS", "confidence": 0.8}
        valid, _error = validate_agent_response("market_analyst", data)
        assert valid

    def test_validate_agent_response_auditor_block(self):
        data = {"audit_status": "BLOCK", "violations": ["limit exceeded"]}
        valid, _error = validate_agent_response("auditor_guardian", data)
        assert valid

    def test_validate_agent_response_unknown_agent(self):
        valid, error = validate_agent_response("unknown_agent", {})
        assert not valid
        assert "unknown" in error.lower()

    def test_validate_agent_response_invalid_schema(self):
        data = {"risk_status": "INVALID_STATUS"}
        valid, _error = validate_agent_response("risk_manager", data)
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


class TestOrchestrator:
    def test_orchestrate_with_mocked_llm(self):
        mock_responses = {
            "orchestrator": json.dumps({"status": "OK", "next_action": "SEND_TO_EXECUTION", "reasoning_summary": ["market bullish"]}),
            "user_profile_manager": json.dumps({"profile_status": "COMPLETE", "investment_style": "INTERMEDIATE", "manual_approval_required": False}),
            "market_analyst": json.dumps({"analysis_status": "VALID", "bias": "BULLISH_BIAS", "market_regime": "TRENDING_UP", "confidence": 0.8, "symbol": "BTCUSDT", "market": "spot"}),
            "risk_manager": json.dumps({"risk_status": "APPROVED", "max_position_value": 500, "approved_position_value": 300, "risk_amount": 15, "stop_required": True}),
            "portfolio_manager": json.dumps({"portfolio_action": "BUY", "symbol": "BTCUSDT", "side": "BUY", "target_position_value": 300, "target_allocation_pct": 5, "thesis": ["momentum strong"]}),
            "execution_manager": json.dumps({"execution_status": "READY", "symbol": "BTCUSDT", "side": "BUY", "order_type": "MARKET", "quantity": 0.01}),
            "advisor_explainer": json.dumps({"headline": "Buy BTCUSDT", "summary": "Market is bullish, risk approved"}),
            "auditor_guardian": json.dumps({"audit_status": "PASS", "checks_performed": ["limits", "profile"]}),
            "news_sentiment_analyst": json.dumps({"status": "VALID", "sentiment": "POSITIVE", "confidence": 0.7, "asset": "BTC"}),
            "onchain_analyst": json.dumps({"status": "VALID", "onchain_bias": "BULLISH", "confidence": 0.6, "asset": "BTC"}),
        }

        def mock_post(url, **kwargs):
            messages = kwargs.get("json", {}).get("messages", [])
            system_msg = messages[0]["content"] if messages else ""
            for agent_id, agent in AGENTS.items():
                if agent.system_prompt == system_msg:
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
        assert result["actions"][0]["symbol"] == "BTCUSDT"
        assert result["tokens_used"] > 0

    def test_orchestrate_veto_blocks_actions(self):
        mock_responses = {
            "market_analyst": json.dumps({"analysis_status": "VALID", "bias": "BULLISH_BIAS", "confidence": 0.8}),
            "risk_manager": json.dumps({"risk_status": "REJECTED", "rejection_reasons": ["too risky"]}),
            "advisor_explainer": json.dumps({"headline": "Blocked", "summary": "Risk manager rejected"}),
        }

        def mock_post(url, **kwargs):
            messages = kwargs.get("json", {}).get("messages", [])
            system_msg = messages[0]["content"] if messages else ""
            for agent_id, agent in AGENTS.items():
                if agent.system_prompt == system_msg:
                    content = mock_responses.get(agent_id, "{}")
                    mock = MagicMock()
                    mock.status_code = 200
                    mock.json.return_value = {
                        "choices": [{"message": {"content": content}}],
                        "usage": {"total_tokens": 50},
                    }
                    mock.raise_for_status = MagicMock()
                    return mock
            mock = MagicMock()
            mock.status_code = 200
            mock.json.return_value = {
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"total_tokens": 10},
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
                    plan="free",
                    user_id_hash="test-hash",
                )

        assert result is not None
        assert result["actions"] == []
        assert "BLOQUEADO" in result["market_overview"]

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
        assert result is not None
        assert result["actions"] == []
