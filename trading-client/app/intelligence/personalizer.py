"""Personalizer — builds user-specific dashboard data without LLM.

Combines Event Journal entries with user portfolio data to produce
the 'Since Last Visit', 'Today Priorities', and 'AI Activity' payloads.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.intelligence_event import IntelligenceEvent
from app.database.models.position import Position
from app.database.models.signal import Signal
from app.database.models.user_settings import UserSettings
from app.intelligence.event_journal import EventJournal

# Icon + color mapping for frontend
EVENT_ICONS: dict[str, str] = {
    "new_opportunity": "🟢",
    "invalidated": "🔴",
    "consensus_change": "🟡",
    "institutional_flow": "🔵",
    "risk_change": "🟠",
    "portfolio_change": "⚪",
    "macro_event": "⚫",
    "news_high_impact": "📰",
    "whale_move": "🐋",
    "funding_shift": "💰",
}

EVENT_COLORS: dict[str, str] = {
    "new_opportunity": "green",
    "invalidated": "red",
    "consensus_change": "yellow",
    "institutional_flow": "blue",
    "risk_change": "orange",
    "portfolio_change": "white",
    "macro_event": "black",
    "news_high_impact": "blue",
    "whale_move": "blue",
    "funding_shift": "yellow",
}

# Map AI agent log phases to agent names
PHASE_TO_AGENT: dict[str, str] = {
    "grant_authorized": "Consensus",
    "intelligence_fetch": "Consensus",
    "alert": "News",
    "portfolio_match": "Consensus",
    "no_signals": "Consensus",
    "no_actions": "Consensus",
    "trailing_update": "Technical",
    "auto_stop_loss": "Technical",
    "auto_take_profit": "Technical",
    "auto_trailing": "Technical",
    "auto_breakeven": "Technical",
    "start": "Consensus",
    "end": "Consensus",
    "gathering": "Technical",
    "analyzing": "Consensus",
    "decision": "Consensus",
    "hold": "Consensus",
    "skip": "Consensus",
    "proposed": "Consensus",
    "context": "Technical",
    "error": "System",
}


def _get_greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Buenos días"
    elif hour < 19:
        return "Buenas tardes"
    return "Buenas noches"


def _get_user_assets(session: Session, user_id: int) -> list[str]:
    """Get asset symbols from user's open positions (e.g. ['BTC', 'ETH', 'SOL'])."""
    positions = session.execute(
        select(Position).where(Position.status == "open")
    ).scalars().all()
    assets = []
    for p in positions:
        symbol = p.symbol.upper().replace("USDT", "").replace("USDC", "")
        if symbol:
            assets.append(symbol)
    return list(set(assets))


def _get_last_login(session: Session, user_id: int) -> datetime:
    """Get user's last login timestamp, defaulting to 24h ago."""
    settings_row = session.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    ).scalars().first()
    if settings_row and settings_row.last_login_at:
        return settings_row.last_login_at
    return datetime.now(UTC) - timedelta(hours=24)


def _update_last_login(session: Session, user_id: int) -> None:
    """Update user's last_login_at to now."""
    settings_row = session.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    ).scalars().first()
    if settings_row:
        settings_row.last_login_at = datetime.now(UTC)
        session.commit()


def _format_change(event: IntelligenceEvent) -> dict[str, Any]:
    """Format an IntelligenceEvent for the frontend ChangeItem."""
    return {
        "id": f"evt-{event.id}",
        "type": event.event_type,
        "icon": EVENT_ICONS.get(event.event_type, "ℹ️"),
        "color": EVENT_COLORS.get(event.event_type, "gray"),
        "title": event.title,
        "detail": event.detail or "",
        "timestamp": event.created_at.isoformat() if event.created_at else "",
    }


def get_changes_since_last_login(session: Session, user_id: int) -> dict[str, Any]:
    """Build the 'Since Last Visit' payload for a user."""
    last_login = _get_last_login(session, user_id)
    # SQLite stores naive datetimes — make last_login naive for comparison
    last_login_naive = last_login.replace(tzinfo=None) if last_login.tzinfo else last_login
    user_assets = _get_user_assets(session, user_id)

    # 1. Events from journal
    journal = EventJournal(session)
    events = journal.get_for_user(since=last_login, user_assets=user_assets, limit=20)

    # 2. Portfolio changes (deterministic)
    positions = list(
        session.execute(
            select(Position).where(Position.status == "open")
        ).scalars().all()
    )
    portfolio_changes: list[dict[str, Any]] = []
    for p in positions:
        if p.updated_at and p.updated_at > last_login_naive:
            pnl = float(p.unrealized_pnl) if p.unrealized_pnl else 0.0
            asset = p.symbol.upper().replace("USDT", "").replace("USDC", "")
            portfolio_changes.append({
                "id": f"port-{p.id}",
                "type": "portfolio_change",
                "icon": "⚪",
                "color": "white",
                "title": f"{asset} posición actualizada",
                "detail": f"PnL: {pnl:+.2f} USDT",
                "timestamp": p.updated_at.isoformat() if p.updated_at else "",
            })

    # 3. Combine and sort by timestamp desc
    all_changes = [_format_change(e) for e in events] + portfolio_changes
    all_changes.sort(key=lambda c: c.get("timestamp", ""), reverse=True)

    # 4. To-review list
    to_review: list[dict[str, str]] = []
    for p in positions[:5]:
        asset = p.symbol.upper().replace("USDT", "").replace("USDC", "")
        to_review.append({"asset": asset, "reason": "Posición abierta"})

    # 5. Update last_login
    _update_last_login(session, user_id)

    hours = max(1, int((datetime.now(UTC) - last_login).total_seconds() / 3600))

    return {
        "lastLogin": last_login.isoformat(),
        "hoursSinceLogin": hours,
        "greeting": _get_greeting(),
        "changes": all_changes,
        "toReview": to_review,
    }


def get_today_priorities(session: Session, user_id: int) -> dict[str, Any]:
    """Build the 'Today Priorities' payload for a user."""
    positions = list(
        session.execute(
            select(Position).where(Position.status == "open")
        ).scalars().all()
    )

    # Recent signals from DB
    signals = list(
        session.execute(
            select(Signal).order_by(Signal.timestamp.desc()).limit(10)
        ).scalars().all()
    )

    priorities: list[dict[str, Any]] = []

    # From positions
    for pos in positions[:3]:
        asset = pos.symbol.upper().replace("USDT", "").replace("USDC", "")
        pnl_pct = 0.0
        if pos.entry_price and pos.current_price and float(pos.entry_price) > 0:
            pnl_pct = ((float(pos.current_price) - float(pos.entry_price)) / float(pos.entry_price)) * 100

        recommendation = "HOLD"
        if pnl_pct > 5:
            recommendation = "TAKE_PARTIAL_PROFIT"
        elif pnl_pct < -3:
            recommendation = "SELL"

        priorities.append({
            "id": f"pos-{pos.id}",
            "asset": asset,
            "recommendation": recommendation,
            "confidence": max(50, min(90, 70 + int(pnl_pct))),
            "risk": "medium",
            "mainReason": f"Posición abierta, PnL: {pnl_pct:+.1f}%",
            "expiresAt": None,
            "reasons": [
                {"label": "Technical", "confirmed": True},
                {"label": "On-chain", "confirmed": False},
                {"label": "News", "confirmed": False},
                {"label": "Macro", "confirmed": False},
            ],
        })

    # From recent signals (if we have room)
    if len(priorities) < 3:
        for sig in signals[:3 - len(priorities)]:
            asset = sig.symbol.upper().replace("USDT", "").replace("USDC", "")
            priorities.append({
                "id": f"sig-{sig.id}",
                "asset": asset,
                "recommendation": sig.signal_type if sig.signal_type in ("BUY", "SELL", "HOLD") else "HOLD",
                "confidence": int(float(sig.confidence) * 100) if sig.confidence else 50,
                "risk": "medium",
                "mainReason": sig.explanation or "Señal generada por estrategia",
                "expiresAt": None,
                "reasons": [
                    {"label": sig.strategy_name, "confirmed": True},
                    {"label": "On-chain", "confirmed": False},
                    {"label": "News", "confirmed": False},
                    {"label": "Macro", "confirmed": False},
                ],
            })

    return {"priorities": priorities}


def get_activity(session: Session, *, hours: int = 24, limit: int = 20) -> dict[str, Any]:
    """Build the 'AI Activity' timeline payload."""
    journal = EventJournal(session)
    events = journal.get_recent(hours=hours, limit=limit)

    if events:
        entries = []
        for e in events:
            entries.append({
                "id": f"evt-{e.id}",
                "timestamp": e.created_at.isoformat() if e.created_at else "",
                "agent": e.agent_source,
                "action": e.title,
                "detail": e.detail or "",
            })
        return {"entries": entries}

    # Fallback: use AI agent logs if journal is empty
    try:
        from app.api.helpers import get_or_create_agent
        agent = get_or_create_agent()
        logs = agent.get_log(limit=limit)
        entries = []
        for i, log in enumerate(logs):
            phase = log.get("phase", "")
            agent_name = PHASE_TO_AGENT.get(phase, "Consensus")
            entries.append({
                "id": f"log-{i}",
                "timestamp": log.get("timestamp", datetime.now(UTC).isoformat()),
                "agent": agent_name,
                "action": log.get("message", ""),
                "detail": log.get("message", ""),
            })
        return {"entries": entries}
    except Exception:
        return {"entries": []}
