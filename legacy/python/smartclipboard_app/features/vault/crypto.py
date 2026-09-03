"""Crypto primitives for the secure vault feature."""

from __future__ import annotations

import base64
import os
from typing import Any

Fernet: Any | None
hashes: Any | None
PBKDF2HMAC: Any | None

try:
    from cryptography.fernet import Fernet as _Fernet
    from cryptography.hazmat.primitives import hashes as _hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC as _PBKDF2HMAC
except ImportError:
    Fernet = None
    hashes = None
    PBKDF2HMAC = None
    HAS_CRYPTO = False
else:
    Fernet = _Fernet
    hashes = _hashes
    PBKDF2HMAC = _PBKDF2HMAC
    HAS_CRYPTO = True


def create_salt() -> bytes:
    return os.urandom(16)


def derive_key(password: str, salt: bytes):
    if not HAS_CRYPTO or PBKDF2HMAC is None or hashes is None:
        return None
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


__all__ = ["Fernet", "HAS_CRYPTO", "PBKDF2HMAC", "hashes", "create_salt", "derive_key"]
