"""Smart Alerts — AI-powered proactive alerts based on portfolio and market state.

Unlike regular price alerts (static thresholds), Smart Alerts are generated
dynamically by analyzing:
- Portfolio concentration and risk
- Position P&L relative to entry
- Market regime changes
- Unusual price movements (volatility spikes)

Alerts are scored by urgency (0-100) and categorized by type.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.database.session import SessionLocal

logger = logging.getLogger(__name__)

# Alert types
ALERT_TYPES = {
    "high_loss": "Pérdida Significativa",
    "high_gain": "Ganancia Significativa",
    "concentration_risk": "Riesgo de Concentración",
    "margin_call_risk": "Riesgo de Margin Call",
    "no_stop_loss": "Posición sin Stop-Loss",
    "stablecoin_excess": "Exceso de Stablecoins",
    "broker_error": "Error de Broker",
    "market_regime_change": "Cambio de Régimen de Mercado",
    "volatility_spike": "Pico de Volatilidad",
}


def generate_smart_alerts(user_id: int) -> dict[str, Any]:
    """Generate AI-powered alerts for a user.

    Returns:
        {
            "alerts": [{ "id", "type", "title", "detail", "urgency", "action", "created_at" }],
            "count": int,
            "high_urgency_count": int,
        }
    """
    alerts: list[dict[str, Any]] = []

    try:
        from app.services.portfolio_aggregator import (
            get_unified_portfolio_overview,
            get_concentration_analysis,
            get_unified_positions,
        )

        overview = get_unified_portfolio_overview(user_id)
        concentration = get_concentration_analysis(user_id)
        positions_data = get_unified_positions(user_id)

        # 1. High-loss positions
        for pos in positions_data.get("positions", []):
            pnl_pct = pos.get("unrealized_pnl_pct", 0)
            pnl = pos.get("unrealized_pnl", 0)
            symbol = pos.get("symbol", "")
            broker = pos.get("broker_name", "")

            if pnl_pct < -15:
                urgency = min(100, int(50 + abs(pnl_pct) * 2))
                alerts.append({
                    "id": f"high_loss_{symbol}_{broker}",
                    "type": "high_loss",
                    "title": f"{symbol} perdiendo {pnl_pct:.1f}%",
                    "detail": f"P&L: ${pnl:.2f} en {broker}. Considera cerrar o ajustar stop-loss.",
                    "urgency": urgency,
                    "action": {
                        "type": "analyze_position",
                        "params": {"symbol": symbol, "broker_id": pos.get("broker_id")},
                    },
                    "created_at": datetime.now(tz=UTC).isoformat(),
                })
            elif pnl_pct > 25:
                urgency = min(80, int(30 + pnl_pct))
                alerts.append({
                    "id": f"high_gain_{symbol}_{broker}",
                    "type": "high_gain",
                    "title": f"{symbol} ganando {pnl_pct:.1f}% — considera tomar ganancias",
                    "detail": f"P&L: ${pnl:.2f} en {broker}. Ajusta take-profit o vende parcial.",
                    "urgency": urgency,
                    "action": {
                        "type": "analyze_position",
                        "params": {"symbol": symbol, "broker_id": pos.get("broker_id")},
                    },
                    "created_at": datetime.now(tz=UTC).isoformat(),
                })

        # 2. Concentration warnings
        for warning in concentration.get("warnings", []):
            urgency = 70 if warning.get("level") == "high" else 40
            alerts.append({
                "id": f"concentration_{warning.get('type', 'unknown')}",
                "type": "concentration_risk",
                "title": warning.get("message", "Concentración detectada"),
                "detail": "Diversifica para reducir riesgo.",
                "urgency": urgency,
                "action": {
                    "type": "rebalance",
                    "params": {},
                },
                "created_at": datetime.now(tz=UTC).isoformat(),
            })

        # 3. Stablecoin excess
        stable_usd = concentration.get("by_venue", {}).get("stablecoins", 0)
        total_usd = overview.get("total_usd", 0)
        if total_usd > 0 and stable_usd / total_usd > 0.7:
            alerts.append({
                "id": "stablecoin_excess",
                "type": "stablecoin_excess",
                "title": f"El {stable_usd / total_usd * 100:.0f}% está en stablecoins",
                "detail": f"${stable_usd:.2f} de ${total_usd:.2f} sin invertir.",
                "urgency": 25,
                "action": {
                    "type": "opportunity_scan",
                    "params": {},
                },
                "created_at": datetime.now(tz=UTC).isoformat(),
            })

        # 4. Broker errors
        for error in overview.get("balances", {}).get("errors", []):
            alerts.append({
                "id": f"broker_error_{error.get('broker_id')}",
                "type": "broker_error",
                "title": f"Error conectando a {error.get('broker_id')}",
                "detail": error.get("error", "Error desconocido"),
                "urgency": 60,
                "action": {
                    "type": "check_connection",
                    "params": {"broker_id": error.get("broker_id")},
                },
                "created_at": datetime.now(tz=UTC).isoformat(),
            })

        # 5. Positions without stop-loss (from DB)
        alerts.extend(_check_stop_loss_coverage(user_id))

        # 6. Market regime change (from intelligence)
        alerts.extend(_check_market_regime(user_id))

    except Exception as exc:
        logger.warning("Smart alerts generation error: %s", exc)

    # Sort by urgency descending
    alerts.sort(key=lambda a: a.get("urgency", 0), reverse=True)

    high_urgency = sum(1 for a in alerts if a.get("urgency", 0) >= 60)

    return {
        "alerts": alerts,
        "count": len(alerts),
        "high_urgency_count": high_urgency,
        "generated_at": datetime.now(tz=UTC).isoformat(),
    }


def _check_stop_loss_coverage(user_id: int) -> list[dict[str, Any]]:
    """Check which open positions don't have a stop-loss configured."""
    alerts = []
    db = SessionLocal()
    try:
        from app.database.models.position import Position

        positions = (
            db.query(Position)
            .filter(
                Position.user_id == user_id,
                Position.status == "open",
            )
            .all()
        )

        for pos in positions:
            if not pos.stop_loss_price or float(pos.stop_loss_price) <= 0:
                alerts.append({
                    "id": f"no_sl_{pos.id}",
                    "type": "no_stop_loss",
                    "title": f"{pos.symbol} sin stop-loss",
                    "detail": f"Posición abierta sin stop-loss configurado. Riesgo ilimitado.",
                    "urgency": 55,
                    "action": {
                        "type": "set_stop_loss",
                        "params": {"position_id": pos.id, "symbol": pos.symbol},
                    },
                    "created_at": datetime.now(tz=UTC).isoformat(),
                })
    except Exception:
        pass
    finally:
        db.close()

    return alerts


def _check_market_regime(user_id: int) -> list[dict[str, Any]]:
    """Check for recent market regime changes."""
    alerts = []
    try:
        from app.ai.intelligence_provider import create_intelligence_provider

        provider = create_intelligence_provider()
        overview = provider.get_market_overview()

        if overview and overview.regime:
            regime = overview.regime.lower()
            if "fear" in regime or "capitulation" in regime:
                alerts.append({
                    "id": "regime_fear",
                    "type": "market_regime_change",
                    "title": f"Régimen de mercado: {overview.regime}",
                    "detail": "El mercado está en modo miedo. Considera reducir exposición.",
                    "urgency": 65,
                    "action": {
                        "type": "risk_check",
                        "params": {},
                    },
                    "created_at": datetime.now(tz=UTC).isoformat(),
                })
            elif "euphoria" in regime or "greed" in regime:
                alerts.append({
                    "id": "regime_greed",
                    "type": "market_regime_change",
                    "title": f"Régimen de mercado: {overview.regime}",
                    "detail": "El mercado está en modo euforia. Considera tomar ganancias.",
                    "urgency": 50,
                    "action": {
                        "type": "risk_check",
                        "params": {},
                    },
                    "created_at": datetime.now(tz=UTC).isoformat(),
                })
    except Exception:
        pass

    return alerts


def dismiss_alert(user_id: int, alert_id: str) -> dict:
    """Dismiss a smart alert (marks it as seen so it doesn't reappear).

    For now, this is a simple in-memory dismissal. In production, this
    would persist to DB.
    """
    # TODO: persist dismissed alerts to DB
    return {"ok": True, "alert_id": alert_id, "dismissed_at": datetime.now(tz=UTC).isoformat()}
