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
from app.database.models.user_settings import UserSettings
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


class ConfigureRequest(BaseModel):
    provider: str  # groq | gemini | omniroute | ollama | openai | deepseek | mistral | ...
    api_key: str | None = None  # groq/gemini/premium key
    model: str | None = None


class FallbackProviderEntry(BaseModel):
    provider: str
    api_key: str | None = None
    model: str | None = None


class SaveAlvoraConfigRequest(BaseModel):
    """Full Alvora config — primary provider + fallback chain + persona."""
    provider: str = "gemini"
    api_key: str | None = None  # none = don't change existing
    model: str | None = None
    fallback_chain: list[FallbackProviderEntry] | None = None
    # Persona
    language: str = "es"
    response_style: str = "detailed"
    risk_advice_level: str = "balanced"
    auto_suggest_actions: bool = True
    max_tokens: int = 1800
    temperature: float = 0.5
    # Context
    include_positions: bool = True
    include_market_data: bool = True
    include_profile: bool = True
    include_recommendations: bool = True


class TestProviderRequest(BaseModel):
    provider: str
    api_key: str | None = None
    model: str | None = None


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
# Configure provider (without starting the autonomous agent)
# ---------------------------------------------------------------------------

@router.post("/configure")
@limiter.limit(RATE_AI)
def alvora_configure(
    request: Request,
    req: ConfigureRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Save AI provider + key for Alvora without starting the autonomous agent.

    Persists to the same user_settings table used by AIAgentPage, so the
    config is shared. Rebuilds the provider immediately so Alvora can chat
    right away.
    """
    from app.api.routes.ai_agent import _save_user_keys
    from app.api.helpers import get_or_create_agent

    provider = req.provider.strip().lower()
    valid = {"groq", "gemini", "omniroute", "ollama", "openai", "deepseek", "mistral", "together", "perplexity", "grok"}
    if provider not in valid:
        raise HTTPException(status_code=400, detail=f"Provider invalido: {provider}")

    api_key = (req.api_key or "").strip() or None
    model = (req.model or "").strip() or None

    # Save to DB using the same function as AIAgentPage
    save_kwargs: dict = {"ai_provider": provider, "last_ai_provider_used": provider}
    if provider == "groq":
        if api_key:
            save_kwargs["groq_key"] = api_key
        if model:
            save_kwargs["ai_model"] = model
            save_kwargs["last_model_used"] = model
    elif provider == "gemini":
        if api_key:
            save_kwargs["gemini_key"] = api_key
        if model:
            save_kwargs["ai_model"] = model
            save_kwargs["last_model_used"] = model
    elif provider in ("openai", "deepseek", "mistral", "together", "perplexity", "grok"):
        if api_key:
            save_kwargs["premium_key"] = api_key
            save_kwargs["premium_provider"] = provider
        if model:
            save_kwargs["ai_model"] = model
            save_kwargs["last_model_used"] = model
            save_kwargs["premium_model"] = model
    elif provider == "omniroute":
        if api_key:
            save_kwargs["omniroute_key"] = api_key  # handled by _save_user_keys? no, need custom
        if model:
            save_kwargs["ai_model"] = model
            save_kwargs["last_model_used"] = model

    # _save_user_keys doesn't handle omniroute_key, save manually
    if provider == "omniroute" and api_key:
        try:
            from app.services.crypto import encrypt
            db = SessionLocal()
            try:
                s = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()
                if not s:
                    s = UserSettings(user_id=current_user.id)
                    db.add(s)
                s.ai_omniroute_key_enc = encrypt(api_key)
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.warning("Alvora configure: failed to save omniroute key: %s", exc)

    _save_user_keys(current_user.id, **save_kwargs)

    # Apply to the agent singleton and rebuild provider
    agent = get_or_create_agent()
    agent.provider = provider
    if provider == "groq":
        if api_key:
            agent.groq_api_key = api_key
        if model:
            agent.groq_model = model
    elif provider == "gemini":
        if api_key:
            agent.gemini_api_key = api_key
        if model:
            agent.gemini_model = model
    elif provider in ("openai", "deepseek", "mistral", "together", "perplexity", "grok"):
        if api_key:
            agent.openai_api_key = api_key
        if model:
            agent.openai_model = model
    elif provider == "omniroute":
        if api_key:
            agent.omniroute_api_key = api_key
        if model:
            agent.omniroute_model = model
    try:
        agent._rebuild_provider()
    except Exception:
        pass

    # Check availability
    available = agent._ai_provider is not None and agent._ai_provider.is_available()
    return {
        "ok": True,
        "provider": provider,
        "model": model,
        "available": available,
    }


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
    """Close an open position at current market price.

    Can close DB-managed positions (by position_id) or broker-managed
    spot positions (by symbol only, delegates to /api/positions/close).
    """
    position_id = params.get("position_id")
    symbol = (params.get("symbol") or "").upper().replace("/", "").replace("-", "").replace("_", "")

    # If no position_id, try broker-managed close via trading endpoint
    if not position_id:
        if not symbol:
            return {"status": "error", "reason": "Falta position_id o symbol"}
        db = SessionLocal()
        try:
            # Check if there's a DB position for this symbol first
            from app.database.models.position import Position
            pos = db.query(Position).filter(
                Position.user_id == user.id,
                Position.status == "open",
            ).filter(Position.symbol.ilike(f"%{symbol}%")).first()
            if pos:
                position_id = pos.id
            db.close()
        except Exception:
            db.close()

        if not position_id:
            # No DB position — delegate to broker-managed close endpoint
            from app.api.routes.trading import close_broker_position, ClosePositionRequest
            broker_id = params.get("broker_id", "binance")
            req = ClosePositionRequest(symbol=symbol, broker_id=broker_id)
            try:
                return close_broker_position(req, user)
            except HTTPException as exc:
                return {"status": "error", "reason": exc.detail}
            except Exception as exc:
                logger.error("Alvora close_position (broker) error: %s", exc)
                return {"status": "error", "reason": str(exc)}

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
    # Call the unwrapped function (bypass rate limiter decorator)
    # ai_agent_execute.__wrapped__ is the raw function without @limiter.limit
    raw_fn = getattr(ai_agent_execute, "__wrapped__", ai_agent_execute)
    try:
        return raw_fn(None, req, user)  # type: ignore[arg-type]
    except HTTPException as exc:
        return {"status": "error", "reason": exc.detail}
    except Exception as exc:
        logger.error("Alvora open_trade error: %s", exc)
        return {"status": "error", "reason": str(exc)}


def _execute_set_sl_tp(user: LocalUser, params: dict, field: str) -> dict:
    """Update stop_loss or take_profit on an open position.

    Accepts both absolute values (stop_loss=1836.80) and percentages
    (stop_loss_pct=3.0). When a percentage is given, the absolute value
    is calculated from the position's entry price.

    Can find position by position_id OR by symbol (first open match).
    """
    position_id = params.get("position_id")
    symbol = (params.get("symbol") or "").upper().replace("/", "").replace("-", "").replace("_", "")

    if not position_id and not symbol:
        return {"status": "error", "reason": "Falta position_id o symbol"}

    # Accept both absolute (stop_loss=1836.80) and percentage (stop_loss_pct=3.0)
    pct_key = f"{field}_pct"  # stop_loss_pct | take_profit_pct
    value = params.get(field)
    pct_value = params.get(pct_key)

    if value is None and pct_value is None:
        return {"status": "error", "reason": f"Falta {field} o {pct_key}"}

    from app.database.models.position import Position
    db = SessionLocal()
    try:
        # Find position by ID first, then by symbol
        pos = None
        if position_id:
            try:
                pid = int(position_id)
                pos = db.query(Position).filter(
                    Position.id == pid,
                    Position.user_id == user.id,
                    Position.status == "open",
                ).first()
            except (TypeError, ValueError):
                pass

        if not pos and symbol:
            pos = db.query(Position).filter(
                Position.user_id == user.id,
                Position.status == "open",
            ).filter(Position.symbol.ilike(f"%{symbol}%")).first()

        if not pos:
            # No DB position found — try broker-managed position via new endpoint
            if symbol:
                db.close()
                from app.api.routes.trading import set_sl_tp, SetSlTpRequest
                req = SetSlTpRequest(
                    symbol=symbol,
                    stop_loss=float(value) if value is not None else None,
                    take_profit=float(value) if value is not None else None,
                    stop_loss_pct=float(pct_value) if pct_value is not None else None,
                    take_profit_pct=float(pct_value) if pct_value is not None else None,
                )
                # Map field to correct request field
                if field == "stop_loss":
                    req = SetSlTpRequest(
                        symbol=symbol,
                        stop_loss=float(value) if value is not None else None,
                        stop_loss_pct=float(pct_value) if pct_value is not None else None,
                    )
                else:
                    req = SetSlTpRequest(
                        symbol=symbol,
                        take_profit=float(value) if value is not None else None,
                        take_profit_pct=float(pct_value) if pct_value is not None else None,
                    )
                try:
                    return set_sl_tp(req, user)
                except Exception as exc:
                    return {"status": "error", "reason": f"No se pudo setear {field} en broker: {exc}"}
            return {"status": "error", "reason": "Posicion no encontrada en la base de datos local. Las posiciones spot del broker no soportan SL/TP directo."}

        # Calculate absolute value from percentage if needed
        if value is not None:
            abs_value = float(value)
        else:
            # Calculate from entry price
            pct = float(pct_value)
            entry_price = float(pos.entry_price or pos.current_price or 0)
            if entry_price <= 0:
                return {"status": "error", "reason": f"No se puede calcular {field} sin precio de entrada"}
            if field == "stop_loss":
                abs_value = entry_price * (1 - pct / 100)
            else:  # take_profit
                abs_value = entry_price * (1 + pct / 100)

        abs_value = round(abs_value, 8)

        if field == "stop_loss":
            pos.stop_loss = Dec(str(abs_value))
        else:
            pos.take_profit = Dec(str(abs_value))
        db.commit()
        return {
            "status": "executed",
            "action": f"set_{field}",
            "position_id": pos.id,
            "symbol": pos.symbol,
            field: abs_value,
            "pct_used": float(pct_value) if pct_value else None,
            "entry_price": float(pos.entry_price) if pos.entry_price else None,
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


# ---------------------------------------------------------------------------
# Configuration (full Alvora config: primary + fallback + persona)
# ---------------------------------------------------------------------------

def _get_or_create_alvora_config(db, user_id: int):
    from app.database.models.alvora_config import AlvoraConfig
    cfg = db.query(AlvoraConfig).filter(AlvoraConfig.user_id == user_id).first()
    if not cfg:
        cfg = AlvoraConfig(user_id=user_id)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


@router.get("/config")
def get_alvora_config(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Get the user's Alvora configuration (API keys masked)."""
    db = SessionLocal()
    try:
        cfg = _get_or_create_alvora_config(db, current_user.id)
        return cfg.to_dict(include_keys=False)
    finally:
        db.close()


@router.post("/config")
def save_alvora_config(
    req: SaveAlvoraConfigRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Save full Alvora configuration.

    API keys are encrypted before storage. If api_key is None, the existing
    key is preserved. The fallback chain is stored as encrypted JSON.
    """
    import json
    from app.services.crypto import encrypt

    db = SessionLocal()
    try:
        cfg = _get_or_create_alvora_config(db, current_user.id)

        # Primary provider
        cfg.provider = req.provider
        if req.api_key is not None:
            cfg.api_key_enc = encrypt(req.api_key) if req.api_key else None
        if req.model is not None:
            cfg.model = req.model.strip() or None

        # Fallback chain
        if req.fallback_chain is not None:
            chain = []
            for entry in req.fallback_chain:
                item = {"provider": entry.provider, "model": entry.model or ""}
                if entry.api_key is not None:
                    item["api_key_enc"] = encrypt(entry.api_key) if entry.api_key else None
                else:
                    # Preserve existing key if we have one
                    item["api_key_enc"] = None  # will be filled from existing
                chain.append(item)

            # Preserve existing fallback keys for entries that didn't provide a new key
            if cfg.fallback_chain_json:
                try:
                    existing = json.loads(cfg.fallback_chain_json)
                    for i, new_entry in enumerate(chain):
                        if new_entry["api_key_enc"] is None and i < len(existing):
                            new_entry["api_key_enc"] = existing[i].get("api_key_enc")
                except Exception:
                    pass

            cfg.fallback_chain_json = json.dumps(chain)

        # Persona
        cfg.language = req.language
        cfg.response_style = req.response_style
        cfg.risk_advice_level = req.risk_advice_level
        cfg.auto_suggest_actions = req.auto_suggest_actions
        cfg.max_tokens = req.max_tokens
        cfg.temperature = req.temperature

        # Context
        cfg.include_positions = req.include_positions
        cfg.include_market_data = req.include_market_data
        cfg.include_profile = req.include_profile
        cfg.include_recommendations = req.include_recommendations

        db.commit()

        # Apply to the agent singleton so Alvora uses the new config immediately
        try:
            alvora_svc._apply_alvora_config(current_user.id, cfg)
        except Exception as exc:
            logger.warning("Alvora config: failed to apply immediately: %s", exc)

        return {"ok": True, "config": cfg.to_dict(include_keys=False)}
    except Exception as exc:
        db.rollback()
        logger.error("Alvora config save error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()


@router.post("/test-provider")
@limiter.limit(RATE_AI)
def test_provider(
    request: Request,
    req: TestProviderRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Test a specific AI provider + key + model by sending a minimal request."""
    import requests as req_lib
    from app.config import get_settings
    from app.services.crypto import decrypt

    settings = get_settings()
    provider = req.provider.strip().lower()
    api_key = (req.api_key or "").strip() or None
    model = (req.model or "").strip() or None

    # If no key provided in request, try DB then .env
    if not api_key:
        db = SessionLocal()
        try:
            cfg = _get_or_create_alvora_config(db, current_user.id)
            if cfg.api_key_enc and cfg.provider == provider:
                try:
                    api_key = decrypt(cfg.api_key_enc)
                except Exception:
                    pass
            # Also check fallback chain
            if not api_key and cfg.fallback_chain_json:
                import json
                try:
                    chain = json.loads(cfg.fallback_chain_json)
                    for entry in chain:
                        if entry.get("provider") == provider and entry.get("api_key_enc"):
                            try:
                                api_key = decrypt(entry["api_key_enc"])
                            except Exception:
                                pass
                            if api_key:
                                break
                except Exception:
                    pass
        finally:
            db.close()

    # .env fallback
    if not api_key:
        env_map = {
            "groq": "GROQ_API_KEY",
            "gemini": "GEMINI_API_KEY",
        }
        if provider in env_map:
            api_key = getattr(settings, env_map[provider], None)

    try:
        if provider == "groq":
            if not api_key:
                return {"ok": False, "error": "GROQ_API_KEY no configurada"}
            test_model = model or "openai/gpt-oss-120b"
            resp = req_lib.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": test_model, "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5},
                timeout=15,
            )
            if resp.status_code == 200:
                return {"ok": True, "provider": "Groq", "model": test_model}
            return {"ok": False, "error": f"Groq {resp.status_code}: {resp.text[:200]}"}

        elif provider == "gemini":
            if not api_key:
                return {"ok": False, "error": "GEMINI_API_KEY no configurada"}
            test_model = model or "gemini-flash-latest"
            resp = req_lib.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{test_model}:generateContent?key={api_key}",
                headers={"Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": "Hi"}]}], "generationConfig": {"maxOutputTokens": 5}},
                timeout=15,
            )
            if resp.status_code == 200:
                return {"ok": True, "provider": "Gemini", "model": test_model}
            return {"ok": False, "error": f"Gemini {resp.status_code}: {resp.text[:200]}"}

        elif provider == "ollama":
            ollama_url = getattr(settings, "OLLAMA_URL", "http://localhost:11434")
            test_model = model or "qwen2.5:14b"
            try:
                resp = req_lib.post(
                    f"{ollama_url}/api/chat",
                    json={"model": test_model, "messages": [{"role": "user", "content": "Hi"}], "stream": False},
                    timeout=10,
                )
                if resp.status_code == 200:
                    return {"ok": True, "provider": "Ollama", "model": test_model}
                return {"ok": False, "error": f"Ollama {resp.status_code}: {resp.text[:200]}"}
            except Exception as exc:
                return {"ok": False, "error": f"Ollama no disponible: {exc}"}

        elif provider == "omniroute":
            omni_url = getattr(settings, "OMNIROUTE_URL", "http://localhost:20128")
            test_model = model or "default"
            try:
                resp = req_lib.post(
                    f"{omni_url}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key or 'free'}", "Content-Type": "application/json"},
                    json={"model": test_model, "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5},
                    timeout=10,
                )
                if resp.status_code == 200:
                    return {"ok": True, "provider": "OmniRoute", "model": test_model}
                return {"ok": False, "error": f"OmniRoute {resp.status_code}: {resp.text[:200]}"}
            except Exception as exc:
                return {"ok": False, "error": f"OmniRoute no disponible: {exc}"}

        elif provider in ("openai", "deepseek", "mistral", "together", "perplexity", "grok"):
            PREMIUM_BASE_URLS = {
                "openai": "https://api.openai.com/v1",
                "deepseek": "https://api.deepseek.com/v1",
                "mistral": "https://api.mistral.ai/v1",
                "together": "https://api.together.xyz/v1",
                "perplexity": "https://api.perplexity.ai",
                "grok": "https://api.x.ai/v1",
            }
            if not api_key:
                return {"ok": False, "error": f"{provider.upper()}_API_KEY no configurada"}
            base_url = PREMIUM_BASE_URLS[provider]
            test_model = model or "default"
            resp = req_lib.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": test_model, "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5},
                timeout=15,
            )
            if resp.status_code == 200:
                return {"ok": True, "provider": provider, "model": test_model}
            return {"ok": False, "error": f"{provider} {resp.status_code}: {resp.text[:200]}"}

        else:
            return {"ok": False, "error": f"Provider '{provider}' no soportado"}

    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/test-chain")
@limiter.limit(RATE_AI)
def test_fallback_chain(
    request: Request,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Test the full fallback chain — primary + all fallbacks in order."""
    import json
    from app.services.crypto import decrypt

    db = SessionLocal()
    try:
        cfg = _get_or_create_alvora_config(db, current_user.id)
        results = []

        # Test primary
        primary_key = None
        if cfg.api_key_enc:
            try:
                primary_key = decrypt(cfg.api_key_enc)
            except Exception:
                pass

        # Also test .env keys as fallback
        from app.config import get_settings
        settings = get_settings()
        if not primary_key:
            env_map = {"groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY"}
            if cfg.provider in env_map:
                primary_key = getattr(settings, env_map[cfg.provider], None)

        # Test primary via the test-provider endpoint logic
        test_req = TestProviderRequest(provider=cfg.provider, api_key=primary_key, model=cfg.model)
        primary_result = test_provider(request, test_req, current_user)
        results.append({
            "role": "primary",
            "provider": cfg.provider,
            "model": cfg.model or "",
            **primary_result,
        })

        # Test fallbacks
        if cfg.fallback_chain_json:
            try:
                chain = json.loads(cfg.fallback_chain_json)
                for i, entry in enumerate(chain):
                    fb_key = None
                    if entry.get("api_key_enc"):
                        try:
                            fb_key = decrypt(entry["api_key_enc"])
                        except Exception:
                            pass
                    if not fb_key:
                        env_map = {"groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY"}
                        if entry.get("provider") in env_map:
                            fb_key = getattr(settings, env_map[entry["provider"]], None)

                    fb_req = TestProviderRequest(
                        provider=entry.get("provider", ""),
                        api_key=fb_key,
                        model=entry.get("model"),
                    )
                    fb_result = test_provider(request, fb_req, current_user)
                    results.append({
                        "role": f"fallback_{i+1}",
                        "provider": entry.get("provider", ""),
                        "model": entry.get("model", ""),
                        **fb_result,
                    })
            except Exception:
                pass

        working = [r for r in results if r.get("ok")]
        return {
            "total": len(results),
            "working": len(working),
            "results": results,
            "has_working": len(working) > 0,
        }
    finally:
        db.close()
