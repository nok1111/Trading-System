"""Position Reconciler — reconcilia posiciones en DB con el broker real.

Loop en background que cada N segundos:
1. Para cada usuario con broker conectado:
   a. Fetch get_open_positions() del broker (futures) o get_account_balances() (spot)
   b. Compara con posiciones "open" en DB
   c. Cierra posiciones DB que ya no existen en el broker (cerradas externamente)
   d. Actualiza entry_price, current_price, unrealized_pnl desde el broker
   e. Crea posiciones DB para posiciones del broker no registradas (abiertas externamente)
2. Actualiza last_sync_at en BrokerAccount
3. Registra resultados en log

Esto asegura que la DB siempre refleje el estado real del broker sin
intervención manual del usuario.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

# Intervalo default entre ciclos de reconciliación (segundos)
DEFAULT_RECONCILE_INTERVAL = 60


class PositionReconciler:
    """Reconcilia posiciones DB ↔ broker en background thread."""

    def __init__(self, interval: int = DEFAULT_RECONCILE_INTERVAL) -> None:
        self._interval = interval
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._running = False
        self._cycle_count = 0
        self._last_cycle_at: datetime | None = None
        self._last_result: dict[str, Any] = {}

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def last_cycle_at(self) -> datetime | None:
        return self._last_cycle_at

    @property
    def last_result(self) -> dict[str, Any]:
        return self._last_result

    def start(self) -> None:
        if self._running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="PositionReconciler")
        self._thread.start()
        self._running = True
        logger.info("PositionReconciler started (interval=%ds)", self._interval)

    def stop(self) -> None:
        self._stop_event.set()
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("PositionReconciler stopped")

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._run_cycle()
            except Exception as exc:
                logger.error("PositionReconciler cycle error: %s", exc)
            self._stop_event.wait(self._interval)

    def _run_cycle(self) -> None:
        self._cycle_count += 1
        self._last_cycle_at = datetime.now(tz=UTC)

        from app.database.session import SessionLocal
        from app.database.models.broker_account import BrokerAccount

        session = SessionLocal()
        try:
            # Get all connected broker accounts (any active status)
            accounts = session.query(BrokerAccount).filter(
                BrokerAccount.status.notin_(["pending_validation", "revoked", "error", "disconnected", ""]),
            ).all()

            if not accounts:
                self._last_result = {"cycle": self._cycle_count, "accounts": 0, "total_changes": 0}
                return

            total_closed = 0
            total_updated = 0
            total_created = 0
            per_broker: list[dict] = []

            for acct in accounts:
                try:
                    result = self._reconcile_account(session, acct)
                    total_closed += result.get("closed", 0)
                    total_updated += result.get("updated", 0)
                    total_created += result.get("created", 0)
                    per_broker.append(result)
                except Exception as exc:
                    logger.warning("Reconcile failed for %s user=%s: %s", acct.broker_id, acct.user_id, exc)
                    per_broker.append({
                        "broker_id": acct.broker_id,
                        "user_id": acct.user_id,
                        "error": str(exc),
                    })

            self._last_result = {
                "cycle": self._cycle_count,
                "accounts": len(accounts),
                "closed": total_closed,
                "updated": total_updated,
                "created": total_created,
                "total_changes": total_closed + total_updated + total_created,
                "per_broker": per_broker,
                "timestamp": self._last_cycle_at.isoformat(),
            }
        finally:
            session.close()

    def _reconcile_account(self, session, acct) -> dict:
        """Reconcile a single broker account. Returns summary dict."""
        from app.api.helpers import resolve_broker_credentials
        from app.brokers.registry import get_adapter
        from app.brokers.models import normalize_symbol
        from app.database.models.position import Position
        from app.services.auth import LocalUser

        # Build a minimal user object for credential resolution
        class _MinimalUser:
            def __init__(self, uid: int):
                self.id = uid

        user = _MinimalUser(acct.user_id)
        creds = resolve_broker_credentials(acct.broker_id, user)
        if not creds:
            return {"broker_id": acct.broker_id, "user_id": acct.user_id, "error": "no credentials"}

        adapter = get_adapter(acct.broker_id, creds)

        # Fetch real positions from broker
        broker_positions = adapter.get_open_positions()

        # For spot: derive holdings from balances (non-stablecoin)
        STABLECOINS = {"USDT", "BUSD", "USDC", "USD", "UST", "TUSD", "FDUSD", "USDP", "EUR"}
        if not broker_positions:
            try:
                balances = adapter.get_account_balances()
                for bal in balances:
                    if bal.asset in STABLECOINS or bal.total <= 0:
                        continue
                    current_price = None
                    for quote in ("USDT", "USDC", "USD"):
                        try:
                            ticker = adapter.get_ticker(f"{bal.asset}/{quote}")
                            current_price = ticker.price
                            break
                        except Exception:
                            continue
                    from app.brokers.models import Position as BrokerPosition
                    # Fetch entry price from trade history
                    entry_price = Decimal("0")
                    try:
                        sym = normalize_symbol(f"{bal.asset}/USDT")
                        trades = adapter.get_trades(symbol=sym, limit=500)
                        buy_trades = [t for t in trades if t.side.value == "buy"]
                        if buy_trades:
                            total_cost = sum(float(t.price) * float(t.quantity) for t in buy_trades)
                            total_qty = sum(float(t.quantity) for t in buy_trades)
                            if total_qty > 0:
                                entry_price = Decimal(str(round(total_cost / total_qty, 8)))
                    except Exception:
                        pass
                    unrealized = Decimal("0")
                    if entry_price > 0 and current_price:
                        unrealized = Decimal(str(round(
                            (float(current_price) - float(entry_price)) * float(bal.total), 8
                        )))
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
                            metadata={"source": "broker_balance"},
                        ),
                    )
            except Exception as exc:
                logger.debug("Spot holdings fetch failed for %s: %s", acct.broker_id, exc)

        # Build map of broker positions by symbol
        broker_map: dict[str, Any] = {}
        for bpos in broker_positions:
            sym = normalize_symbol(bpos.symbol)
            broker_map[sym] = bpos

        # Get DB positions for this user + broker
        db_positions = session.query(Position).filter(
            Position.status == "open",
            Position.user_id == acct.user_id,
            Position.broker_id == acct.broker_id,
        ).all()

        closed_count = 0
        updated_count = 0
        details: list[str] = []

        for p in db_positions:
            sym = normalize_symbol(p.symbol)
            bpos = broker_map.get(sym)

            # Skip short positions — they are simulated in DB and don't
            # correspond to actual broker holdings (Binance Spot has no shorts)
            if p.side == "short":
                continue

            if bpos is None:
                # Position in DB but NOT in broker → closed externally
                # Fetch current price for PnL calculation
                try:
                    ticker = adapter.get_ticker(sym)
                    close_price = float(ticker.price)
                except Exception:
                    close_price = float(p.current_price or p.entry_price or 0)

                entry = float(p.entry_price or 0)
                qty = float(p.quantity or 0)
                if p.side == "long":
                    realized = (close_price - entry) * qty
                else:
                    realized = (entry - close_price) * qty

                p.realized_pnl = Decimal(str(round(realized, 8)))
                p.current_price = Decimal(str(close_price))
                p.status = "closed"
                p.closed_at = datetime.now(tz=UTC)
                meta = p.metadata_json or {}
                meta["closed_by"] = "auto_reconcile"
                meta["close_reason"] = "not in broker"
                meta["reconciled_at"] = datetime.now(tz=UTC).isoformat()
                p.metadata_json = meta

                closed_count += 1
                details.append(f"Closed {sym}: not in broker (PnL={realized:.4f})")
            else:
                # Position exists in both → update with broker data
                changed = False
                if bpos.current_price and bpos.current_price != p.current_price:
                    p.current_price = bpos.current_price
                    changed = True
                if bpos.entry_price and bpos.entry_price > 0 and bpos.entry_price != p.entry_price:
                    p.entry_price = bpos.entry_price
                    changed = True
                if bpos.unrealized_pnl:
                    p.unrealized_pnl = bpos.unrealized_pnl
                    changed = True
                if bpos.quantity and bpos.quantity != p.quantity:
                    p.quantity = bpos.quantity
                    changed = True
                if changed:
                    meta = p.metadata_json or {}
                    meta["reconciled_at"] = datetime.now(tz=UTC).isoformat()
                    p.metadata_json = meta
                    updated_count += 1
                    details.append(f"Updated {sym}: entry/price/qty from broker")

        # Create DB positions for broker-only positions (opened externally)
        created_count = 0
        existing_symbols = {normalize_symbol(p.symbol) for p in db_positions}
        for sym, bpos in broker_map.items():
            if sym in existing_symbols:
                continue
            # Skip spot holdings with zero entry_price (can't calculate PnL)
            if bpos.metadata.get("source") == "broker_balance":
                continue
            new_pos = Position(
                user_id=acct.user_id,
                broker_id=acct.broker_id,
                symbol=sym,
                side=bpos.side,
                quantity=bpos.quantity,
                entry_price=bpos.entry_price,
                current_price=bpos.current_price,
                unrealized_pnl=bpos.unrealized_pnl,
                realized_pnl=Decimal("0"),
                stop_loss=None,
                take_profit=None,
                status="open",
                strategy_name=bpos.strategy_name or "broker_external",
                opened_at=bpos.opened_at or datetime.now(tz=UTC),
                metadata_json={
                    "source": "auto_reconcile",
                    "leverage": bpos.metadata.get("leverage"),
                    "liquidation_price": bpos.metadata.get("liquidation_price"),
                    "margin_mode": bpos.metadata.get("margin_mode"),
                    "created_at": datetime.now(tz=UTC).isoformat(),
                },
            )
            session.add(new_pos)
            created_count += 1
            details.append(f"Created {sym}: from broker (side={bpos.side}, qty={bpos.quantity})")

        # Update last_sync_at
        acct.last_sync_at = datetime.now(tz=UTC)
        session.commit()

        return {
            "broker_id": acct.broker_id,
            "user_id": acct.user_id,
            "closed": closed_count,
            "updated": updated_count,
            "created": created_count,
            "db_positions": len(db_positions),
            "broker_positions": len(broker_map),
            "details": details,
        }


# Singleton
_reconciler: PositionReconciler | None = None


def get_position_reconciler() -> PositionReconciler:
    global _reconciler
    if _reconciler is None:
        from app.config import get_settings
        interval = getattr(get_settings(), "RECONCILE_INTERVAL", DEFAULT_RECONCILE_INTERVAL)
        _reconciler = PositionReconciler(interval=interval)
    return _reconciler
