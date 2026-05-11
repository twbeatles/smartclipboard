from __future__ import annotations

import sqlite3

from smartclipboard_core.file_paths import file_signature_from_content

from ..shared import logger
from ..typing_helpers import DBRuntimeMixin


class SearchSchemaMixin(DBRuntimeMixin):
    @staticmethod
    def _normalize_unique_name(name: str) -> str:
        return " ".join(str(name or "").split()).strip()

    def _dedupe_collections_for_unique_index(self, cursor) -> None:
        cursor.execute("SELECT id, name FROM collections ORDER BY id ASC")
        rows = cursor.fetchall()
        groups: dict[str, list[int]] = {}
        for collection_id, name in rows:
            normalized = self._normalize_unique_name(name) or f"Collection {collection_id}"
            if normalized != name:
                cursor.execute("UPDATE collections SET name = ? WHERE id = ?", (normalized, collection_id))
            groups.setdefault(normalized, []).append(int(collection_id))

        for collection_ids in groups.values():
            if len(collection_ids) <= 1:
                continue
            keep_id = collection_ids[0]
            duplicate_ids = collection_ids[1:]
            placeholders = ",".join("?" for _ in duplicate_ids)
            cursor.execute(
                f"UPDATE history SET collection_id = ? WHERE collection_id IN ({placeholders})",
                [keep_id, *duplicate_ids],
            )
            cursor.execute(
                f"UPDATE deleted_history SET collection_id = ? WHERE collection_id IN ({placeholders})",
                [keep_id, *duplicate_ids],
            )
            cursor.execute(f"DELETE FROM collections WHERE id IN ({placeholders})", duplicate_ids)

    @staticmethod
    def _dedupe_snippet_shortcuts_for_unique_index(cursor) -> None:
        cursor.execute(
            """
            SELECT shortcut, GROUP_CONCAT(id)
            FROM snippets
            WHERE shortcut IS NOT NULL AND shortcut != ''
            GROUP BY shortcut
            HAVING COUNT(*) > 1
            """
        )
        duplicate_groups = cursor.fetchall()
        for _shortcut, raw_ids in duplicate_groups:
            snippet_ids = [int(value) for value in str(raw_ids).split(",") if value]
            for duplicate_id in snippet_ids[1:]:
                cursor.execute("UPDATE snippets SET shortcut = '' WHERE id = ?", (duplicate_id,))

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
                "ALTER TABLE history ADD COLUMN pinned INTEGER DEFAULT 0",
                "ALTER TABLE history ADD COLUMN use_count INTEGER DEFAULT 0",
                "ALTER TABLE history ADD COLUMN category TEXT DEFAULT ''",
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
                    url_title TEXT DEFAULT '',
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
                "ALTER TABLE deleted_history ADD COLUMN url_title TEXT DEFAULT ''",
            ):
                try:
                    cursor.execute(col_sql)
                except sqlite3.OperationalError:
                    pass

            try:
                self._dedupe_collections_for_unique_index(cursor)
                self._dedupe_snippet_shortcuts_for_unique_index(cursor)
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_collections_name_unique ON collections(name)")
                cursor.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_snippets_shortcut_unique "
                    "ON snippets(shortcut) WHERE shortcut IS NOT NULL AND shortcut != ''"
                )
            except sqlite3.OperationalError as e:
                logger.debug(f"Unique index creation skipped: {e}")

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
