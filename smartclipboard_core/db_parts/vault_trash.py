from __future__ import annotations
import datetime
import sqlite3

from smartclipboard_core.file_paths import file_signature_from_content

from .shared import logger

class VaultTrashMixin:
    @staticmethod
    def _tag_tokens(tags_value) -> list[str]:
        normalized = str(tags_value or "").replace("，", ",")
        return [token.strip() for token in normalized.split(",") if token.strip()]

    @classmethod
    def _merge_tag_strings(cls, active_tags, deleted_tags) -> str:
        merged: list[str] = []
        seen: set[str] = set()
        for token in cls._tag_tokens(active_tags) + cls._tag_tokens(deleted_tags):
            normalized = token.casefold()
            if normalized in seen:
                continue
            seen.add(normalized)
            merged.append(token)
        return ", ".join(merged)

    def _resolve_restore_collection_id_locked(self, cursor, *candidates) -> int | None:
        for candidate in candidates:
            if candidate is None:
                continue
            try:
                collection_id = int(candidate)
            except (TypeError, ValueError):
                continue
            if hasattr(self, "_collection_exists") and not self._collection_exists(cursor, collection_id):
                continue
            return collection_id
        return None

    def _next_pin_order_locked(self, cursor, exclude_item_id: int | None = None) -> int:
        if exclude_item_id is None:
            cursor.execute("SELECT COALESCE(MAX(pin_order), -1) + 1 FROM history WHERE pinned = 1")
        else:
            cursor.execute(
                "SELECT COALESCE(MAX(pin_order), -1) + 1 FROM history WHERE pinned = 1 AND id != ?",
                (exclude_item_id,),
            )
        row = cursor.fetchone()
        return int(row[0] or 0) if row else 0

    def _find_restore_merge_target_locked(self, cursor, content, item_type):
        if item_type == "FILE":
            file_signature = file_signature_from_content(content)
            if not file_signature:
                return None
            cursor.execute(
                """
                SELECT id, tags, note, bookmark, collection_id, pinned, pin_order, use_count, timestamp
                FROM history
                WHERE type = 'FILE' AND file_signature = ?
                ORDER BY timestamp DESC, id DESC
                LIMIT 1
                """,
                (file_signature,),
            )
            return cursor.fetchone()

        if item_type != "IMAGE":
            cursor.execute(
                """
                SELECT id, tags, note, bookmark, collection_id, pinned, pin_order, use_count, timestamp
                FROM history
                WHERE content = ? AND type NOT IN ('IMAGE', 'FILE')
                ORDER BY timestamp DESC, id DESC
                LIMIT 1
                """,
                (content,),
            )
            return cursor.fetchone()

        return None

    def _build_merged_restore_metadata_locked(self, cursor, item_id: int, active_row, deleted_row) -> dict[str, int | str | None]:
        active_tags, active_note, active_bookmark, active_collection_id, active_pinned, active_pin_order, active_use_count, _active_timestamp = active_row
        deleted_tags = deleted_row[4] or ""
        deleted_note = deleted_row[5] or ""
        deleted_bookmark = int(deleted_row[6] or 0)
        deleted_collection_id = deleted_row[7]
        deleted_pinned = int(deleted_row[8] or 0)
        deleted_use_count = int(deleted_row[10] or 0)

        merged_pinned = 1 if active_pinned or deleted_pinned else 0
        if active_pinned:
            merged_pin_order = int(active_pin_order or 0)
        elif deleted_pinned:
            merged_pin_order = self._next_pin_order_locked(cursor, exclude_item_id=item_id)
        else:
            merged_pin_order = 0

        active_note_text = str(active_note or "")
        return {
            "tags": self._merge_tag_strings(active_tags, deleted_tags),
            "note": active_note_text if active_note_text.strip() else str(deleted_note or ""),
            "bookmark": 1 if int(active_bookmark or 0) or deleted_bookmark else 0,
            "collection_id": self._resolve_restore_collection_id_locked(cursor, active_collection_id, deleted_collection_id),
            "pinned": merged_pinned,
            "pin_order": merged_pin_order,
            "use_count": int(active_use_count or 0) + deleted_use_count,
        }

    def _build_insert_restore_metadata_locked(self, cursor, item_id: int, deleted_row) -> dict[str, int | str | None]:
        deleted_pinned = int(deleted_row[8] or 0)
        return {
            "tags": str(deleted_row[4] or ""),
            "note": str(deleted_row[5] or ""),
            "bookmark": int(deleted_row[6] or 0),
            "collection_id": self._resolve_restore_collection_id_locked(cursor, deleted_row[7]),
            "pinned": deleted_pinned,
            "pin_order": self._next_pin_order_locked(cursor, exclude_item_id=item_id) if deleted_pinned else 0,
            "use_count": int(deleted_row[10] or 0),
        }

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
                    existing_row = self._find_restore_merge_target_locked(cursor, item[0], item[2])
                    if existing_row:
                        item_id = int(existing_row[0])
                        metadata = self._build_merged_restore_metadata_locked(cursor, item_id, existing_row[1:], item)
                    else:
                        timestamp = item[3] or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        item_id, _updated_existing = self._add_item_locked(cursor, item[0], item[1], item[2], timestamp=timestamp)
                        if not item_id:
                            raise sqlite3.Error("Failed to restore history row")
                        item_id = int(item_id)
                        metadata = self._build_insert_restore_metadata_locked(cursor, item_id, item)

                    self._set_item_metadata_locked(cursor, item_id, **metadata)
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

