"""Plan limits and feature access control (Trading Client version).

Plan limits are received from the Auth Server via license validation.
This module provides the same PLAN_LIMITS dict for local reference.
"""

from __future__ import annotations

PLAN_LIMITS: dict[str, dict] = {
    "free": {
        "max_pairs": 3,
        "max_positions": 3,
        "max_ai_requests_per_day": 50,
        "max_ai_interval_seconds": 120,
        "features": ["paper_trading", "ai_agent_analysis", "ai_agent_autotrade"],
    },
    "pro": {
        "max_pairs": 10,
        "max_positions": 10,
        "max_ai_requests_per_day": 500,
        "max_ai_interval_seconds": 15,
        "features": ["paper_trading", "ai_agent_analysis", "ai_agent_autotrade", "telegram_notifications", "ai_provider_keys", "ai_premium_providers"],
    },
    "premium": {
        "max_pairs": 999,
        "max_positions": 999,
        "max_ai_requests_per_day": 99999,
        "max_ai_interval_seconds": 10,
        "features": ["paper_trading", "ai_agent_analysis", "ai_agent_autotrade", "telegram_notifications", "ai_provider_keys", "ai_premium_providers", "priority_support", "custom_strategies"],
    },
}


def get_plan_limits(subscription: str) -> dict:
    return PLAN_LIMITS.get(subscription, PLAN_LIMITS["free"])


def has_feature(subscription: str, feature: str) -> bool:
    limits = get_plan_limits(subscription)
    return feature in limits["features"]
