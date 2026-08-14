"""Real-time WebSocket endpoints for positions and orders.

These endpoints poll the broker at regular intervals and push updates
to connected clients, replacing the frontend's REST polling.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.api.helpers import resolve_broker_credentials
from app.brokers.registry import get_adapter
from app.services.license import validate_license

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ws", tags=["realtime"])

# Poll intervals (seconds)
POSITIONS_INTERVAL = 5
ORDERS_INTERVAL = 10


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
