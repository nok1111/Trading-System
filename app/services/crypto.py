"""Utilidades de encriptación para API keys de usuarios."""

from __future__ import annotations

from app.config import get_settings

settings = get_settings()

_fernet = None


def _get_fernet():
    global _fernet
    if _fernet is None:
        key = settings.ENCRYPTION_KEY
        if not key:
            # Generate a key derived from JWT_SECRET for simplicity
            import hashlib
            import base64
            derived = hashlib.sha256(settings.JWT_SECRET.encode()).digest()
            key = base64.urlsafe_b64encode(derived)
        from cryptography.fernet import Fernet
        _fernet = Fernet(key)
    return _fernet


def encrypt(plaintext: str) -> str:
    """Encrypt a string and return base64-encoded ciphertext."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
