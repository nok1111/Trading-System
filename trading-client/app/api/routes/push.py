"""Web Push notification endpoints.

Endpoints:
  GET  /api/push/vapid-public-key  — returns the VAPID public key for the browser
  POST /api/push/subscribe         — store a push subscription
  POST /api/push/unsubscribe       — remove a push subscription
  POST /api/push/test              — send a test push notification
"""

import json
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.database.models.push_subscription import PushSubscription
from app.services.auth import LocalUser, get_current_user

router = APIRouter(prefix="/api/push", tags=["push"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db)]


# VAPID keys — generated on the server
VAPID_PRIVATE_KEY_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "vapid_private.pem")
VAPID_PUBLIC_KEY_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "vapid_public.pem")

# VAPID subject (contact info)
VAPID_SUBJECT = "mailto:admin@alvora.app"


def _get_vapid_public_key_b64() -> str:
    """Read the VAPID public key and return as base64url (for browser use)."""
    import base64
    from cryptography.hazmat.primitives import serialization

    key_path = os.path.abspath(VAPID_PUBLIC_KEY_PATH)
    if not os.path.exists(key_path):
        raise HTTPException(status_code=500, detail="VAPID keys not configured on server")

    with open(key_path, "rb") as f:
        pub = serialization.load_pem_public_key(f.read())

    raw = pub.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


class PushSubscriptionRequest(BaseModel):
    endpoint: str
    keys: dict  # { p256dh: str, auth: str }


@router.get("/vapid-public-key")
def get_vapid_public_key(
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Return the VAPID public key for the browser to use for push subscription."""
    return {"publicKey": _get_vapid_public_key_b64()}


@router.post("/subscribe")
def push_subscribe(
    req: PushSubscriptionRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: DbSession = None,
) -> dict:
    """Store a push subscription for the current user."""
    # Check if subscription already exists
    existing = db.query(PushSubscription).filter(
        PushSubscription.user_id == current_user.id,
        PushSubscription.endpoint == req.endpoint,
    ).first()

    if existing:
        return {"status": "already_subscribed"}

    sub = PushSubscription(
        user_id=current_user.id,
        endpoint=req.endpoint,
        p256dh_key=req.keys.get("p256dh", ""),
        auth_key=req.keys.get("auth", ""),
    )
    db.add(sub)
    db.commit()
    return {"status": "subscribed"}


@router.post("/unsubscribe")
def push_unsubscribe(
    req: PushSubscriptionRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: DbSession = None,
) -> dict:
    """Remove a push subscription for the current user."""
    db.query(PushSubscription).filter(
        PushSubscription.user_id == current_user.id,
        PushSubscription.endpoint == req.endpoint,
    ).delete()
    db.commit()
    return {"status": "unsubscribed"}


@router.post("/test")
def push_test(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: DbSession = None,
) -> dict:
    """Send a test push notification to all of the user's subscriptions."""
    subs = db.query(PushSubscription).filter(
        PushSubscription.user_id == current_user.id,
    ).all()

    if not subs:
        raise HTTPException(status_code=404, detail="No push subscriptions found")

    from pywebpush import webpush, WebPushException

    private_key_path = os.path.abspath(VAPID_PRIVATE_KEY_PATH)
    payload = json.dumps({
        "title": "Alvora Test",
        "body": "Notificaciones push funcionando correctamente!",
        "icon": "/icon.png",
        "badge": "/badge.png",
    })

    sent = 0
    errors = 0
    for sub in subs:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh_key,
                "auth": sub.auth_key,
            },
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=private_key_path,
                vapid_claims={"sub": VAPID_SUBJECT},
            )
            sent += 1
        except WebPushException as exc:
            # If 410 Gone or 404, the subscription is no longer valid — remove it
            if hasattr(exc, "response") and exc.response and exc.response.status_code in (404, 410):
                db.delete(sub)
            errors += 1

    db.commit()
    return {"status": "ok", "sent": sent, "errors": errors}


def send_push_to_user(db: Session, user_id: int, title: str, body: str, url: str = "/") -> int:
    """Send a push notification to all subscriptions of a user.

    Returns the number of successfully sent notifications.
    """
    subs = db.query(PushSubscription).filter(
        PushSubscription.user_id == user_id,
    ).all()

    if not subs:
        return 0

    from pywebpush import webpush, WebPushException

    private_key_path = os.path.abspath(VAPID_PRIVATE_KEY_PATH)
    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url,
        "icon": "/icon.png",
    })

    sent = 0
    for sub in subs:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh_key,
                "auth": sub.auth_key,
            },
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=private_key_path,
                vapid_claims={"sub": VAPID_SUBJECT},
            )
            sent += 1
        except WebPushException as exc:
            if hasattr(exc, "response") and exc.response and exc.response.status_code in (404, 410):
                db.delete(sub)
        except Exception:
            pass

    db.commit()
    return sent
