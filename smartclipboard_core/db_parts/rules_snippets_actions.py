from __future__ import annotations
import datetime
import sqlite3

from .shared import logger

class RulesSnippetsActionsMixin:
    def add_snippet(self, name, content, shortcut="", category="일반"):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "INSERT INTO snippets (name, content, shortcut, category, created_at) VALUES (?, ?, ?, ?, ?)",
                    (name, content, shortcut, category, created_at)
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
        """v10.2: 스니펫 수정"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "UPDATE snippets SET name=?, content=?, shortcut=?, category=? WHERE id=?",
                    (name, content, shortcut, category, snippet_id)
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

    def get_copy_rules(self):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT id, name, pattern, action, replacement, enabled, priority "
                    "FROM copy_rules ORDER BY priority DESC, id DESC"
                )
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.debug(f"Get copy rules error: {e}")
                return []

    def add_copy_rule(self, name, pattern, action, replacement=""):
        """복사 규칙 추가. 성공 여부를 반환."""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT COALESCE(MAX(priority), 0) + 1 FROM copy_rules")
                priority = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT INTO copy_rules (name, pattern, action, replacement, priority) VALUES (?, ?, ?, ?, ?)",
                    (name, pattern, action, replacement, priority),
                )
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Rule Add Error: {e}")
                self.conn.rollback()
                return False

    def is_duplicate_copy_rule(
        self,
        pattern: str,
        action: str,
        replacement: str = "",
        exclude_id: int | None = None,
    ) -> bool:
        """동일 복사 규칙 존재 여부."""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                if exclude_id is None:
                    cursor.execute(
                        "SELECT 1 FROM copy_rules WHERE pattern = ? AND action = ? AND replacement = ? LIMIT 1",
                        (pattern, action, replacement),
                    )
                else:
                    cursor.execute(
                        "SELECT 1 FROM copy_rules "
                        "WHERE pattern = ? AND action = ? AND replacement = ? AND id != ? LIMIT 1",
                        (pattern, action, replacement, exclude_id),
                    )
                return cursor.fetchone() is not None
            except sqlite3.Error as e:
                logger.debug(f"Duplicate copy rule check error: {e}")
                return False

    def update_copy_rule(self, rule_id, name, pattern, action, replacement=""):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "UPDATE copy_rules SET name = ?, pattern = ?, action = ?, replacement = ? WHERE id = ?",
                    (name, pattern, action, replacement, rule_id),
                )
                self.conn.commit()
                return cursor.rowcount == 1
            except sqlite3.Error as e:
                logger.error(f"Rule Update Error: {e}")
                self.conn.rollback()
                return False

    def update_copy_rule_priorities(self, ordered_ids: list[int]) -> bool:
        if not ordered_ids:
            return True
        if len(ordered_ids) != len(set(ordered_ids)):
            logger.error("Rule priority update failed: duplicate ids")
            return False

        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("BEGIN")
                total = len(ordered_ids)
                for index, rule_id in enumerate(ordered_ids):
                    priority = total - index
                    cursor.execute(
                        "UPDATE copy_rules SET priority = ? WHERE id = ?",
                        (priority, rule_id),
                    )
                    if cursor.rowcount != 1:
                        raise sqlite3.Error(f"Invalid copy rule id: {rule_id}")
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Rule priority update failed: {e}")
                self.conn.rollback()
                return False

    def toggle_copy_rule(self, rule_id, enabled):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE copy_rules SET enabled = ? WHERE id = ?", (enabled, rule_id))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Rule Toggle Error: {e}")
                self.conn.rollback()

    def delete_copy_rule(self, rule_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM copy_rules WHERE id = ?", (rule_id,))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Rule Delete Error: {e}")
                self.conn.rollback()

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
        """동일 클립보드 액션 존재 여부."""
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

