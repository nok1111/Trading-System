"""Real-time WebSocket endpoints for positions and orders.

These endpoints poll the broker at regular intervals and push updates
to connected clients, replacing the frontend's REST polling.
"""

from __future__ import annotations

import asyncio
import logging
import threading

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.api.helpers import resolve_broker_credentials
from app.brokers.registry import get_adapter
from app.services.license import validate_license

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ws", tags=["realtime"])

# Poll intervals (seconds)
POSITIONS_INTERVAL = 5
ORDERS_INTERVAL = 10
DB_POSITIONS_INTERVAL = 3

# In-process pub/sub for DB position updates (thread-safe)
_position_subscribers: dict[int, list[threading.Event]] = {}
_subscribers_lock = threading.Lock()


def notify_position_update(user_id: int):
    """Push a position update notification to all WS subscribers for this user.

    Called from trading.py when positions change (close, SL/TP, auto-sell).
    Thread-safe: can be called from sync endpoints.
    """
    with _subscribers_lock:
        subscribers = list(_position_subscribers.get(user_id, []))
    for event in subscribers:
        event.set()


async def _validate_ws_token(websocket: WebSocket, token: str) -> bool:
    """Validate JWT token for WebSocket connection."""
    license_info = validate_license(token)
    if not license_info or not license_info.get("valid"):
        await websocket.close(code=4001, reason="Unauthorized")
        return False
    return True


def _get_adapter_for_user(broker_id: str, user_id: int):
    """Resolve broker adapter for the given user."""
    creds = resolve_broker_credentials(broker_id, user_id=user_id)
    if not creds:
        return None
    try:
        return get_adapter(broker_id, creds)
    except Exception:
        return None


@router.websocket("/positions/{broker_id}")
async def ws_positions(websocket: WebSocket, broker_id: str, token: str = Query(...)):
    """WebSocket that pushes position updates every 5 seconds.

    Messages:
    - {"type": "snapshot", "positions": [...]}
    - {"type": "update", "positions": [...], "changed": true|false}
    - {"type": "error", "message": "..."}
    """
    if not await _validate_ws_token(websocket, token):
        return

    await websocket.accept()

    # Extract user_id from license validation
    license_info = validate_license(token)
    user_id = license_info.get("user_id", 0) if license_info else 0

    last_positions_hash = None

    try:
        while True:
            try:
                adapter = _get_adapter_for_user(broker_id, user_id)
                if not adapter:
                    await websocket.send_json({"type": "error", "message": "No broker credentials"})
                    await asyncio.sleep(POSITIONS_INTERVAL)
                    continue

                positions = adapter.get_positions()
                positions_data = [
                    {
                        "symbol": p.symbol,
                        "side": p.side.value if hasattr(p.side, "value") else str(p.side),
                        "quantity": str(p.quantity),
                        "entry_price": str(p.entry_price) if p.entry_price else None,
                        "current_price": str(p.current_price) if p.current_price else None,
                        "unrealized_pnl": str(p.unrealized_pnl) if p.unrealized_pnl else None,
                        "leverage": p.leverage,
                        "liquidation_price": str(p.liquidation_price) if p.liquidation_price else None,
                    }
                    for p in positions
                ]

                # Detect changes by comparing hash
                current_hash = hash(tuple(
                    (p["symbol"], p["side"], p["quantity"], p["unrealized_pnl"])
                    for p in positions_data
                ))
                changed = current_hash != last_positions_hash
                last_positions_hash = current_hash

                msg_type = "snapshot" if last_positions_hash is None and changed else "update"
                await websocket.send_json({
                    "type": msg_type,
                    "positions": positions_data,
                    "changed": changed,
                })

            except WebSocketDisconnect:
                break
            except Exception as exc:
                logger.debug("WS positions error: %s", exc)
                await websocket.send_json({"type": "error", "message": "Error fetching positions"})

            await asyncio.sleep(POSITIONS_INTERVAL)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("WS positions disconnected: %s", exc)


@router.websocket("/orders/{broker_id}")
async def ws_orders(websocket: WebSocket, broker_id: str, token: str = Query(...)):
    """WebSocket that pushes open orders updates every 10 seconds.

    Messages:
    - {"type": "snapshot", "orders": [...]}
    - {"type": "update", "orders": [...], "changed": true|false}
    - {"type": "error", "message": "..."}
    """
    if not await _validate_ws_token(websocket, token):
        return

    await websocket.accept()

    license_info = validate_license(token)
    user_id = license_info.get("user_id", 0) if license_info else 0

    last_orders_hash = None

    try:
        while True:
            try:
                adapter = _get_adapter_for_user(broker_id, user_id)
                if not adapter:
                    await websocket.send_json({"type": "error", "message": "No broker credentials"})
                    await asyncio.sleep(ORDERS_INTERVAL)
                    continue

                orders = adapter.get_open_orders()
                orders_data = [
                    {
                        "broker_order_id": o.broker_order_id,
                        "symbol": o.symbol,
                        "side": o.side.value if hasattr(o.side, "value") else str(o.side),
                        "type": o.type.value if hasattr(o.type, "value") else str(o.type),
                        "quantity": str(o.quantity),
                        "price": str(o.price) if o.price else None,
                        "status": o.status.value if hasattr(o.status, "value") else str(o.status),
                    }
                    for o in orders
                ]

                current_hash = hash(tuple(
                    (o["broker_order_id"], o["status"], o["quantity"])
                    for o in orders_data
                ))
                changed = current_hash != last_orders_hash
                last_orders_hash = current_hash

                msg_type = "snapshot" if last_orders_hash is None and changed else "update"
                await websocket.send_json({
                    "type": msg_type,
                    "orders": orders_data,
                    "changed": changed,
                })

            except WebSocketDisconnect:
                break
            except Exception as exc:
                logger.debug("WS orders error: %s", exc)
                await websocket.send_json({"type": "error", "message": "Error fetching orders"})

            await asyncio.sleep(ORDERS_INTERVAL)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("WS orders disconnected: %s", exc)


def _serialize_db_positions(positions: list) -> list[dict]:
    """Serialize DB Position ORM objects to dicts for WS."""
    result = []
    for p in positions:
        result.append({
            "id": p.id,
            "symbol": p.symbol,
            "side": p.side,
            "quantity": str(p.quantity) if p.quantity else "0",
            "entry_price": str(p.entry_price) if p.entry_price else None,
            "current_price": str(p.current_price) if p.current_price else None,
            "stop_loss": str(p.stop_loss) if p.stop_loss else None,
            "take_profit": str(p.take_profit) if p.take_profit else None,
            "unrealized_pnl": str(p.unrealized_pnl) if p.unrealized_pnl else None,
            "realized_pnl": str(p.realized_pnl) if p.realized_pnl else None,
            "status": p.status,
            "auto_sell_enabled": p.auto_sell_enabled,
            "broker_id": getattr(p, "broker_id", None),
            "opened_at": p.opened_at.isoformat() if p.opened_at else None,
            "closed_at": p.closed_at.isoformat() if p.closed_at else None,
            "strategy_name": p.strategy_name,
            "metadata_json": p.metadata_json if isinstance(p.metadata_json, dict) else {},
        })
    return result


@router.websocket("/db-positions")
async def ws_db_positions(websocket: WebSocket, token: str = Query(...)):
    """WebSocket that pushes DB position updates in real-time.

    Combines periodic polling (every 3s) with instant push notifications
    when positions change (close, SL/TP, auto-sell toggle).

    Messages:
    - {"type": "snapshot", "positions": [...]}
    - {"type": "update", "positions": [...], "changed": true|false}
    - {"type": "closed", "position_id": 123, "positions": [...]}
    """
    if not await _validate_ws_token(websocket, token):
        return

    await websocket.accept()

    license_info = validate_license(token)
    user_id = license_info.get("user_id", 0) if license_info else 0

    # Register for push notifications (thread-safe Event)
    notify_event = threading.Event()
    with _subscribers_lock:
        _position_subscribers.setdefault(user_id, []).append(notify_event)

    last_hash = None

    try:
        while True:
            try:
                # Check for push notification (instant update, thread-safe)
                push_notify = notify_event.is_set()
                if push_notify:
                    notify_event.clear()

                # Fetch DB positions
                from app.database.session import SessionLocal
                from app.database.models.position import Position

                db = SessionLocal()
                try:
                    positions = db.query(Position).filter(
                        Position.user_id == user_id,
                    ).order_by(Position.id.desc()).limit(100).all()
                    positions_data = _serialize_db_positions(positions)
                finally:
                    db.close()

                # Detect changes
                current_hash = hash(tuple(
                    (p["id"], p["status"], str(p.get("stop_loss")), str(p.get("take_profit")),
                     str(p.get("unrealized_pnl")), p.get("auto_sell_enabled"))
                    for p in positions_data
                ))
                changed = current_hash != last_hash
                msg_type = "snapshot" if last_hash is None else "update"
                last_hash = current_hash

                # Send update if changed or push notification
                if changed or push_notify:
                    # Detect closed positions
                    closed_ids = []
                    if push_notify:
                        for p in positions_data:
                            if p["status"] == "closed" and p.get("closed_at"):
                                closed_ids.append(p["id"])

                    msg = {
                        "type": msg_type,
                        "positions": positions_data,
                        "changed": changed,
                    }
                    if closed_ids:
                        msg["closed_ids"] = closed_ids
                    await websocket.send_json(msg)

            except WebSocketDisconnect:
                break
            except Exception as exc:
                logger.debug("WS db-positions error: %s", exc)
                await websocket.send_json({"type": "error", "message": "Error fetching positions"})

            await asyncio.sleep(DB_POSITIONS_INTERVAL)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("WS db-positions disconnected: %s", exc)
    finally:
        # Unregister subscriber
        with _subscribers_lock:
            if user_id in _position_subscribers:
                try:
                    _position_subscribers[user_id].remove(notify_event)
                except ValueError:
                    pass
