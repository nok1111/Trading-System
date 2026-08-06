"""Broker account service — business logic for creating, validating, syncing, and revoking broker accounts."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.brokers.base import BrokerAdapter, BrokerError
from app.brokers.capabilities import BrokerCapabilities
from app.brokers.models import BrokerCredentials, BrokerInfo, CredentialValidationResult
from app.brokers.registry import get_adapter, get_capabilities, is_implemented, list_brokers
from app.database.models.broker_account import BrokerAccount as BrokerAccountModel
from app.services.crypto import decrypt, encrypt


def _mask_api_key(key: str) -> str:
    if not key or len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


def _to_safe_dict(account: BrokerAccountModel) -> dict[str, Any]:
    """Convert a BrokerAccount model to a safe dict (no secrets)."""
    return {
        "id": account.id,
        "brokerId": account.broker_id,
        "displayName": account.display_name,
        "status": account.status,
        "permissions": {
            "read": account.permissions_read,
            "trade": account.permissions_trade,
            "withdraw": account.permissions_withdraw,
        },
        "environment": account.environment,
        "lastSyncAt": account.last_sync_at.isoformat() if account.last_sync_at else None,
        "apiKeyPreview": _mask_api_key(decrypt(account.api_key_enc)) if account.api_key_enc else "",
    }


def get_supported_brokers() -> list[dict[str, Any]]:
    """Return all supported brokers with capabilities and metadata."""
    brokers: list[dict[str, Any]] = []
    for info in list_brokers():
        caps = get_capabilities(info.broker_id)
        brokers.append(
            {
                "brokerId": info.broker_id,
                "displayName": info.display_name,
                "logoUrl": info.logo_url,
                "websiteUrl": info.website_url,
                "apiDocsUrl": info.api_docs_url,
                "supportedMarkets": [m.value for m in info.supported_markets],
                "capabilities": {
                    "spot": caps.spot,
                    "margin": caps.margin,
                    "futures": caps.futures,
                    "staking": caps.staking,
                    "earn": caps.earn,
                    "websocket": caps.websocket,
                    "marketOrders": caps.market_orders,
                    "limitOrders": caps.limit_orders,
                    "stopOrders": caps.stop_orders,
                    "withdrawals": caps.withdrawals,
                },
                "requiresPassphrase": _requires_passphrase(info.broker_id),
                "environments": _get_environments(info.broker_id),
                "implemented": _is_implemented(info.broker_id),
            }
        )
    return brokers


def _is_implemented(broker_id: str) -> bool:
    """Check if a broker adapter is fully implemented (not a stub)."""
    return is_implemented(broker_id)


def _requires_passphrase(broker_id: str) -> bool:
    """Check if a broker requires a passphrase (e.g. OKX, KuCoin)."""
    from app.brokers.adapters.ccxt_adapter import get_exchange_meta

    if broker_id == "binance":
        return False
    meta = get_exchange_meta(broker_id)
    return meta.get("passphrase", False)


def _get_environments(broker_id: str) -> list[str]:
    from app.brokers.adapters.ccxt_adapter import get_exchange_meta

    if broker_id == "binance":
        return ["testnet", "live"]
    meta = get_exchange_meta(broker_id)
    if meta.get("sandbox"):
        return ["sandbox", "live"]
    return ["live"]


def validate_credentials(
    broker_id: str,
    api_key: str,
    api_secret: str,
    passphrase: str | None = None,
    environment: str = "live",
) -> dict[str, Any]:
    """Validate credentials against the broker without saving them."""
    creds = BrokerCredentials(
        broker_id=broker_id,
        api_key=api_key,
        api_secret=api_secret,
        passphrase=passphrase,
        testnet=environment == "testnet",
    )

    try:
        adapter = get_adapter(broker_id, creds)
    except BrokerError as exc:
        return {
            "valid": False,
            "status": "NOT_CONNECTED",
            "permissions": {"read": False, "trade": False, "withdraw": False},
            "errorMessage": str(exc),
        }

    try:
        result: CredentialValidationResult = adapter.validate_credentials()
    except NotImplementedError:
        return {
            "valid": False,
            "status": "NOT_CONNECTED",
            "permissions": {"read": False, "trade": False, "withdraw": False},
            "errorMessage": f"Broker {broker_id} no implementado todavía",
        }
    except Exception as exc:
        return {
            "valid": False,
            "status": "DEGRADED",
            "permissions": {"read": False, "trade": False, "withdraw": False},
            "errorMessage": str(exc),
        }

    has_withdraw = any("withdraw" in p.lower() for p in result.permissions)
    if has_withdraw:
        return {
            "valid": False,
            "status": "SECURITY_BLOCKED",
            "permissions": {"read": True, "trade": False, "withdraw": True},
            "errorMessage": "Las credenciales tienen permiso de retiro. Por seguridad, no se permiten.",
        }

    has_trade = any("trad" in p.lower() for p in result.permissions)
    status = "CONNECTED_TRADING" if has_trade else "CONNECTED_READ_ONLY"

    return {
        "valid": result.valid,
        "status": status if result.valid else "DISCONNECTED",
        "permissions": {"read": result.valid, "trade": has_trade and result.valid, "withdraw": False},
        "errorMessage": result.error_message,
    }


def create_account(
    db: Session,
    user_id: int,
    broker_id: str,
    api_key: str,
    api_secret: str,
    passphrase: str | None = None,
    display_name: str | None = None,
    environment: str = "live",
) -> dict[str, Any]:
    """Create a new broker account with encrypted credentials."""
    validation = validate_credentials(
        broker_id, api_key, api_secret, passphrase, environment
    )

    if not validation["valid"]:
        raise ValueError(f"Credenciales inválidas: {validation.get('errorMessage', '')}")

    account_id = str(uuid.uuid4())
    account = BrokerAccountModel(
        id=account_id,
        user_id=user_id,
        broker_id=broker_id,
        display_name=display_name,
        api_key_enc=encrypt(api_key),
        api_secret_enc=encrypt(api_secret),
        passphrase_enc=encrypt(passphrase) if passphrase else None,
        environment=environment,
        status=validation["status"],
        permissions_read=validation["permissions"]["read"],
        permissions_trade=validation["permissions"]["trade"],
        permissions_withdraw=False,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return _to_safe_dict(account)


def list_accounts(db: Session, user_id: int) -> list[dict[str, Any]]:
    """List all broker accounts for a user (safe dicts, no secrets)."""
    rows = db.execute(
        select(BrokerAccountModel).where(BrokerAccountModel.user_id == user_id)
    ).scalars().all()
    return [_to_safe_dict(r) for r in rows]


def get_account(db: Session, account_id: str, user_id: int) -> dict[str, Any] | None:
    """Get a single broker account by ID (safe dict, no secrets)."""
    row = db.execute(
        select(BrokerAccountModel).where(
            BrokerAccountModel.id == account_id,
            BrokerAccountModel.user_id == user_id,
        )
    ).scalar_one_or_none()
    if not row:
        return None
    return _to_safe_dict(row)


def update_account(
    db: Session,
    account_id: str,
    user_id: int,
    display_name: str | None = None,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """Update broker account metadata (not credentials)."""
    row = db.execute(
        select(BrokerAccountModel).where(
            BrokerAccountModel.id == account_id,
            BrokerAccountModel.user_id == user_id,
        )
    ).scalar_one_or_none()
    if not row:
        return None
    if display_name is not None:
        row.display_name = display_name
    if environment is not None:
        row.environment = environment
    db.commit()
    db.refresh(row)
    return _to_safe_dict(row)


def delete_account(db: Session, account_id: str, user_id: int) -> bool:
    """Delete a broker account and its encrypted credentials."""
    row = db.execute(
        select(BrokerAccountModel).where(
            BrokerAccountModel.id == account_id,
            BrokerAccountModel.user_id == user_id,
        )
    ).scalar_one_or_none()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def sync_account(db: Session, account_id: str, user_id: int) -> dict[str, Any] | None:
    """Sync a broker account — update last_sync_at and re-validate status."""
    row = db.execute(
        select(BrokerAccountModel).where(
            BrokerAccountModel.id == account_id,
            BrokerAccountModel.user_id == user_id,
        )
    ).scalar_one_or_none()
    if not row:
        return None

    try:
        creds = BrokerCredentials(
            broker_id=row.broker_id,
            api_key=decrypt(row.api_key_enc),
            api_secret=decrypt(row.api_secret_enc),
            passphrase=decrypt(row.passphrase_enc) if row.passphrase_enc else None,
            testnet=row.environment == "testnet",
        )
        adapter = get_adapter(row.broker_id, creds)
        result = adapter.validate_credentials()
        if result.valid:
            has_trade = any("trad" in p.lower() for p in result.permissions)
            row.status = "CONNECTED_TRADING" if has_trade else "CONNECTED_READ_ONLY"
            row.permissions_read = True
            row.permissions_trade = has_trade
        else:
            row.status = "DEGRADED"
    except Exception:
        row.status = "DEGRADED"

    row.last_sync_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _to_safe_dict(row)


def revoke_account(db: Session, account_id: str, user_id: int) -> dict[str, Any] | None:
    """Revoke a broker account — mark as REVOKED but keep record."""
    row = db.execute(
        select(BrokerAccountModel).where(
            BrokerAccountModel.id == account_id,
            BrokerAccountModel.user_id == user_id,
        )
    ).scalar_one_or_none()
    if not row:
        return None
    row.status = "REVOKED"
    db.commit()
    db.refresh(row)
    return _to_safe_dict(row)


def resolve_account_credentials(
    db: Session,
    account_id: str,
    user_id: int,
) -> BrokerCredentials | None:
    """Resolve encrypted credentials for a broker account into BrokerCredentials."""
    row = db.execute(
        select(BrokerAccountModel).where(
            BrokerAccountModel.id == account_id,
            BrokerAccountModel.user_id == user_id,
        )
    ).scalar_one_or_none()
    if not row:
        return None
    return BrokerCredentials(
        broker_id=row.broker_id,
        api_key=decrypt(row.api_key_enc),
        api_secret=decrypt(row.api_secret_enc),
        passphrase=decrypt(row.passphrase_enc) if row.passphrase_enc else None,
        testnet=row.environment == "testnet",
    )
