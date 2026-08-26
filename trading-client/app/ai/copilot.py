"""Alvora Copilot — unified AI layer that merges the autonomous agent and advisor chat.

This service provides a single entry point for all AI interactions:
- /chat — conversational advisor (delegates to alvora_chat with unified context)
- /suggest — proactive suggestions based on unified portfolio + market state
- /analyze-position — deep analysis of a single position
- /quick-action — one-click AI actions (rebalance, risk check, opportunity scan)

The Copilot integrates data from:
- PortfolioAggregator (F1.2) for unified multi-broker context
- IntelligenceProvider for market state (Fear & Greed, dominance, regime)
- AI agent for trade decisions and position analysis
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.ai.alvora import alvora_chat, parse_actions
from app.ai.alvora_context import build_alvora_context
from app.database.session import SessionLocal

logger = logging.getLogger(__name__)


def copilot_chat(user_id: int, message: str, conversation_id: int | None = None) -> dict:
    """Unified chat endpoint — delegates to Alvora with enriched context.

    The context now includes unified portfolio data from all connected brokers
    (via PortfolioAggregator), not just the first broker.
    """
    return alvora_chat(user_id, message, conversation_id)


def copilot_suggest(user_id: int) -> dict:
    """Generate proactive suggestions based on the user's unified portfolio.

    Returns a list of suggestions, each with:
    - type: "rebalance" | "risk_warning" | "opportunity" | "close_position" | "adjust_sl_tp"
    - priority: "high" | "medium" | "low"
    - title: short description
    - detail: longer explanation
    - action: optional action payload (for confirmation cards)
    """
    suggestions: list[dict[str, Any]] = []

    try:
        from app.services.portfolio_aggregator import (
            get_unified_portfolio_overview,
            get_concentration_analysis,
        )

        overview = get_unified_portfolio_overview(user_id)
        concentration = get_concentration_analysis(user_id)

        # 1. Concentration warnings
        for warning in concentration.get("warnings", []):
            suggestions.append({
                "type": "risk_warning",
                "priority": warning.get("level", "medium"),
                "title": warning.get("message", "Concentración detectada"),
                "detail": "Revisa tu distribución para reducir riesgo.",
                "action": None,
            })

        # 2. Position P&L analysis
        positions = overview.get("positions", {}).get("positions", [])
        for pos in positions:
            pnl = pos.get("unrealized_pnl", 0)
            pnl_pct = pos.get("unrealized_pnl_pct", 0)

            # Large negative PnL — suggest closing or setting SL
            if pnl_pct < -10:
                suggestions.append({
                    "type": "close_position",
                    "priority": "high" if pnl_pct < -20 else "medium",
                    "title": f"{pos['symbol']} está perdiendo {pnl_pct:.1f}%",
                    "detail": f"P&L no realizado: ${pnl:.2f}. Considera cerrar o ajustar stop-loss.",
                    "action": {
                        "type": "close_position",
                        "params": {
                            "symbol": pos["symbol"],
                            "broker_id": pos["broker_id"],
                            "quantity": pos["quantity"],
                        },
                    },
                })
            # Large positive PnL — suggest taking profits
            elif pnl_pct > 20:
                suggestions.append({
                    "type": "adjust_sl_tp",
                    "priority": "medium",
                    "title": f"{pos['symbol']} ganando {pnl_pct:.1f}% — considera tomar ganancias",
                    "detail": f"P&L no realizado: ${pnl:.2f}. Ajusta tu take-profit o vende parcial.",
                    "action": {
                        "type": "set_take_profit",
                        "params": {
                            "symbol": pos["symbol"],
                            "broker_id": pos["broker_id"],
                        },
                    },
                })

        # 3. Stablecoin-heavy portfolio — suggest deploying capital
        stable_usd = concentration.get("by_venue", {}).get("stablecoins", 0)
        total_usd = overview.get("total_usd", 0)
        if total_usd > 0 and stable_usd / total_usd > 0.6:
            suggestions.append({
                "type": "opportunity",
                "priority": "low",
                "title": f"El {stable_usd / total_usd * 100:.0f}% de tu portfolio está en stablecoins",
                "detail": "Tienes capital disponible para invertir. ¿Quieres ver oportunidades?",
                "action": {
                    "type": "scan_opportunities",
                    "params": {},
                },
            })

        # 4. No positions — suggest getting started
        if overview.get("position_count", 0) == 0 and total_usd > 100:
            suggestions.append({
                "type": "opportunity",
                "priority": "low",
                "title": "No tienes posiciones abiertas",
                "detail": f"Tienes ${total_usd:.2f} disponible. ¿Quieres explorar oportunidades de trading?",
                "action": {
                    "type": "scan_opportunities",
                    "params": {},
                },
            })

    except Exception as exc:
        logger.warning("Copilot suggest error: %s", exc)
        suggestions.append({
            "type": "risk_warning",
            "priority": "low",
            "title": "No pude analizar tu portfolio completamente",
            "detail": f"Error: {exc}",
            "action": None,
        })

    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    suggestions.sort(key=lambda s: priority_order.get(s.get("priority", "low"), 3))

    return {
        "suggestions": suggestions,
        "count": len(suggestions),
        "generated_at": datetime.now(tz=UTC).isoformat(),
    }


def copilot_analyze_position(user_id: int, symbol: str, broker_id: str | None = None) -> dict:
    """Deep analysis of a single position using AI.

    Returns AI-generated analysis with:
    - market_overview: current market context
    - analysis: detailed analysis of the position
    - suggestion: what to do (hold, close, adjust SL/TP)
    - confidence: 0-1
    - reason: explanation
    """
    try:
        from app.services.portfolio_aggregator import get_unified_positions

        positions_data = get_unified_positions(user_id)

        # Find the position
        target_pos = None
        for pos in positions_data["positions"]:
            if pos["symbol"] == symbol or pos["symbol"].startswith(symbol + "/"):
                if broker_id is None or pos["broker_id"] == broker_id:
                    target_pos = pos
                    break

        if not target_pos:
            return {"error": f"Posición {symbol} no encontrada"}

        # Build a focused prompt for the AI
        pnl = target_pos.get("unrealized_pnl", 0)
        pnl_pct = target_pos.get("unrealized_pnl_pct", 0)
        entry = target_pos.get("entry_price", 0)
        current = target_pos.get("current_price", 0)
        qty = target_pos.get("quantity", 0)
        side = target_pos.get("side", "long")
        leverage = target_pos.get("leverage", 1)

        prompt = (
            f"Analiza mi posición de {symbol} en {target_pos['broker_name']}:\n"
            f"- Side: {side}\n"
            f"- Cantidad: {qty}\n"
            f"- Precio de entrada: ${entry}\n"
            f"- Precio actual: ${current}\n"
            f"- P&L no realizado: ${pnl:.2f} ({pnl_pct:.1f}%)\n"
            f"- Apalancamiento: {leverage}x\n\n"
            f"¿Debería mantener, cerrar o ajustar stop-loss/take-profit? "
            f"Dame tu análisis detallado y una recomendación clara."
        )

        # Delegate to Alvora for the AI analysis
        result = alvora_chat(user_id, prompt)

        return {
            "symbol": symbol,
            "position": target_pos,
            "analysis": result.get("reply", ""),
            "actions": result.get("actions", []),
            "conversation_id": result.get("conversation_id"),
            "error": result.get("error"),
        }
    except Exception as exc:
        logger.error("Copilot analyze position error: %s", exc)
        return {"error": str(exc)}


def copilot_quick_action(user_id: int, action: str) -> dict:
    """Execute a quick AI action.

    Actions:
    - "rebalance" — suggest portfolio rebalancing
    - "risk_check" — full risk assessment
    - "opportunity_scan" — scan for trading opportunities
    - "close_all_review" — review all positions for potential closure
    """
    prompts = {
        "rebalance": (
            "Analiza mi portfolio unificado y sugiere un rebalanceo. "
            "¿Qué porcentaje debería tener en cada asset? ¿Qué posiciones "
            "debería reducir o aumentar? Dame un plan concreto."
        ),
        "risk_check": (
            "Haz un chequeo completo de riesgo de mi portfolio. "
            "Analiza: concentración por asset, concentración por broker, "
            "exposición neta, apalancamiento, y si tengo stop-loss configurado "
            "en todas mis posiciones. ¿Hay algún riesgo urgente?"
        ),
        "opportunity_scan": (
            "Escanea el mercado y dame 3 oportunidades de trading concretas "
            "que encajen con mi perfil. Para cada una: símbolo, razón, "
            "punto de entrada, stop-loss y take-profit sugeridos."
        ),
        "close_all_review": (
            "Revisa todas mis posiciones abiertas una por una. Para cada una, "
            "dime si debería mantenerla o cerrarla, y por qué. "
            "Prioriza las que están perdiendo más."
        ),
    }

    prompt = prompts.get(action)
    if not prompt:
        return {"error": f"Acción desconocida: {action}"}

    return alvora_chat(user_id, prompt)
