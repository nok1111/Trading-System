"""Auto-Pilot — one-click trading setup for beginners.

Combines:
1. User profile (risk tolerance, experience, capital)
2. Market regime detection (trending/ranging/volatile)
3. Strategy assignment (best strategy per symbol)
4. Risk configuration (from PROFILE_RISK_LIMITS)

Produces a complete trading plan that the user can activate with one click.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.services.market_regime import (
    MarketRegime,
    detect_regime,
    detect_regimes_batch,
    get_profile_recommendations,
    PROFILE_SYMBOL_FILTER,
)

logger = logging.getLogger(__name__)


@dataclass
class AutoPilotPlan:
    """Complete auto-pilot trading plan."""

    risk_tolerance: str
    experience_level: str
    capital_range: str
    trading_goal: str
    # Market overview
    market_overview: list[dict[str, Any]]
    # Per-symbol recommendations
    symbol_plans: list[dict[str, Any]]
    # Risk config
    risk_limits: dict[str, Any]
    # Summary
    total_symbols: int
    recommended_strategies: list[str]
    regime_distribution: dict[str, int]
    summary: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_tolerance": self.risk_tolerance,
            "experience_level": self.experience_level,
            "capital_range": self.capital_range,
            "trading_goal": self.trading_goal,
            "market_overview": self.market_overview,
            "symbol_plans": self.symbol_plans,
            "risk_limits": self.risk_limits,
            "total_symbols": self.total_symbols,
            "recommended_strategies": self.recommended_strategies,
            "regime_distribution": self.regime_distribution,
            "summary": self.summary,
            "warnings": self.warnings,
        }


def generate_auto_pilot_plan(
    risk_tolerance: str = "moderate",
    experience_level: str = "beginner",
    capital_range: str = "100-1000",
    trading_goal: str = "growth",
    interval: str = "1h",
    max_symbols: int = 5,
) -> AutoPilotPlan:
    """Generate a complete auto-pilot trading plan.

    Args:
        risk_tolerance: conservative | moderate | aggressive
        experience_level: beginner | intermediate | advanced
        capital_range: capital bracket from onboarding
        trading_goal: growth | income | preservation | speculation
        interval: timeframe for analysis
        max_symbols: max symbols to include in plan

    Returns:
        AutoPilotPlan with everything configured
    """
    # Get allowed symbols for this profile
    allowed_symbols = PROFILE_SYMBOL_FILTER.get(risk_tolerance, [])
    if not allowed_symbols:
        # Aggressive — use top symbols by volume
        allowed_symbols = [
            "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
            "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "PEPE/USDT", "INJ/USDT",
        ]

    # Limit symbols based on profile
    if risk_tolerance == "conservative":
        max_symbols = min(max_symbols, 3)
    elif risk_tolerance == "moderate":
        max_symbols = min(max_symbols, 5)
    else:
        max_symbols = min(max_symbols, 8)

    symbols_to_analyze = allowed_symbols[:max_symbols]

    # Detect regime for each symbol
    regimes = detect_regimes_batch(symbols_to_analyze, interval=interval, limit=200)

    # Get profile recommendations
    recommendations = get_profile_recommendations(risk_tolerance, experience_level)

    # Build per-symbol plans
    symbol_plans: list[dict[str, Any]] = []
    market_overview: list[dict[str, Any]] = []
    regime_dist: dict[str, int] = {}
    all_recommended_strategies: set[str] = set()
    warnings: list[str] = []

    for regime in regimes:
        regime_dict = regime.to_dict()
        market_overview.append(regime_dict)

        # Count regime distribution
        regime_dist[regime.regime] = regime_dist.get(regime.regime, 0) + 1

        # Get strategy recommendation for this symbol
        regime_strategies = regime.recommended_strategies
        profile_strategies = recommendations["recommended_strategies"]

        # Intersection: regime-recommended AND profile-allowed
        best_strategies = [s for s in regime_strategies if s in profile_strategies]
        if not best_strategies:
            # Fallback to profile strategies
            best_strategies = profile_strategies[:2]

        best_strategy = best_strategies[0] if best_strategies else "trend_momentum"
        all_recommended_strategies.add(best_strategy)

        # Skip trending_down for conservative (don't buy in downtrend)
        if regime.regime == "trending_down" and risk_tolerance == "conservative":
            warnings.append(f"{regime.symbol} en tendencia bajista — no se recomienda comprar")
            symbol_plans.append({
                "symbol": regime.symbol,
                "regime": regime.regime,
                "recommended_strategy": None,
                "reason": "Tendencia bajista — evitar compra (perfil conservador)",
                "regime_data": regime_dict,
            })
            continue

        symbol_plans.append({
            "symbol": regime.symbol,
            "regime": regime.regime,
            "recommended_strategy": best_strategy,
            "alternative_strategies": best_strategies[1:3],
            "regime_confidence": regime.confidence,
            "reason": regime.description,
            "regime_data": regime_dict,
        })

    # Generate summary
    summary = _generate_summary(
        risk_tolerance, experience_level, trading_goal,
        regime_dist, len(symbol_plans), all_recommended_strategies,
        risk_limits=recommendations["risk_limits"],
    )

    return AutoPilotPlan(
        risk_tolerance=risk_tolerance,
        experience_level=experience_level,
        capital_range=capital_range,
        trading_goal=trading_goal,
        market_overview=market_overview,
        symbol_plans=symbol_plans,
        risk_limits=recommendations["risk_limits"],
        total_symbols=len(symbol_plans),
        recommended_strategies=list(all_recommended_strategies),
        regime_distribution=regime_dist,
        summary=summary,
        warnings=warnings,
    )


def _generate_summary(
    risk_tolerance: str,
    experience_level: str,
    trading_goal: str,
    regime_dist: dict[str, int],
    total_symbols: int,
    strategies: set[str],
    risk_limits: dict[str, Any] | None = None,
) -> str:
    """Generate a human-readable summary of the auto-pilot plan."""
    profile_labels = {
        "conservative": "Conservador",
        "moderate": "Moderado",
        "aggressive": "Agresivo",
    }
    goal_labels = {
        "growth": "crecimiento",
        "income": "ingresos",
        "preservation": "preservacion",
        "speculation": "especulacion",
    }

    # Find dominant regime
    if regime_dist:
        dominant_regime = max(regime_dist, key=regime_dist.get)
        regime_label = {
            "trending_up": "tendencia alcista",
            "trending_down": "tendencia bajista",
            "ranging": "lateral",
            "volatile": "alta volatilidad",
            "squeeze": "compresion (baja volatilidad)",
            "reversal": "posible reversal",
        }.get(dominant_regime, "mixto")
    else:
        regime_label = "no determinado"

    profile_label = profile_labels.get(risk_tolerance, "Moderado")
    goal_label = goal_labels.get(trading_goal, "crecimiento")

    strategy_list = ", ".join(strategies) if strategies else "trend_momentum"

    # Risk limits
    if risk_limits:
        sl = risk_limits.get("sl_range", (2.0, 3.0))
        tp = risk_limits.get("tp_range", (4.0, 8.0))
        max_pos = risk_limits.get("max_positions", 5)
        risk_str = f"SL {sl[0]:.1f}%-{sl[1]:.1f}%, TP {tp[0]:.1f}%-{tp[1]:.1f}%, max {max_pos} posiciones."
    else:
        risk_str = ""

    return (
        f"Plan {profile_label} para {goal_label}: "
        f"{total_symbols} simbolos en mercado {regime_label}. "
        f"Estrategias: {strategy_list}. {risk_str}"
    )
