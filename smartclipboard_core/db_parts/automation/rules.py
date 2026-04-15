from __future__ import annotations

import sqlite3

from ..shared import logger


class CopyRulesMixin:
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

    def is_duplicate_copy_rule(self, pattern: str, action: str, replacement: str = "", exclude_id: int | None = None) -> bool:
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
                        "SELECT 1 FROM copy_rules WHERE pattern = ? AND action = ? AND replacement = ? AND id != ? LIMIT 1",
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
