from __future__ import annotations

import datetime
import sqlite3

from ..shared import logger


class VaultRetentionMixin:
    def add_vault_item(self, encrypted_content, label):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "INSERT INTO secure_vault (encrypted_content, label, created_at) VALUES (?, ?, ?)",
                    (encrypted_content, label, created_at),
                )
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Vault Add Error: {e}")
                return False

    def get_vault_items(self):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT id, encrypted_content, label, created_at FROM secure_vault ORDER BY id DESC")
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.error(f"Vault Get Error: {e}")
                return []

    def delete_vault_item(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM secure_vault WHERE id = ?", (item_id,))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Vault Delete Error: {e}")
