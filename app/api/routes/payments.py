"""Binance Pay — Subscription payment endpoints."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.config import get_settings
from app.database.models import User
from app.database.session import SessionLocal
from app.services.auth import get_current_user
from app.services.binance_pay import (
    PLAN_PRICES,
    create_payment_order,
    query_order_status,
    verify_webhook_signature,
)

router = APIRouter(prefix="/api/payments", tags=["payments"])


class PaymentRequest(BaseModel):
    plan: str  # "pro" or "premium"


@router.post("/create")
def create_payment(
    req: PaymentRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Crea una orden de pago en Binance Pay para upgrade de plan."""
    if req.plan not in ("pro", "premium"):
        raise HTTPException(status_code=400, detail="Plan inválido. Opciones: pro, premium")
    if current_user.subscription == req.plan:
        raise HTTPException(status_code=400, detail=f"Ya tienes el plan {req.plan}")

    result = create_payment_order(req.plan, current_user.id, current_user.email)
    if not result:
        raise HTTPException(
            status_code=503,
            detail="Binance Pay no configurado. Contacta al administrador.",
        )
    return result


@router.get("/status/{order_id}")
def check_payment_status(
    order_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Verifica el estado de una orden de pago."""
    result = query_order_status(order_id)
    if not result:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    # If paid, upgrade the user's plan
    if result.get("status") == "PAID":
        db = SessionLocal()
        try:
            user = db.get(User, current_user.id)
            if user and user.subscription != result.get("plan"):
                # Extract plan from order_id: ALVORA-PRO-123-...
                parts = order_id.split("-")
                if len(parts) >= 2:
                    plan = parts[1].lower()
                    if plan in ("pro", "premium"):
                        user.subscription = plan
                        db.commit()
                        result["upgraded"] = True
                        result["new_plan"] = plan
        finally:
            db.close()
    return result


@router.get("/plans")
def get_payment_plans() -> dict:
    """Retorna los planes disponibles con precios."""
    return {
        "plans": {
            key: {
                "label": val["label"],
                "price": val["amount"],
                "currency": val["currency"],
                "duration": val["duration"],
            }
            for key, val in PLAN_PRICES.items()
        },
        "payment_method": "binance_pay",
        "enabled": bool(get_settings().BINANCE_PAY_API_KEY),
    }


@router.post("/webhook")
async def binance_pay_webhook(request: Request) -> dict:
    """Webhook para recibir notificaciones de pago de Binance Pay."""
    body = await request.body()
    payload = body.decode()

    # Verify signature
    timestamp = request.headers.get("BinancePay-Timestamp", "")
    nonce = request.headers.get("BinancePay-Nonce", "")
    signature = request.headers.get("BinancePay-Signature", "")

    if not verify_webhook_signature(timestamp, nonce, payload, signature):
        raise HTTPException(status_code=401, detail="Signature verification failed")

    data = json.loads(payload)
    merchant_trade_no = data.get("merchantTradeNo", "")
    status = data.get("status", "")
    plan = data.get("goods", {}).get("referenceGoodsId", "").replace("alvora-", "").replace("-monthly", "")

    if status == "PAID" and plan in ("pro", "premium"):
        db = SessionLocal()
        try:
            # Extract user_id from order: ALVORA-PRO-123-1690293...
            parts = merchant_trade_no.split("-")
            if len(parts) >= 3:
                user_id = int(parts[2])
                user = db.get(User, user_id)
                if user:
                    user.subscription = plan
                    db.commit()
        except Exception:
            pass
        finally:
            db.close()

    return {"returnCode": "SUCCESS", "returnMessage": "OK"}
