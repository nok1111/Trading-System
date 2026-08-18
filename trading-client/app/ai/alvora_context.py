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
    """Get open positions — tries broker API first (real-time), falls back to DB."""
    # ─── 1. Try broker API (real-time positions from Binance, etc.) ──────
    broker_positions = _get_broker_positions(db, user_id)
    if broker_positions:
        return broker_positions

    # ─── 2. Fallback: DB positions ───────────────────────────────────────
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


def _get_broker_positions(db, user_id: int) -> list[dict]:
    """Fetch real-time open positions from the user's connected broker.

    Uses the broker adapter directly (same logic as /api/broker/{id}/positions).
    Returns empty list if no broker connected or fetch fails.
    """
    try:
        from app.api.helpers import resolve_broker_credentials
        from app.brokers.registry import get_adapter
        from app.brokers.base import BrokerAdapter

        # Find the user's connected broker(s)
        from app.database.models.broker_account import BrokerAccount
        accounts = db.query(BrokerAccount).filter(
            BrokerAccount.user_id == user_id,
            BrokerAccount.status == "CONNECTED_TRADING",
        ).all()
        if not accounts:
            return []

        all_positions: list[dict] = []
        STABLECOINS = {"USDT", "BUSD", "USDC", "USD", "UST", "TUSD", "FDUSD", "USDP", "GUSD", "PAX", "EUR"}

        for acct in accounts:
            try:
                creds = resolve_broker_credentials(acct.broker_id, None)
                # resolve_broker_credentials uses current_user param, but we need user_id
                # Re-resolve manually since we have user_id not current_user
                if not creds:
                    # Manual resolution
                    from app.services.crypto import decrypt
                    if acct.api_key_enc:
                        creds = type("BrokerCredentials", (), {
                            "broker_id": acct.broker_id,
                            "api_key": decrypt(acct.api_key_enc),
                            "api_secret": decrypt(acct.api_secret_enc),
                            "passphrase": decrypt(acct.passphrase_enc) if acct.passphrase_enc else None,
                            "testnet": acct.environment in ("testnet", "demo", "sandbox"),
                        })()
                if not creds:
                    continue

                adapter = get_adapter(acct.broker_id, creds)

                # Try futures positions first
                broker_positions = adapter.get_open_positions()

                # If no futures, derive spot holdings from balances
                if not broker_positions:
                    try:
                        balances = adapter.get_account_balances()
                    except Exception:
                        balances = ()

                    for bal in balances:
                        if bal.asset in STABLECOINS or bal.total <= 0:
                            continue
                        current_price = None
                        for quote in ("USDT", "USDC", "USD", "FDUSD"):
                            try:
                                ticker = adapter.get_ticker(f"{bal.asset}/{quote}")
                                current_price = ticker.price
                                break
                            except Exception:
                                continue

                        entry_price = 0.0
                        try:
                            from app.brokers.models import normalize_symbol
                            sym = normalize_symbol(f"{bal.asset}/USDT")
                            trades = adapter.get_trades(symbol=sym, limit=500)
                            buy_trades = [t for t in trades if t.side.value == "buy"]
                            if buy_trades:
                                total_cost = sum(float(t.price) * float(t.quantity) for t in buy_trades)
                                total_qty = sum(float(t.quantity) for t in buy_trades)
                                if total_qty > 0:
                                    entry_price = round(total_cost / total_qty, 8)
                        except Exception:
                            pass

                        unrealized = 0.0
                        if entry_price > 0 and current_price:
                            unrealized = round((float(current_price) - entry_price) * float(bal.total), 8)

                        from app.brokers.models import Position as BrokerPosition
                        broker_positions = broker_positions + (
                            BrokerPosition(
                                symbol=f"{bal.asset}/USDT",
                                side="long",
                                quantity=bal.total,
                                entry_price=entry_price,
                                current_price=current_price,
                                unrealized_pnl=unrealized,
                                status="open",
                                strategy_name="spot_holding",
                                metadata={"source": "broker_balance", "asset": bal.asset},
                            ),
                        )

                for pos in broker_positions:
                    entry = _safe_float(pos.entry_price)
                    current = _safe_float(pos.current_price) or entry
                    pnl = _safe_float(pos.unrealized_pnl)
                    qty = _safe_float(pos.quantity)
                    pnl_pct = ((current - entry) / entry * 100) if entry > 0 else 0
                    all_positions.append({
                        "id": None,  # broker positions don't have DB id
                        "symbol": pos.symbol,
                        "side": pos.side,
                        "broker_id": acct.broker_id,
                        "quantity": qty,
                        "entry_price": entry,
                        "current_price": current,
                        "unrealized_pnl": pnl,
                        "pnl_pct": round(pnl_pct, 2),
                        "stop_loss": None,
                        "take_profit": None,
                        "auto_sell_enabled": True,
                        "strategy": pos.strategy_name,
                        "opened_at": "",
                        "source": "broker",  # not in DB — can't set SL/TP directly
                    })
            except Exception as exc:
                logger.warning("Alvora context: broker positions for %s failed: %s", acct.broker_id, exc)
                continue

        return all_positions
    except Exception as exc:
        logger.warning("Alvora context: broker positions failed: %s", exc)
        return []


def _get_account_snapshot(db, user_id: int) -> dict | None:
    """Get account snapshot — tries DB first, falls back to broker balance API."""
    # ─── 1. Try DB snapshot ──────────────────────────────────────────────
    try:
        from app.database.models.account_snapshot import AccountSnapshot
        row = (
            db.query(AccountSnapshot)
            .filter(AccountSnapshot.user_id == user_id)
            .order_by(AccountSnapshot.timestamp.desc())
            .first()
        )
        if row:
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
        pass

    # ─── 2. Fallback: live broker balance ────────────────────────────────
    try:
        from app.database.models.broker_account import BrokerAccount
        from app.api.helpers import resolve_broker_credentials
        from app.brokers.registry import get_adapter
        from app.services.crypto import decrypt

        accounts = db.query(BrokerAccount).filter(
            BrokerAccount.user_id == user_id,
            BrokerAccount.status == "CONNECTED_TRADING",
        ).all()
        if not accounts:
            return None

        acct = accounts[0]
        creds = type("BrokerCredentials", (), {
            "broker_id": acct.broker_id,
            "api_key": decrypt(acct.api_key_enc),
            "api_secret": decrypt(acct.api_secret_enc),
            "passphrase": decrypt(acct.passphrase_enc) if acct.passphrase_enc else None,
            "testnet": acct.environment in ("testnet", "demo", "sandbox"),
        })()
        adapter = get_adapter(acct.broker_id, creds)

        balances = adapter.get_account_balances()
        STABLECOINS = {"USDT", "BUSD", "USDC", "USD", "FDUSD", "EUR"}
        cash = 0.0
        total_asset_value = 0.0
        for bal in balances:
            if bal.asset in STABLECOINS:
                cash += _safe_float(bal.total)
            else:
                # Estimate USD value
                price = 0.0
                for quote in ("USDT", "USDC", "USD"):
                    try:
                        ticker = adapter.get_ticker(f"{bal.asset}/{quote}")
                        price = _safe_float(ticker.price)
                        break
                    except Exception:
                        continue
                total_asset_value += _safe_float(bal.total) * price

        equity = cash + total_asset_value
        return {
            "broker_id": acct.broker_id,
            "cash": round(cash, 2),
            "equity": round(equity, 2),
            "buying_power": round(cash, 2),
            "total_pnl": 0.0,
            "daily_pnl": 0.0,
            "open_positions_count": 0,
            "timestamp": "",
        }
    except Exception as exc:
        logger.warning("Alvora context: broker balance fallback failed: %s", exc)
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
            pos_id = p["id"] if p["id"] else "sin_id"
            source_tag = " [spot broker, sin ID en DB]" if not p["id"] else ""
            lines.append(
                f"  - #{pos_id} {p['symbol']} {p['side']} qty={p['quantity']:.6f} "
                f"entry={p['entry_price']:.4f} current={p['current_price']:.4f} "
                f"P&L={pnl_sign}{_fmt_usd(p['unrealized_pnl'])} ({p['pnl_pct']:+.1f}%) {sl} {tp} "
                f"auto_sell={'si' if p['auto_sell_enabled'] else 'no'} [{p['broker_id']}]{source_tag}"
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
