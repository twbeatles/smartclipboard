from __future__ import annotations

import sqlite3

from ..shared import logger


class TagCatalogMixin:
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
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT DISTINCT tags FROM history WHERE tags != '' AND tags IS NOT NULL")
                all_tags = set()
                for (tags_str,) in cursor.fetchall():
                    for tag in tags_str.split(","):
                        tag = tag.strip()
                        if tag:
                            all_tags.add(tag)
                return sorted(all_tags)
            except sqlite3.Error as e:
                logger.debug(f"Get all tags error: {e}")
                return []

    def update_url_title(self, item_id: int, title: str) -> bool:
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
