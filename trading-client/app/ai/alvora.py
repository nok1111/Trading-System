"""Alvora — the advisor chat agent.

Conversational layer on top of the AI provider. Unlike AITradingAgent (autonomous
loop that emits JSON trade decisions), Alvora is a chat advisor that:
- Reads the user's real-time context (portfolio, positions, market, profile)
- Holds a conversation with history
- Proposes actions (close_position, open_trade, set_stop_loss, set_take_profit)
  that the user confirms before execution
- Persists conversations + messages to DB
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.ai.alvora_context import build_alvora_context
from app.ai.provider import ChatMessage
from app.config import get_settings
from app.database.session import SessionLocal

logger = logging.getLogger(__name__)

_ACTION_RE = re.compile(r"^\[ACTION:([a-z_]+)\|(.+)\]\s*$", re.MULTILINE)
_MAX_HISTORY = 12  # max prior messages sent to the LLM (keeps token budget bounded)


def _load_alvora_prompt() -> str:
    prompts_dir = Path(get_settings().AI_PROMPTS_DIR)
    path = prompts_dir / "alvora_chat.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    logger.warning("Alvora chat prompt not found: %s", path)
    return "Eres Alvora, asesor de trading del usuario."


ALVORA_PROMPT = _load_alvora_prompt()


# Predefined conversation starters (quick prompts)
QUICK_PROMPTS: list[dict[str, str]] = [
    {"id": "portfolio_review", "label": "Revisa mi portafolio", "message": "Revisa mi portafolio actual. Como esta mi exposicion y mi P&L? Hay algo que deberia cambiar?"},
    {"id": "market_now", "label": "Como esta el mercado ahora?", "message": "Como esta el mercado ahora mismo? Cual es el sentimiento y hay oportunidades claras para mi perfil?"},
    {"id": "position_advice", "label": "Que hago con mis posiciones?", "message": "Analiza mis posiciones abiertas una por una. Cuales deberia mantener, cuales cerrar y por que?"},
    {"id": "risk_check", "label": "Chequea mi riesgo", "message": "Hazme un chequeo de riesgo. Estoy expuesto a algo peligroso? Mi stop-loss y take-profit estan bien configurados?"},
    {"id": "opportunities", "label": "Hay oportunidades hoy?", "message": "Hay oportunidades de trading hoy que encajen con mi perfil? Dame concrete: simbolo, razon, SL y TP sugeridos."},
    {"id": "improve_strategy", "label": "Como mejoro mi estrategia?", "message": "Segun mi perfil y mi historial reciente, como podria mejorar mi estrategia de trading?"},
]


def parse_actions(text: str) -> tuple[str, list[dict[str, Any]]]:
    """Extract [ACTION:...] markers from text.

    Returns (clean_text, actions) where clean_text has the markers removed
    and actions is a list of structured dicts with an auto-generated id.
    """
    actions: list[dict[str, Any]] = []
    matches = list(_ACTION_RE.finditer(text))
    if not matches:
        return text.strip(), []

    for i, m in enumerate(matches):
        action_type = m.group(1)
        params_str = m.group(2)
        params: dict[str, str] = {}
        for pair in params_str.split("|"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                params[k.strip()] = v.strip()
        actions.append({
            "id": f"act_{i + 1}",
            "type": action_type,
            "params": params,
            "reason": params.get("reason", ""),
        })

    clean = _ACTION_RE.sub("", text).strip()
    return clean, actions


def _get_provider_for_user(user_id: int):
    """Resolve the AI provider configured by the user (reuses the agent singleton)."""
    import app.api.state as state
    from app.api.helpers import get_or_create_agent
    agent = get_or_create_agent()
    # Ensure provider reflects the user's saved config
    try:
        agent._rebuild_provider()
    except Exception:
        pass
    return agent._ai_provider


def _build_history_messages(db, conversation_id: int) -> list[ChatMessage]:
    """Load prior messages from DB and convert to ChatMessage list (capped)."""
    from app.database.models.alvora_message import AlvoraMessage
    rows = (
        db.query(AlvoraMessage)
        .filter(AlvoraMessage.conversation_id == conversation_id)
        .order_by(AlvoraMessage.created_at.asc())
        .all()
    )
    # Keep only the most recent N (already-ordered ascending, take tail)
    recent = rows[-_MAX_HISTORY:] if len(rows) > _MAX_HISTORY else rows
    return [ChatMessage(role=r.role, content=r.content) for r in recent]


def _auto_title(message: str) -> str:
    """Generate a short conversation title from the first user message."""
    text = message.strip().replace("\n", " ")
    if len(text) <= 60:
        return text
    return text[:57] + "..."


def alvora_chat(user_id: int, message: str, conversation_id: int | None = None) -> dict:
    """Send a message to Alvora and get a response.

    Creates a new conversation if conversation_id is None.
    Returns: {conversation_id, message_id, reply, actions, provider, model, latency_ms, error?}
    """
    db = SessionLocal()
    try:
        from app.database.models.alvora_conversation import AlvoraConversation
        from app.database.models.alvora_message import AlvoraMessage

        # Resolve or create conversation
        if conversation_id is None:
            conv = AlvoraConversation(user_id=user_id, title=_auto_title(message))
            db.add(conv)
            db.commit()
            db.refresh(conv)
            conversation_id = conv.id
        else:
            conv = db.query(AlvoraConversation).filter(
                AlvoraConversation.id == conversation_id,
                AlvoraConversation.user_id == user_id,
            ).first()
            if not conv:
                return {"error": "Conversacion no encontrada", "conversation_id": None}

        # Persist the user message
        user_msg = AlvoraMessage(
            conversation_id=conversation_id,
            role="user",
            content=message,
        )
        db.add(user_msg)
        db.commit()
        db.refresh(user_msg)

        # Build context + history
        context = build_alvora_context(user_id)
        system_prompt = f"{ALVORA_PROMPT}\n\n{context}"
        history = _build_history_messages(db, conversation_id)
        # The history already includes the just-persisted user message (tail).

        # Get provider
        provider = _get_provider_for_user(user_id)
        if provider is None or not provider.is_available():
            error_msg = "Alvora no tiene un proveedor de IA configurado. Configura tu proveedor (Groq, Gemini, OmniRoute, etc.) en la pagina AI Trading Agent primero."
            assistant_msg = AlvoraMessage(
                conversation_id=conversation_id,
                role="assistant",
                content=error_msg,
            )
            db.add(assistant_msg)
            conv.updated_at = datetime.now(UTC)
            db.commit()
            db.refresh(assistant_msg)
            return {
                "conversation_id": conversation_id,
                "message_id": assistant_msg.id,
                "reply": error_msg,
                "actions": [],
                "error": "no_provider",
            }

        # Call the provider
        try:
            chat_resp = provider.chat(system_prompt, history, max_tokens=1800, temperature=0.5)
        except Exception as exc:
            logger.error("Alvora chat provider error: %s", exc)
            chat_resp = None

        if chat_resp is None or not chat_resp.success:
            err = (chat_resp.error if chat_resp else "Sin respuesta del proveedor") or "Error desconocido"
            error_text = f"No pude generar una respuesta en este momento. Detalle: {err}"
            assistant_msg = AlvoraMessage(
                conversation_id=conversation_id,
                role="assistant",
                content=error_text,
            )
            db.add(assistant_msg)
            conv.updated_at = datetime.now(UTC)
            db.commit()
            db.refresh(assistant_msg)
            return {
                "conversation_id": conversation_id,
                "message_id": assistant_msg.id,
                "reply": error_text,
                "actions": [],
                "error": err,
            }

        # Parse actions from the response
        clean_text, actions = parse_actions(chat_resp.text)

        # Persist assistant message
        assistant_msg = AlvoraMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=clean_text,
            actions_json=actions,
            provider=chat_resp.provider_name,
            model=chat_resp.model,
            latency_ms=chat_resp.latency_ms,
        )
        db.add(assistant_msg)
        conv.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(assistant_msg)

        return {
            "conversation_id": conversation_id,
            "message_id": assistant_msg.id,
            "reply": clean_text,
            "actions": actions,
            "provider": chat_resp.provider_name,
            "model": chat_resp.model,
            "latency_ms": chat_resp.latency_ms,
        }
    except Exception as exc:
        logger.error("Alvora chat error: %s", exc)
        return {"error": str(exc), "conversation_id": conversation_id}
    finally:
        db.close()


def list_conversations(user_id: int, limit: int = 50) -> list[dict]:
    """List conversations for a user, newest first."""
    db = SessionLocal()
    try:
        from app.database.models.alvora_conversation import AlvoraConversation
        from app.database.models.alvora_message import AlvoraMessage
        from sqlalchemy import func as sqlfunc

        rows = (
            db.query(AlvoraConversation)
            .filter(AlvoraConversation.user_id == user_id)
            .order_by(AlvoraConversation.updated_at.desc())
            .limit(limit)
            .all()
        )
        result = []
        for c in rows:
            msg_count = db.query(sqlfunc.count(AlvoraMessage.id)).filter(
                AlvoraMessage.conversation_id == c.id
            ).scalar() or 0
            result.append({
                "id": c.id,
                "title": c.title,
                "message_count": msg_count,
                "created_at": c.created_at.isoformat() if c.created_at else "",
                "updated_at": c.updated_at.isoformat() if c.updated_at else "",
            })
        return result
    except Exception:
        return []
    finally:
        db.close()


def get_conversation_messages(user_id: int, conversation_id: int, limit: int = 100) -> list[dict]:
    """Get messages for a conversation (verifies ownership)."""
    db = SessionLocal()
    try:
        from app.database.models.alvora_conversation import AlvoraConversation
        from app.database.models.alvora_message import AlvoraMessage

        conv = db.query(AlvoraConversation).filter(
            AlvoraConversation.id == conversation_id,
            AlvoraConversation.user_id == user_id,
        ).first()
        if not conv:
            return []

        rows = (
            db.query(AlvoraMessage)
            .filter(AlvoraMessage.conversation_id == conversation_id)
            .order_by(AlvoraMessage.created_at.asc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "role": r.role,
                "content": r.content,
                "actions": r.actions_json or [],
                "provider": r.provider,
                "model": r.model,
                "latency_ms": r.latency_ms,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in rows
        ]
    except Exception:
        return []
    finally:
        db.close()


def delete_conversation(user_id: int, conversation_id: int) -> bool:
    """Delete a conversation and its messages (verifies ownership)."""
    db = SessionLocal()
    try:
        from app.database.models.alvora_conversation import AlvoraConversation
        from app.database.models.alvora_message import AlvoraMessage

        conv = db.query(AlvoraConversation).filter(
            AlvoraConversation.id == conversation_id,
            AlvoraConversation.user_id == user_id,
        ).first()
        if not conv:
            return False
        db.query(AlvoraMessage).filter(AlvoraMessage.conversation_id == conversation_id).delete()
        db.delete(conv)
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()


def get_quick_prompts() -> list[dict[str, str]]:
    """Return the predefined conversation starters."""
    return list(QUICK_PROMPTS)


def alvora_status(user_id: int) -> dict:
    """Check if Alvora is available (provider configured)."""
    try:
        provider = _get_provider_for_user(user_id)
        available = provider is not None and provider.is_available()
        name = provider.get_name() if provider else None
        return {"available": available, "provider": name}
    except Exception as exc:
        return {"available": False, "provider": None, "error": str(exc)}
