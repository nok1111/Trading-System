"""Alvora context builder — assembles real-time user + market context for the advisor chat.

Gathers data from DB and services directly (no HTTP recursion):
- User profile (risk tolerance, experience, goal, strategies)
- Linked broker accounts (metadata only, no keys)
- Open positions
- Latest account snapshot (balance, equity, PnL)
- Market state (Fear & Greed, BTC dominance, regime)
- Recent AI recommendations

The result is a formatted text block injected into the Alvora system prompt.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.database.session import SessionLocal

logger = logging.getLogger(__name__)


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _fmt_usd(v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"${v / 1_000:.1f}K"
    return f"${v:.2f}"


def _get_user_profile(db, user_id: int) -> dict | None:
    try:
        from app.database.models.user_profile import UserProfile
        prof = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        return prof.to_dict() if prof else None
    except Exception:
        return None


def _get_broker_accounts(db, user_id: int) -> list[dict]:
    try:
        from app.database.models.broker_account import BrokerAccount
        rows = db.query(BrokerAccount).filter(BrokerAccount.user_id == user_id).all()
        return [
            {
                "broker_id": r.broker_id,
                "display_name": r.display_name or r.broker_id,
                "environment": r.environment,
                "status": r.status,
                "permissions_trade": r.permissions_trade,
            }
            for r in rows
        ]
    except Exception:
        return []


def _get_open_positions(db, user_id: int) -> list[dict]:
    try:
        from app.database.models.position import Position
        rows = (
            db.query(Position)
            .filter(Position.status == "open", Position.user_id == user_id)
            .order_by(Position.opened_at.desc())
            .limit(30)
            .all()
        )
        result = []
        for p in rows:
            entry = _safe_float(p.entry_price)
            current = _safe_float(p.current_price) or entry
            pnl = _safe_float(p.unrealized_pnl)
            qty = _safe_float(p.quantity)
            pnl_pct = ((current - entry) / entry * 100) if entry > 0 else 0
            result.append({
                "id": p.id,
                "symbol": p.symbol,
                "side": p.side,
                "broker_id": p.broker_id,
                "quantity": qty,
                "entry_price": entry,
                "current_price": current,
                "unrealized_pnl": pnl,
                "pnl_pct": round(pnl_pct, 2),
                "stop_loss": _safe_float(p.stop_loss) if p.stop_loss else None,
                "take_profit": _safe_float(p.take_profit) if p.take_profit else None,
                "auto_sell_enabled": p.auto_sell_enabled,
                "strategy": p.strategy_name,
                "opened_at": p.opened_at.isoformat() if p.opened_at else "",
            })
        return result
    except Exception as exc:
        logger.warning("Alvora context: positions query failed: %s", exc)
        return []


def _get_account_snapshot(db, user_id: int) -> dict | None:
    try:
        from app.database.models.account_snapshot import AccountSnapshot
        row = (
            db.query(AccountSnapshot)
            .filter(AccountSnapshot.user_id == user_id)
            .order_by(AccountSnapshot.timestamp.desc())
            .first()
        )
        if not row:
            return None
        return {
            "broker_id": row.broker_id,
            "cash": _safe_float(row.cash),
            "equity": _safe_float(row.equity),
            "buying_power": _safe_float(row.buying_power),
            "total_pnl": _safe_float(row.total_pnl),
            "daily_pnl": _safe_float(row.daily_pnl),
            "open_positions_count": row.open_positions_count or 0,
            "timestamp": row.timestamp.isoformat() if row.timestamp else "",
        }
    except Exception:
        return None


def _get_market_state() -> dict:
    """Fear & Greed, BTC dominance, regime — via market_data_service (cached, no auth)."""
    result: dict[str, Any] = {}
    try:
        from app.services.market_data_service import get_market_data_service
        svc = get_market_data_service()
        try:
            fg = svc.get_fear_greed(limit=1)
            if fg:
                result["fear_greed"] = {"value": int(fg[0].get("value", 50)), "classification": fg[0].get("value_classification", "Neutral")}
        except Exception:
            pass
        try:
            stats = svc.get_global_crypto_stats()
            mcap_pct = stats.get("market_cap_percentage", {})
            result["dominance"] = {
                "btc": round(mcap_pct.get("btc", 0), 1),
                "eth": round(mcap_pct.get("eth", 0), 1),
                "market_cap_change_24h": round(stats.get("market_cap_change_percentage_24h_usd", 0), 2),
            }
        except Exception:
            pass
    except Exception as exc:
        logger.warning("Alvora context: market state failed: %s", exc)
    return result


def _get_recent_recommendations(db, user_id: int, limit: int = 5) -> list[dict]:
    try:
        from app.database.models.ai_recommendation import AIRecommendation
        rows = (
            db.query(AIRecommendation)
            .filter(AIRecommendation.user_id == user_id)
            .order_by(AIRecommendation.timestamp.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "asset": r.asset,
                "action_type": r.action_type,
                "confidence": _safe_float(r.confidence),
                "reason": r.reason or "",
                "status": r.status,
                "timestamp": r.timestamp.isoformat() if r.timestamp else "",
            }
            for r in rows
        ]
    except Exception:
        return []


def build_alvora_context(user_id: int) -> str:
    """Assemble the full context block for the Alvora system prompt.

    Returns a formatted text string. Empty sections are omitted.
    """
    db = SessionLocal()
    try:
        profile = _get_user_profile(db, user_id)
        brokers = _get_broker_accounts(db, user_id)
        positions = _get_open_positions(db, user_id)
        snapshot = _get_account_snapshot(db, user_id)
        recommendations = _get_recent_recommendations(db, user_id)
    finally:
        db.close()

    market = _get_market_state()

    lines: list[str] = ["=== CONTEXTO ==="]

    # Profile
    if profile:
        risk_map = {"conservative": "conservador", "moderate": "moderado", "aggressive": "agresivo"}
        exp_map = {"beginner": "principiante", "intermediate": "intermedio", "advanced": "avanzado"}
        goal_map = {"growth": "crecimiento", "income": "ingresos", "preservation": "preservacion", "speculation": "especulacion"}
        strategies = profile.get("preferred_strategies", [])
        lines.append(f"PERFIL: {risk_map.get(profile.get('risk_tolerance', ''), profile.get('risk_tolerance', ''))}, "
                     f"experiencia {exp_map.get(profile.get('experience_level', ''), profile.get('experience_level', ''))}, "
                     f"objetivo {goal_map.get(profile.get('trading_goal', ''), profile.get('trading_goal', ''))}, "
                     f"estrategias: {', '.join(strategies) if strategies else 'swing'}, "
                     f"capital: {profile.get('capital_range', 'no especificado')}")
    else:
        lines.append("PERFIL: no configurado (onboarding pendiente)")

    # Brokers
    if brokers:
        connected = [b for b in brokers if b["status"] == "active"]
        broker_strs = [f"{b['display_name']} ({b['environment']}, trade={'si' if b['permissions_trade'] else 'no'})" for b in brokers]
        lines.append(f"BROKERS VINCULADOS: {len(brokers)} ({len(connected)} activos) — {', '.join(broker_strs)}")
    else:
        lines.append("BROKERS VINCULADOS: ninguno (el usuario no ha conectado un broker)")

    # Account snapshot
    if snapshot:
        lines.append(f"CUENTA ({snapshot['broker_id']}): equity {_fmt_usd(snapshot['equity'])}, "
                     f"cash {_fmt_usd(snapshot['cash'])}, "
                     f"P&L total {_fmt_usd(snapshot['total_pnl'])}, "
                     f"P&L hoy {_fmt_usd(snapshot['daily_pnl'])}, "
                     f"posiciones abiertas: {snapshot['open_positions_count']}")

    # Positions
    if positions:
        total_pnl = sum(p["unrealized_pnl"] for p in positions)
        lines.append(f"POSICIONES ABIERTAS ({len(positions)}), P&L no realizado total: {_fmt_usd(total_pnl)}:")
        for p in positions[:15]:
            sl = f"SL={p['stop_loss']:.2f}" if p["stop_loss"] else "SL=none"
            tp = f"TP={p['take_profit']:.2f}" if p["take_profit"] else "TP=none"
            pnl_sign = "+" if p["unrealized_pnl"] >= 0 else ""
            lines.append(
                f"  - #{p['id']} {p['symbol']} {p['side']} qty={p['quantity']:.6f} "
                f"entry={p['entry_price']:.4f} current={p['current_price']:.4f} "
                f"P&L={pnl_sign}{_fmt_usd(p['unrealized_pnl'])} ({p['pnl_pct']:+.1f}%) {sl} {tp} "
                f"auto_sell={'si' if p['auto_sell_enabled'] else 'no'} [{p['broker_id']}]"
            )
        if len(positions) > 15:
            lines.append(f"  ... y {len(positions) - 15} mas")
    else:
        lines.append("POSICIONES ABIERTAS: ninguna")

    # Market state
    if market:
        parts = []
        if "fear_greed" in market:
            fg = market["fear_greed"]
            parts.append(f"Fear&Greed {fg['value']} ({fg['classification']})")
        if "dominance" in market:
            dom = market["dominance"]
            parts.append(f"BTC dominance {dom['btc']:.1f}%, ETH {dom['eth']:.1f}%, mcap 24h {dom['market_cap_change_24h']:+.1f}%")
        if parts:
            lines.append("MERCADO: " + " | ".join(parts))

    # Recommendations
    if recommendations:
        pending = [r for r in recommendations if r["status"] == "pending"]
        if pending:
            rec_strs = [f"{r['action_type']} {r['asset']} (conf {r['confidence']:.2f})" for r in pending[:3]]
            lines.append(f"RECOMENDACIONES RECIENTES PENDIENTES: {', '.join(rec_strs)}")

    lines.append("=== FIN CONTEXTO ===")
    return "\n".join(lines)
