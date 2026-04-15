from __future__ import annotations

import sqlite3

from smartclipboard_core.file_paths import file_signature_from_content

from ..shared import logger


class SearchSchemaMixin:
    def create_tables(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT,
                    image_data BLOB,
                    type TEXT,
                    timestamp TEXT,
                    pinned INTEGER DEFAULT 0,
                    use_count INTEGER DEFAULT 0,
                    category TEXT DEFAULT ''
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS snippets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    shortcut TEXT,
                    category TEXT DEFAULT '일반',
                    created_at TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS copy_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    action TEXT NOT NULL,
                    replacement TEXT DEFAULT '',
                    enabled INTEGER DEFAULT 1,
                    priority INTEGER DEFAULT 0
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS secure_vault (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    encrypted_content BLOB,
                    label TEXT,
                    created_at TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS clipboard_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    action_params TEXT DEFAULT '{}',
                    enabled INTEGER DEFAULT 1,
                    priority INTEGER DEFAULT 0
                )
                """
            )

            for sql in (
                "ALTER TABLE history ADD COLUMN tags TEXT DEFAULT ''",
                "ALTER TABLE history ADD COLUMN pin_order INTEGER DEFAULT 0",
                "ALTER TABLE history ADD COLUMN file_path TEXT DEFAULT ''",
                "ALTER TABLE history ADD COLUMN file_signature TEXT DEFAULT ''",
                "ALTER TABLE history ADD COLUMN url_title TEXT DEFAULT ''",
                "ALTER TABLE history ADD COLUMN collection_id INTEGER DEFAULT NULL",
                "ALTER TABLE history ADD COLUMN note TEXT DEFAULT ''",
                "ALTER TABLE history ADD COLUMN bookmark INTEGER DEFAULT 0",
                "ALTER TABLE history ADD COLUMN expires_at TEXT DEFAULT NULL",
            ):
                try:
                    cursor.execute(sql)
                except sqlite3.OperationalError:
                    pass

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS collections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    icon TEXT DEFAULT '📁',
                    color TEXT DEFAULT '#6366f1',
                    created_at TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS deleted_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_id INTEGER,
                    content TEXT,
                    image_data BLOB,
                    type TEXT,
                    original_timestamp TEXT,
                    tags TEXT DEFAULT '',
                    note TEXT DEFAULT '',
                    bookmark INTEGER DEFAULT 0,
                    collection_id INTEGER DEFAULT NULL,
                    pinned INTEGER DEFAULT 0,
                    pin_order INTEGER DEFAULT 0,
                    use_count INTEGER DEFAULT 0,
                    deleted_at TEXT,
                    expires_at TEXT
                )
                """
            )
            for col_sql in (
                "ALTER TABLE deleted_history ADD COLUMN original_timestamp TEXT",
                "ALTER TABLE deleted_history ADD COLUMN tags TEXT DEFAULT ''",
                "ALTER TABLE deleted_history ADD COLUMN note TEXT DEFAULT ''",
                "ALTER TABLE deleted_history ADD COLUMN bookmark INTEGER DEFAULT 0",
                "ALTER TABLE deleted_history ADD COLUMN collection_id INTEGER DEFAULT NULL",
                "ALTER TABLE deleted_history ADD COLUMN pinned INTEGER DEFAULT 0",
                "ALTER TABLE deleted_history ADD COLUMN pin_order INTEGER DEFAULT 0",
                "ALTER TABLE deleted_history ADD COLUMN use_count INTEGER DEFAULT 0",
            ):
                try:
                    cursor.execute(col_sql)
                except sqlite3.OperationalError:
                    pass

            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_pinned ON history(pinned)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_type ON history(type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_timestamp ON history(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_bookmark ON history(bookmark)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_file_signature ON history(file_signature)")
            except sqlite3.OperationalError as e:
                logger.debug(f"Index creation skipped: {e}")

            try:
                cursor.execute(
                    "SELECT id, content FROM history WHERE type = 'FILE' AND COALESCE(file_signature, '') = ''"
                )
                stale_file_rows = cursor.fetchall()
                for item_id, content in stale_file_rows:
                    cursor.execute(
                        "UPDATE history SET file_signature = ? WHERE id = ?",
                        (file_signature_from_content(content), item_id),
                    )
            except sqlite3.OperationalError as e:
                logger.debug(f"FILE signature backfill skipped: {e}")

            self.conn.commit()
            logger.info("DB 테이블 초기화 완료 (v10.1)")
            self.ensure_search_index()
        except sqlite3.Error as e:
            logger.error(f"DB Init Error: {e}")
        except Exception as e:
            logger.error(f"DB Init Error (search index): {e}")
