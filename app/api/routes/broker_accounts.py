"""Broker accounts endpoints — manage user's broker API credentials."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database.models import User
from app.database.session import SessionLocal
from app.services.auth import get_current_user
from app.services.crypto import decrypt, encrypt

router = APIRouter(prefix="/api", tags=["broker-accounts"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class BrokerCapabilityFlags(BaseModel):
    spot: bool = True
    margin: bool = False
    futures: bool = False
    staking: bool = False
    earn: bool = False
    websocket: bool = True
    marketOrders: bool = True
    limitOrders: bool = True
    stopOrders: bool = True
    withdrawals: bool = False


class SupportedBroker(BaseModel):
    brokerId: str
    displayName: str
    logoUrl: Optional[str] = None
    websiteUrl: Optional[str] = None
    apiDocsUrl: Optional[str] = None
    supportedMarkets: list[str] = []
    capabilities: BrokerCapabilityFlags
    requiresPassphrase: bool = False
    environments: list[str] = []
    implemented: bool = True


class BrokerAccountPermissions(BaseModel):
    read: bool = True
    trade: bool = False
    withdraw: bool = False


class BrokerAccount(BaseModel):
    id: str
    brokerId: str
    displayName: str
    status: str
    permissions: BrokerAccountPermissions
    environment: str
    lastSyncAt: Optional[str] = None
    apiKeyPreview: str


class CredentialValidationRequest(BaseModel):
    brokerId: str
    apiKey: str
    apiSecret: str
    passphrase: Optional[str] = None
    environment: Optional[str] = None


class CredentialValidationResponse(BaseModel):
    valid: bool
    status: str
    permissions: BrokerAccountPermissions
    errorMessage: Optional[str] = None


class CreateBrokerAccountRequest(BaseModel):
    brokerId: str
    displayName: Optional[str] = None
    apiKey: str
    apiSecret: str
    passphrase: Optional[str] = None
    environment: Optional[str] = None


# ---------------------------------------------------------------------------
# Static broker definitions
# ---------------------------------------------------------------------------

SUPPORTED_BROKERS: list[SupportedBroker] = [
    SupportedBroker(
        brokerId="binance",
        displayName="Binance",
        websiteUrl="https://www.binance.com",
        apiDocsUrl="https://binance-docs.github.io/apidocs",
        supportedMarkets=["spot"],
        capabilities=BrokerCapabilityFlags(
            spot=True, margin=False, futures=False, earn=True,
            websocket=True, marketOrders=True, limitOrders=True, stopOrders=True,
        ),
        requiresPassphrase=False,
        environments=["testnet", "live"],
        implemented=True,
    ),
    SupportedBroker(
        brokerId="bybit",
        displayName="Bybit",
        websiteUrl="https://www.bybit.com",
        apiDocsUrl="https://bybit-exchange.github.io/docs/v5/intro",
        supportedMarkets=["spot", "futures"],
        capabilities=BrokerCapabilityFlags(
            spot=True, margin=True, futures=True,
            websocket=True, marketOrders=True, limitOrders=True, stopOrders=True,
        ),
        requiresPassphrase=False,
        environments=["testnet", "live"],
        implemented=False,
    ),
    SupportedBroker(
        brokerId="coinbase",
        displayName="Coinbase",
        websiteUrl="https://www.coinbase.com",
        apiDocsUrl="https://docs.cloud.coinbase.com",
        supportedMarkets=["spot", "futures"],
        capabilities=BrokerCapabilityFlags(
            spot=True, futures=True, staking=True, earn=True,
            websocket=True, marketOrders=True, limitOrders=True,
        ),
        requiresPassphrase=False,
        environments=["sandbox", "live"],
        implemented=False,
    ),
    SupportedBroker(
        brokerId="kraken",
        displayName="Kraken",
        websiteUrl="https://www.kraken.com",
        apiDocsUrl="https://docs.kraken.com",
        supportedMarkets=["spot", "margin"],
        capabilities=BrokerCapabilityFlags(
            spot=True, margin=True, staking=True,
            websocket=True, marketOrders=True, limitOrders=True, stopOrders=True,
        ),
        requiresPassphrase=False,
        environments=["live"],
        implemented=False,
    ),
    SupportedBroker(
        brokerId="okx",
        displayName="OKX",
        websiteUrl="https://www.okx.com",
        apiDocsUrl="https://www.okx.com/docs-v5",
        supportedMarkets=["spot", "margin", "futures"],
        capabilities=BrokerCapabilityFlags(
            spot=True, margin=True, futures=True, staking=True, earn=True,
            websocket=True, marketOrders=True, limitOrders=True, stopOrders=True,
        ),
        requiresPassphrase=True,
        environments=["demo", "live"],
        implemented=False,
    ),
]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/brokers")
def list_brokers() -> list[dict]:
    """Returns supported brokers."""
    return [b.model_dump() for b in SUPPORTED_BROKERS]


@router.get("/broker-accounts")
def list_broker_accounts(
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[dict]:
    """Returns the user's connected broker accounts."""
    accounts: list[dict] = []
    if current_user.binance_api_key_enc:
        try:
            key_preview = decrypt(current_user.binance_api_key_enc)[:8] + "..."
        except Exception:
            key_preview = "..."
        accounts.append({
            "id": "binance-main",
            "brokerId": "binance",
            "displayName": "Binance",
            "status": "CONNECTED_READ_ONLY",
            "permissions": {"read": True, "trade": False, "withdraw": False},
            "environment": "live",
            "lastSyncAt": None,
            "apiKeyPreview": key_preview,
        })
    return accounts


@router.post("/broker-accounts/validate")
def validate_credentials(
    req: CredentialValidationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Validates broker credentials by making a test API call to Binance."""
    if req.brokerId != "binance":
        raise HTTPException(status_code=400, detail="Solo Binance está soportado por ahora")

    try:
        from app.brokers.binance_broker import BinanceBroker

        testnet = req.environment == "testnet"
        broker = BinanceBroker(
            api_key=req.apiKey,
            api_secret=req.apiSecret,
            testnet=testnet,
        )

        # Try a simple API call — fetch account info
        account = broker.get_account()
        if account is not None:
            return {
                "valid": True,
                "status": "CONNECTED_READ_ONLY",
                "permissions": {"read": True, "trade": False, "withdraw": False},
                "errorMessage": None,
            }
    except Exception as exc:
        return {
            "valid": False,
            "status": "DISCONNECTED",
            "permissions": {"read": False, "trade": False, "withdraw": False},
            "errorMessage": str(exc),
        }

    return {
        "valid": False,
        "status": "DISCONNECTED",
        "permissions": {"read": False, "trade": False, "withdraw": False},
        "errorMessage": "No se pudo conectar con Binance",
    }


@router.post("/broker-accounts")
def create_broker_account(
    req: CreateBrokerAccountRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Creates a broker account — stores encrypted credentials on the user."""
    if req.brokerId != "binance":
        raise HTTPException(status_code=400, detail="Solo Binance está soportado por ahora")

    db = SessionLocal()
    try:
        user = db.get(User, current_user.id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        # Encrypt and store credentials
        user.binance_api_key_enc = encrypt(req.apiKey)
        user.binance_api_secret_enc = encrypt(req.apiSecret)
        db.commit()
        db.refresh(user)

        key_preview = decrypt(user.binance_api_key_enc)[:8] + "..."
        return {
            "id": "binance-main",
            "brokerId": "binance",
            "displayName": req.displayName or "Binance",
            "status": "CONNECTED_READ_ONLY",
            "permissions": {"read": True, "trade": False, "withdraw": False},
            "environment": req.environment or "live",
            "lastSyncAt": None,
            "apiKeyPreview": key_preview,
        }
    finally:
        db.close()


@router.delete("/broker-accounts/{account_id}")
def delete_broker_account(
    account_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Deletes a broker account — removes stored credentials."""
    db = SessionLocal()
    try:
        user = db.get(User, current_user.id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        user.binance_api_key_enc = None
        user.binance_api_secret_enc = None
        db.commit()
        return {"deleted": True}
    finally:
        db.close()
