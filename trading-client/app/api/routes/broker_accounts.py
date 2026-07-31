"""Broker account CRUD endpoints — manage user's broker connections."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services.auth import LocalUser, get_current_user
from app.services.broker_account_service import (
    create_account,
    delete_account,
    get_account,
    list_accounts,
    revoke_account,
    sync_account,
    update_account,
    validate_credentials,
)

router = APIRouter(prefix="/api/broker-accounts", tags=["broker-accounts"])


class ValidateRequest(BaseModel):
    brokerId: str
    apiKey: str
    apiSecret: str
    passphrase: str | None = None
    environment: str = "live"


class CreateRequest(BaseModel):
    brokerId: str
    displayName: str | None = None
    apiKey: str
    apiSecret: str
    passphrase: str | None = None
    environment: str = "live"


class UpdateRequest(BaseModel):
    displayName: str | None = None
    environment: str | None = None


@router.get("")
def list_user_accounts(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    """List all broker accounts for the current user (no secrets)."""
    return list_accounts(db, current_user.id)


@router.post("/validate")
def validate(
    req: ValidateRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Validate credentials against the broker without saving them."""
    return validate_credentials(
        broker_id=req.brokerId,
        api_key=req.apiKey,
        api_secret=req.apiSecret,
        passphrase=req.passphrase,
        environment=req.environment,
    )


@router.post("")
def create(
    req: CreateRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Create a new broker account with encrypted credentials."""
    try:
        return create_account(
            db=db,
            user_id=current_user.id,
            broker_id=req.brokerId,
            api_key=req.apiKey,
            api_secret=req.apiSecret,
            passphrase=req.passphrase,
            display_name=req.displayName,
            environment=req.environment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{account_id}")
def get_one(
    account_id: str,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Get a single broker account by ID (no secrets)."""
    result = get_account(db, account_id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return result


@router.patch("/{account_id}")
def update(
    account_id: str,
    req: UpdateRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Update broker account metadata (not credentials)."""
    result = update_account(
        db=db,
        account_id=account_id,
        user_id=current_user.id,
        display_name=req.displayName,
        environment=req.environment,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return result


@router.delete("/{account_id}")
def delete(
    account_id: str,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Delete a broker account and its encrypted credentials."""
    success = delete_account(db, account_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return {"deleted": True}


@router.post("/{account_id}/sync")
def sync(
    account_id: str,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Sync a broker account — re-validate and update last_sync_at."""
    result = sync_account(db, account_id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return result


@router.post("/{account_id}/revoke")
def revoke(
    account_id: str,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Revoke a broker account — mark as REVOKED."""
    result = revoke_account(db, account_id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return result


@router.get("/binance/credentials")
def get_binance_credentials(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Return decrypted Binance API keys for client-side signing.

    The client uses these to sign requests locally (HMAC-SHA256) and
    sends them through the VPS proxy. Keys are never sent to the proxy.
    """
    from app.api.helpers import resolve_broker_credentials

    creds = resolve_broker_credentials("binance", current_user)
    if not creds:
        raise HTTPException(status_code=404, detail="No hay cuenta de Binance configurada")

    return {
        "api_key": creds.api_key,
        "api_secret": creds.api_secret,
        "testnet": creds.testnet,
    }
