"""Servicio de notificaciones por Telegram."""

from __future__ import annotations

import httpx

from app.config import get_settings

settings = get_settings()


async def send_telegram_message(chat_id: str, text: str) -> bool:
    """Envía un mensaje a un chat de Telegram vía Bot API."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
            return resp.status_code == 200
    except Exception:
        return False


def send_telegram_message_sync(chat_id: str, text: str) -> bool:
    """Versión síncrona para usar en threads del AI agent."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return False
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
            return resp.status_code == 200
    except Exception:
        return False


def notify_trade(
    chat_id: str,
    action: str,
    symbol: str,
    quantity: float,
    price: float,
    reason: str = "",
) -> bool:
    """Notifica una operación de trading."""
    emoji = "🟢" if action.lower() == "buy" else "🔴"
    text = (
        f"{emoji} <b>Alvora — {action.upper()}</b>\n\n"
        f"📊 Par: <b>{symbol}</b>\n"
        f"💰 Cantidad: {quantity}\n"
        f"💵 Precio: ${price:.4f}\n"
    )
    if reason:
        text += f"🤖 Razón: {reason}\n"
    return send_telegram_message_sync(chat_id, text)


def notify_stop_loss(chat_id: str, symbol: str, entry: float, exit_price: float, pnl: float) -> bool:
    """Notifica un stop-loss ejecutado."""
    text = (
        f"🛑 <b>Alvora — Stop-Loss</b>\n\n"
        f"📊 Par: <b>{symbol}</b>\n"
        f"📥 Entry: ${entry:.4f}\n"
        f"📤 Exit: ${exit_price:.4f}\n"
        f"📉 PnL: <b>${pnl:.2f}</b>\n"
    )
    return send_telegram_message_sync(chat_id, text)


def notify_take_profit(chat_id: str, symbol: str, entry: float, exit_price: float, pnl: float) -> bool:
    """Notifica un take-profit ejecutado."""
    text = (
        f"🎯 <b>Alvora — Take-Profit</b>\n\n"
        f"📊 Par: <b>{symbol}</b>\n"
        f"📥 Entry: ${entry:.4f}\n"
        f"📤 Exit: ${exit_price:.4f}\n"
        f"📈 PnL: <b>+${pnl:.2f}</b>\n"
    )
    return send_telegram_message_sync(chat_id, text)


def notify_ai_decision(chat_id: str, cycle: int, actions: list[dict]) -> bool:
    """Notifica las decisiones del AI agent en un ciclo."""
    if not actions:
        text = f"🤖 <b>Alvora — Ciclo {cycle}</b>\n\nSin acciones. Manteniendo posiciones."
    else:
        lines = [f"🤖 <b>Alvora — Ciclo {cycle}</b>\n"]
        for a in actions:
            emoji = "🟢" if a.get("type") == "buy" else "🔴"
            lines.append(f"{emoji} {a['type'].upper()} {a['symbol']} — {a.get('reason', '')[:80]}")
        text = "\n".join(lines)
    return send_telegram_message_sync(chat_id, text)
