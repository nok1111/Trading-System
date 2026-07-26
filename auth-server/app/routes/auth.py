"""Authentication endpoints (register, login, me)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.user import User
from app.database.session import SessionLocal, get_db
from app.services.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    hash_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


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
        return {
            "token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "subscription": user.subscription,
                "risk_profile": user.risk_profile,
            },
        }
    finally:
        db.close()


@router.post("/login")
def auth_login(req: LoginRequest) -> dict:
    """Login with email and password, returns JWT."""
    db = SessionLocal()
    try:
        user = authenticate_user(db, req.email, req.password)
        if not user:
            raise HTTPException(status_code=401, detail="Credenciales inválidas")
        token = create_access_token(user.id)
        return {
            "token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "subscription": user.subscription,
                "risk_profile": user.risk_profile,
            },
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
        "created_at": str(current_user.created_at),
    }
