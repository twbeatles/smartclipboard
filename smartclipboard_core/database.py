"""Core database layer for SmartClipboard."""

from __future__ import annotations

import datetime
import logging
import os
import sqlite3
import threading
from typing import Optional


def get_app_directory() -> str:
    """Return base directory for app data and database files."""
    import sys

    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # In source mode this file lives in smartclipboard_core/, so use parent.
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


APP_DIR = get_app_directory()
DB_FILE = os.path.join(APP_DIR, "clipboard_history_v6.db")
DEFAULT_MAX_HISTORY = 100
CLEANUP_INTERVAL = 10
FILTER_TAG_MAP = {
    "📝 텍스트": "TEXT",
    "🖼️ 이미지": "IMAGE",
    "🔗 링크": "LINK",
    "💻 코드": "CODE",
    "🎨 색상": "COLOR",
}

logger = logging.getLogger(__name__)


class ClipboardDB:
    def __init__(self, db_file: Optional[str] = None, app_dir: Optional[str] = None):
        self.app_dir = app_dir or APP_DIR
        self.db_file = db_file or os.path.join(self.app_dir, "clipboard_history_v6.db")
        self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
        # v10.6: WAL 모드 활성화 (동시성 및 성능 향상)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.lock = threading.RLock()
        self.add_count = 0  # v10.0: cleanup 최적화를 위한 카운터
        self.create_tables()

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
                    deleted_at TEXT,
                    expires_at TEXT
                )
            """)
            
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
        except sqlite3.Error as e:
            logger.error(f"DB Init Error: {e}")

    def add_item(self, content: str, image_data: bytes | None, type_tag: str) -> int | bool:
        """항목 추가 - 중복 텍스트는 끌어올리기"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                if type_tag != "IMAGE":
                    cursor.execute("SELECT id FROM history WHERE content = ? AND pinned = 0", (content,))
                    existing = cursor.fetchone()
                    if existing:
                        cursor.execute("DELETE FROM history WHERE id = ?", (existing[0],))
                
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "INSERT INTO history (content, image_data, type, timestamp) VALUES (?, ?, ?, ?)", 
                    (content, image_data, type_tag, timestamp)
                )
                self.conn.commit()
                # v10.0: cleanup 최적화 - 매번이 아닌 N회마다 실행
                self.add_count += 1
                if self.add_count >= CLEANUP_INTERVAL:
                    self.cleanup()
                    self.add_count = 0
                item_id = cursor.lastrowid
                logger.debug(f"항목 추가: {type_tag} (id={item_id})")
                return item_id  # 삽입된 항목 ID 반환 (성능 최적화)
            except sqlite3.Error as e:
                logger.exception("DB Add Error")
                self.conn.rollback()
                return False

    def get_items(self, search_query: str = "", type_filter: str = "전체") -> list:
        with self.lock:
            try:
                cursor = self.conn.cursor()
                sql = "SELECT id, content, type, timestamp, pinned, use_count, pin_order FROM history WHERE 1=1"
                params = []

                if search_query:
                    sql += " AND content LIKE ?"
                    params.append(f"%{search_query}%")
                
                if type_filter == "📌 고정":
                    sql += " AND pinned = 1"
                elif type_filter == "⭐ 북마크":
                    sql += " AND bookmark = 1"
                elif type_filter in FILTER_TAG_MAP:  # v10.0: 상수 사용
                    sql += " AND type = ?"
                    params.append(FILTER_TAG_MAP[type_filter])
                elif type_filter != "전체":
                    # 레거시 필터 호환성
                    legacy_map = {"텍스트": "TEXT", "이미지": "IMAGE", "링크": "LINK", "코드": "CODE", "색상": "COLOR"}
                    if type_filter in legacy_map:
                        sql += " AND type = ?"
                        params.append(legacy_map[type_filter])

                sql += " ORDER BY pinned DESC, pin_order ASC, id DESC"
                cursor.execute(sql, params)
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.exception("DB Get Error")
                return []

    def update_pin_order(self, item_id: int, order: int) -> bool:
        """고정 항목의 순서를 업데이트"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE history SET pin_order = ? WHERE id = ?", (order, item_id))
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Pin order update failed: {e}")
                self.conn.rollback()
                return False

    def update_pin_orders(self, ordered_ids: list[int]) -> bool:
        """고정 항목 순서를 원자적으로 업데이트"""
        if not ordered_ids:
            return True
        if len(ordered_ids) != len(set(ordered_ids)):
            logger.error("Pin order update failed: duplicate ids")
            return False

        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("BEGIN")
                for order, item_id in enumerate(ordered_ids):
                    cursor.execute(
                        "UPDATE history SET pin_order = ? WHERE id = ? AND pinned = 1",
                        (order, item_id),
                    )
                    if cursor.rowcount != 1:
                        raise sqlite3.Error(f"Invalid pinned item id: {item_id}")
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Pin orders bulk update failed: {e}")
                self.conn.rollback()
                return False

    def toggle_pin(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT pinned FROM history WHERE id=?", (item_id,))
                current = cursor.fetchone()
                if current:
                    new_status = 0 if current[0] else 1
                    if new_status == 1:
                        # 새 고정 항목은 맨 아래에 추가 (최대 pin_order + 1)
                        cursor.execute("SELECT COALESCE(MAX(pin_order), -1) + 1 FROM history WHERE pinned = 1")
                        new_order = cursor.fetchone()[0]
                        cursor.execute("UPDATE history SET pinned = ?, pin_order = ? WHERE id = ?", 
                                       (new_status, new_order, item_id))
                    else:
                        # 고정 해제 시 pin_order 초기화
                        cursor.execute("UPDATE history SET pinned = ?, pin_order = 0 WHERE id = ?", 
                                       (new_status, item_id))
                    self.conn.commit()
                    return new_status
            except sqlite3.Error as e:
                logger.error(f"DB Pin Error: {e}")
                self.conn.rollback()
            return 0

    def increment_use_count(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE history SET use_count = use_count + 1 WHERE id = ?", (item_id,))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"DB Use Count Error: {e}")
                self.conn.rollback()

    def delete_item(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM history WHERE id = ?", (item_id,))
                self.conn.commit()
                logger.info(f"항목 삭제: {item_id}")
            except sqlite3.Error as e:
                logger.error(f"DB Delete Error: {e}")
                self.conn.rollback()

    def clear_all(self):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM history WHERE pinned = 0")
                self.conn.commit()
                logger.info("고정되지 않은 모든 항목 삭제")
            except sqlite3.Error as e:
                logger.error(f"DB Clear Error: {e}")
                self.conn.rollback()

    def get_content(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT content, image_data, type FROM history WHERE id=?", (item_id,))
                return cursor.fetchone()
            except sqlite3.Error as e:
                logger.error(f"DB Get Content Error: {e}")
                return None
    
    def get_all_text_content(self):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT content, timestamp FROM history WHERE type != 'IMAGE' ORDER BY id DESC")
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.error(f"DB Get All Text Error: {e}")
                return []

    def get_statistics(self):
        """통계 정보 반환"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                stats = {}
                cursor.execute("SELECT COUNT(*) FROM history")
                stats['total'] = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM history WHERE pinned = 1")
                stats['pinned'] = cursor.fetchone()[0]
                cursor.execute("SELECT type, COUNT(*) FROM history GROUP BY type")
                stats['by_type'] = dict(cursor.fetchall())
                return stats
            except sqlite3.Error as e:
                logger.error(f"DB Stats Error: {e}")
                return {'total': 0, 'pinned': 0, 'by_type': {}}

    # --- 스니펫 메서드 ---
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

    # --- 설정 메서드 ---
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

    def _get_max_history(self, fallback: int = DEFAULT_MAX_HISTORY) -> int:
        """Resolve max_history setting with safe bounds."""
        raw_value = self.get_setting("max_history", fallback)
        try:
            max_history = int(raw_value)
        except (TypeError, ValueError):
            max_history = fallback
        return min(max(max_history, 10), 500)

    def cleanup(self, max_history: int | None = None) -> None:
        """오래된 항목 정리 - 이미지 제한 및 전체 제한 적용."""
        with self.lock:
            try:
                cursor = self.conn.cursor()

                # v10.5: 이미지 항목 별도 제한 (최대 20개)
                max_image_history = 20
                cursor.execute("SELECT COUNT(*) FROM history WHERE type='IMAGE' AND pinned=0")
                img_count = cursor.fetchone()[0]
                if img_count > max_image_history:
                    diff = img_count - max_image_history
                    cursor.execute(
                        f"DELETE FROM history WHERE id IN (SELECT id FROM history WHERE type='IMAGE' AND pinned=0 ORDER BY id ASC LIMIT {diff})"
                    )
                    logger.info(f"오래된 이미지 {diff}개 정리됨")

                # 전체 히스토리 제한 (설정값 반영)
                effective_max_history = self._get_max_history() if max_history is None else max_history
                cursor.execute("SELECT COUNT(*) FROM history WHERE pinned = 0")
                result = cursor.fetchone()
                if not result:
                    self.conn.commit()
                    return

                count = result[0]
                if count > effective_max_history:
                    diff = count - effective_max_history
                    cursor.execute(
                        f"DELETE FROM history WHERE id IN (SELECT id FROM history WHERE pinned = 0 ORDER BY id ASC LIMIT {diff})"
                    )
                    self.conn.commit()
                    logger.info(f"오래된 항목 {diff}개 정리")
                else:
                    self.conn.commit()

                # v10.6: 주기적 VACUUM 실행 (50회 cleanup 마다)
                self.add_count += 1
                if self.add_count >= 50:
                    self.add_count = 0
                    self.conn.execute("VACUUM")
                    logger.info("Database VACUUM completed")
            except sqlite3.Error as e:
                logger.error(f"DB Cleanup Error: {e}")

    def backup_db(self, target_path: str | None = None, force: bool = False) -> bool:
        """WAL 안전 온라인 백업. target_path가 없으면 일일 자동 백업."""
        with self.lock:
            try:
                backup_dir = os.path.join(self.app_dir, "backups")
                os.makedirs(backup_dir, exist_ok=True)

                if target_path:
                    backup_file = target_path
                    os.makedirs(os.path.dirname(os.path.abspath(backup_file)) or ".", exist_ok=True)
                else:
                    today = datetime.datetime.now().strftime("%Y%m%d")
                    backup_file = os.path.join(backup_dir, f"clipboard_history_{today}.db")
                    if os.path.exists(backup_file) and not force:
                        return True

                dest_conn = sqlite3.connect(backup_file)
                try:
                    self.conn.backup(dest_conn)
                finally:
                    dest_conn.close()

                logger.info(f"Database backup created: {backup_file}")

                # 자동 백업만 7일 유지
                if not target_path:
                    backups = sorted(
                        [f for f in os.listdir(backup_dir) if f.startswith("clipboard_history_") and f.endswith(".db")]
                    )
                    if len(backups) > 7:
                        for old_backup in backups[:-7]:
                            try:
                                os.remove(os.path.join(backup_dir, old_backup))
                                logger.info(f"Old backup deleted: {old_backup}")
                            except OSError as cleanup_err:
                                logger.warning(f"Failed to delete old backup: {cleanup_err}")
                return True
            except Exception as e:
                logger.error(f"Backup Error: {e}")
                return False

    # --- 태그 관련 메서드 ---
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

    # --- Collections 메서드 ---
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
                self.conn.commit()
                return cursor.lastrowid
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
                    "SELECT id, content, type, timestamp, pinned, use_count, pin_order FROM history WHERE collection_id = ? ORDER BY pinned DESC, pin_order ASC, id DESC",
                    (collection_id,)
                )
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.error(f"Get Items by Collection Error: {e}")
                return []


    def get_items_by_tag(self, tag):
        with self.lock:
            try:
                normalized_tag = (tag or "").replace("，", ",").strip().strip(",")
                if not normalized_tag:
                    return []
                cursor = self.conn.cursor()
                cursor.execute(
                    """
                    SELECT id, content, type, timestamp, pinned, use_count, pin_order
                    FROM history
                    WHERE tags IS NOT NULL
                      AND tags != ''
                      AND instr(
                          ',' || REPLACE(REPLACE(REPLACE(tags, '，', ','), ', ', ','), ' ,', ',') || ',',
                          ',' || ? || ','
                      ) > 0
                    ORDER BY pinned DESC, pin_order ASC, id DESC
                    """,
                    (normalized_tag,),
                )
                return cursor.fetchall()
            except sqlite3.Error:
                return []

    # --- 통계 관련 메서드 ---
    def get_today_count(self):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                today = datetime.date.today().strftime("%Y-%m-%d")
                cursor.execute("SELECT COUNT(*) FROM history WHERE timestamp LIKE ?", (f"{today}%",))
                result = cursor.fetchone()
                return result[0] if result else 0
            except sqlite3.Error as e:
                logger.debug(f"Get today count error: {e}")
                return 0
    
    def get_top_items(self, limit=5):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT content, use_count FROM history WHERE type != 'IMAGE' AND use_count > 0 ORDER BY use_count DESC LIMIT ?", (limit,))
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.debug(f"Get top items error: {e}")
                return []

    # --- 복사 규칙 메서드 ---
    def get_copy_rules(self):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT id, name, pattern, action, replacement, enabled, priority FROM copy_rules ORDER BY priority DESC")
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.debug(f"Get copy rules error: {e}")
                return []
    
    def add_copy_rule(self, name, pattern, action, replacement=""):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("INSERT INTO copy_rules (name, pattern, action, replacement) VALUES (?, ?, ?, ?)", (name, pattern, action, replacement))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Rule Add Error: {e}")
                self.conn.rollback()
    
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
    
    # --- v8.0: 보안 보관함 메서드 ---
    def add_vault_item(self, encrypted_content, label):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("INSERT INTO secure_vault (encrypted_content, label, created_at) VALUES (?, ?, ?)",
                               (encrypted_content, label, created_at))
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Vault Add Error: {e}")
                return False
    
    def get_vault_items(self):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT id, encrypted_content, label, created_at FROM secure_vault ORDER BY id DESC")
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.error(f"Vault Get Error: {e}")
                return []
    
    def delete_vault_item(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM secure_vault WHERE id = ?", (item_id,))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Vault Delete Error: {e}")
    
    # --- v8.0: 클립보드 액션 메서드 ---
    def get_clipboard_actions(self):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT id, name, pattern, action_type, action_params, enabled, priority FROM clipboard_actions ORDER BY priority DESC")
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.error(f"Get Actions Error: {e}")
                return []
    
    def add_clipboard_action(self, name, pattern, action_type, action_params="{}"):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("INSERT INTO clipboard_actions (name, pattern, action_type, action_params) VALUES (?, ?, ?, ?)",
                               (name, pattern, action_type, action_params))
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Action Add Error: {e}")
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
    
    def move_to_collection(self, item_id, collection_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE history SET collection_id = ? WHERE id = ?", (collection_id, item_id))
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Move to Collection Error: {e}")
                self.conn.rollback()
                return False

    # --- v10.0: 북마크 메서드 ---
    def toggle_bookmark(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT bookmark FROM history WHERE id = ?", (item_id,))
                current = cursor.fetchone()
                if current:
                    new_status = 0 if current[0] else 1
                    cursor.execute("UPDATE history SET bookmark = ? WHERE id = ?", (new_status, item_id))
                    self.conn.commit()
                    return new_status
            except sqlite3.Error as e:
                logger.error(f"Toggle Bookmark Error: {e}")
                self.conn.rollback()
            return 0
    
    def get_bookmarked_items(self):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT id, content, type, timestamp, pinned, use_count, pin_order FROM history WHERE bookmark = 1 ORDER BY id DESC")
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.error(f"Get Bookmarked Error: {e}")
                return []

    # --- v10.0: 메모 메서드 ---
    def set_note(self, item_id, note):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE history SET note = ? WHERE id = ?", (note, item_id))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Set Note Error: {e}")
    
    def get_note(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT note FROM history WHERE id = ?", (item_id,))
                result = cursor.fetchone()
                return result[0] if result else ""
            except sqlite3.Error as e:
                logger.error(f"Get Note Error: {e}")
                return ""

    # --- v10.0: 휴지통 (실행취소) 메서드 ---
    def soft_delete(self, item_id):
        """항목을 휴지통으로 이동 (7일 후 영구 삭제)"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT content, image_data, type FROM history WHERE id = ?", (item_id,))
                item = cursor.fetchone()
                if item:
                    deleted_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    expires_at = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute("INSERT INTO deleted_history (original_id, content, image_data, type, deleted_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
                                   (item_id, item[0], item[1], item[2], deleted_at, expires_at))
                    cursor.execute("DELETE FROM history WHERE id = ?", (item_id,))
                    self.conn.commit()
                    return True
            except sqlite3.Error as e:
                logger.error(f"Soft Delete Error: {e}")
                self.conn.rollback()
            return False
    
    def restore_item(self, deleted_id):
        """휴지통에서 항목 복원"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT content, image_data, type FROM deleted_history WHERE id = ?", (deleted_id,))
                item = cursor.fetchone()
                if item:
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute("INSERT INTO history (content, image_data, type, timestamp) VALUES (?, ?, ?, ?)",
                                   (item[0], item[1], item[2], timestamp))
                    cursor.execute("DELETE FROM deleted_history WHERE id = ?", (deleted_id,))
                    self.conn.commit()
                    return True
            except sqlite3.Error as e:
                logger.error(f"Restore Item Error: {e}")
                self.conn.rollback()
            return False
    
    def get_deleted_items(self):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT id, content, type, deleted_at, expires_at FROM deleted_history ORDER BY deleted_at DESC")
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.error(f"Get Deleted Items Error: {e}")
                return []
    
    def empty_trash(self):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM deleted_history")
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Empty Trash Error: {e}")
                self.conn.rollback()
    
    def cleanup_expired_trash(self):
        """만료된 휴지통 항목 영구 삭제"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("DELETE FROM deleted_history WHERE expires_at < ?", (now,))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Cleanup Expired Trash Error: {e}")

    # --- v10.0: 임시 클립보드 메서드 ---
    def add_temp_item(self, content, image_data, type_tag, minutes=30):
        """임시 항목 추가 (N분 후 자동 만료)"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                expires_at = (datetime.datetime.now() + datetime.timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("INSERT INTO history (content, image_data, type, timestamp, expires_at) VALUES (?, ?, ?, ?, ?)",
                               (content, image_data, type_tag, timestamp, expires_at))
                self.conn.commit()
                return cursor.lastrowid
            except sqlite3.Error as e:
                logger.error(f"Add Temp Item Error: {e}")
                return None
    
    def cleanup_expired_items(self):
        """만료된 임시 항목 삭제"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("DELETE FROM history WHERE expires_at IS NOT NULL AND expires_at < ?", (now,))
                deleted = cursor.rowcount
                self.conn.commit()
                if deleted > 0:
                    logger.info(f"만료된 임시 항목 {deleted}개 삭제됨")
                return deleted
            except sqlite3.Error as e:
                logger.error(f"Cleanup Expired Items Error: {e}")
                return 0

    def close(self):
        if self.conn:
            self.conn.close()
            logger.info("DB 연결 종료")

