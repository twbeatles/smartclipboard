"""Secure vault manager implementation."""

from __future__ import annotations

import base64
import logging
import os
import time

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

logger = logging.getLogger(__name__)


class SecureVaultManager:
    """AES-256 encrypted secure vault."""

    def __init__(self, db, logger_=None):
        self.db = db
        self.fernet = None
        self.is_unlocked = False
        self.last_activity = time.time()
        self.lock_timeout = 300
        self.logger = logger_ or logger

    def derive_key(self, password, salt):
        if not HAS_CRYPTO:
            return None
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    def set_master_password(self, password):
        if not HAS_CRYPTO:
            return False
        salt = os.urandom(16)
        key = self.derive_key(password, salt)
        self.fernet = Fernet(key)
        verification = self.fernet.encrypt(b"VAULT_VERIFIED")
        self.db.set_setting("vault_salt", base64.b64encode(salt).decode())
        self.db.set_setting("vault_verification", verification.decode())
        self.is_unlocked = True
        self.last_activity = time.time()
        return True

    def unlock(self, password):
        if not HAS_CRYPTO:
            return False
        salt_b64 = self.db.get_setting("vault_salt")
        verification = self.db.get_setting("vault_verification")
        if not salt_b64 or not verification:
            return False
        try:
            salt = base64.b64decode(salt_b64)
            key = self.derive_key(password, salt)
            self.fernet = Fernet(key)
            if self.fernet.decrypt(verification.encode()) == b"VAULT_VERIFIED":
                self.is_unlocked = True
                self.last_activity = time.time()
                return True
        except (ValueError, TypeError) as exc:
            self.logger.debug("Vault unlock decode error: %s", exc)
        except Exception as exc:
            self.logger.debug("Vault unlock crypto error: %s", exc)
            self.fernet = None
        return False

    def lock(self):
        self.fernet = None
        self.is_unlocked = False

    def check_timeout(self):
        if self.is_unlocked and (time.time() - self.last_activity > self.lock_timeout):
            self.lock()
            return True
        return False

    def encrypt(self, text):
        if not self.is_unlocked or not self.fernet:
            return None
        self.last_activity = time.time()
        return self.fernet.encrypt(text.encode())

    def decrypt(self, encrypted_data):
        if not self.is_unlocked or not self.fernet:
            return None
        self.last_activity = time.time()
        try:
            return self.fernet.decrypt(encrypted_data).decode()
        except Exception as exc:
            self.logger.debug("Decrypt error: %s", exc)
            return None

    def has_master_password(self):
        return self.db.get_setting("vault_salt") is not None


__all__ = ["SecureVaultManager", "HAS_CRYPTO"]
