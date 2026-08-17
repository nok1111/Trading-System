"""Alvora advisor chat endpoints.

Conversational AI agent that lives in the local system. Provides:
- POST /api/alvora/chat — send a message, get a reply (+ optional actions)
- GET  /api/alvora/conversations — list conversations
- GET  /api/alvora/conversations/{id}/messages — message history
- POST /api/alvora/conversations — new conversation
- DELETE /api/alvora/conversations/{id} — delete conversation
- POST /api/alvora/execute — execute a confirmed action
- GET  /api/alvora/quick-prompts — predefined conversation starters
- GET  /api/alvora/status — provider availability
"""

import logging
from datetime import UTC, datetime
from decimal import Decimal as Dec
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.ai import alvora as alvora_svc
from app.api.helpers import resolve_binancekeys
from app.api.rate_limit import RATE_AI, RATE_TRADE, limiter
from app.config import get_settings
from app.database.session import SessionLocal
from app.services.auth import LocalUser, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/alvora", tags=["alvora"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None


class ExecuteActionRequest(BaseModel):
    action_type: str  # close_position | open_trade | set_stop_loss | set_take_profit
    params: dict
    conversation_id: int | None = None


class NewConversationRequest(BaseModel):
    title: str | None = None


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

@router.post("/chat")
@limiter.limit(RATE_AI)
def alvora_chat(
    request: Request,
    req: ChatRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Send a message to Alvora and receive a reply.

    Creates a new conversation if conversation_id is omitted.
    The reply may include proposed actions that the user must confirm
    via /api/alvora/execute.
    """
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Mensaje vacio")
    result = alvora_svc.alvora_chat(current_user.id, req.message.strip(), req.conversation_id)
    if result.get("error") and not result.get("conversation_id"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

@router.get("/conversations")
def list_conversations(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    """List the user's conversations, newest first."""
    return alvora_svc.list_conversations(current_user.id, limit)


@router.post("/conversations")
def create_conversation(
    req: NewConversationRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Create a new empty conversation."""
    from app.database.models.alvora_conversation import AlvoraConversation
    db = SessionLocal()
    try:
        conv = AlvoraConversation(
            user_id=current_user.id,
            title=req.title or "Nueva conversacion",
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return {
            "id": conv.id,
            "title": conv.title,
            "created_at": conv.created_at.isoformat() if conv.created_at else "",
        }
    finally:
        db.close()


@router.get("/conversations/{conversation_id}/messages")
def get_messages(
    conversation_id: int,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    limit: int = Query(100, ge=1, le=500),
) -> list[dict]:
    """Get all messages in a conversation."""
    msgs = alvora_svc.get_conversation_messages(current_user.id, conversation_id, limit)
    if not msgs:
        # Could be empty (new conv) or not owned — distinguish
        from app.database.models.alvora_conversation import AlvoraConversation
        db = SessionLocal()
        try:
            conv = db.query(AlvoraConversation).filter(
                AlvoraConversation.id == conversation_id,
                AlvoraConversation.user_id == current_user.id,
            ).first()
            if not conv:
                raise HTTPException(status_code=404, detail="Conversacion no encontrada")
        finally:
            db.close()
    return msgs


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Delete a conversation and all its messages."""
    ok = alvora_svc.delete_conversation(current_user.id, conversation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversacion no encontrada")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Action execution (user-confirmed)
# ---------------------------------------------------------------------------

@router.post("/execute")
@limiter.limit(RATE_TRADE)
def execute_action(
    request: Request,
    req: ExecuteActionRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Execute a confirmed action proposed by Alvora.

    The user must explicitly confirm in the UI before this is called.
    Supported action types:
    - close_position: close an open position at market price
    - open_trade: open a new buy/short (delegates to the trading engine)
    - set_stop_loss: update a position's stop-loss
    - set_take_profit: update a position's take-profit
    """
    action_type = req.action_type
    params = req.params or {}

    if action_type == "close_position":
        return _execute_close_position(current_user, params)
    if action_type == "open_trade":
        return _execute_open_trade(current_user, params)
    if action_type == "set_stop_loss":
        return _execute_set_sl_tp(current_user, params, "stop_loss")
    if action_type == "set_take_profit":
        return _execute_set_sl_tp(current_user, params, "take_profit")
    raise HTTPException(status_code=400, detail=f"Tipo de accion no soportado: {action_type}")


def _execute_close_position(user: LocalUser, params: dict) -> dict:
    """Close an open position at current market price."""
    position_id = params.get("position_id")
    if not position_id:
        return {"status": "error", "reason": "Falta position_id"}
    try:
        position_id = int(position_id)
    except (TypeError, ValueError):
        return {"status": "error", "reason": "position_id invalido"}

    from app.database.models.position import Position
    from app.database.models.trade import Trade
    from app.services.market_data_service import get_market_data_service
    from app.brokers.models import normalize_symbol

    db = SessionLocal()
    try:
        pos = db.query(Position).filter(
            Position.id == position_id,
            Position.user_id == user.id,
            Position.status == "open",
        ).first()
        if not pos:
            return {"status": "error", "reason": "Posicion no encontrada o ya cerrada"}

        # Fetch current price
        sell_price = None
        try:
            from app.data.price_stream import get_price_stream
            stream = get_price_stream()
            if stream and stream.is_connected:
                p = stream.get_price(pos.symbol)
                if p and p > 0:
                    sell_price = Dec(str(p))
        except Exception:
            pass
        if not sell_price or sell_price <= 0:
            try:
                ticker = get_market_data_service().get_ticker(normalize_symbol(pos.symbol))
                if ticker and ticker.price > 0:
                    sell_price = Dec(str(ticker.price))
            except Exception as exc:
                return {"status": "error", "reason": f"No se pudo obtener precio: {exc}"}
        if not sell_price or sell_price <= 0:
            return {"status": "error", "reason": "Precio invalido"}

        entry = pos.entry_price
        qty = pos.quantity
        realized_pnl = (sell_price - entry) * qty if pos.side == "long" else (entry - sell_price) * qty

        # Attempt real broker sell in live mode
        broker_sold = False
        settings = get_settings()
        if settings.TRADING_MODE == "live" and settings.LIVE_TRADING_ENABLED:
            try:
                from app.api.helpers import get_shared_broker
                keys = resolve_binancekeys(user)
                broker = get_shared_broker(keys)
                if hasattr(broker, "sell"):
                    broker.sell(pos.symbol, float(qty))
                    broker_sold = True
            except Exception as exc:
                logger.warning("Alvora close_position: broker sell failed (will close in DB): %s", exc)

        # Close in DB
        pos.status = "closed"
        pos.closed_at = datetime.now(tz=UTC)
        pos.current_price = sell_price
        pos.realized_pnl = Dec(str(round(float(realized_pnl), 8)))
        meta = pos.metadata_json or {}
        meta["closed_by"] = "alvora_chat"
        meta["broker_order"] = broker_sold
        pos.metadata_json = meta

        trade = Trade(
            user_id=user.id,
            timestamp=datetime.now(tz=UTC),
            symbol=pos.symbol,
            side="SELL",
            quantity=qty,
            price=sell_price,
            commission=Dec("0"),
            slippage=Dec("0"),
            realized_pnl=realized_pnl,
            strategy_name=pos.strategy_name,
            position_id=pos.id,
            broker_id=pos.broker_id,
            metadata_json={"source": "alvora_chat", "broker_order": broker_sold},
        )
        db.add(trade)
        db.commit()

        return {
            "status": "executed",
            "action": "close_position",
            "position_id": pos.id,
            "symbol": pos.symbol,
            "price": str(sell_price),
            "realized_pnl": str(realized_pnl),
            "broker_order": broker_sold,
        }
    except Exception as exc:
        db.rollback()
        logger.error("Alvora close_position error: %s", exc)
        return {"status": "error", "reason": str(exc)}
    finally:
        db.close()


def _execute_open_trade(user: LocalUser, params: dict) -> dict:
    """Open a new trade — delegates to the AI agent execute logic."""
    from app.api.routes.ai_agent import AIExecuteRequest, ai_agent_execute
    from fastapi import Request as _Req

    symbol = (params.get("symbol") or "").upper()
    if not symbol:
        return {"status": "error", "reason": "Falta symbol"}
    action_type = params.get("action_type", "buy").lower()
    if action_type not in ("buy", "short", "sell"):
        return {"status": "error", "reason": "action_type invalido"}

    req = AIExecuteRequest(
        action_type=action_type,  # type: ignore[arg-type]
        symbol=symbol,
        confidence=float(params.get("confidence", 0.7)),
        reason=params.get("reason", "Alvora chat"),
        stop_loss_pct=float(params["stop_loss_pct"]) if params.get("stop_loss_pct") else None,
        take_profit_pct=float(params["take_profit_pct"]) if params.get("take_profit_pct") else None,
        position_size_usd=float(params["position_size_usd"]) if params.get("position_size_usd") else None,
    )
    # Build a lightweight Request stub for the rate limiter (which reads .client)
    class _StubReq:
        client = "127.0.0.1"
    try:
        return ai_agent_execute(_StubReq(), req, user)  # type: ignore[arg-type]
    except HTTPException as exc:
        return {"status": "error", "reason": exc.detail}
    except Exception as exc:
        logger.error("Alvora open_trade error: %s", exc)
        return {"status": "error", "reason": str(exc)}


def _execute_set_sl_tp(user: LocalUser, params: dict, field: str) -> dict:
    """Update stop_loss or take_profit on an open position."""
    position_id = params.get("position_id")
    if not position_id:
        return {"status": "error", "reason": "Falta position_id"}
    value_key = field  # stop_loss | take_profit
    value = params.get(value_key)
    if value is None:
        return {"status": "error", "reason": f"Falta {value_key}"}
    try:
        position_id = int(position_id)
        value = float(value)
    except (TypeError, ValueError):
        return {"status": "error", "reason": "Parametros invalidos"}

    from app.database.models.position import Position
    db = SessionLocal()
    try:
        pos = db.query(Position).filter(
            Position.id == position_id,
            Position.user_id == user.id,
            Position.status == "open",
        ).first()
        if not pos:
            return {"status": "error", "reason": "Posicion no encontrada"}
        if field == "stop_loss":
            pos.stop_loss = Dec(str(value))
        else:
            pos.take_profit = Dec(str(value))
        db.commit()
        return {
            "status": "executed",
            "action": f"set_{field}",
            "position_id": pos.id,
            "symbol": pos.symbol,
            field: value,
        }
    except Exception as exc:
        db.rollback()
        return {"status": "error", "reason": str(exc)}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

@router.get("/quick-prompts")
def quick_prompts() -> list[dict]:
    """Predefined conversation starters."""
    return alvora_svc.get_quick_prompts()


@router.get("/status")
def alvora_status(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Check if Alvora is available (AI provider configured)."""
    return alvora_svc.alvora_status(current_user.id)
