"""Binance Pay integration — Merchant API.

Copied from the main project, adapted to use Auth Server settings.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import httpx

from app.config import get_settings

settings = get_settings()

BINANCE_PAY_BASE = "https://bpay.binanceapi.com"

PLAN_PRICES = {
    "pro": {"amount": "29.00", "currency": "USDT", "label": "Pro", "duration": "month"},
    "premium": {"amount": "99.00", "currency": "USDT", "label": "Premium", "duration": "month"},
}


def _get_timestamp_ms() -> int:
    return int(time.time() * 1000)


def _build_signature(timestamp: str, nonce: str, payload: str) -> str:
    message = f"{timestamp}\n{nonce}\n{payload}\n"
    return hmac.new(
        settings.BINANCE_PAY_API_SECRET.encode(),
        message.encode(),
        hashlib.sha512,
    ).hexdigest().upper()


def _get_headers(payload: str) -> dict:
    timestamp = str(_get_timestamp_ms())
    nonce = str(_get_timestamp_ms()) + " Alvora"
    signature = _build_signature(timestamp, nonce, payload)
    return {
        "BinancePay-Timestamp": timestamp,
        "BinancePay-Nonce": nonce,
        "BinancePay-Certificate-SN": settings.BINANCE_PAY_API_KEY or "",
        "BinancePay-Signature": signature,
        "Content-Type": "application/json",
    }


def create_payment_order(plan: str, user_id: int, user_email: str) -> dict | None:
    """Create a Binance Pay order for subscription upgrade."""
    if not settings.BINANCE_PAY_API_KEY or not settings.BINANCE_PAY_API_SECRET:
        return None

    plan_info = PLAN_PRICES.get(plan)
    if not plan_info:
        return None

    merchant_id = settings.BINANCE_PAY_MERCHANT_ID or "Alvora"
    order_id = f"ALVORA-{plan.upper()}-{user_id}-{int(time.time())}"

    payload_body = {
        "env": {"terminalType": "WEB"},
        "merchantTradeNo": order_id,
        "merchantTradeName": f"Alvora {plan_info['label']} - Monthly",
        "tradeAmount": {"value": plan_info["amount"], "currency": plan_info["currency"]},
        "goods": {
            "goodsType": "01",
            "goodsCategory": "Z000",
            "referenceGoodsId": f"alvora-{plan}-monthly",
            "goodsName": f"Alvora {plan_info['label']} Subscription",
            "goodsDetail": f"Monthly subscription to Alvora {plan_info['label']} plan for {user_email}",
        },
        "returnUrl": "/dashboard?payment=success",
        "cancelUrl": "/dashboard?payment=cancelled",
    }

    payload_str = json.dumps(payload_body, separators=(",", ":"))
    headers = _get_headers(payload_str)

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{BINANCE_PAY_BASE}/binancepay/openapi/v3/order",
                headers=headers,
                content=payload_str,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "SUCCESS":
                return {
                    "order_id": order_id,
                    "prepay_id": data.get("data", {}).get("prepayId"),
                    "checkout_url": data.get("data", {}).get("checkoutUrl"),
                    "qr_code": data.get("data", {}).get("qrcodeLink"),
                    "deeplink": data.get("data", {}).get("deeplink"),
                    "plan": plan,
                    "amount": plan_info["amount"],
                    "currency": plan_info["currency"],
                }
            return None
    except Exception:
        return None


def query_order_status(merchant_trade_no: str) -> dict | None:
    """Query the status of a Binance Pay order."""
    if not settings.BINANCE_PAY_API_KEY or not settings.BINANCE_PAY_API_SECRET:
        return None

    payload_body = {"merchantTradeNo": merchant_trade_no}
    payload_str = json.dumps(payload_body, separators=(",", ":"))
    headers = _get_headers(payload_str)

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(
                f"{BINANCE_PAY_BASE}/binancepay/openapi/v3/order/query",
                headers=headers,
                content=payload_str,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "SUCCESS":
                order_data = data.get("data", {})
                return {
                    "status": order_data.get("status"),
                    "order_id": merchant_trade_no,
                    "paid_amount": order_data.get("tradeAmount", {}).get("value"),
                    "currency": order_data.get("tradeAmount", {}).get("currency"),
                }
            return None
    except Exception:
        return None


def verify_webhook_signature(timestamp: str, nonce: str, payload: str, signature: str) -> bool:
    expected = _build_signature(timestamp, nonce, payload)
    return expected == signature.upper()
