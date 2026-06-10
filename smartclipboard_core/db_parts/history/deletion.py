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


class HistoryDeletionMixin(DBRuntimeMixin):
    def delete_item(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM history WHERE id = ?", (item_id,))
                self.conn.commit()
                logger.info(f"항목 삭제: {item_id}")
            except sqlite3.Error as e:
                logger.error(f"DB Delete Error: {e}")
                self.conn.rollback()

    def clear_all(self):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM history WHERE pinned = 0")
                self.conn.commit()
                logger.info("고정되지 않은 모든 항목 삭제")
            except sqlite3.Error as e:
                logger.error(f"DB Clear Error: {e}")
                self.conn.rollback()

    def soft_delete_unpinned(self) -> int:
        """Move all unpinned items to trash while preserving metadata."""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM history WHERE pinned = 0")
                row = cursor.fetchone()
                count = int(row[0]) if row else 0
                if count <= 0:
                    return 0

                deleted_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                expires_at = (
                    datetime.datetime.now() + datetime.timedelta(days=7)
                ).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    """
                    INSERT INTO deleted_history (
                        original_id,
                        content,
                        image_data,
                        type,
                        original_timestamp,
                        tags,
                        note,
                        bookmark,
                        collection_id,
                        pinned,
                        pin_order,
                        use_count,
                        url_title,
                        deleted_at,
                        expires_at
                    )
                    SELECT
                        id,
                        content,
                        image_data,
                        type,
                        timestamp,
                        COALESCE(tags, ''),
                        COALESCE(note, ''),
                        COALESCE(bookmark, 0),
                        collection_id,
                        COALESCE(pinned, 0),
                        COALESCE(pin_order, 0),
                        COALESCE(use_count, 0),
                        COALESCE(url_title, ''),
                        ?,
                        ?
                    FROM history
                    WHERE pinned = 0
                    """,
                    (deleted_at, expires_at),
                )
                cursor.execute("DELETE FROM history WHERE pinned = 0")
                self.conn.commit()
                logger.info("고정되지 않은 항목 %s개를 휴지통으로 이동", count)
                return count
            except sqlite3.Error as e:
                logger.error(f"Bulk Soft Delete Error: {e}")
                self.conn.rollback()
                return 0


__all__ = ["HistoryDeletionMixin"]
