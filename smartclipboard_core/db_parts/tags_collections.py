from __future__ import annotations
import datetime
import sqlite3

from .shared import history_order_by, logger

class TagsCollectionsMixin:
    def get_item_tags(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT tags FROM history WHERE id = ?", (item_id,))
                result = cursor.fetchone()
                return result[0] if result and result[0] else ""
            except sqlite3.Error as e:
                logger.debug(f"Get item tags error: {e}")
                return ""

    def set_item_tags(self, item_id, tags):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE history SET tags = ? WHERE id = ?", (tags, item_id))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Tag Update Error: {e}")
                self.conn.rollback()

    def get_all_tags(self):
        """모든 고유 태그 목록 반환"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT DISTINCT tags FROM history WHERE tags != '' AND tags IS NOT NULL")
                all_tags = set()
                for (tags_str,) in cursor.fetchall():
                    for tag in tags_str.split(','):
                        tag = tag.strip()
                        if tag:
                            all_tags.add(tag)
                return sorted(all_tags)
            except sqlite3.Error as e:
                logger.debug(f"Get all tags error: {e}")
                return []

    def update_url_title(self, item_id: int, title: str) -> bool:
        """URL 제목을 캐시에 저장"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE history SET url_title = ? WHERE id = ?", (title, item_id))
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"URL title update failed: {e}")
                self.conn.rollback()
                return False

    def add_collection(self, name: str, icon: str = "📁", color: str = "#6366f1") -> int | bool:
        """컬렉션 추가"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "INSERT INTO collections (name, icon, color, created_at) VALUES (?, ?, ?, ?)",
                    (name, icon, color, created_at)
                )
                collection_row_id = cursor.lastrowid
                if collection_row_id is None:
                    raise sqlite3.Error("Inserted collection row has no id")
                self.conn.commit()
                return collection_row_id
            except sqlite3.Error as e:
                logger.error(f"Collection Add Error: {e}")
                self.conn.rollback()
                return False

    def get_collections(self) -> list:
        """모든 컬렉션 조회"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT id, name, icon, color, created_at FROM collections ORDER BY name")
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.error(f"Collection Get Error: {e}")
                return []

    def update_collection(self, collection_id: int, name: str, icon: str = "📁", color: str = "#6366f1") -> bool:
        """컬렉션 수정"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "UPDATE collections SET name = ?, icon = ?, color = ? WHERE id = ?",
                    (name, icon, color, collection_id)
                )
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Collection Update Error: {e}")
                self.conn.rollback()
                return False

    def delete_collection(self, collection_id: int) -> bool:
        """컬렉션 삭제 (항목의 collection_id는 NULL로 설정)"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                # 해당 컬렉션의 항목들 연결 해제
                cursor.execute("UPDATE history SET collection_id = NULL WHERE collection_id = ?", (collection_id,))
                cursor.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Collection Delete Error: {e}")
                self.conn.rollback()
                return False

    def assign_to_collection(self, item_id: int, collection_id: int | None) -> bool:
        """항목을 컬렉션에 할당 (None이면 해제)"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE history SET collection_id = ? WHERE id = ?", (collection_id, item_id))
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Assign Collection Error: {e}")
                self.conn.rollback()
                return False

    def get_items_by_collection(self, collection_id: int) -> list:
        """컬렉션별 항목 조회"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT id, content, type, timestamp, pinned, use_count, pin_order "
                    f"FROM history WHERE collection_id = ? {history_order_by()}",
                    (collection_id,)
                )
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.error(f"Get Items by Collection Error: {e}")
                return []

    def get_items_uncategorized(self) -> list:
        """컬렉션이 없는(미분류) 항목 조회"""
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
        """여러 항목을 컬렉션으로 이동(또는 해제). 적용 건수 반환."""
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

