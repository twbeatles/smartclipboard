"""Vault bootstrap persistence helpers."""

from __future__ import annotations


def store_vault_bootstrap(db, salt_b64: str, verification: str, logger) -> bool:
    with db.lock:
        try:
            cursor = db.conn.cursor()
            cursor.execute("BEGIN")
            cursor.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("vault_salt", salt_b64),
            )
            cursor.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("vault_verification", verification),
            )
            db.conn.commit()
            return True
        except Exception as exc:
            db.conn.rollback()
            logger.debug("Vault bootstrap save failed: %s", exc)
            return False


__all__ = ["store_vault_bootstrap"]
