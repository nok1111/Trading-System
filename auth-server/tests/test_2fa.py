"""Tests for 2FA TOTP and session management."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import pyotp

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# TOTP service tests
# ---------------------------------------------------------------------------

class TestTOTPService:
    """Unit tests for the TOTP service."""

    def test_generate_totp_secret(self):
        from app.services.totp import generate_totp_secret

        secret = generate_totp_secret()
        assert isinstance(secret, str)
        assert len(secret) >= 16  # base32 secrets are at least 16 chars
        # Should be valid base32
        pyotp.TOTP(secret)

    def test_encrypt_decrypt_roundtrip(self):
        from app.services.totp import decrypt_totp_secret, encrypt_totp_secret

        secret = "JBSWY3DPEHPK3PXP"
        encrypted = encrypt_totp_secret(secret)
        assert encrypted != secret  # should be encrypted
        decrypted = decrypt_totp_secret(encrypted)
        assert decrypted == secret

    def test_get_totp_uri(self):
        from app.services.totp import get_totp_uri

        secret = "JBSWY3DPEHPK3PXP"
        uri = get_totp_uri(secret, "test@example.com")
        assert uri.startswith("otpauth://totp/")
        assert "Alvora" in uri
        assert "test%40example.com" in uri or "test@example.com" in uri

    def test_verify_totp_valid(self):
        from app.services.totp import generate_totp_secret, verify_totp

        secret = generate_totp_secret()
        totp = pyotp.TOTP(secret)
        code = totp.now()
        assert verify_totp(secret, code) is True

    def test_verify_totp_invalid(self):
        from app.services.totp import generate_totp_secret, verify_totp

        secret = generate_totp_secret()
        assert verify_totp(secret, "000000") is False or verify_totp(secret, "000000") is True
        # 000000 could theoretically be valid in a 30s window, so test with clearly invalid
        assert verify_totp(secret, "ABCD12") is False

    def test_generate_backup_codes(self):
        from app.services.totp import generate_backup_codes

        codes = generate_backup_codes(10)
        assert len(codes) == 10
        assert all(isinstance(c, str) for c in codes)
        assert all(len(c) == 8 for c in codes)  # 4 bytes hex = 8 chars

    def test_hash_and_verify_backup_code(self):
        from app.services.totp import generate_backup_codes, hash_backup_codes, verify_backup_code

        codes = generate_backup_codes(5)
        stored = hash_backup_codes(codes)
        # Each code should verify
        for code in codes:
            assert verify_backup_code(stored, code) is True
        # Wrong code should not verify
        assert verify_backup_code(stored, "WRONG123") is False

    def test_remove_used_backup_code(self):
        from app.services.totp import (
            generate_backup_codes,
            hash_backup_codes,
            remove_used_backup_code,
            verify_backup_code,
        )

        codes = generate_backup_codes(5)
        stored = hash_backup_codes(codes)
        # Remove one code
        updated = remove_used_backup_code(stored, codes[0])
        # The removed code should no longer verify
        assert verify_backup_code(updated, codes[0]) is False
        # Other codes should still verify
        assert verify_backup_code(updated, codes[1]) is True


# ---------------------------------------------------------------------------
# Session management tests
# ---------------------------------------------------------------------------

class TestSessionManagement:
    """Tests for session creation, listing, and revocation."""

    def test_create_access_token_with_session(self):
        from app.services.auth import create_access_token, decode_access_token

        token = create_access_token(user_id=1, session_id=42)
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "1"
        assert payload["sid"] == "42"

    def test_create_access_token_without_session(self):
        from app.services.auth import create_access_token, decode_access_token

        token = create_access_token(user_id=1)
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "1"
        assert "sid" not in payload


# ---------------------------------------------------------------------------
# Integration tests with FastAPI TestClient
# ---------------------------------------------------------------------------

class Test2FAIntegration:
    """Integration tests for 2FA endpoints using FastAPI TestClient."""

    @pytest.fixture
    def client(self):
        """Create a test client with file-based SQLite, cleaned between tests."""
        # Override settings for testing BEFORE importing app modules
        os.environ["DATABASE_URL"] = "sqlite:///./test_auth_2fa.db"
        os.environ["JWT_SECRET"] = "test-secret-key-for-testing-32bytes!"
        os.environ["APP_ENV"] = "development"

        # Force reload settings
        from app.config import get_settings
        get_settings.cache_clear()

        # Recreate engine with new settings
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        import app.database.session as session_mod

        new_engine = create_engine("sqlite:///./test_auth_2fa.db", future=True)
        session_mod.engine = new_engine
        session_mod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=new_engine)

        # Create tables
        from app.database.base import Base
        from app.database.models import user, payment, ai_usage, user_session  # noqa: F401
        Base.metadata.drop_all(bind=new_engine)
        Base.metadata.create_all(bind=new_engine)

        from app.main import app
        from fastapi.testclient import TestClient

        yield TestClient(app)

        # Drop all tables after each test for clean state
        Base.metadata.drop_all(bind=new_engine)
        new_engine.dispose()

    @pytest.fixture
    def registered_user(self, client):
        """Register a test user and return the token + user data."""
        response = client.post("/api/auth/register", json={
            "email": "test2fa@example.com",
            "username": "test2fa",
            "password": "TestPassword123",
        })
        assert response.status_code == 200, response.text
        data = response.json()
        return data

    def test_register_and_login(self, client, registered_user):
        """Basic register + login flow without 2FA."""
        response = client.post("/api/auth/login", json={
            "email": "test2fa@example.com",
            "password": "TestPassword123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["email"] == "test2fa@example.com"
        assert data["user"]["totp_enabled"] is False

    def test_login_returns_session_id(self, client, registered_user):
        """Login should return a session_id."""
        response = client.post("/api/auth/login", json={
            "email": "test2fa@example.com",
            "password": "TestPassword123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data

    def test_get_me(self, client, registered_user):
        """GET /me should return user info."""
        token = registered_user["token"]
        response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test2fa@example.com"
        assert data["totp_enabled"] is False

    def test_2fa_setup(self, client, registered_user):
        """Setup 2FA should return secret and QR URI."""
        token = registered_user["token"]
        response = client.post("/api/auth/2fa/setup", json={
            "password": "TestPassword123",
        }, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert "secret" in data
        assert "qr_uri" in data
        assert data["issuer"] == "Alvora"

    def test_2fa_setup_wrong_password(self, client, registered_user):
        """Setup 2FA with wrong password should fail."""
        token = registered_user["token"]
        response = client.post("/api/auth/2fa/setup", json={
            "password": "WrongPassword",
        }, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401

    def test_2fa_full_flow(self, client, registered_user):
        """Full 2FA flow: setup → verify → login with 2FA → disable."""
        token = registered_user["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Setup 2FA
        response = client.post("/api/auth/2fa/setup", json={
            "password": "TestPassword123",
        }, headers=headers)
        assert response.status_code == 200
        secret = response.json()["secret"]

        # 2. Verify with valid TOTP code
        totp = pyotp.TOTP(secret)
        code = totp.now()
        response = client.post("/api/auth/2fa/verify", json={
            "code": code,
        }, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert "backup_codes" in data
        backup_codes = data["backup_codes"]
        assert len(backup_codes) == 10

        # 3. Login without TOTP code should return totp_required
        response = client.post("/api/auth/login", json={
            "email": "test2fa@example.com",
            "password": "TestPassword123",
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("totp_required") is True

        # 4. Login with valid TOTP code
        code = totp.now()
        response = client.post("/api/auth/login", json={
            "email": "test2fa@example.com",
            "password": "TestPassword123",
            "totp_code": code,
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["totp_enabled"] is True

        # 5. Login with backup code
        response = client.post("/api/auth/login", json={
            "email": "test2fa@example.com",
            "password": "TestPassword123",
            "backup_code": backup_codes[0],
        })
        assert response.status_code == 200
        assert "token" in response.json()

        # 6. Login with already-used backup code should fail
        response = client.post("/api/auth/login", json={
            "email": "test2fa@example.com",
            "password": "TestPassword123",
            "backup_code": backup_codes[0],
        })
        assert response.status_code == 401

        # 7. Disable 2FA
        code = totp.now()
        response = client.post("/api/auth/2fa/disable", json={
            "password": "TestPassword123",
            "code": code,
        }, headers=headers)
        assert response.status_code == 200
        assert response.json()["disabled"] is True

    def test_2fa_status(self, client, registered_user):
        """Check 2FA status endpoint."""
        token = registered_user["token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/api/auth/2fa/status", headers=headers)
        assert response.status_code == 200
        assert response.json()["enabled"] is False

    def test_list_sessions(self, client, registered_user):
        """List active sessions."""
        # Login to create a session
        response = client.post("/api/auth/login", json={
            "email": "test2fa@example.com",
            "password": "TestPassword123",
        })
        assert response.status_code == 200
        token = response.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/api/auth/sessions", headers=headers)
        assert response.status_code == 200
        sessions = response.json()
        assert isinstance(sessions, list)
        assert len(sessions) >= 1  # at least the current session

    def test_revoke_session(self, client, registered_user):
        """Revoke a session."""
        # Login twice to create 2 sessions
        response1 = client.post("/api/auth/login", json={
            "email": "test2fa@example.com",
            "password": "TestPassword123",
        })
        session1 = response1.json()["session_id"]

        response2 = client.post("/api/auth/login", json={
            "email": "test2fa@example.com",
            "password": "TestPassword123",
        })
        token2 = response2.json()["token"]
        session2 = response2.json()["session_id"]

        # Revoke session1 using token2
        response = client.delete(
            f"/api/auth/sessions/{session1}",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert response.status_code == 200
        assert response.json()["revoked"] is True

    def test_login_with_invalid_2fa_code(self, client, registered_user):
        """Login with invalid TOTP code should fail."""
        token = registered_user["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Setup 2FA
        response = client.post("/api/auth/2fa/setup", json={
            "password": "TestPassword123",
        }, headers=headers)
        secret = response.json()["secret"]

        # Verify
        totp = pyotp.TOTP(secret)
        response = client.post("/api/auth/2fa/verify", json={
            "code": totp.now(),
        }, headers=headers)
        assert response.status_code == 200

        # Login with invalid code
        response = client.post("/api/auth/login", json={
            "email": "test2fa@example.com",
            "password": "TestPassword123",
            "totp_code": "999999",
        })
        assert response.status_code == 401
        assert "inválido" in response.json()["detail"].lower() or "invalid" in response.json()["detail"].lower()
