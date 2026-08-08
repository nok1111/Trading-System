"""Utilidades de encriptación para API keys de usuarios."""

from __future__ import annotations

import os
from pathlib import Path

from app.config import get_settings

settings = get_settings()

_fernet = None

_KEY_FILE = Path.home() / ".alvora" / "encryption_key"


def _load_or_generate_key() -> str:
    """Load ENCRYPTION_KEY from env, or from ~/.alvora/encryption_key, or generate a new one."""
    env_key = settings.ENCRYPTION_KEY
    if env_key:
        return env_key

    # Try loading from persisted key file
    if _KEY_FILE.exists():
        return _KEY_FILE.read_text(encoding="utf-8").strip()

    # Generate a random key and persist it
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _KEY_FILE.write_text(key, encoding="utf-8")
    try:
        os.chmod(_KEY_FILE, 0o600)
    except OSError:
        pass  # Windows doesn't support chmod the same way
    return key


def _get_fernet():
    global _fernet
    if _fernet is None:
        key = _load_or_generate_key()
        from cryptography.fernet import Fernet
        _fernet = Fernet(key)
    return _fernet


def encrypt(plaintext: str) -> str:
    """Encrypt a string and return base64-encoded ciphertext."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
