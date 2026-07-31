"""SL/TP price monitoring for open positions.

Checks if current prices have reached SL or TP levels for positions
with monitoring_active=True in their metadata_json. For paper positions,
closes them automatically in the DB. For live positions, sends a notification.
"""

import logging
from datetime import UTC, datetime
from decimal import Decimal as Dec

import httpx

logger = logging.getLogger(__name__)


def _fetch_prices(symbols: list[str]) -> dict[str, Dec]:
    """Fetch current prices for a list of symbols from Binance."""
    prices = {}
    if not symbols:
        return prices
    try:
        resp = httpx.get("https://api.binance.com/api/v3/ticker/price", timeout=10.0)
        if resp.status_code == 200:
            all_prices = {p["symbol"]: Dec(str(p["price"])) for p in resp.json()}
            for sym in symbols:
                if sym in all_prices:
                    prices[sym] = all_prices[sym]
    except Exception as exc:
        logger.error("Error fetching prices: %s", exc)
    return prices


def _close_paper_position(db, pos, sell_price: Dec, reason: str) -> dict:
    """Close a paper position in the DB at the given price."""
    from app.database.models.trade import Trade

    entry = pos.entry_price
    qty = pos.quantity
    realized_pnl = (sell_price - entry) * qty

    pos.status = "closed"
    pos.closed_at = datetime.now(tz=UTC)
    pos.current_price = sell_price
    pos.realized_pnl = realized_pnl

    trade = Trade(
        user_id=pos.user_id,
        timestamp=datetime.now(tz=UTC),
        symbol=pos.symbol,
        side="SELL",
        quantity=qty,
        price=sell_price,
        commission=Dec("0"),
        slippage=Dec("0"),
        realized_pnl=realized_pnl,
        strategy_name=getattr(pos, "strategy_name", None) or "SLTP-Monitor",
        position_id=pos.id,
        metadata_json={"source": "sltp_monitor", "reason": reason, "trading_mode": "paper"},
    )
    db.add(trade)

    meta = pos.metadata_json or {}
    if reason == "sl":
        meta["sl_triggered"] = True
    else:
        meta["tp_triggered"] = True
    meta["monitoring_active"] = False
    pos.metadata_json = meta

    return {
        "position_id": pos.id,
        "symbol": pos.symbol,
        "reason": reason,
        "price": str(sell_price),
        "realized_pnl": str(realized_pnl),
    }


def _send_notification(symbol: str, reason: str, price: str) -> None:
    """Send a notification when SL/TP is reached (best-effort)."""
    try:
        from app.notifications.whatsapp import notify_trade_executed

        msg = f"{'SL' if reason == 'sl' else 'TP'} alcanzado para {symbol} a {price}"
        notify_trade_executed(msg)
    except Exception:
        logger.warning("No se pudo enviar notificación para %s %s", symbol, reason)


def check_sltp_prices() -> list[dict]:
    """Check all open positions with monitoring_active for SL/TP triggers.

    Returns a list of result dicts for positions that were triggered.
    """
    from app.database.session import SessionLocal
    from app.database.models.position import Position

    db = SessionLocal()
    results = []
    try:
        positions = db.query(Position).filter(Position.status == "open").all()
        monitored = []
        for pos in positions:
            meta = pos.metadata_json or {}
            if not meta.get("monitoring_active"):
                continue
            if pos.stop_loss is None and pos.take_profit is None:
                continue
            if meta.get("sl_triggered") or meta.get("tp_triggered"):
                continue
            monitored.append(pos)

        if not monitored:
            return []

        symbols = list({pos.symbol for pos in monitored})
        prices = _fetch_prices(symbols)

        for pos in monitored:
            current_price = prices.get(pos.symbol)
            if current_price is None:
                continue

            meta = pos.metadata_json or {}
            is_paper = meta.get("trading_mode") == "paper" or meta.get("source") == "ai_recommendation"

            triggered = None
            sell_price = None

            if pos.stop_loss is not None and current_price <= pos.stop_loss:
                triggered = "sl"
                sell_price = pos.stop_loss
            elif pos.take_profit is not None and current_price >= pos.take_profit:
                triggered = "tp"
                sell_price = pos.take_profit

            if triggered:
                notif_type = "stop_loss_hit" if triggered == "sl" else "take_profit_hit"
                notif_title = f"{'Stop Loss' if triggered == 'sl' else 'Take Profit'} alcanzado: {pos.symbol}"
                notif_msg = f"Precio: {sell_price} | Posición #{pos.id}"

                if is_paper:
                    result = _close_paper_position(db, pos, sell_price, triggered)
                    results.append(result)
                    notif_msg += f" | PnL: {result.get('realized_pnl', 'N/A')}"
                else:
                    _send_notification(pos.symbol, triggered, str(sell_price))
                    meta = pos.metadata_json or {}
                    if triggered == "sl":
                        meta["sl_triggered"] = True
                    else:
                        meta["tp_triggered"] = True
                    meta["monitoring_active"] = False
                    pos.metadata_json = meta
                    results.append({
                        "position_id": pos.id,
                        "symbol": pos.symbol,
                        "reason": triggered,
                        "price": str(sell_price),
                        "action": "notified",
                    })

                # Create in-app notification
                try:
                    from app.services.notification_service import create_notification
                    create_notification(
                        db,
                        type=notif_type,
                        title=notif_title,
                        message=notif_msg,
                        severity="critical" if triggered == "sl" else "info",
                        asset=pos.symbol,
                    )
                except Exception:
                    pass

        db.commit()
        return results
    except Exception as exc:
        db.rollback()
        logger.error("Error in check_sltp_prices: %s", exc)
        return [{"error": str(exc)}]
    finally:
        db.close()
