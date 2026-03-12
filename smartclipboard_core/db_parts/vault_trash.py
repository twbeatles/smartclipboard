from __future__ import annotations
import datetime
import sqlite3

from .shared import logger

class VaultTrashMixin:
    def add_vault_item(self, encrypted_content, label):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("INSERT INTO secure_vault (encrypted_content, label, created_at) VALUES (?, ?, ?)",
                               (encrypted_content, label, created_at))
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

    def soft_delete(self, item_id):
        """항목을 휴지통으로 이동 (7일 후 영구 삭제)"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT content, image_data, type, timestamp, tags, note, bookmark, collection_id, pinned, pin_order, use_count "
                    "FROM history WHERE id = ?",
                    (item_id,),
                )
                item = cursor.fetchone()
                if item:
                    deleted_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    expires_at = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute(
                        "INSERT INTO deleted_history "
                        "(original_id, content, image_data, type, original_timestamp, tags, note, bookmark, collection_id, pinned, pin_order, use_count, deleted_at, expires_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            item_id,
                            item[0],
                            item[1],
                            item[2],
                            item[3],
                            item[4] or "",
                            item[5] or "",
                            item[6] or 0,
                            item[7],
                            item[8] or 0,
                            item[9] or 0,
                            item[10] or 0,
                            deleted_at,
                            expires_at,
                        ),
                    )
                    cursor.execute("DELETE FROM history WHERE id = ?", (item_id,))
                    self.conn.commit()
                    return True
            except sqlite3.Error as e:
                logger.error(f"Soft Delete Error: {e}")
                self.conn.rollback()
            return False

    def restore_item(self, deleted_id):
        """휴지통에서 항목 복원"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT content, image_data, type, original_timestamp, tags, note, bookmark, collection_id, pinned, pin_order, use_count "
                    "FROM deleted_history WHERE id = ?",
                    (deleted_id,),
                )
                item = cursor.fetchone()
                if item:
                    timestamp = item[3] or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute(
                        "INSERT INTO history (content, image_data, type, timestamp, tags, note, bookmark, collection_id, pinned, pin_order, use_count) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            item[0],
                            item[1],
                            item[2],
                            timestamp,
                            item[4] or "",
                            item[5] or "",
                            item[6] or 0,
                            item[7],
                            item[8] or 0,
                            item[9] or 0,
                            item[10] or 0,
                        ),
                    )
                    cursor.execute("DELETE FROM deleted_history WHERE id = ?", (deleted_id,))
                    self.conn.commit()
                    return True
            except sqlite3.Error as e:
                logger.error(f"Restore Item Error: {e}")
                self.conn.rollback()
            return False

    def get_deleted_items(self):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT id, content, type, deleted_at, expires_at FROM deleted_history ORDER BY deleted_at DESC")
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.error(f"Get Deleted Items Error: {e}")
                return []

    def empty_trash(self):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM deleted_history")
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Empty Trash Error: {e}")
                self.conn.rollback()

    def cleanup_expired_trash(self):
        """만료된 휴지통 항목 영구 삭제"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("DELETE FROM deleted_history WHERE expires_at < ?", (now,))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Cleanup Expired Trash Error: {e}")

