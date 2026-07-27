"""Tests for intelligence agents and consensus engine — Fase B."""

from __future__ import annotations

from app.services.consensus import (
    compute_agreement,
    generate_default_scenarios,
)
from app.services.intelligence_agents import (
    INTELLIGENCE_AGENTS,
    PRE_CONSENSUS_AGENTS,
    get_core_intelligence_agents,
    get_intelligence_agent,
    get_optional_intelligence_agents,
    list_intelligence_agents,
)
from app.services.validator import validate_agent_response


class TestIntelligenceAgents:
    def test_all_9_agents_registered(self):
        assert len(INTELLIGENCE_AGENTS) == 9

    def test_agent_ids(self):
        expected = {
            "technical_analyst", "news_analyst", "sentiment_analyst",
            "onchain_analyst", "macro_analyst", "crash_detector",
            "opportunity_detector", "contrarian_agent", "consensus_agent",
        }
        assert set(INTELLIGENCE_AGENTS.keys()) == expected

    def test_pre_consensus_excludes_consensus(self):
        assert "consensus_agent" not in PRE_CONSENSUS_AGENTS
        assert len(PRE_CONSENSUS_AGENTS) == 8

    def test_get_agent(self):
        agent = get_intelligence_agent("technical_analyst")
        assert agent is not None
        assert agent.name == "Technical Market Analyst"

    def test_get_agent_not_found(self):
        assert get_intelligence_agent("nonexistent") is None

    def test_list_agents(self):
        agents = list_intelligence_agents()
        assert len(agents) == 9
        assert all("id" in a for a in agents)

    def test_core_agents(self):
        core = get_core_intelligence_agents()
        assert "technical_analyst" in core
        assert "news_analyst" not in core  # optional

    def test_optional_agents(self):
        optional = get_optional_intelligence_agents()
        assert "news_analyst" in optional
        assert "technical_analyst" not in optional

    def test_all_agents_have_schemas(self):
        for agent in INTELLIGENCE_AGENTS.values():
            assert agent.output_schema is not None
            assert "type" in agent.output_schema
            assert "required" in agent.output_schema

    def test_all_agents_have_prompts(self):
        for agent in INTELLIGENCE_AGENTS.values():
            assert len(agent.system_prompt) > 50


class TestAgentSchemaValidation:
    def test_technical_valid(self):
        data = {
            "asset": "BTC",
            "technicalBias": "BUY_ON_PULLBACK",
            "confidence": 0.76,
            "trendStrength": 0.78,
            "volatility": "medium",
            "supportZones": [104500, 101800],
            "resistanceZones": [109200, 112000],
        }
        valid, error = validate_agent_response("technical_analyst", data)
        assert valid, error

    def test_technical_invalid_bias(self):
        data = {
            "asset": "BTC",
            "technicalBias": "INVALID",
            "confidence": 0.76,
        }
        valid, _ = validate_agent_response("technical_analyst", data)
        assert not valid

    def test_news_valid(self):
        data = {
            "headline": "Nueva regulación sobre exchanges",
            "affectedAssets": ["BTC", "ETH"],
            "impact": "negative",
            "confidence": 0.82,
            "severity": "high",
            "isRumor": False,
            "pricedIn": False,
        }
        valid, error = validate_agent_response("news_analyst", data)
        assert valid, error

    def test_crash_valid(self):
        data = {
            "asset": "SOL",
            "crashRisk": 0.68,
            "riskLevel": "high",
            "horizon": "6h_to_24h",
            "reasons": ["Open interest elevado", "Funding extremo"],
        }
        valid, error = validate_agent_response("crash_detector", data)
        assert valid, error

    def test_opportunity_valid(self):
        data = {
            "asset": "ETH",
            "suggestion": "BUY",
            "entryZone": [5600, 5720],
            "invalidatedBelow": 5480,
            "targets": [5980, 6250],
            "timeHorizon": "3_to_10_days",
            "confidence": 0.74,
        }
        valid, error = validate_agent_response("opportunity_detector", data)
        assert valid, error

    def test_consensus_valid(self):
        data = {
            "asset": "BTC",
            "decision": "BUY_ON_PULLBACK",
            "confidence": 0.79,
            "agreement": {"positive": 5, "neutral": 2, "negative": 1},
            "mainReasons": ["Tendencia alcista"],
            "mainRisks": ["Resistencia cercana"],
            "scenarios": [
                {"name": "bullish", "probability": 0.25, "range": [111000, 118000]},
                {"name": "base", "probability": 0.50, "range": [102000, 110000]},
                {"name": "bearish", "probability": 0.25, "range": [93000, 101000]},
            ],
        }
        valid, error = validate_agent_response("consensus_agent", data)
        assert valid, error

    def test_contrarian_valid(self):
        data = {
            "targetSignal": "BUY ETH",
            "counterArguments": ["Divergencia negativa en RSI"],
            "divergence": True,
            "manipulationRisk": False,
            "recommendation": "PROCEED_WITH_CAUTION",
        }
        valid, error = validate_agent_response("contrarian_agent", data)
        assert valid, error

    def test_unknown_agent(self):
        valid, error = validate_agent_response("nonexistent", {})
        assert not valid
        assert "desconocido" in error.lower()


class TestComputeAgreement:
    def test_all_positive(self):
        results = {
            "technical_analyst": {"technicalBias": "BUY"},
            "opportunity_detector": {"suggestion": "BUY"},
            "onchain_analyst": {"onchainBias": "BULLISH"},
            "sentiment_analyst": {"sentimentScore": 0.5},
        }
        agreement = compute_agreement(results)
        assert agreement["positive"] == 4
        assert agreement["neutral"] == 0
        assert agreement["negative"] == 0

    def test_mixed(self):
        results = {
            "technical_analyst": {"technicalBias": "BUY"},
            "opportunity_detector": {"suggestion": "SELL"},
            "onchain_analyst": {"onchainBias": "NEUTRAL"},
            "sentiment_analyst": {"sentimentScore": 0.1},
        }
        agreement = compute_agreement(results)
        assert agreement["positive"] == 1
        assert agreement["negative"] == 1
        assert agreement["neutral"] == 2

    def test_empty_results(self):
        agreement = compute_agreement({})
        assert agreement == {"positive": 0, "neutral": 0, "negative": 0}

    def test_none_results_filtered(self):
        results = {
            "technical_analyst": None,
            "opportunity_detector": {"suggestion": "BUY"},
        }
        agreement = compute_agreement(results)
        assert agreement["positive"] == 1


class TestDefaultScenarios:
    def test_three_scenarios(self):
        scenarios = generate_default_scenarios(105000.0)
        assert len(scenarios) == 3
        names = [s["name"] for s in scenarios]
        assert "bullish" in names
        assert "base" in names
        assert "bearish" in names

    def test_probabilities_sum_to_one(self):
        scenarios = generate_default_scenarios(50000.0)
        total = sum(s["probability"] for s in scenarios)
        assert abs(total - 1.0) < 0.01

    def test_bullish_above_current(self):
        scenarios = generate_default_scenarios(100000.0)
        bullish = next(s for s in scenarios if s["name"] == "bullish")
        assert bullish["range"][0] > 100000.0

    def test_bearish_below_current(self):
        scenarios = generate_default_scenarios(100000.0)
        bearish = next(s for s in scenarios if s["name"] == "bearish")
        assert bearish["range"][1] < 100000.0

    def test_with_volatility(self):
        scenarios = generate_default_scenarios(100000.0, volatility=0.10)
        bullish = next(s for s in scenarios if s["name"] == "bullish")
        # Higher volatility = wider range
        assert bullish["range"][1] > 105000.0
