"""Secure vault manager implementation."""

from __future__ import annotations

import base64
import logging
import os
import time
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

logger = logging.getLogger(__name__)


class SecureVaultManager:
    """Fernet-encrypted secure vault with PBKDF2-derived keys."""

    def __init__(self, db, logger_=None):
        self.db = db
        self.fernet: Any | None = None
        self.is_unlocked = False
        self.last_activity = time.time()
        self.lock_timeout = 300
        self.logger = logger_ or logger

    def derive_key(self, password, salt):
        if not HAS_CRYPTO or PBKDF2HMAC is None or hashes is None:
            return None
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    def set_master_password(self, password):
        if not HAS_CRYPTO or Fernet is None:
            return False
        salt = os.urandom(16)
        key = self.derive_key(password, salt)
        if key is None:
            return False
        fernet = Fernet(key)
        verification = fernet.encrypt(b"VAULT_VERIFIED")
        self.fernet = fernet
        self.db.set_setting("vault_salt", base64.b64encode(salt).decode())
        self.db.set_setting("vault_verification", verification.decode())
        self.is_unlocked = True
        self.last_activity = time.time()
        return True

    def change_master_password(self, current_password, new_password):
        if not HAS_CRYPTO or Fernet is None:
            return False
        if not current_password or not new_password:
            return False
        if not self.unlock(current_password):
            return False

        old_fernet = self.fernet
        if old_fernet is None:
            return False

        salt = os.urandom(16)
        new_key = self.derive_key(new_password, salt)
        if new_key is None:
            return False
        new_fernet = Fernet(new_key)
        verification = new_fernet.encrypt(b"VAULT_VERIFIED").decode()

        with self.db.lock:
            try:
                cursor = self.db.conn.cursor()
                cursor.execute("SELECT id, encrypted_content FROM secure_vault ORDER BY id")
                vault_rows = cursor.fetchall()

                reencrypted: list[tuple[bytes, int]] = []
                for item_id, encrypted_content in vault_rows:
                    decrypted = old_fernet.decrypt(encrypted_content).decode()
                    reencrypted.append((new_fernet.encrypt(decrypted.encode()), item_id))

                cursor.execute("BEGIN")
                for encrypted_content, item_id in reencrypted:
                    cursor.execute(
                        "UPDATE secure_vault SET encrypted_content = ? WHERE id = ?",
                        (encrypted_content, item_id),
                    )
                cursor.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    ("vault_salt", base64.b64encode(salt).decode()),
                )
                cursor.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    ("vault_verification", verification),
                )
                self.db.conn.commit()
            except Exception as exc:
                self.db.conn.rollback()
                self.logger.debug("Vault password change failed: %s", exc)
                return False

        self.fernet = new_fernet
        self.is_unlocked = True
        self.last_activity = time.time()
        return True

    def unlock(self, password):
        if not HAS_CRYPTO or Fernet is None:
            return False
        salt_b64 = self.db.get_setting("vault_salt")
        verification = self.db.get_setting("vault_verification")
        if not salt_b64 or not verification:
            return False
        try:
            salt = base64.b64decode(salt_b64)
            key = self.derive_key(password, salt)
            if key is None:
                self.fernet = None
                self.is_unlocked = False
                return False
            fernet = Fernet(key)
            if fernet.decrypt(verification.encode()) == b"VAULT_VERIFIED":
                self.fernet = fernet
                self.is_unlocked = True
                self.last_activity = time.time()
                return True
        except (ValueError, TypeError) as exc:
            self.logger.debug("Vault unlock decode error: %s", exc)
        except Exception as exc:
            self.logger.debug("Vault unlock crypto error: %s", exc)
        self.fernet = None
        self.is_unlocked = False
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
