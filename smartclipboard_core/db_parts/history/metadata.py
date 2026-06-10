from __future__ import annotations

import datetime
import os
import sqlite3

from smartclipboard_core.file_paths import (
    file_content_from_paths,
    file_paths_from_content,
    file_signature_from_paths,
)

from ..shared import CLEANUP_INTERVAL, DEFAULT_MAX_HISTORY, FILTER_TAG_MAP, history_order_by, logger
from ..typing_helpers import DBRuntimeMixin


class HistoryMetadataMixin(DBRuntimeMixin):
    def update_pin_order(self, item_id: int, order: int) -> bool:
        """고정 항목의 순서를 업데이트"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE history SET pin_order = ? WHERE id = ?", (order, item_id))
                self.conn.commit()
                return cursor.rowcount == 1
            except sqlite3.Error as e:
                logger.error(f"Pin order update failed: {e}")
                self.conn.rollback()
                return False

    def update_pin_orders(self, ordered_ids: list[int]) -> bool:
        """고정 항목 순서를 원자적으로 업데이트"""
        if not ordered_ids:
            return True
        if len(ordered_ids) != len(set(ordered_ids)):
            logger.error("Pin order update failed: duplicate ids")
            return False

        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("BEGIN")
                for order, item_id in enumerate(ordered_ids):
                    cursor.execute(
                        "UPDATE history SET pin_order = ? WHERE id = ? AND pinned = 1",
                        (order, item_id),
                    )
                    if cursor.rowcount != 1:
                        raise sqlite3.Error(f"Invalid pinned item id: {item_id}")
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Pin orders bulk update failed: {e}")
                self.conn.rollback()
                return False

    def toggle_pin(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT pinned FROM history WHERE id=?", (item_id,))
                current = cursor.fetchone()
                if current:
                    new_status = 0 if current[0] else 1
                    if new_status == 1:
                        # 새 고정 항목은 맨 아래에 추가 (최대 pin_order + 1)
                        cursor.execute("SELECT COALESCE(MAX(pin_order), -1) + 1 FROM history WHERE pinned = 1")
                        new_order = cursor.fetchone()[0]
                        cursor.execute("UPDATE history SET pinned = ?, pin_order = ? WHERE id = ?",
                                       (new_status, new_order, item_id))
                    else:
                        # 고정 해제 시 pin_order 초기화
                        cursor.execute("UPDATE history SET pinned = ?, pin_order = 0 WHERE id = ?",
                                       (new_status, item_id))
                    self.conn.commit()
                    return new_status
            except sqlite3.Error as e:
                logger.error(f"DB Pin Error: {e}")
                self.conn.rollback()
            return 0

    def increment_use_count(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE history SET use_count = use_count + 1 WHERE id = ?", (item_id,))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"DB Use Count Error: {e}")
                self.conn.rollback()

    def toggle_bookmark(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT bookmark FROM history WHERE id = ?", (item_id,))
                current = cursor.fetchone()
                if current:
                    new_status = 0 if current[0] else 1
                    cursor.execute("UPDATE history SET bookmark = ? WHERE id = ?", (new_status, item_id))
                    self.conn.commit()
                    return new_status
            except sqlite3.Error as e:
                logger.error(f"Toggle Bookmark Error: {e}")
                self.conn.rollback()
            return 0

    def set_note(self, item_id, note):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE history SET note = ? WHERE id = ?", (note, item_id))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Set Note Error: {e}")

    def get_note(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT note FROM history WHERE id = ?", (item_id,))
                result = cursor.fetchone()
                return result[0] if result else ""
            except sqlite3.Error as e:
                logger.error(f"Get Note Error: {e}")
                return ""

    def set_item_metadata(self, item_id: int, **metadata) -> bool:
        """항목 메타데이터를 키-값 형태로 일괄 업데이트."""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                updated = self._set_item_metadata_locked(cursor, item_id, **metadata)
                if updated:
                    self.conn.commit()
                return updated
            except sqlite3.Error as e:
                logger.error(f"Set Metadata Error: {e}")
                self.conn.rollback()
                return False

    def _set_item_metadata_locked(self, cursor, item_id: int, **metadata) -> bool:
        """Update metadata without committing the outer transaction."""
        allowed = {
            "tags",
            "note",
            "bookmark",
            "collection_id",
            "pinned",
            "pin_order",
            "use_count",
            "timestamp",
            "url_title",
        }
        updates = {k: v for k, v in metadata.items() if k in allowed}
        if not updates:
            return True

        cols = ", ".join(f"{k} = ?" for k in updates.keys())
        params = list(updates.values())
        params.append(item_id)
        cursor.execute(f"UPDATE history SET {cols} WHERE id = ?", params)
        return cursor.rowcount == 1


__all__ = ["HistoryMetadataMixin"]
