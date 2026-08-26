"""Authentication service: JWT, password hashing, 2FA, session management, FastAPI dependencies."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.models.user import User
from app.database.models.user_session import UserSession
from app.database.session import get_db

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

JWT_SECRET = settings.JWT_SECRET
JWT_ALGORITHM = settings.JWT_ALGORITHM
JWT_EXPIRE_HOURS = settings.JWT_EXPIRE_HOURS


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def create_access_token(
    user_id: int,
    expires_hours: int | None = None,
    session_id: int | None = None,
) -> str:
    """Create a JWT access token.

    If session_id is provided, it is embedded in the token so the session
    can be validated and revoked.
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=expires_hours or JWT_EXPIRE_HOURS)
    payload: dict[str, Any] = {"sub": str(user_id), "exp": expire}
    if session_id is not None:
        payload["sid"] = str(session_id)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    stmt = select(User).where(User.email == email)
    user = db.execute(stmt).scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


def create_session(
    db: Session,
    user_id: int,
    device_name: str = "Unknown",
    ip_address: str | None = None,
    user_agent: str | None = None,
    device_fingerprint: str | None = None,
) -> UserSession:
    """Create a new user session record in the database."""
    expires_at = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    session = UserSession(
        user_id=user_id,
        device_name=device_name,
        ip_address=ip_address,
        user_agent=user_agent,
        device_fingerprint=device_fingerprint,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def revoke_session(db: Session, session_id: int, user_id: int) -> bool:
    """Revoke a session by ID. Returns True if found and revoked."""
    session = db.execute(
        select(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == user_id,
        )
    ).scalar_one_or_none()
    if not session:
        return False
    session.revoked = True
    db.commit()
    return True


def revoke_all_other_sessions(db: Session, user_id: int, keep_session_id: int | None = None) -> int:
    """Revoke all sessions for a user except the current one. Returns count revoked."""
    stmt = select(UserSession).where(
        UserSession.user_id == user_id,
        UserSession.revoked == False,  # noqa: E712
    )
    if keep_session_id is not None:
        stmt = stmt.where(UserSession.id != keep_session_id)
    sessions = db.execute(stmt).scalars().all()
    count = 0
    for s in sessions:
        if not s.revoked:
            s.revoked = True
            count += 1
    if count:
        db.commit()
    return count


def get_active_sessions(db: Session, user_id: int) -> list[UserSession]:
    """List all active (non-revoked, non-expired) sessions for a user."""
    now = datetime.now(timezone.utc)
    sessions = db.execute(
        select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.revoked == False,  # noqa: E712
            UserSession.expires_at > now,
        ).order_by(UserSession.last_active_at.desc())
    ).scalars().all()
    return list(sessions)


def is_session_valid(db: Session, session_id: int | None) -> bool:
    """Check if a session is still valid (not revoked, not expired)."""
    if session_id is None:
        return True  # Tokens without session_id are legacy/valid
    session = db.get(UserSession, session_id)
    if not session:
        return False
    if session.revoked:
        return False
    if session.expires_at < datetime.now(timezone.utc):
        return False
    # Update last_active_at
    session.last_active_at = datetime.now(timezone.utc)
    db.commit()
    return True


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> User:
    """FastAPI dependency that returns the authenticated user or raises 401.

    Validates JWT, checks session validity (if session_id is embedded).
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = int(payload.get("sub", 0))
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo",
        )
    # Validate session if present in token
    session_id_str = payload.get("sid")
    if session_id_str:
        try:
            session_id = int(session_id_str)
            if not is_session_valid(db, session_id):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Sesión revocada o expirada",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except (ValueError, TypeError):
            pass  # Malformed sid, allow through (backward compat)
    return user
