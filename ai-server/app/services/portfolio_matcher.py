"""Portfolio Matcher — personalización determinista por usuario.

NO usa IA. Cruza señales globales con el portafolio del usuario,
perfil de riesgo, exposición, y broker para producir recomendaciones
personalizadas.

Una misma señal global puede producir recomendaciones diferentes:
- Usuario A posee poco BTC → Compra parcial
- Usuario B ya tiene 50% en BTC → Mantener
- Usuario C tiene 80% en BTC → Tomar ganancias
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UserPortfolio:
    """Portafolio del usuario enviado desde el trading-client."""

    user_id_hash: str
    broker: str = "unknown"
    risk_profile: str = "intermediate"  # passive, intermediate, aggressive
    max_allocation_pct: float = 40.0
    max_risk_per_trade_pct: float = 2.0
    positions: list[dict] = field(default_factory=list)  # [{symbol, quantity, avg_entry, current_value, allocation_pct}]
    total_portfolio_value: float = 0.0
    cash_pct: float = 0.0


@dataclass
class PersonalRecommendation:
    """Recomendación personalizada para un usuario."""

    user_id_hash: str
    asset: str
    market_decision: str  # Decisión global del Consensus Agent
    personal_recommendation: str  # BUY_PARTIAL, HOLD, TAKE_PARTIAL_PROFIT, SELL_FULL, AVOID, WAIT
    reason: str
    suggested_action: dict = field(default_factory=dict)
    confidence: float = 0.0


class PortfolioMatcher:
    """Cruza señales globales con el portafolio del usuario — determinista."""

    def match_signals_to_user(
        self,
        signal: dict[str, Any],
        portfolio: UserPortfolio,
    ) -> PersonalRecommendation:
        """Genera una recomendación personalizada a partir de una señal global.

        Args:
            signal: Señal global del Consensus Agent {asset, decision, confidence, ...}.
            portfolio: Portafolio del usuario.

        Returns:
            PersonalRecommendation con la recomendación personalizada.
        """
        asset = signal.get("asset", "")
        market_decision = signal.get("decision", "NO_ACTION")
        confidence = signal.get("confidence", 0.0)

        # Adjust max allocation based on risk profile
        max_alloc = portfolio.max_allocation_pct
        if portfolio.risk_profile == "aggressive":
            max_alloc = min(max_alloc * 1.5, 60.0)
        elif portfolio.risk_profile == "passive":
            max_alloc = min(max_alloc * 0.6, 25.0)

        # Buscar posición del usuario en este asset
        position = next(
            (p for p in portfolio.positions if p.get("symbol", "").upper() == asset.upper()),
            None,
        )

        current_allocation = position.get("allocation_pct", 0.0) if position else 0.0

        # Lógica determinista de personalización
        if market_decision in ("BUY", "BUY_ON_PULLBACK"):
            if current_allocation >= max_alloc * 1.5:
                recommendation = "HOLD"
                reason = f"Ya supera exposición máxima recomendada ({current_allocation:.1f}% vs {max_alloc:.1f}%)"
            elif current_allocation >= max_alloc:
                recommendation = "HOLD"
                reason = f"Exposición en límite máximo ({current_allocation:.1f}%)"
            elif current_allocation > 0:
                recommendation = "BUY_PARTIAL"
                reason = f"Ya tiene posición ({current_allocation:.1f}%), comprar parcial para no sobreexponerse"
            else:
                recommendation = "BUY"
                reason = "Sin posición actual, señal positiva"

        elif market_decision in ("SELL", "SELL_ON_RALLY"):
            if position is None:
                recommendation = "AVOID"
                reason = "No tiene posición para vender"
            elif current_allocation > max_alloc:
                recommendation = "SELL_FULL"
                reason = f"Sobreexpuesto ({current_allocation:.1f}%), vender completo"
            else:
                recommendation = "TAKE_PARTIAL_PROFIT"
                reason = f"Reducir posición ({current_allocation:.1f}%)"

        elif market_decision == "TAKE_PROFIT":
            if position is None:
                recommendation = "AVOID"
                reason = "No tiene posición para tomar ganancias"
            else:
                recommendation = "TAKE_PARTIAL_PROFIT"
                reason = f"Tomar ganancias parciales ({current_allocation:.1f}%)"

        elif market_decision == "AVOID":
            recommendation = "AVOID"
            reason = "Señal global indica evitar este activo"

        elif market_decision == "WAIT_CONFIRMATION":
            recommendation = "WAIT"
            reason = "Esperar confirmación del mercado"

        else:  # HOLD, NO_ACTION
            if position and current_allocation > max_alloc * 1.5:
                recommendation = "TAKE_PARTIAL_PROFIT"
                reason = f"Sobreexpuesto ({current_allocation:.1f}%), reducir aunque el mercado sea neutral"
            else:
                recommendation = "HOLD"
                reason = "Sin acción necesaria"

        # Ajustar por perfil de riesgo
        if portfolio.risk_profile == "passive" and recommendation in ("BUY", "BUY_PARTIAL"):
            recommendation = "BUY_PARTIAL" if recommendation == "BUY" else "WAIT"
            reason += " (perfil pasivo: reducir tamaño)"
        elif portfolio.risk_profile == "aggressive" and recommendation == "WAIT":
            recommendation = "BUY_PARTIAL"
            reason += " (perfil agresivo: aprovechar oportunidad)"
        elif portfolio.risk_profile == "aggressive" and recommendation == "TAKE_PARTIAL_PROFIT":
            reason += " (perfil agresivo: mantener exposición)"

        # Calcular sugerencia de reducción si aplica
        suggested_action: dict[str, Any] = {}
        if "TAKE_PARTIAL_PROFIT" in recommendation or "SELL" in recommendation:
            if current_allocation > max_alloc:
                reduction = current_allocation - max_alloc
                suggested_action["suggestedReductionPercent"] = round(reduction, 1)
            else:
                suggested_action["suggestedReductionPercent"] = 10.0

        if "BUY" in recommendation:
            target_alloc = min(max_alloc, max_alloc - current_allocation)
            suggested_action["suggestedAllocationPercent"] = round(target_alloc, 1)

        return PersonalRecommendation(
            user_id_hash=portfolio.user_id_hash,
            asset=asset,
            market_decision=market_decision,
            personal_recommendation=recommendation,
            reason=reason,
            suggested_action=suggested_action,
            confidence=confidence,
        )

    def match_multiple_signals(
        self,
        signals: list[dict[str, Any]],
        portfolio: UserPortfolio,
    ) -> list[PersonalRecommendation]:
        """Genera recomendaciones para múltiples señales."""
        return [
            self.match_signals_to_user(signal, portfolio)
            for signal in signals
        ]


# Singleton
_matcher: PortfolioMatcher | None = None


def get_portfolio_matcher() -> PortfolioMatcher:
    global _matcher
    if _matcher is None:
        _matcher = PortfolioMatcher()
    return _matcher
