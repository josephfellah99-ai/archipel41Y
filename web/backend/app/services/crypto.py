"""Chiffrement des secrets stockés (clés API) avec une clé dérivée de SECRET_KEY."""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from ..config import get_settings


def _fernet() -> Fernet:
    key = hashlib.sha256(("archipel41-secrets:" + get_settings().secret_key).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None


def mask(value: str | None) -> str | None:
    if not value:
        return None
    return value[:3] + "…" + value[-4:] if len(value) > 10 else "••••"
