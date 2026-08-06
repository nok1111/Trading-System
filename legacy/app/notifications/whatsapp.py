"""WhatsApp Business Cloud API notifications for trade execution."""

import logging

import httpx

logger = logging.getLogger(__name__)

_WHATSAPP_API_URL = "https://graph.facebook.com/v18.0"


def send_whatsapp_message(
    phone_number_id: str,
    access_token: str,
    to_number: str,
    message: str,
) -> bool:
    """Send a WhatsApp text message via Meta Cloud API.

    Args:
        phone_number_id: WhatsApp Business phone number ID
        access_token: Meta Graph API access token
        to_number: Recipient phone number (E.164 format, e.g. "1234567890")
        message: Text message content

    Returns True if sent successfully, False otherwise.
    """
    url = f"{_WHATSAPP_API_URL}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "text",
        "text": {"body": message},
    }
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=10.0)
        resp.raise_for_status()
        logger.info("WhatsApp message sent to %s", to_number)
        return True
    except Exception as exc:
        logger.warning("Failed to send WhatsApp message: %s", exc)
        return False


def notify_trade_executed(
    side: str,
    symbol: str,
    quantity: str,
    price: str,
    strategy: str = "",
    phone_number_id: str = "",
    access_token: str = "",
    to_number: str = "",
) -> None:
    """Send a trade execution notification via WhatsApp.

    All API credentials must be provided; if missing, notification is skipped silently.
    """
    if not all([phone_number_id, access_token, to_number]):
        return

    emoji = "🟢" if side.upper() == "BUY" else "🔴"
    msg = (
        f"{emoji} TRADE EJECUTADO\n"
        f"Side: {side}\n"
        f"Symbol: {symbol}\n"
        f"Qty: {quantity}\n"
        f"Price: ${price}\n"
        f"Strategy: {strategy}\n"
        f"Time: {__import__('datetime').datetime.now().strftime('%H:%M:%S')}"
    )
    send_whatsapp_message(phone_number_id, access_token, to_number, msg)
