from __future__ import annotations
import sqlite3

from .shared import FILTER_TAG_MAP, logger

class SchemaSearchMixin:
    def create_tables(self):
        try:
            cursor = self.conn.cursor()
            # 히스토리 테이블
            cursor.execute("""
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
            """)
            # 스니펫 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS snippets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    shortcut TEXT,
                    category TEXT DEFAULT '일반',
                    created_at TEXT
                )
            """)
            # 설정 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            # 복사 규칙 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS copy_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    action TEXT NOT NULL,
                    replacement TEXT DEFAULT '',
                    enabled INTEGER DEFAULT 1,
                    priority INTEGER DEFAULT 0
                )
            """)
            
            # v8.0 새 테이블: 암호화 보관함
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS secure_vault (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    encrypted_content BLOB,
                    label TEXT,
                    created_at TEXT
                )
            """)
            
            # v8.0 새 테이블: 클립보드 액션 자동화
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clipboard_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    action_params TEXT DEFAULT '{}',
                    enabled INTEGER DEFAULT 1,
                    priority INTEGER DEFAULT 0
                )
            """)
            
            # tags 컬럼 추가 (기존 테이블 마이그레이션)
            try:
                cursor.execute("ALTER TABLE history ADD COLUMN tags TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass  # 이미 존재하는 경우
            # pin_order 컬럼 추가 (고정 항목 순서용)
            try:
                cursor.execute("ALTER TABLE history ADD COLUMN pin_order INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # 이미 존재하는 경우
            # v8.0: file_path 컬럼 추가 (파일 히스토리용)
            try:
                cursor.execute("ALTER TABLE history ADD COLUMN file_path TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass
            # v8.0: url_title 컬럼 추가 (링크 제목 캐시)
            try:
                cursor.execute("ALTER TABLE history ADD COLUMN url_title TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass
            
            # v10.0: 컬렉션 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS collections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    icon TEXT DEFAULT '📁',
                    color TEXT DEFAULT '#6366f1',
                    created_at TEXT
                )
            """)
            
            # v10.0: 휴지통 (실행취소용)
            cursor.execute("""
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
            """)
            # 비파괴 마이그레이션: 기존 deleted_history 확장
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
            
            # v10.0: collection_id 컬럼 추가
            try:
                cursor.execute("ALTER TABLE history ADD COLUMN collection_id INTEGER DEFAULT NULL")
            except sqlite3.OperationalError:
                pass
            # v10.0: note 컬럼 추가 (메모 첨부)
            try:
                cursor.execute("ALTER TABLE history ADD COLUMN note TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass
            # v10.0: bookmark 컬럼 추가
            try:
                cursor.execute("ALTER TABLE history ADD COLUMN bookmark INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            # v10.0: expires_at 컬럼 추가 (임시 클립보드)
            try:
                cursor.execute("ALTER TABLE history ADD COLUMN expires_at TEXT DEFAULT NULL")
            except sqlite3.OperationalError:
                pass
            
            # v10.1: 자주 사용되는 컬럼에 인덱스 추가 (쿼리 성능 최적화)
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_pinned ON history(pinned)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_type ON history(type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_timestamp ON history(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_bookmark ON history(bookmark)")
            except sqlite3.OperationalError as e:
                logger.debug(f"Index creation skipped: {e}")
            
            self.conn.commit()
            logger.info("DB 테이블 초기화 완료 (v10.1)")

            # v11: unified full-text search index (FTS5) for fast search across fields.
            # This is safe to call repeatedly; creation/migration is idempotent.
            self.ensure_search_index()
        except sqlite3.Error as e:
            logger.error(f"DB Init Error: {e}")
        except Exception as e:
            logger.error(f"DB Init Error (search index): {e}")

    def ensure_search_index(self) -> bool:
        """Ensure FTS5 table + triggers exist and are populated.

        On first creation, we force a one-time backup to protect user data.
        """
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='history_fts'")
                exists = cursor.fetchone() is not None

                if not exists:
                    # One-time safety net before touching schema in a user's DB.
                    try:
                        self.backup_db(force=True)
                    except Exception:
                        logger.exception("FTS init: backup failed (continuing)")

                    cursor.execute(
                        "CREATE VIRTUAL TABLE IF NOT EXISTS history_fts "
                        "USING fts5(content, tags, note, url_title, tokenize='unicode61')"
                    )

                # Keep the index in sync with history table mutations.
                cursor.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS history_ai AFTER INSERT ON history BEGIN
                        INSERT INTO history_fts(rowid, content, tags, note, url_title)
                        VALUES (new.id, COALESCE(new.content, ''), COALESCE(new.tags, ''), COALESCE(new.note, ''), COALESCE(new.url_title, ''));
                    END;
                    """
                )
                cursor.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS history_ad AFTER DELETE ON history BEGIN
                        DELETE FROM history_fts WHERE rowid = old.id;
                    END;
                    """
                )
                cursor.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS history_au AFTER UPDATE OF content, tags, note, url_title ON history BEGIN
                        DELETE FROM history_fts WHERE rowid = old.id;
                        INSERT INTO history_fts(rowid, content, tags, note, url_title)
                        VALUES (new.id, COALESCE(new.content, ''), COALESCE(new.tags, ''), COALESCE(new.note, ''), COALESCE(new.url_title, ''));
                    END;
                    """
                )

                # Populate index (or refresh if we just created it).
                if not exists:
                    cursor.execute("INSERT INTO history_fts(history_fts) VALUES('rebuild')")

                self.conn.commit()
                return True
            except sqlite3.OperationalError as e:
                # If SQLite is built without FTS5, keep the app usable.
                logger.warning(f"FTS unavailable or failed to initialize: {e}")
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                return False
            except sqlite3.Error as e:
                logger.error(f"FTS init error: {e}")
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                return False

    @staticmethod
    def _tokenize_search_query(query: str) -> list[str]:
        import re

        if not query:
            return []
        # Extract "word-like" unicode tokens; drops punctuation that can break MATCH syntax.
        tokens = re.findall(r"[\w]+", query, flags=re.UNICODE)
        return [t for t in (x.strip() for x in tokens) if t]

    @classmethod
    def _build_fts_match(cls, query: str) -> str:
        tokens = cls._tokenize_search_query(query)
        if not tokens:
            return ""
        parts = []
        for t in tokens:
            # Avoid overly broad single-character prefix searches.
            parts.append(f"{t}*" if len(t) > 1 else t)
        # Space is AND in FTS5 query syntax.
        return " ".join(parts)

    def search_items(
        self,
        query: str,
        type_filter: str = "전체",
        tag_filter: str | None = None,
        bookmarked: bool = False,
        collection_id: int | None = None,
        limit: int | None = None,
        uncategorized: bool = False,
    ) -> list:
        """Unified search with FTS5 when available; falls back to LIKE safely.

        Returns rows shaped like `get_items`: (id, content, type, timestamp, pinned, use_count, pin_order)
        """
        q = (query or "").strip()
        normalized_tag = (tag_filter or "").replace("，", ",").strip().strip(",") if tag_filter else ""

        # Expose last search state for UI messaging without breaking call sites.
        self._last_search_used_fts = False
        self._last_search_fallback = False
        self._last_search_error = None

        # Prefer FTS if initialized.
        match_expr = self._build_fts_match(q)
        if q and match_expr:
            with self.lock:
                try:
                    cursor = self.conn.cursor()
                    sql = (
                        "SELECT h.id, h.content, h.type, h.timestamp, h.pinned, h.use_count, h.pin_order "
                        "FROM history h "
                        "JOIN history_fts ON history_fts.rowid = h.id "
                        "WHERE history_fts MATCH ?"
                    )
                    params: list[object] = [match_expr]

                    if normalized_tag:
                        sql += (
                            " AND h.tags IS NOT NULL AND h.tags != '' AND instr("
                            " ',' || REPLACE(REPLACE(REPLACE(h.tags, '，', ','), ', ', ','), ' ,', ',') || ',',"
                            " ',' || ? || ','"
                            " ) > 0"
                        )
                        params.append(normalized_tag)

                    if bookmarked or type_filter == "⭐ 북마크":
                        sql += " AND h.bookmark = 1"
                    elif type_filter == "📌 고정":
                        sql += " AND h.pinned = 1"
                    elif type_filter in FILTER_TAG_MAP:
                        sql += " AND h.type = ?"
                        params.append(FILTER_TAG_MAP[type_filter])
                    elif type_filter != "전체":
                        legacy_map = {"텍스트": "TEXT", "이미지": "IMAGE", "링크": "LINK", "코드": "CODE", "색상": "COLOR"}
                        if type_filter in legacy_map:
                            sql += " AND h.type = ?"
                            params.append(legacy_map[type_filter])

                    if collection_id is not None:
                        sql += " AND h.collection_id = ?"
                        params.append(collection_id)
                    elif uncategorized:
                        sql += " AND h.collection_id IS NULL"

                    sql += " ORDER BY h.pinned DESC, h.pin_order ASC, bm25(history_fts) ASC, h.id DESC"
                    if limit is not None:
                        sql += " LIMIT ?"
                        params.append(int(limit))

                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
                    self._last_search_used_fts = True
                    return rows
                except sqlite3.Error as e:
                    self._last_search_fallback = True
                    self._last_search_error = str(e)
                    logger.debug(f"FTS search failed, falling back to LIKE: {e}")

        # Fallback: LIKE across key fields.
        with self.lock:
            cursor = self.conn.cursor()
            sql = (
                "SELECT id, content, type, timestamp, pinned, use_count, pin_order "
                "FROM history WHERE 1=1"
            )
            params2: list[object] = []

            if q:
                like = f"%{q}%"
                sql += " AND (content LIKE ? OR tags LIKE ? OR note LIKE ? OR url_title LIKE ?)"
                params2.extend([like, like, like, like])

            if normalized_tag:
                sql += (
                    " AND tags IS NOT NULL AND tags != '' AND instr("
                    " ',' || REPLACE(REPLACE(REPLACE(tags, '，', ','), ', ', ','), ' ,', ',') || ',',"
                    " ',' || ? || ','"
                    " ) > 0"
                )
                params2.append(normalized_tag)

            if bookmarked or type_filter == "⭐ 북마크":
                sql += " AND bookmark = 1"
            elif type_filter == "📌 고정":
                sql += " AND pinned = 1"
            elif type_filter in FILTER_TAG_MAP:
                sql += " AND type = ?"
                params2.append(FILTER_TAG_MAP[type_filter])
            elif type_filter != "전체":
                legacy_map = {"텍스트": "TEXT", "이미지": "IMAGE", "링크": "LINK", "코드": "CODE", "색상": "COLOR"}
                if type_filter in legacy_map:
                    sql += " AND type = ?"
                    params2.append(legacy_map[type_filter])

            if collection_id is not None:
                sql += " AND collection_id = ?"
                params2.append(collection_id)
            elif uncategorized:
                sql += " AND collection_id IS NULL"

            sql += " ORDER BY pinned DESC, pin_order ASC, id DESC"
            if limit is not None:
                sql += " LIMIT ?"
                params2.append(int(limit))

            cursor.execute(sql, params2)
            return cursor.fetchall()

