from __future__ import annotations

import datetime
import sqlite3

from ..shared import logger


class SnippetSettingsMixin:
    def add_snippet(self, name, content, shortcut="", category="일반"):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "INSERT INTO snippets (name, content, shortcut, category, created_at) VALUES (?, ?, ?, ?, ?)",
                    (name, content, shortcut, category, created_at),
                )
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Snippet Add Error: {e}")
                self.conn.rollback()
                return False

    def get_snippets(self, category=""):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                if category and category != "전체":
                    cursor.execute("SELECT id, name, content, shortcut, category FROM snippets WHERE category = ?", (category,))
                else:
                    cursor.execute("SELECT id, name, content, shortcut, category FROM snippets")
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.error(f"Snippet Get Error: {e}")
                return []

    def delete_snippet(self, snippet_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM snippets WHERE id = ?", (snippet_id,))
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Snippet Delete Error: {e}")
                self.conn.rollback()
                return False

    def update_snippet(self, snippet_id, name, content, shortcut="", category="일반"):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "UPDATE snippets SET name=?, content=?, shortcut=?, category=? WHERE id=?",
                    (name, content, shortcut, category, snippet_id),
                )
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Snippet Update Error: {e}")
                self.conn.rollback()
                return False

    def get_setting(self, key, default=None):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
                result = cursor.fetchone()
                return result[0] if result else default
            except sqlite3.Error as e:
                logger.debug(f"Setting get error: {e}")
                return default

    def set_setting(self, key, value):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Setting Save Error: {e}")
                self.conn.rollback()
