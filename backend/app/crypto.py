"""Symmetric encryption for data that must never be stored in plaintext (Plaid access tokens)."""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet

from app.config import ENCRYPTION_KEY


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    if not ENCRYPTION_KEY:
        raise RuntimeError(
            "ENCRYPTION_KEY is not set. Generate one with: "
            "python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(ENCRYPTION_KEY.encode())


def encrypt(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()
