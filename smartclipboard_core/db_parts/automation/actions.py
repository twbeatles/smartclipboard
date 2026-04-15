from __future__ import annotations

import sqlite3

from ..shared import logger


class ClipboardActionsMixin:
    def get_clipboard_actions(self):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT id, name, pattern, action_type, action_params, enabled, priority "
                    "FROM clipboard_actions ORDER BY priority DESC, id DESC"
                )
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.error(f"Get Actions Error: {e}")
                return []

    def add_clipboard_action(self, name, pattern, action_type, action_params="{}"):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT COALESCE(MAX(priority), 0) + 1 FROM clipboard_actions")
                priority = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT INTO clipboard_actions (name, pattern, action_type, action_params, priority) VALUES (?, ?, ?, ?, ?)",
                    (name, pattern, action_type, action_params, priority),
                )
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Action Add Error: {e}")
                self.conn.rollback()
                return False

    def is_duplicate_clipboard_action(
        self,
        pattern: str,
        action_type: str,
        action_params: str = "{}",
        exclude_id: int | None = None,
    ) -> bool:
        with self.lock:
            try:
                cursor = self.conn.cursor()
                if exclude_id is None:
                    cursor.execute(
                        "SELECT 1 FROM clipboard_actions WHERE pattern = ? AND action_type = ? AND action_params = ? LIMIT 1",
                        (pattern, action_type, action_params),
                    )
                else:
                    cursor.execute(
                        "SELECT 1 FROM clipboard_actions "
                        "WHERE pattern = ? AND action_type = ? AND action_params = ? AND id != ? LIMIT 1",
                        (pattern, action_type, action_params, exclude_id),
                    )
                return cursor.fetchone() is not None
            except sqlite3.Error as e:
                logger.debug(f"Duplicate clipboard action check error: {e}")
                return False

    def update_clipboard_action(self, action_id, name, pattern, action_type, action_params="{}"):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    """
                    UPDATE clipboard_actions
                    SET name = ?, pattern = ?, action_type = ?, action_params = ?
                    WHERE id = ?
                    """,
                    (name, pattern, action_type, action_params, action_id),
                )
                self.conn.commit()
                return cursor.rowcount == 1
            except sqlite3.Error as e:
                logger.error(f"Action Update Error: {e}")
                self.conn.rollback()
                return False

    def update_clipboard_action_priorities(self, ordered_ids: list[int]) -> bool:
        if not ordered_ids:
            return True
        if len(ordered_ids) != len(set(ordered_ids)):
            logger.error("Action priority update failed: duplicate ids")
            return False

        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("BEGIN")
                total = len(ordered_ids)
                for index, action_id in enumerate(ordered_ids):
                    priority = total - index
                    cursor.execute(
                        "UPDATE clipboard_actions SET priority = ? WHERE id = ?",
                        (priority, action_id),
                    )
                    if cursor.rowcount != 1:
                        raise sqlite3.Error(f"Invalid clipboard action id: {action_id}")
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Action priority update failed: {e}")
                self.conn.rollback()
                return False

    def toggle_clipboard_action(self, action_id, enabled):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE clipboard_actions SET enabled = ? WHERE id = ?", (enabled, action_id))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Action Toggle Error: {e}")
                self.conn.rollback()

    def delete_clipboard_action(self, action_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM clipboard_actions WHERE id = ?", (action_id,))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Action Delete Error: {e}")
                self.conn.rollback()
