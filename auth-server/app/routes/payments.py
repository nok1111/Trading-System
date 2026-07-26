"""Payment endpoints — Binance Pay for subscription upgrades."""

import json
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.config import get_settings
from app.database.models.payment import Payment
from app.database.models.user import User
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
    """Create a Binance Pay order for subscription upgrade."""
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

    # Save payment record to DB
    db = SessionLocal()
    try:
        payment = Payment(
            user_id=current_user.id,
            order_id=result["order_id"],
            plan=req.plan,
            amount=result["amount"],
            currency=result["currency"],
            status="PENDING",
            prepay_id=result.get("prepay_id"),
            checkout_url=result.get("checkout_url"),
        )
        db.add(payment)
        db.commit()
    finally:
        db.close()

    return result


@router.get("/status/{order_id}")
def check_payment_status(
    order_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Check the status of a payment order."""
    result = query_order_status(order_id)
    if not result:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    # If paid, upgrade the user's plan
    if result.get("status") == "PAID":
        db = SessionLocal()
        try:
            user = db.get(User, current_user.id)
            if user and user.subscription != result.get("plan"):
                parts = order_id.split("-")
                if len(parts) >= 2:
                    plan = parts[1].lower()
                    if plan in ("pro", "premium"):
                        user.subscription = plan
                        # Update payment record
                        payment = db.query(Payment).filter_by(order_id=order_id).first()
                        if payment:
                            payment.status = "PAID"
                            payment.paid_at = datetime.now(timezone.utc)
                        db.commit()
                        result["upgraded"] = True
                        result["new_plan"] = plan
        finally:
            db.close()
    return result


@router.get("/plans")
def get_payment_plans() -> dict:
    """Return available plans with prices."""
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
    """Webhook for Binance Pay payment notifications."""
    body = await request.body()
    payload = body.decode()

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
            parts = merchant_trade_no.split("-")
            if len(parts) >= 3:
                user_id = int(parts[2])
                user = db.get(User, user_id)
                if user:
                    user.subscription = plan
                    # Update payment record
                    payment = db.query(Payment).filter_by(order_id=merchant_trade_no).first()
                    if payment:
                        payment.status = "PAID"
                        payment.paid_at = datetime.now(timezone.utc)
                    db.commit()
        except Exception:
            pass
        finally:
            db.close()

    return {"returnCode": "SUCCESS", "returnMessage": "OK"}
