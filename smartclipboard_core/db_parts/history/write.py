from __future__ import annotations

import datetime
import os
import sqlite3
from typing import Any, cast

from smartclipboard_core.file_paths import (
    file_content_from_paths,
    file_paths_from_content,
    file_signature_from_paths,
)

from ..shared import CLEANUP_INTERVAL, DEFAULT_MAX_HISTORY, FILTER_TAG_MAP, history_order_by, logger
from ..typing_helpers import DBRuntimeMixin


class HistoryWriteMixin(DBRuntimeMixin):
    def _add_item_locked(
        self,
        cursor,
        content: str,
        image_data: bytes | None,
        type_tag: str,
        timestamp: str | None = None,
    ) -> tuple[int | bool, bool]:
        """Insert/update a history item without committing the transaction."""
        item_timestamp = timestamp or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        updated_existing = False

        if type_tag == "FILE":
            normalized_paths = file_paths_from_content(content)
            normalized_content = file_content_from_paths(normalized_paths)
            if not normalized_content:
                return False, False

            file_path = normalized_paths[0]
            file_signature = file_signature_from_paths(normalized_paths)
            cursor.execute(
                "SELECT id FROM history WHERE type = 'FILE' AND file_signature = ? "
                "ORDER BY timestamp DESC, id DESC LIMIT 1",
                (file_signature,),
            )
            existing = cursor.fetchone()
            if existing:
                item_id = int(existing[0])
                cursor.execute(
                    "UPDATE history SET content = ?, image_data = NULL, type = ?, timestamp = ?, "
                    "file_path = ?, file_signature = ? WHERE id = ?",
                    (normalized_content, type_tag, item_timestamp, file_path, file_signature, item_id),
                )
                updated_existing = True
            else:
                cursor.execute(
                    "INSERT INTO history (content, image_data, type, timestamp, file_path, file_signature) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (normalized_content, None, type_tag, item_timestamp, file_path, file_signature),
                )
                item_id = cursor.lastrowid
                if item_id is None:
                    raise sqlite3.Error("Inserted history row has no id")
            return item_id, updated_existing

        if type_tag != "IMAGE":
            cursor.execute(
                "SELECT id FROM history WHERE content = ? AND type NOT IN ('IMAGE', 'FILE') "
                "ORDER BY timestamp DESC, id DESC LIMIT 1",
                (content,),
            )
            existing = cursor.fetchone()
            if existing:
                item_id = int(existing[0])
                cursor.execute(
                    "UPDATE history SET content = ?, image_data = NULL, type = ?, timestamp = ?, "
                    "file_path = '', file_signature = '' WHERE id = ?",
                    (content, type_tag, item_timestamp, item_id),
                )
                updated_existing = True
            else:
                cursor.execute(
                    "INSERT INTO history (content, image_data, type, timestamp, file_path, file_signature) "
                    "VALUES (?, ?, ?, ?, '', '')",
                    (content, image_data, type_tag, item_timestamp),
                )
                item_id = cursor.lastrowid
                if item_id is None:
                    raise sqlite3.Error("Inserted history row has no id")
            return item_id, updated_existing

        cursor.execute(
            "INSERT INTO history (content, image_data, type, timestamp, file_path, file_signature) "
            "VALUES (?, ?, ?, ?, '', '')",
            (content, image_data, type_tag, item_timestamp),
        )
        item_id = cursor.lastrowid
        if item_id is None:
            raise sqlite3.Error("Inserted history row has no id")
        return item_id, False

    def add_item(self, content: str, image_data: bytes | None, type_tag: str) -> int | bool:
        """항목 추가. 동일 텍스트는 기존 항목을 최신 상태로 갱신."""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                item_id, updated_existing = self._add_item_locked(cursor, content, image_data, type_tag)
                if not item_id:
                    return False

                self.conn.commit()

                if updated_existing:
                    logger.debug(f"항목 갱신: {type_tag} (id={item_id})")
                else:
                    # v10.0: cleanup 최적화 - 매번이 아닌 N회마다 실행
                    self.add_count += 1
                    if self.add_count >= CLEANUP_INTERVAL:
                        cast(Any, self).cleanup()
                        self.add_count = 0
                    logger.debug(f"항목 추가: {type_tag} (id={item_id})")
                return item_id
            except sqlite3.Error as e:
                logger.exception("DB Add Error")
                self.conn.rollback()
                return False

    def replace_text_item_or_merge(self, item_id: int, content: str, type_tag: str) -> int | bool:
        """Replace a text history row, merging into an existing duplicate when needed."""
        if not content:
            return False

        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    """
                    SELECT tags, note, bookmark, collection_id, pinned, pin_order, use_count, timestamp, url_title
                    FROM history
                    WHERE id = ?
                    LIMIT 1
                    """,
                    (item_id,),
                )
                current_row = cursor.fetchone()
                if current_row is None:
                    return False

                cursor.execute(
                    """
                    SELECT id, tags, note, bookmark, collection_id, pinned, pin_order, use_count, timestamp, url_title
                    FROM history
                    WHERE id != ? AND content = ? AND type NOT IN ('IMAGE', 'FILE')
                    ORDER BY timestamp DESC, id DESC
                    LIMIT 1
                    """,
                    (item_id, content),
                )
                existing_row = cursor.fetchone()
                if existing_row:
                    target_id = int(existing_row[0])
                    synthetic_deleted_row = (
                        content,
                        None,
                        type_tag,
                        current_row[7],
                        current_row[0],
                        current_row[1],
                        current_row[2],
                        current_row[3],
                        current_row[4],
                        current_row[5],
                        current_row[6],
                        current_row[8],
                    )
                    metadata = self._build_merged_restore_metadata_locked(
                        cursor,
                        target_id,
                        existing_row[1:],
                        synthetic_deleted_row,
                    )
                    self._set_item_metadata_locked(cursor, target_id, **metadata)
                    cursor.execute("DELETE FROM history WHERE id = ?", (item_id,))
                    self.conn.commit()
                    return target_id

                cursor.execute(
                    """
                    UPDATE history
                    SET content = ?, image_data = NULL, type = ?, file_path = '', file_signature = '', url_title = ''
                    WHERE id = ?
                    """,
                    (content, type_tag, item_id),
                )
                self.conn.commit()
                return item_id if cursor.rowcount == 1 else False
            except sqlite3.Error as e:
                logger.error(f"Text Replace Merge Error: {e}")
                self.conn.rollback()
                return False


__all__ = ["HistoryWriteMixin"]
