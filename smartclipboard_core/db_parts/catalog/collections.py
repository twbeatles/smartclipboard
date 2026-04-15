from __future__ import annotations

import datetime
import sqlite3

from ..shared import history_order_by, logger


class CollectionCatalogMixin:
    @staticmethod
    def _normalize_collection_name(name: str) -> str:
        return " ".join(str(name or "").split()).strip()

    @staticmethod
    def _collection_exists(cursor, collection_id: int) -> bool:
        cursor.execute("SELECT 1 FROM collections WHERE id = ? LIMIT 1", (collection_id,))
        return cursor.fetchone() is not None

    def add_collection(self, name: str, icon: str = "📁", color: str = "#6366f1") -> int | bool:
        normalized_name = self._normalize_collection_name(name)
        if not normalized_name:
            return False
        with self.lock:
            try:
                cursor = self.conn.cursor()
                collection_row_id = self._add_collection_locked(cursor, normalized_name, icon, color)
                if collection_row_id:
                    self.conn.commit()
                return collection_row_id
            except sqlite3.Error as e:
                logger.error(f"Collection Add Error: {e}")
                self.conn.rollback()
                return False

    def get_collections(self) -> list:
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT id, name, icon, color, created_at FROM collections ORDER BY name")
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.error(f"Collection Get Error: {e}")
                return []

    def get_collection_by_name(self, name: str):
        normalized_name = self._normalize_collection_name(name)
        if not normalized_name:
            return None
        with self.lock:
            try:
                cursor = self.conn.cursor()
                return self._get_collection_by_name_locked(cursor, normalized_name)
            except sqlite3.Error as e:
                logger.error(f"Collection Lookup Error: {e}")
                return None

    def _get_collection_by_name_locked(self, cursor, normalized_name: str):
        cursor.execute(
            "SELECT id, name, icon, color, created_at FROM collections WHERE name = ?",
            (normalized_name,),
        )
        return cursor.fetchone()

    def _add_collection_locked(self, cursor, normalized_name: str, icon: str, color: str) -> int | bool:
        existing = self._get_collection_by_name_locked(cursor, normalized_name)
        if existing:
            logger.warning("Collection Add Error: duplicate name '%s'", normalized_name)
            return False
        created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO collections (name, icon, color, created_at) VALUES (?, ?, ?, ?)",
            (normalized_name, icon, color, created_at),
        )
        collection_row_id = cursor.lastrowid
        if collection_row_id is None:
            raise sqlite3.Error("Inserted collection row has no id")
        return collection_row_id

    def is_duplicate_collection_name(self, name: str, exclude_id: int | None = None) -> bool:
        normalized_name = self._normalize_collection_name(name)
        if not normalized_name:
            return False
        with self.lock:
            try:
                cursor = self.conn.cursor()
                if exclude_id is None:
                    cursor.execute("SELECT 1 FROM collections WHERE name = ? LIMIT 1", (normalized_name,))
                else:
                    cursor.execute("SELECT 1 FROM collections WHERE name = ? AND id != ? LIMIT 1", (normalized_name, exclude_id))
                return cursor.fetchone() is not None
            except sqlite3.Error as e:
                logger.error(f"Collection Duplicate Check Error: {e}")
                return False

    def update_collection(self, collection_id: int, name: str, icon: str = "📁", color: str = "#6366f1") -> bool:
        normalized_name = self._normalize_collection_name(name)
        if not normalized_name:
            return False
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM collections WHERE name = ? AND id != ? LIMIT 1",
                    (normalized_name, collection_id),
                )
                if cursor.fetchone() is not None:
                    logger.warning("Collection Update Error: duplicate name '%s'", normalized_name)
                    return False
                cursor.execute(
                    "UPDATE collections SET name = ?, icon = ?, color = ? WHERE id = ?",
                    (normalized_name, icon, color, collection_id),
                )
                self.conn.commit()
                return cursor.rowcount == 1
            except sqlite3.Error as e:
                logger.error(f"Collection Update Error: {e}")
                self.conn.rollback()
                return False

    def delete_collection(self, collection_id: int) -> bool:
        with self.lock:
            try:
                cursor = self.conn.cursor()
                if not self._collection_exists(cursor, collection_id):
                    logger.warning("Collection Delete Error: missing collection_id=%s", collection_id)
                    return False
                cursor.execute("UPDATE history SET collection_id = NULL WHERE collection_id = ?", (collection_id,))
                cursor.execute("UPDATE deleted_history SET collection_id = NULL WHERE collection_id = ?", (collection_id,))
                cursor.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
                self.conn.commit()
                return cursor.rowcount == 1
            except sqlite3.Error as e:
                logger.error(f"Collection Delete Error: {e}")
                self.conn.rollback()
                return False

    def assign_to_collection(self, item_id: int, collection_id: int | None) -> bool:
        with self.lock:
            try:
                cursor = self.conn.cursor()
                if collection_id is not None and not self._collection_exists(cursor, collection_id):
                    logger.warning("Assign Collection Error: invalid collection_id=%s", collection_id)
                    return False
                cursor.execute("SELECT 1 FROM history WHERE id = ? LIMIT 1", (item_id,))
                if cursor.fetchone() is None:
                    logger.warning("Assign Collection Error: missing item_id=%s", item_id)
                    return False
                cursor.execute("UPDATE history SET collection_id = ? WHERE id = ?", (collection_id, item_id))
                self.conn.commit()
                return cursor.rowcount == 1
            except sqlite3.Error as e:
                logger.error(f"Assign Collection Error: {e}")
                self.conn.rollback()
                return False

    def get_items_by_collection(self, collection_id: int) -> list:
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT id, content, type, timestamp, pinned, use_count, pin_order "
                    f"FROM history WHERE collection_id = ? {history_order_by()}",
                    (collection_id,),
                )
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.error(f"Get Items by Collection Error: {e}")
                return []

    def get_items_uncategorized(self) -> list:
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT id, content, type, timestamp, pinned, use_count, pin_order "
                    f"FROM history WHERE collection_id IS NULL {history_order_by()}"
                )
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.error(f"Get Uncategorized Items Error: {e}")
                return []

    def get_items_by_tag(self, tag):
        with self.lock:
            try:
                normalized_tag = (tag or "").replace("，", ",").strip().strip(",")
                if not normalized_tag:
                    return []
                cursor = self.conn.cursor()
                cursor.execute(
                    f"""
                    SELECT id, content, type, timestamp, pinned, use_count, pin_order
                    FROM history
                    WHERE tags IS NOT NULL
                      AND tags != ''
                      AND instr(
                          ',' || REPLACE(REPLACE(REPLACE(tags, '，', ','), ', ', ','), ' ,', ',') || ',',
                          ',' || ? || ','
                      ) > 0
                    {history_order_by()}
                    """,
                    (normalized_tag,),
                )
                return cursor.fetchall()
            except sqlite3.Error:
                return []

    def move_to_collection(self, item_id, collection_id):
        moved = self.move_items_to_collection([item_id], collection_id)
        return moved > 0

    def move_items_to_collection(self, item_ids: list[int], collection_id: int | None) -> int:
        if not item_ids:
            return 0

        unique_ids: list[int] = []
        seen = set()
        for raw_item_id in item_ids:
            try:
                item_id = int(raw_item_id)
            except (TypeError, ValueError):
                continue
            if item_id <= 0 or item_id in seen:
                continue
            seen.add(item_id)
            unique_ids.append(item_id)

        if not unique_ids:
            return 0

        placeholders = ",".join("?" for _ in unique_ids)
        with self.lock:
            try:
                cursor = self.conn.cursor()
                if collection_id is not None and not self._collection_exists(cursor, collection_id):
                    logger.warning("Move Items to Collection Error: invalid collection_id=%s", collection_id)
                    return 0
                cursor.execute(
                    f"UPDATE history SET collection_id = ? WHERE id IN ({placeholders})",
                    [collection_id, *unique_ids],
                )
                moved = cursor.rowcount if cursor.rowcount is not None and cursor.rowcount >= 0 else 0
                self.conn.commit()
                return moved
            except sqlite3.Error as e:
                logger.error(f"Move Items to Collection Error: {e}")
                self.conn.rollback()
                return 0
