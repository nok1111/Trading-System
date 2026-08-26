"""TOTP (Time-based One-Time Password) service for 2FA."""

from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any

import pyotp

from app.config import get_settings

settings = get_settings()


def _get_encryption_key() -> bytes:
    """Get the encryption key for TOTP secrets.

    Falls back to JWT_SECRET if ENCRYPTION_KEY is not set (dev only).
    """
    key = getattr(settings, "ENCRYPTION_KEY", None) or settings.JWT_SECRET
    return hashlib.sha256(key.encode()).digest()


def _xor_encrypt(plaintext: str) -> str:
    """Simple XOR-based encryption for TOTP secrets (not high-security, but obscures at rest).

    For production, consider using cryptography.fernet instead.
    """
    key = _get_encryption_key()
    data = plaintext.encode()
    encrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    return encrypted.hex()


def _xor_decrypt(ciphertext: str) -> str:
    """Decrypt XOR-encrypted TOTP secret."""
    key = _get_encryption_key()
    data = bytes.fromhex(ciphertext)
    decrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    return decrypted.decode()


def generate_totp_secret() -> str:
    """Generate a new random TOTP secret (base32 encoded)."""
    return pyotp.random_base32()


def encrypt_totp_secret(secret: str) -> str:
    """Encrypt a TOTP secret for storage."""
    return _xor_encrypt(secret)


def decrypt_totp_secret(encrypted: str) -> str:
    """Decrypt a stored TOTP secret."""
    return _xor_decrypt(encrypted)


def get_totp_uri(secret: str, email: str, issuer: str = "Alvora") -> str:
    """Build the otpauth:// URI for QR code generation."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP code against the secret.

    Allows a 1-step window (±30s) for clock drift.
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def generate_backup_codes(count: int = 10) -> list[str]:
    """Generate one-time-use backup codes."""
    return [secrets.token_hex(4).upper() for _ in range(count)]


def hash_backup_codes(codes: list[str]) -> str:
    """Hash backup codes for storage (store only hashes)."""
    hashed = [hashlib.sha256(c.encode()).hexdigest() for c in codes]
    return json.dumps(hashed)


def verify_backup_code(stored_json: str, code: str) -> bool:
    """Verify a backup code against stored hashes.

    Returns True if matched (caller should remove the used code).
    """
    try:
        hashed_list = json.loads(stored_json)
    except (json.JSONDecodeError, TypeError):
        return False
    code_hash = hashlib.sha256(code.upper().strip().encode()).hexdigest()
    return code_hash in hashed_list


def remove_used_backup_code(stored_json: str, used_code: str) -> str:
    """Remove a used backup code from the stored JSON."""
    try:
        hashed_list = json.loads(stored_json)
    except (json.JSONDecodeError, TypeError):
        return stored_json
    used_hash = hashlib.sha256(used_code.upper().strip().encode()).hexdigest()
    hashed_list = [h for h in hashed_list if h != used_hash]
    return json.dumps(hashed_list)
