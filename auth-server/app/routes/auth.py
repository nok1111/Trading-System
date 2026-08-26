"""Authentication endpoints (register, login, me, 2FA, sessions)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.user import User
from app.database.models.user_session import UserSession
from app.database.session import SessionLocal, get_db
from app.services.auth import (
    authenticate_user,
    create_access_token,
    create_session,
    get_active_sessions,
    get_current_user,
    hash_password,
    revoke_all_other_sessions,
    revoke_session,
)
from app.services.totp import (
    decrypt_totp_secret,
    encrypt_totp_secret,
    generate_backup_codes,
    generate_totp_secret,
    get_totp_uri,
    hash_backup_codes,
    remove_used_backup_code,
    verify_backup_code,
    verify_totp,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str
    totp_code: str | None = None
    backup_code: str | None = None
    device_name: str = "Unknown"


class Setup2FARequest(BaseModel):
    password: str  # verify current password before enabling


class Verify2FARequest(BaseModel):
    code: str


class Disable2FARequest(BaseModel):
    password: str
    code: str


class LoginWithBackupRequest(BaseModel):
    email: str
    password: str
    backup_code: str
    device_name: str = "Unknown"


def _extract_device_info(request: Request) -> dict:
    """Extract device info from request headers."""
    user_agent = request.headers.get("user-agent", "Unknown")
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else None)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    # Try to get a friendly device name from UA
    device_name = "Unknown"
    if "Windows" in user_agent:
        device_name = "Windows PC"
    elif "Mac" in user_agent:
        device_name = "Mac"
    elif "Linux" in user_agent:
        device_name = "Linux PC"
    elif "Android" in user_agent:
        device_name = "Android Device"
    elif "iOS" in user_agent or "iPhone" in user_agent or "iPad" in user_agent:
        device_name = "iOS Device"
    return {"device_name": device_name, "ip_address": ip, "user_agent": user_agent}


def _user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "subscription": user.subscription,
        "risk_profile": user.risk_profile,
        "totp_enabled": user.totp_enabled,
    }


@router.post("/register")
def auth_register(req: RegisterRequest) -> dict:
    """Register a new user (free plan by default)."""
    db = SessionLocal()
    try:
        existing = db.execute(select(User).where(User.email == req.email)).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Email ya registrado")
        existing_user = db.execute(select(User).where(User.username == req.username)).scalar_one_or_none()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username ya registrado")
        user = User(
            email=req.email,
            username=req.username,
            hashed_password=hash_password(req.password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token(user.id)
        return {"token": token, "user": _user_to_dict(user)}
    finally:
        db.close()


@router.post("/login")
def auth_login(req: LoginRequest, request: Request) -> dict:
    """Login with email and password, returns JWT.

    If 2FA is enabled, requires `totp_code` or `backup_code`.
    Returns `totp_required: true` if 2FA is needed but not provided.
    """
    db = SessionLocal()
    try:
        user = authenticate_user(db, req.email, req.password)
        if not user:
            raise HTTPException(status_code=401, detail="Credenciales inválidas")

        # Check 2FA
        if user.totp_enabled and user.totp_secret:
            if not req.totp_code and not req.backup_code:
                return {
                    "totp_required": True,
                    "user": _user_to_dict(user),
                }

            if req.backup_code:
                # Verify backup code
                if not user.backup_codes_json or not verify_backup_code(user.backup_codes_json, req.backup_code):
                    raise HTTPException(status_code=401, detail="Código de respaldo inválido")
                # Remove used backup code
                user.backup_codes_json = remove_used_backup_code(user.backup_codes_json, req.backup_code)
                db.commit()
            else:
                # Verify TOTP code
                try:
                    secret = decrypt_totp_secret(user.totp_secret)
                except Exception:
                    raise HTTPException(status_code=500, detail="Error interno de 2FA")
                if not verify_totp(secret, req.totp_code):
                    raise HTTPException(status_code=401, detail="Código 2FA inválido")

        # Create session
        device_info = _extract_device_info(request)
        if req.device_name and req.device_name != "Unknown":
            device_info["device_name"] = req.device_name
        session = create_session(
            db,
            user.id,
            device_name=device_info["device_name"],
            ip_address=device_info["ip_address"],
            user_agent=device_info["user_agent"],
        )

        token = create_access_token(user.id, session_id=session.id)
        return {
            "token": token,
            "user": _user_to_dict(user),
            "session_id": session.id,
        }
    finally:
        db.close()


@router.get("/me")
def auth_me(current_user: Annotated[User, Depends(get_current_user)]) -> dict:
    """Return the current authenticated user."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "subscription": current_user.subscription,
        "risk_profile": current_user.risk_profile,
        "is_active": current_user.is_active,
        "is_admin": current_user.is_admin,
        "totp_enabled": current_user.totp_enabled,
        "created_at": str(current_user.created_at),
    }


# ---------------------------------------------------------------------------
# 2FA endpoints
# ---------------------------------------------------------------------------

@router.post("/2fa/setup")
def setup_2fa(
    req: Setup2FARequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Generate a new TOTP secret and return the QR URI.

    The secret is NOT activated yet — the user must verify with a code
    via /2fa/verify to confirm their authenticator app is working.
    """
    # Verify current password
    if not _verify_current_password(current_user, req.password):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    secret = generate_totp_secret()
    encrypted = encrypt_totp_secret(secret)
    uri = get_totp_uri(secret, current_user.email)

    # Store the encrypted secret temporarily (not enabled yet)
    # We save it to the user record but totp_enabled stays False
    # until /2fa/verify is called
    db = SessionLocal()
    try:
        db_user = db.get(User, current_user.id)
        if db_user:
            db_user.totp_secret = encrypted
            db.commit()
    finally:
        db.close()

    return {
        "secret": secret,  # returned once so user can manually enter if QR fails
        "qr_uri": uri,
        "issuer": "Alvora",
        "account": current_user.email,
    }


@router.post("/2fa/verify")
def verify_2fa(
    req: Verify2FARequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Verify a TOTP code and activate 2FA.

    On success, generates backup codes and enables 2FA.
    """
    db = SessionLocal()
    try:
        db_user = db.get(User, current_user.id)
        if not db_user or not db_user.totp_secret:
            raise HTTPException(status_code=400, detail="2FA no configurado. Llama a /2fa/setup primero.")

        try:
            secret = decrypt_totp_secret(db_user.totp_secret)
        except Exception:
            raise HTTPException(status_code=500, detail="Error interno descifrando secreto 2FA")

        if not verify_totp(secret, req.code):
            raise HTTPException(status_code=401, detail="Código 2FA inválido")

        # Generate backup codes
        backup_codes = generate_backup_codes()
        db_user.backup_codes_json = hash_backup_codes(backup_codes)
        db_user.totp_enabled = True
        db.commit()

        return {
            "enabled": True,
            "backup_codes": backup_codes,  # returned once, user must save them
        }
    finally:
        db.close()


@router.post("/2fa/disable")
def disable_2fa(
    req: Disable2FARequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Disable 2FA. Requires both password and a valid TOTP code."""
    if not _verify_current_password(current_user, req.password):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    db = SessionLocal()
    try:
        db_user = db.get(User, current_user.id)
        if not db_user or not db_user.totp_enabled:
            raise HTTPException(status_code=400, detail="2FA no está activado")

        try:
            secret = decrypt_totp_secret(db_user.totp_secret)
        except Exception:
            raise HTTPException(status_code=500, detail="Error interno de 2FA")

        if not verify_totp(secret, req.code):
            raise HTTPException(status_code=401, detail="Código 2FA inválido")

        db_user.totp_secret = None
        db_user.totp_enabled = False
        db_user.backup_codes_json = None
        db.commit()

        return {"disabled": True}
    finally:
        db.close()


@router.get("/2fa/status")
def get_2fa_status(current_user: Annotated[User, Depends(get_current_user)]) -> dict:
    """Check if 2FA is enabled for the current user."""
    return {
        "enabled": current_user.totp_enabled,
        "has_secret": bool(current_user.totp_secret),
    }


# ---------------------------------------------------------------------------
# Session management endpoints
# ---------------------------------------------------------------------------

@router.get("/sessions")
def list_sessions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    """List all active sessions for the current user."""
    sessions = get_active_sessions(db, current_user.id)
    return [
        {
            "id": s.id,
            "device_name": s.device_name,
            "ip_address": s.ip_address,
            "user_agent": s.user_agent,
            "created_at": s.created_at.isoformat() if s.created_at else "",
            "last_active_at": s.last_active_at.isoformat() if s.last_active_at else "",
            "expires_at": s.expires_at.isoformat() if s.expires_at else "",
        }
        for s in sessions
    ]


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Revoke a specific session by ID."""
    ok = revoke_session(db, session_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return {"revoked": True, "session_id": session_id}


@router.post("/sessions/revoke-all-others")
def revoke_all_others(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Revoke all sessions except the current one.

    Reads the current session_id from the JWT token.
    """
    from app.services.auth import decode_access_token

    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    current_session_id = None
    if token:
        payload = decode_access_token(token)
        if payload and payload.get("sid"):
            try:
                current_session_id = int(payload["sid"])
            except (ValueError, TypeError):
                pass

    count = revoke_all_other_sessions(db, current_user.id, keep_session_id=current_session_id)
    return {"revoked_count": count}


def _verify_current_password(user: User, password: str) -> bool:
    """Verify the current password for a user (used by 2FA setup/disable)."""
    from app.services.auth import verify_password
    return verify_password(password, user.hashed_password)
