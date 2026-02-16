# Restored legacy runtime source
# Source: legacy/클립모드 매니저 (legacy).py
# Restored: 2026-02-13
# Purpose: refactor/signal tracing; optional runtime via SMARTCLIPBOARD_LEGACY_IMPL=src
"""
SmartClipboard Pro v10.6
고급 클립보드 매니저 - 확장 기능 버전

주요 기능:
- 클립보드 히스토리 자동 저장
- 암호화 보안 보관함
- 클립보드 액션 자동화
- 플로팅 미니 창
- 다양한 테마 지원
"""
import sys
import os
import sqlite3
import datetime
import re
import threading
import time
import webbrowser
import keyboard
import winreg
import logging
import json
import shutil
import base64
import uuid
import csv
import hashlib  # v10.1: 모듈 레벨 import로 이동 (성능 최적화)
from urllib.parse import quote  # v10.3: URL 인코딩용

from smartclipboard_core.search_query import parse_search_query
from smartclipboard_core.backup_zip import export_history_zip, import_history_zip

# 암호화 라이브러리 체크
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# 웹 스크래핑 라이브러리 체크 (URL 제목 가져오기용)
try:
    import requests
    from bs4 import BeautifulSoup
    HAS_WEB = True
except ImportError:
    HAS_WEB = False

# QR코드 라이브러리 체크
try:
    import qrcode
    from PIL import ImageQt
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QTableWidget, QTableWidgetItem, QPushButton, QTextEdit,
    QLabel, QHeaderView, QAbstractItemView, QMessageBox, QSplitter,
    QSystemTrayIcon, QMenu, QSizePolicy, QStyle, QStackedWidget,
    QFileDialog, QComboBox, QDialog, QFormLayout, QSpinBox,
    QCheckBox, QTabWidget, QGroupBox, QFrame, QInputDialog
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QByteArray, QBuffer,
    QSettings, QPropertyAnimation, QEasingCurve, QPoint, QEvent,
    QObject, QSignalBlocker, QRunnable, QThreadPool, pyqtSlot, QUrl, QMimeData
)
from PyQt6.QtGui import (
    QColor, QFont, QIcon, QAction, QPixmap, QImage,
    QPainter, QKeySequence, QShortcut, QLinearGradient, QBrush, QPen
)

# --- 경로 설정 (Windows 시작 시 CWD가 System32가 되는 문제 해결) ---
def get_app_directory():
    """실행 파일 위치 기반 앱 디렉토리 반환"""
    if getattr(sys, 'frozen', False):
        # PyInstaller로 패키징된 경우
        return os.path.dirname(sys.executable)
    else:
        # 개발 환경
        return os.path.dirname(os.path.abspath(__file__))

APP_DIR = get_app_directory()

# --- 로깅 설정 ---
from logging.handlers import RotatingFileHandler

LOG_FILE = os.path.join(APP_DIR, "clipboard_manager.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=1*1024*1024, backupCount=3, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- 설정 ---
DB_FILE = os.path.join(APP_DIR, "clipboard_history_v6.db")
MAX_HISTORY = 100 
HOTKEY = "ctrl+shift+v"
APP_NAME = "SmartClipboardPro"
ORG_NAME = "MySmartTools"
VERSION = "10.5"

# 기본 핫키 설정
DEFAULT_HOTKEYS = {
    "show_main": "ctrl+shift+v",
    "show_mini": "alt+v",
    "paste_last": "ctrl+shift+z",
}

# v10.0: 필터 태그 매핑 (성능 최적화)
FILTER_TAG_MAP = {
    "📝 텍스트": "TEXT",
    "🖼️ 이미지": "IMAGE",
    "🔗 링크": "LINK",
    "💻 코드": "CODE",
    "🎨 색상": "COLOR",
    "📁 파일": "FILE",
}

# v10.0: cleanup 호출 간격 (매번 아닌 N회마다)
CLEANUP_INTERVAL = 10

# v10.0: 클립보드 분석용 사전 컴파일된 정규식 (성능 최적화)
RE_URL = re.compile(r'^https?://')
RE_HEX_COLOR = re.compile(r'^#(?:[0-9a-fA-F]{3}){1,2}$')
RE_RGB_COLOR = re.compile(r'^rgb\s*\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)$', re.I)
RE_HSL_COLOR = re.compile(r'^hsl\s*\(\s*\d+\s*,\s*\d+%?\s*,\s*\d+%?\s*\)$', re.I)

# v10.0: 코드 감지 인디케이터 (상수화)
CODE_INDICATORS = frozenset(["def ", "class ", "function ", "const ", "let ", "var ", "{", "}", "=>", "import ", "from ", "#include", "public ", "private "])

# v10.1: 타입 아이콘 상수 (UI 렌더링 최적화)
TYPE_ICONS = {"TEXT": "📝", "LINK": "🔗", "IMAGE": "🖼️", "CODE": "💻", "COLOR": "🎨", "FILE": "📁"}

# v10.1: UI 텍스트 상수 (유지보수성 및 향후 다국어 지원 대비)
UI_TEXTS = {
    "empty_history": "📋 클립보드 히스토리가 비어있습니다\n\n텍스트나 이미지를 복사하면 자동으로 저장됩니다\n⌨️ Ctrl+Shift+V로 언제든 호출 가능",
    "search_no_results": "🔍 '{query}'에 대한 검색 결과가 없습니다",
    "tag_no_results": "🏷️ '{tag}' 태그를 가진 항목이 없습니다",
    "image_item": "[이미지 캡처됨]",
    "image_tooltip": "🖼️ 이미지 항목 - 더블클릭으로 미리보기",
}

# --- 테마 정의 ---
# v10.6: 새로운 색상 체계 - 더 세련되고 모던한 팔레트
THEMES = {
    "dark": {
        "name": "🌙 다크 모드",
        "background": "#0f0f14",
        "surface": "#1a1a24",
        "surface_variant": "#252532",
        "primary": "#6366f1",  # 인디고 퍼플
        "primary_variant": "#818cf8",
        "secondary": "#22d3ee",  # 시안
        "text": "#f1f5f9",
        "text_secondary": "#94a3b8",
        "border": "#334155",
        "success": "#34d399",
        "warning": "#fbbf24",
        "error": "#f87171",
        "gradient_start": "#6366f1",
        "gradient_end": "#a855f7",
        "glow": "rgba(99, 102, 241, 0.3)",
        # 호버 전용 색상
        "hover_bg": "#2d2d3d",
        "hover_text": "#ffffff",
        "selected_text": "#ffffff",
    },
    "light": {
        "name": "☀️ 라이트 모드",
        "background": "#f8fafc",
        "surface": "#ffffff",
        "surface_variant": "#f1f5f9",
        "primary": "#4f46e5",  # 딥 인디고
        "primary_variant": "#6366f1",
        "secondary": "#0891b2",  # 틸
        "text": "#0f172a",
        "text_secondary": "#475569",
        "border": "#cbd5e1",
        "success": "#10b981",
        "warning": "#f59e0b",
        "error": "#ef4444",
        "gradient_start": "#4f46e5",
        "gradient_end": "#7c3aed",
        "glow": "rgba(79, 70, 229, 0.15)",
        # 호버 전용 색상
        "hover_bg": "#eef2ff",
        "hover_text": "#1e1b4b",
        "selected_text": "#ffffff",
    },
    "ocean": {
        "name": "🌊 오션 모드",
        "background": "#0c1929",
        "surface": "#132337",
        "surface_variant": "#1c3347",
        "primary": "#0ea5e9",  # 스카이 블루
        "primary_variant": "#38bdf8",
        "secondary": "#f97316",  # 오렌지
        "text": "#e0f2fe",
        "text_secondary": "#7dd3fc",
        "border": "#1e4059",
        "success": "#34d399",
        "warning": "#fbbf24",
        "error": "#fb7185",
        "gradient_start": "#0ea5e9",
        "gradient_end": "#06b6d4",
        "glow": "rgba(14, 165, 233, 0.25)",
        # 호버 전용 색상
        "hover_bg": "#1e4059",
        "hover_text": "#ffffff",
        "selected_text": "#0c1929",
    },
    "purple": {
        "name": "💜 퍼플 모드",
        "background": "#0f0720",
        "surface": "#1a1030",
        "surface_variant": "#2a1a48",
        "primary": "#c084fc",  # 라벤더
        "primary_variant": "#e879f9",
        "secondary": "#fb7185",  # 로즈
        "text": "#f3e8ff",
        "text_secondary": "#d8b4fe",
        "border": "#3b2068",
        "success": "#34d399",
        "warning": "#fbbf24",
        "error": "#fb7185",
        "gradient_start": "#c084fc",
        "gradient_end": "#e879f9",
        "glow": "rgba(192, 132, 252, 0.3)",
        # 호버 전용 색상
        "hover_bg": "#3b2068",
        "hover_text": "#ffffff",
        "selected_text": "#ffffff",
    },
    "midnight": {
        "name": "🌌 미드나잇",
        "background": "#030712",
        "surface": "#0f172a",
        "surface_variant": "#1e293b",
        "primary": "#38bdf8",  # 네온 스카이
        "primary_variant": "#7dd3fc",
        "secondary": "#f472b6",  # 핫 핑크
        "text": "#f8fafc",
        "text_secondary": "#cbd5e1",
        "border": "#1e293b",
        "success": "#4ade80",
        "warning": "#facc15",
        "error": "#f87171",
        "gradient_start": "#38bdf8",
        "gradient_end": "#a78bfa",
        "glow": "rgba(56, 189, 248, 0.25)",
        # 호버 전용 색상
        "hover_bg": "#334155",
        "hover_text": "#ffffff",
        "selected_text": "#030712",
    }
}


# v9.0: 글래스모피즘 및 애니메이션 상수
GLASS_STYLES = {
    "dark": {"glass_bg": "rgba(22, 33, 62, 0.85)", "shadow": "rgba(0, 0, 0, 0.4)"},
    "light": {"glass_bg": "rgba(255, 255, 255, 0.9)", "shadow": "rgba(0, 0, 0, 0.1)"},
    "ocean": {"glass_bg": "rgba(21, 38, 66, 0.88)", "shadow": "rgba(0, 0, 0, 0.35)"},
    "purple": {"glass_bg": "rgba(28, 26, 41, 0.9)", "shadow": "rgba(0, 0, 0, 0.45)"},
    "midnight": {"glass_bg": "rgba(26, 26, 46, 0.92)", "shadow": "rgba(0, 0, 0, 0.5)"},
}

# 애니메이션 duration (ms)
ANIM_FAST = 150
ANIM_NORMAL = 250
ANIM_SLOW = 400


# --- 데이터베이스 클래스 ---
# v10.5: Worker Signals 클래스
class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)

class Worker(QRunnable):
    """비동기 작업 실행을 위한 Worker 클래스"""
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            import traceback
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()

class ClipboardDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        # v10.6: WAL 모드 활성화 (동시성 및 성능 향상)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        # Some operations call other DB methods; use a re-entrant lock to avoid deadlocks.
        self.lock = threading.RLock()
        self.add_count = 0  # v10.0: cleanup 최적화를 위한 카운터
        self.maintenance_count = 0  # low-cost periodic maintenance counter
        self._fts_recovery_attempted = False
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
            
            # v10.1+: 런타임 인덱스 보장 (멱등)
            self.ensure_runtime_indexes()
            
            self.conn.commit()
            logger.info("DB 테이블 초기화 완료 (v10.1)")

            # v11: unified full-text search (FTS5) index for fast search.
            self.ensure_search_index()
        except sqlite3.Error as e:
            logger.error(f"DB Init Error: {e}")
        except Exception as e:
            logger.error(f"DB Init Error (search index): {e}")

    def ensure_runtime_indexes(self):
        """Ensure query-critical indexes exist (idempotent)."""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_pinned ON history(pinned)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_type ON history(type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_timestamp ON history(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_bookmark ON history(bookmark)")
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_history_sort ON history(pinned DESC, pin_order ASC, id DESC)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_history_collection_sort ON history(collection_id, pinned DESC, pin_order ASC, id DESC)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_history_content_unpinned ON history(content) WHERE pinned = 0"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_history_file_path_unpinned ON history(file_path) "
                    "WHERE type='FILE' AND pinned=0"
                )
                self.conn.commit()
                return True
            except sqlite3.OperationalError as e:
                logger.debug(f"Index creation skipped: {e}")
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                return False

    def ensure_search_index(self):
        """Ensure FTS5 table + triggers exist and are populated.

        On first creation, we force a one-time backup to protect user data.
        """
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='history_fts'")
                exists = cursor.fetchone() is not None

                if not exists:
                    try:
                        self.backup_db(force=True)
                    except Exception:
                        logger.exception("FTS init: backup failed (continuing)")

                    cursor.execute(
                        "CREATE VIRTUAL TABLE IF NOT EXISTS history_fts "
                        "USING fts5(content, tags, note, url_title, tokenize='unicode61')"
                    )

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

                if not exists:
                    cursor.execute("DELETE FROM history_fts")
                    cursor.execute(
                        """
                        INSERT INTO history_fts(rowid, content, tags, note, url_title)
                        SELECT id, COALESCE(content, ''), COALESCE(tags, ''), COALESCE(note, ''), COALESCE(url_title, '')
                        FROM history
                        """
                    )

                self.conn.commit()
                return True
            except sqlite3.OperationalError as e:
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

    def maybe_recover_fts(self):
        """Try to recover missing/broken FTS index at most once per session."""
        if self._fts_recovery_attempted:
            return False
        self._fts_recovery_attempted = True
        try:
            ok = self.ensure_search_index()
            if ok:
                logger.info("FTS recovery succeeded")
            return ok
        except Exception:
            logger.exception("FTS recovery failed")
            return False

    @staticmethod
    def _tokenize_search_query(query: str):
        if not query:
            return []
        # Extract "word-like" unicode tokens; drops punctuation that can break MATCH syntax.
        return [t for t in re.findall(r"[\w]+", query, flags=re.UNICODE) if t]

    @classmethod
    def _build_fts_match(cls, query: str):
        tokens = cls._tokenize_search_query(query)
        if not tokens:
            return ""
        parts = []
        for t in tokens:
            parts.append(f"{t}*" if len(t) > 1 else t)
        return " ".join(parts)

    def search_items(self, query: str, type_filter: str = "전체", tag_filter=None, bookmarked: bool = False, collection_id=None, limit=None):
        """Unified search with FTS5 when available; falls back to LIKE safely."""
        q = (query or "").strip()
        normalized_tag = (tag_filter or "").replace("，", ",").strip().strip(",") if tag_filter else ""

        self._last_search_used_fts = False
        self._last_search_fallback = False
        self._last_search_error = None

        if not q:
            if normalized_tag:
                return self.get_items_by_tag(normalized_tag)
            if bookmarked or type_filter == "⭐ 북마크":
                return self.get_bookmarked_items()
            if collection_id is not None:
                return self.get_items_by_collection(collection_id)
            return self.get_items("", type_filter, limit=limit)

        match_expr = self._build_fts_match(q)
        has_fts = False
        if match_expr:
            with self.lock:
                try:
                    cursor = self.conn.cursor()
                    cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='history_fts'")
                    has_fts = cursor.fetchone() is not None
                except sqlite3.Error as e:
                    self._last_search_error = str(e)
            if not has_fts:
                self._last_search_fallback = True
                self._last_search_error = self._last_search_error or "history_fts missing"
                if self.maybe_recover_fts():
                    with self.lock:
                        try:
                            cursor = self.conn.cursor()
                            cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='history_fts'")
                            has_fts = cursor.fetchone() is not None
                        except sqlite3.Error as e:
                            self._last_search_error = str(e)

        if match_expr and has_fts:
            with self.lock:
                try:
                    cursor = self.conn.cursor()
                    sql = (
                        "SELECT h.id, h.content, h.type, h.timestamp, h.pinned, h.use_count, h.pin_order "
                        "FROM history h "
                        "JOIN history_fts ON history_fts.rowid = h.id "
                        "WHERE history_fts MATCH ?"
                    )
                    params = [match_expr]

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

                    if collection_id is not None:
                        sql += " AND h.collection_id = ?"
                        params.append(collection_id)

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
                    if "no such table" in str(e).lower():
                        self.maybe_recover_fts()

        with self.lock:
            cursor = self.conn.cursor()
            like = f"%{q}%"
            sql = (
                "SELECT id, content, type, timestamp, pinned, use_count, pin_order "
                "FROM history WHERE (content LIKE ? OR tags LIKE ? OR note LIKE ? OR url_title LIKE ?)"
            )
            params2 = [like, like, like, like]

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

            if collection_id is not None:
                sql += " AND collection_id = ?"
                params2.append(collection_id)

            sql += " ORDER BY pinned DESC, pin_order ASC, id DESC"
            if limit is not None:
                sql += " LIMIT ?"
                params2.append(int(limit))

            cursor.execute(sql, params2)
            return cursor.fetchall()

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

    def add_file_item(self, paths: list[str]) -> int | bool:
        """Add a FILE history item from local file paths.

        Stores:
          - content: newline-joined paths (search/display)
          - file_path: JSON list (structured retrieval)
        """
        paths = [p for p in (paths or []) if p]
        if not paths:
            return False

        file_path_json = json.dumps(paths, ensure_ascii=False)
        content = "\n".join(paths)

        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT id FROM history WHERE type = 'FILE' AND file_path = ? AND pinned = 0", (file_path_json,))
                existing = cursor.fetchone()
                if existing:
                    cursor.execute("DELETE FROM history WHERE id = ?", (existing[0],))

                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "INSERT INTO history (content, image_data, type, timestamp, file_path) VALUES (?, ?, ?, ?, ?)",
                    (content, None, "FILE", timestamp, file_path_json),
                )
                self.conn.commit()

                self.add_count += 1
                if self.add_count >= CLEANUP_INTERVAL:
                    self.cleanup()
                    self.add_count = 0
                return cursor.lastrowid
            except sqlite3.Error:
                logger.exception("DB Add FILE Error")
                self.conn.rollback()
                return False

    def get_file_paths(self, item_id: int) -> list[str]:
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT file_path FROM history WHERE id=?", (item_id,))
                row = cursor.fetchone()
                if not row or not row[0]:
                    return []
                raw = row[0]
                try:
                    data = json.loads(raw)
                    if isinstance(data, list):
                        return [str(x) for x in data if x]
                except Exception:
                    pass
                return [p for p in str(raw).splitlines() if p.strip()]
            except sqlite3.Error as e:
                logger.error(f"DB Get file paths Error: {e}")
                return []

    def update_item_content(
        self,
        item_id: int,
        content: str,
        type_tag: str | None = None,
        file_paths: list[str] | None = None,
    ) -> bool:
        """Update an existing item in-place (timestamp preserved)."""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                if file_paths is not None:
                    file_path_json = json.dumps([p for p in file_paths if p], ensure_ascii=False)
                    content = "\n".join([p for p in file_paths if p]) if type_tag == "FILE" else content
                    if type_tag is None:
                        cursor.execute("UPDATE history SET content = ?, file_path = ? WHERE id = ?", (content, file_path_json, item_id))
                    else:
                        cursor.execute(
                            "UPDATE history SET content = ?, type = ?, file_path = ? WHERE id = ?",
                            (content, type_tag, file_path_json, item_id),
                        )
                else:
                    if type_tag is None:
                        cursor.execute("UPDATE history SET content = ? WHERE id = ?", (content, item_id))
                    else:
                        cursor.execute("UPDATE history SET content = ?, type = ? WHERE id = ?", (content, type_tag, item_id))

                self.conn.commit()
                return True
            except sqlite3.Error:
                logger.exception("DB Update content Error")
                self.conn.rollback()
                return False

    def get_items(self, search_query: str = "", type_filter: str = "전체", limit: int | None = None) -> list:
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
                if limit is not None:
                    sql += " LIMIT ?"
                    params.append(int(limit))
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

    def cleanup(self):
        """오래된 항목 정리 - 이미지 제한 및 전체 제한 적용"""
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

                # 전체 히스토리 제한
                cursor.execute("SELECT COUNT(*) FROM history WHERE pinned = 0")
                result = cursor.fetchone()
                if not result:
                    self.conn.commit()
                    return

                count = result[0]
                if count > MAX_HISTORY:
                    diff = count - MAX_HISTORY
                    cursor.execute(
                        f"DELETE FROM history WHERE id IN (SELECT id FROM history WHERE pinned = 0 ORDER BY id ASC LIMIT {diff})"
                    )
                    self.conn.commit()
                    logger.info(f"오래된 항목 {diff}개 정리")
                else:
                    self.conn.commit()

                # Low-cost periodic maintenance instead of blocking VACUUM.
                self.maintenance_count += 1
                if self.maintenance_count >= 50:
                    self.maintenance_count = 0
                    try:
                        cursor.execute("PRAGMA optimize")
                    except sqlite3.Error as optimize_err:
                        logger.debug(f"PRAGMA optimize skipped: {optimize_err}")
            except sqlite3.Error as e:
                logger.error(f"DB Cleanup Error: {e}")

    def backup_db(self, target_path=None, force: bool = False):
        """WAL-safe online backup. If target_path is None, performs daily backup."""
        with self.lock:
            try:
                backup_dir = os.path.join(APP_DIR, "backups")
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

                if not target_path:
                    backups = sorted(
                        [f for f in os.listdir(backup_dir) if f.startswith("clipboard_history_") and f.endswith(".db")]
                    )
                    if len(backups) > 7:
                        for old_backup in backups[:-7]:
                            try:
                                os.remove(os.path.join(backup_dir, old_backup))
                                logger.info(f"Old backup deleted: {old_backup}")
                            except Exception as e:
                                logger.warning(f"Failed to delete old backup: {e}")
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

    def set_expires_at(self, item_id: int, expires_at: str | None) -> bool:
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE history SET expires_at = ? WHERE id = ?", (expires_at, item_id))
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Set expires_at Error: {e}")
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                return False

    def get_expires_at_map(self, item_ids: list[int]) -> dict[int, str]:
        ids = [int(x) for x in (item_ids or []) if x is not None]
        if not ids:
            return {}
        placeholders = ",".join(["?"] * len(ids))
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(f"SELECT id, expires_at FROM history WHERE id IN ({placeholders})", ids)
                out: dict[int, str] = {}
                for iid, exp in cursor.fetchall():
                    if exp:
                        out[int(iid)] = str(exp)
                return out
            except sqlite3.Error as e:
                logger.debug(f"Get expires_at map Error: {e}")
                return {}

    def set_bookmarks(self, item_ids: list[int], value: int) -> int:
        ids = [int(x) for x in (item_ids or []) if x is not None]
        if not ids:
            return 0
        placeholders = ",".join(["?"] * len(ids))
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(f"UPDATE history SET bookmark = ? WHERE id IN ({placeholders})", [int(value)] + ids)
                self.conn.commit()
                return cursor.rowcount or 0
            except sqlite3.Error as e:
                logger.error(f"Set bookmarks Error: {e}")
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                return 0

    def set_collection_many(self, item_ids: list[int], collection_id: int | None) -> int:
        ids = [int(x) for x in (item_ids or []) if x is not None]
        if not ids:
            return 0
        placeholders = ",".join(["?"] * len(ids))
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    f"UPDATE history SET collection_id = ? WHERE id IN ({placeholders})",
                    [collection_id] + ids,
                )
                self.conn.commit()
                return cursor.rowcount or 0
            except sqlite3.Error as e:
                logger.error(f"Set collection many Error: {e}")
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                return 0

    def close(self):
        if self.conn:
            self.conn.close()
            logger.info("DB 연결 종료")


# --- v8.0: 암호화 보관함 관리자 ---
class SecureVaultManager:
    """AES-256 암호화를 사용한 보안 보관함 관리자"""
    
    def __init__(self, db):
        self.db = db
        self.fernet = None
        self.is_unlocked = False
        self.last_activity = time.time()
        self.lock_timeout = 300  # 5분 자동 잠금
    
    def derive_key(self, password, salt):
        """비밀번호에서 암호화 키 생성"""
        if not HAS_CRYPTO:
            return None
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def set_master_password(self, password):
        """마스터 비밀번호 설정 (최초 설정)"""
        if not HAS_CRYPTO:
            return False
        salt = os.urandom(16)
        key = self.derive_key(password, salt)
        self.fernet = Fernet(key)
        # salt와 검증용 데이터 저장
        verification = self.fernet.encrypt(b"VAULT_VERIFIED")
        self.db.set_setting("vault_salt", base64.b64encode(salt).decode())
        self.db.set_setting("vault_verification", verification.decode())
        self.is_unlocked = True
        self.last_activity = time.time()
        return True
    
    def unlock(self, password):
        """보관함 잠금 해제 - v10.1: 예외 처리 개선"""
        if not HAS_CRYPTO:
            return False
        salt_b64 = self.db.get_setting("vault_salt")
        verification = self.db.get_setting("vault_verification")
        
        if not salt_b64 or not verification:
            return False
        
        try:
            salt = base64.b64decode(salt_b64)
            key = self.derive_key(password, salt)
            self.fernet = Fernet(key)
            # 검증
            decrypted = self.fernet.decrypt(verification.encode())
            if decrypted == b"VAULT_VERIFIED":
                self.is_unlocked = True
                self.last_activity = time.time()
                return True
        except (ValueError, TypeError) as e:
            # Base64 디코딩 오류 또는 타입 오류
            logger.debug(f"Vault unlock decode error: {e}")
        except Exception as e:
            # 암호화 관련 오류 (InvalidToken 등)
            logger.debug(f"Vault unlock crypto error: {e}")
            self.fernet = None  # 실패 시 fernet 초기화
        return False
    
    def lock(self):
        """보관함 잠금"""
        self.fernet = None
        self.is_unlocked = False
    
    def check_timeout(self):
        """자동 잠금 체크"""
        if self.is_unlocked and (time.time() - self.last_activity > self.lock_timeout):
            self.lock()
            return True
        return False
    
    def encrypt(self, text):
        """텍스트 암호화"""
        if not self.is_unlocked or not self.fernet:
            return None
        self.last_activity = time.time()
        return self.fernet.encrypt(text.encode())
    
    def decrypt(self, encrypted_data):
        """데이터 복호화"""
        if not self.is_unlocked or not self.fernet:
            return None
        self.last_activity = time.time()
        try:
            return self.fernet.decrypt(encrypted_data).decode()
        except Exception as e:
            logger.debug(f"Decrypt error: {e}")
            return None
    
    def has_master_password(self):
        """마스터 비밀번호가 설정되어 있는지 확인"""
        return self.db.get_setting("vault_salt") is not None


# --- v8.0: 클립보드 액션 자동화 관리자 ---
class ClipboardActionManager(QObject):  # v10.5: QObject 상속 (시그널 사용)
    """복사된 내용에 따라 자동 액션을 수행하는 관리자"""
    action_completed = pyqtSignal(str, object)  # v10.5: 액션 완료 시그널
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.actions_cache = []
        self.reload_actions()
        self.threadpool = QThreadPool.globalInstance()  # v10.5: 전역 스레드풀
    
    def reload_actions(self):
        """액션 규칙 캐시 갱신 - v10.6: 정규식 사전 컴파일 최적화"""
        raw_actions = self.db.get_clipboard_actions()
        self.actions_cache = []
        for action in raw_actions:
            aid, name, pattern, action_type, params_json, enabled, priority = action
            if not pattern: continue
            try:
                # 패턴 미리 컴파일
                compiled_pattern = re.compile(pattern)
                self.actions_cache.append({
                    "id": aid, "name": name, "pattern": pattern, 
                    "compiled": compiled_pattern,
                    "type": action_type, "params": params_json, 
                    "enabled": enabled, "priority": priority
                })
            except re.error as e:
                logger.warning(f"Invalid regex in action '{name}': {e}")
    
    def process(self, text, item_id=None):
        """텍스트에 매칭되는 액션 실행"""
        results = []
        for action in self.actions_cache:
            if not action["enabled"]:
                continue
            
            try:
                if action["compiled"].search(text):
                    params_json = action["params"]
                    params = json.loads(params_json) if params_json else {}
                    
                    action_type = action["type"]
                    name = action["name"]
                    aid = action["id"]
                    
                    # v10.5: fetch_url_title은 비동기로 처리
                    if action_type == "fetch_title":
                        self.fetch_url_title_async(text, item_id, name)
                        results.append((name, {"type": "notify", "message": "URL 제목 가져오는 중..."}))
                    else:
                        result = self.execute_action(action_type, text, params, item_id)
                        if result:
                            results.append((name, result))
            except Exception as e:
                logger.warning(f"Action processing error '{action['name']}': {e}")
            except re.error as e:
                logger.warning(f"Invalid regex in action '{name}': {e}")
        return results
    
    def execute_action(self, action_type, text, params, item_id):
        """동기 액션 실행"""
        if action_type == "fetch_title":
            return None  # 비동기로 별도 처리
        elif action_type == "format_phone":
            return self.format_phone(text)
        elif action_type == "format_email":
            return self.format_email(text)
        elif action_type == "notify":
            return {"type": "notify", "message": params.get("message", "패턴 매칭됨")}
        elif action_type == "transform":
            return self.transform_text(text, params.get("mode", "trim"))
        return None
    
    def fetch_url_title_async(self, url, item_id, action_name):
        """URL 제목 비동기 요청"""
        if not HAS_WEB:
            return
            
        worker = Worker(self._fetch_title_logic, url, item_id)
        worker.signals.result.connect(lambda res: self._handle_title_result(res, action_name))
        self.threadpool.start(worker)

    @staticmethod
    def _fetch_title_logic(url, item_id):
        """작업 스레드에서 실행될 로직"""
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(url, headers=headers, timeout=(3, 5), verify=True)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.string if soup.title else None
            return {"title": title.strip() if title else None, "item_id": item_id, "url": url}
        except Exception as e:
            logger.debug(f"Fetch title error: {e}")
            return {"title": None, "item_id": item_id, "error": str(e)}

    def _handle_title_result(self, result, action_name):
        """비동기 결과 처리 (메인 스레드)"""
        title = result.get("title")
        item_id = result.get("item_id")
        
        if title and item_id:
            # DB 캐시 업데이트
            self.db.update_url_title(item_id, title)
            # 메인 윈도우에 알림
            self.action_completed.emit(action_name, {"type": "title", "title": title})
    
    def fetch_url_title(self, url, item_id):
        return None

    
    def format_phone(self, text):
        """전화번호 포맷팅"""
        # 숫자만 추출
        digits = re.sub(r'\D', '', text)
        if len(digits) == 11 and digits.startswith('010'):
            formatted = f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
            return {"type": "format", "original": text, "formatted": formatted}
        elif len(digits) == 10:
            formatted = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
            return {"type": "format", "original": text, "formatted": formatted}
        return None
    
    def format_email(self, text):
        """이메일 정규화"""
        email = text.strip().lower()
        return {"type": "format", "original": text, "formatted": email}
    
    def transform_text(self, text, mode):
        """텍스트 변환"""
        if mode == "trim":
            return {"type": "transform", "result": text.strip()}
        elif mode == "upper":
            return {"type": "transform", "result": text.upper()}
        elif mode == "lower":
            return {"type": "transform", "result": text.lower()}
        return None


# --- v8.0: 내보내기/가져오기 관리자 ---
class ExportImportManager:
    """다양한 포맷으로 데이터 내보내기/가져오기"""
    
    def __init__(self, db):
        self.db = db
    
    def export_json(self, path, filter_type="all", date_from=None):
        """JSON으로 내보내기 - v10.3: date_from 필터링 구현"""
        try:
            items = self.db.get_items("", "전체")
            export_data = {
                "app": "SmartClipboard Pro",
                "version": VERSION,
                "exported_at": datetime.datetime.now().isoformat(),
                "items": []
            }
            for item in items:
                pid, content, ptype, timestamp, pinned, use_count, pin_order = item
                if filter_type != "all" and filter_type != ptype:
                    continue
                if ptype == "IMAGE":
                    continue  # 이미지는 JSON에서 제외
                # v10.3: 날짜 필터링 적용
                if date_from and timestamp:
                    try:
                        item_date = datetime.datetime.strptime(timestamp.split()[0], "%Y-%m-%d").date()
                        if item_date < date_from:
                            continue
                    except (ValueError, IndexError):
                        pass  # 날짜 파싱 실패 시 포함
                export_data["items"].append({
                    "content": content,
                    "type": ptype,
                    "timestamp": timestamp,
                    "pinned": bool(pinned),
                    "use_count": use_count
                })
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            return len(export_data["items"])
        except Exception as e:
            logger.error(f"JSON Export Error: {e}")
            return -1
    
    def export_csv(self, path, filter_type="all"):
        """CSV로 내보내기"""
        try:
            items = self.db.get_items("", "전체")
            with open(path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["내용", "유형", "시간", "고정", "사용횟수"])
                count = 0
                for item in items:
                    pid, content, ptype, timestamp, pinned, use_count, pin_order = item
                    if filter_type != "all" and filter_type != ptype:
                        continue
                    if ptype == "IMAGE":
                        continue
                    writer.writerow([content, ptype, timestamp, "예" if pinned else "아니오", use_count])
                    count += 1
            return count
        except Exception as e:
            logger.error(f"CSV Export Error: {e}")
            return -1
    
    def export_markdown(self, path, filter_type="all"):
        """Markdown으로 내보내기"""
        try:
            items = self.db.get_items("", "전체")
            with open(path, 'w', encoding='utf-8') as f:
                f.write(f"# SmartClipboard Pro 히스토리\n\n")
                f.write(f"내보낸 날짜: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("---\n\n")
                
                count = 0
                for item in items:
                    pid, content, ptype, timestamp, pinned, use_count, pin_order = item
                    if filter_type != "all" and filter_type != ptype:
                        continue
                    if ptype == "IMAGE":
                        continue
                    
                    pin_mark = "📌 " if pinned else ""
                    type_icon = TYPE_ICONS.get(ptype, "📝")  # v10.3: 상수 사용
                    
                    f.write(f"### {pin_mark}{type_icon} {timestamp}\n\n")
                    if ptype == "CODE":
                        f.write(f"```\n{content}\n```\n\n")
                    elif ptype == "LINK":
                        f.write(f"[{content}]({content})\n\n")
                    else:
                        f.write(f"{content}\n\n")
                    f.write("---\n\n")
                    count += 1
            return count
        except Exception as e:
            logger.error(f"Markdown Export Error: {e}")
            return -1
    
    def import_json(self, path):
        """JSON에서 가져오기 - v10.3: 타입 유효성 검증 추가"""
        VALID_TYPES = {"TEXT", "LINK", "IMAGE", "CODE", "COLOR"}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            imported = 0
            for item in data.get("items", []):
                content = item.get("content", "")
                ptype = item.get("type", "TEXT")
                # v10.3: 유효하지 않은 타입은 TEXT로 폴백
                if ptype not in VALID_TYPES:
                    ptype = "TEXT"
                if content:
                    self.db.add_item(content, None, ptype)
                    imported += 1
            return imported
        except Exception as e:
            logger.error(f"JSON Import Error: {e}")
            return -1
    
    def import_csv(self, path):
        """CSV에서 가져오기 - v10.3: 타입 유효성 검증 추가"""
        VALID_TYPES = {"TEXT", "LINK", "IMAGE", "CODE", "COLOR"}
        try:
            imported = 0
            with open(path, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                next(reader)  # 헤더 건너뛰기
                for row in reader:
                    if len(row) >= 2:
                        content, ptype = row[0], row[1]
                        # v10.3: 유효하지 않은 타입은 TEXT로 폴백
                        if ptype not in VALID_TYPES:
                            ptype = "TEXT"
                        if content:
                            self.db.add_item(content, None, ptype)
                            imported += 1
            return imported
        except Exception as e:
            logger.error(f"CSV Import Error: {e}")
            return -1

# --- (레거시 HotkeyListener 클래스 제거됨 - MainWindow.register_hotkeys()로 대체) ---


# --- 토스트 알림 ---
class ToastNotification(QFrame):
    """플로팅 토스트 알림 위젯 (슬라이드 애니메이션 + 스택 지원)"""
    _active_toasts = []  # 활성 토스트 목록
    
    def __init__(self, parent, message, duration=2000, toast_type="info"):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.duration = duration
        self.parent_window = parent
        
        # 타입별 색상
        colors = {
            "info": "#3b82f6",
            "success": "#22c55e", 
            "warning": "#f59e0b",
            "error": "#ef4444"
        }
        icons = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}
        
        color = colors.get(toast_type, colors["info"])
        icon = icons.get(toast_type, icons["info"])
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 10px;
            }}
            QLabel {{
                color: white;
                font-size: 13px;
                font-weight: bold;
                background: transparent;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 16px; background: transparent;")
        layout.addWidget(icon_label)
        
        msg_label = QLabel(message)
        msg_label.setStyleSheet("background: transparent;")
        layout.addWidget(msg_label)
        
        self.adjustSize()
        
        # 그림자 효과 추가
        from PyQt6.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)
        
        # 시작 위치 계산 (화면 오른쪽 바깥에서 시작)
        if parent:
            parent_rect = parent.geometry()
            self.target_x = parent_rect.right() - self.width() - 20
            stack_offset = len(ToastNotification._active_toasts) * (self.height() + 12)
            self.target_y = parent_rect.bottom() - self.height() - 50 - stack_offset
            # 시작점: 오른쪽 바깥
            self.move(parent_rect.right() + 10, self.target_y)
        
        # 활성 토스트 목록에 추가
        ToastNotification._active_toasts.append(self)
        
        # 슬라이드 인 애니메이션
        self.slide_in_animation = QPropertyAnimation(self, b"pos")
        self.slide_in_animation.setDuration(300)
        self.slide_in_animation.setStartValue(self.pos())
        self.slide_in_animation.setEndValue(QPoint(self.target_x, self.target_y))
        self.slide_in_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # 투명도 효과 설정
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(1.0)
        # Note: GraphicsEffect는 하나만 적용 가능하므로 그림자를 우선 적용
        
        # 자동 닫기 타이머
        QTimer.singleShot(duration, self.fade_out)
    
    def showEvent(self, event):
        super().showEvent(event)
        # 표시될 때 슬라이드 인 시작
        self.slide_in_animation.start()
    
    def fade_out(self):
        """페이드 아웃 후 닫기"""
        # 슬라이드 아웃 애니메이션
        self.slide_out_animation = QPropertyAnimation(self, b"pos")
        self.slide_out_animation.setDuration(200)
        self.slide_out_animation.setStartValue(self.pos())
        if self.parent_window:
            parent_rect = self.parent_window.geometry()
            self.slide_out_animation.setEndValue(QPoint(parent_rect.right() + 10, self.pos().y()))
        self.slide_out_animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self.slide_out_animation.finished.connect(self._cleanup)
        self.slide_out_animation.start()
    
    def _cleanup(self):
        """토스트 정리"""
        if self in ToastNotification._active_toasts:
            ToastNotification._active_toasts.remove(self)
        self.close()
        self.deleteLater()
    
    @staticmethod
    def show_toast(parent, message, duration=2000, toast_type="info"):
        toast = ToastNotification(parent, message, duration, toast_type)
        toast.show()
        return toast


# --- 설정 다이얼로그 ---
class SettingsDialog(QDialog):
    def __init__(self, parent, db, current_theme):
        super().__init__(parent)
        self.db = db
        self.current_theme = current_theme
        self.setWindowTitle("⚙️ 설정")
        self.setMinimumSize(450, 400)
        self.apply_dialog_theme()
        self.init_ui()
    
    def apply_dialog_theme(self):
        """다이얼로그에 테마 적용"""
        theme = THEMES.get(self.current_theme, THEMES["dark"])
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme["background"]};
                color: {theme["text"]};
            }}
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {theme["border"]};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
                color: {theme["primary"]};
            }}
            QComboBox, QSpinBox, QLineEdit {{
                background-color: {theme["surface_variant"]};
                border: 1px solid {theme["border"]};
                border-radius: 6px;
                padding: 6px;
                color: {theme["text"]};
            }}
            QLabel {{
                color: {theme["text"]};
            }}
            QPushButton {{
                background-color: {theme["surface_variant"]};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: {theme["text"]};
            }}
            QPushButton:hover {{
                background-color: {theme["primary"]};
                color: white;
            }}
            QTabWidget::pane {{
                border: 1px solid {theme["border"]};
                border-radius: 6px;
                background-color: {theme["surface"]};
            }}
            QTabBar::tab {{
                background-color: {theme["surface_variant"]};
                color: {theme["text_secondary"]};
                padding: 8px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
            QTabBar::tab:selected {{
                background-color: {theme["primary"]};
                color: white;
            }}
        """)

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        tabs = QTabWidget()
        
        # 일반 탭
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        
        # 테마 선택
        theme_group = QGroupBox("🎨 테마")
        theme_layout = QFormLayout(theme_group)
        self.theme_combo = QComboBox()
        for key, theme in THEMES.items():
            self.theme_combo.addItem(theme["name"], key)
        self.theme_combo.setCurrentIndex(list(THEMES.keys()).index(self.current_theme))
        theme_layout.addRow("테마 선택:", self.theme_combo)
        general_layout.addWidget(theme_group)
        
        # 히스토리 설정
        history_group = QGroupBox("📋 히스토리")
        history_layout = QFormLayout(history_group)
        self.max_history_spin = QSpinBox()
        self.max_history_spin.setRange(10, 500)
        self.max_history_spin.setValue(int(self.db.get_setting("max_history", MAX_HISTORY)))
        history_layout.addRow("최대 저장 개수:", self.max_history_spin)
        general_layout.addWidget(history_group)
        
        # 미니 창 설정
        mini_window_group = QGroupBox("🔲 미니 창")
        mini_window_layout = QFormLayout(mini_window_group)
        self.mini_window_enabled = QCheckBox("미니 클립보드 창 활성화")
        self.mini_window_enabled.setChecked(self.db.get_setting("mini_window_enabled", "true").lower() == "true")
        self.mini_window_enabled.setToolTip("비활성화하면 Alt+V 단축키로 미니 창이 열리지 않습니다.")
        mini_window_layout.addRow(self.mini_window_enabled)
        general_layout.addWidget(mini_window_group)
        
        # v8.1: 로깅 레벨 설정
        logging_group = QGroupBox("📝 로깅")
        logging_layout = QFormLayout(logging_group)
        self.log_level_combo = QComboBox()
        log_levels = [("DEBUG - 상세 디버깅", "DEBUG"), ("INFO - 일반 정보", "INFO"), 
                      ("WARNING - 경고만", "WARNING"), ("ERROR - 오류만", "ERROR")]
        for name, value in log_levels:
            self.log_level_combo.addItem(name, value)
        current_level = self.db.get_setting("log_level", "INFO")
        level_values = [v for _, v in log_levels]
        if current_level in level_values:
            self.log_level_combo.setCurrentIndex(level_values.index(current_level))
        logging_layout.addRow("로깅 레벨:", self.log_level_combo)
        general_layout.addWidget(logging_group)
        
        general_layout.addStretch()
        tabs.addTab(general_tab, "일반")
        
        # 단축키 탭
        shortcut_tab = QWidget()
        shortcut_layout = QVBoxLayout(shortcut_tab)
        shortcut_info = QLabel("""
<b>키보드 단축키</b><br><br>
<b>Ctrl+Shift+V</b> - 창 표시/숨기기<br>
<b>Ctrl+C</b> - 선택 항목 복사<br>
<b>Delete</b> - 선택 항목 삭제<br>
<b>Ctrl+P</b> - 고정/해제 토글<br>
<b>Enter</b> - 붙여넣기<br>
<b>Escape</b> - 창 숨기기<br>
<b>Ctrl+F</b> - 검색창 포커스<br>
<b>↑/↓</b> - 리스트 탐색
        """)
        shortcut_info.setWordWrap(True)
        shortcut_layout.addWidget(shortcut_info)
        shortcut_layout.addStretch()
        tabs.addTab(shortcut_tab, "단축키")
        
        layout.addWidget(tabs)
        
        # 버튼
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("저장")
        btn_save.clicked.connect(self.save_settings)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def save_settings(self):
        # 테마 설정 저장
        selected_theme = self.theme_combo.currentData()
        current_theme = self.current_theme
        
        self.db.set_setting("theme", selected_theme)
        self.db.set_setting("max_history", self.max_history_spin.value())
        
        # 미니 창 설정 저장 및 핫키 즉시 재등록
        mini_enabled = "true" if self.mini_window_enabled.isChecked() else "false"
        self.db.set_setting("mini_window_enabled", mini_enabled)
        # 핫키 재등록하여 설정 즉시 반영
        if self.parent() and hasattr(self.parent(), 'register_hotkeys'):
            self.parent().register_hotkeys()
        
        # v8.1: 로깅 레벨 저장 및 적용
        selected_log_level = self.log_level_combo.currentData()
        self.db.set_setting("log_level", selected_log_level)
        # 런타임에 로깅 레벨 변경
        log_level_map = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, 
                         "WARNING": logging.WARNING, "ERROR": logging.ERROR}
        if selected_log_level in log_level_map:
            logger.setLevel(log_level_map[selected_log_level])
            for handler in logger.handlers:
                handler.setLevel(log_level_map[selected_log_level])
        
        if selected_theme != current_theme:
            QMessageBox.information(self, "테마 변경", "설정한 테마가 적용되었습니다.")
            if self.parent():
                self.parent().change_theme(selected_theme)
        
        self.accept()

    def get_selected_theme(self):
        return self.theme_combo.currentData()


# --- v8.0: 보안 보관함 다이얼로그 ---
class SecureVaultDialog(QDialog):
    """암호화된 보안 보관함 UI"""
    
    def __init__(self, parent, db, vault_manager):
        super().__init__(parent)
        self.db = db
        self.vault = vault_manager
        self.parent_window = parent
        self.setWindowTitle("🔒 보안 보관함")
        self.setMinimumSize(500, 450)
        self.init_ui()
        
        if self.vault.is_unlocked:
            self.load_items()
        else:
            self.show_lock_ui()
    
    def init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(12)
        
        # 상태 표시
        self.status_label = QLabel("🔒 보관함이 잠겨 있습니다")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.layout.addWidget(self.status_label)
        
        # 비밀번호 입력
        self.password_widget = QWidget()
        pw_layout = QVBoxLayout(self.password_widget)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("마스터 비밀번호 입력...")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self.unlock_vault)
        pw_layout.addWidget(self.password_input)
        
        btn_unlock = QPushButton("🔓 잠금 해제")
        btn_unlock.clicked.connect(self.unlock_vault)
        pw_layout.addWidget(btn_unlock)
        
        self.layout.addWidget(self.password_widget)
        
        # 항목 목록 (처음에는 숨김)
        self.items_widget = QWidget()
        items_layout = QVBoxLayout(self.items_widget)
        items_layout.setContentsMargins(0, 0, 0, 0)
        
        # 툴바
        toolbar = QHBoxLayout()
        btn_add = QPushButton("➕ 새 항목")
        btn_add.clicked.connect(self.add_item)
        btn_lock = QPushButton("🔒 잠금")
        btn_lock.clicked.connect(self.lock_vault)
        toolbar.addWidget(btn_add)
        toolbar.addStretch()
        toolbar.addWidget(btn_lock)
        items_layout.addLayout(toolbar)
        
        # 테이블
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["레이블", "생성일", "동작"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 100)
        self.table.verticalHeader().setVisible(False)
        items_layout.addWidget(self.table)
        
        self.items_widget.setVisible(False)
        self.layout.addWidget(self.items_widget)
        
        # 닫기 버튼
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.close)
        self.layout.addWidget(btn_close)
    
    def show_lock_ui(self):
        """잠금 상태 UI 표시"""
        self.status_label.setText("🔒 보관함이 잠겨 있습니다")
        self.password_widget.setVisible(True)
        self.items_widget.setVisible(False)
        
        if not self.vault.has_master_password():
            self.status_label.setText("🔐 마스터 비밀번호를 설정해주세요 (최초 설정)")
    
    def unlock_vault(self):
        """보관함 잠금 해제"""
        password = self.password_input.text()
        if not password:
            QMessageBox.warning(self, "경고", "비밀번호를 입력하세요.")
            return
        
        if not self.vault.has_master_password():
            # 최초 설정 - v10.2: 비밀번호 강도 검증 강화
            is_valid, error_msg = self.validate_password_strength(password)
            if not is_valid:
                QMessageBox.warning(self, "비밀번호 강도 부족", error_msg)
                return
            if self.vault.set_master_password(password):
                QMessageBox.information(self, "설정 완료", "마스터 비밀번호가 설정되었습니다.")
                self.load_items()
            else:
                QMessageBox.critical(self, "오류", "암호화 라이브러리가 없습니다.\npip install cryptography")
        else:
            if self.vault.unlock(password):
                self.load_items()
            else:
                QMessageBox.warning(self, "실패", "비밀번호가 일치하지 않습니다.")
        
        self.password_input.clear()
    
    def lock_vault(self):
        """보관함 잠금"""
        self.vault.lock()
        self.show_lock_ui()
    
    def load_items(self):
        """항목 로드"""
        self.status_label.setText("🔓 보관함이 열려 있습니다")
        self.password_widget.setVisible(False)
        self.items_widget.setVisible(True)
        
        items = self.db.get_vault_items()
        self.table.setRowCount(0)
        
        for row_idx, (vid, encrypted, label, created_at) in enumerate(items):
            self.table.insertRow(row_idx)
            
            label_item = QTableWidgetItem(label or "[레이블 없음]")
            label_item.setData(Qt.ItemDataRole.UserRole, vid)
            self.table.setItem(row_idx, 0, label_item)
            
            self.table.setItem(row_idx, 1, QTableWidgetItem(created_at[:10] if created_at else ""))
            
            # 동작 버튼
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(2, 2, 2, 2)
            
            btn_copy = QPushButton("📋")
            btn_copy.setToolTip("복호화하여 복사")
            btn_copy.clicked.connect(lambda checked, v=vid, e=encrypted: self.copy_item(v, e))
            btn_delete = QPushButton("🗑")
            btn_delete.setToolTip("삭제")
            btn_delete.clicked.connect(lambda checked, v=vid: self.delete_item(v))
            
            btn_layout.addWidget(btn_copy)
            btn_layout.addWidget(btn_delete)
            self.table.setCellWidget(row_idx, 2, btn_widget)
    
    def add_item(self):
        """새 항목 추가"""
        label, ok1 = QInputDialog.getText(self, "새 항목", "레이블 (선택사항):")
        if not ok1:
            return
        content, ok2 = QInputDialog.getMultiLineText(self, "새 항목", "저장할 내용:")
        if ok2 and content:
            encrypted = self.vault.encrypt(content)
            if encrypted:
                self.db.add_vault_item(encrypted, label)
                self.load_items()
            else:
                QMessageBox.warning(self, "오류", "암호화에 실패했습니다.")
    
    def copy_item(self, vid, encrypted_data):
        """항목 복호화 후 복사"""
        decrypted = self.vault.decrypt(encrypted_data)
        if decrypted:
            clipboard = QApplication.clipboard()
            clipboard.setText(decrypted)
            if self.parent_window:
                self.parent_window.statusBar().showMessage("✅ 복호화된 내용이 클립보드에 복사되었습니다.", 3000)
        else:
            QMessageBox.warning(self, "오류", "복호화에 실패했습니다. 보관함을 다시 열어주세요.")
    
    def delete_item(self, vid):
        """항목 삭제"""
        reply = QMessageBox.question(self, "삭제 확인", "이 항목을 삭제하시겠습니까?",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_vault_item(vid)
            self.load_items()
    
    def validate_password_strength(self, password):
        """v10.2: 비밀번호 강도 검증"""
        if len(password) < 8:
            return False, "비밀번호는 최소 8자 이상이어야 합니다."
        if not any(c.isdigit() for c in password):
            return False, "비밀번호에 숫자가 포함되어야 합니다."
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            return False, "비밀번호에 특수문자가 포함되어야 합니다."
        return True, ""


# --- v8.0: 클립보드 액션 다이얼로그 ---
class ClipboardActionsDialog(QDialog):
    """클립보드 액션 자동화 규칙 관리"""
    
    def __init__(self, parent, db, action_manager):
        super().__init__(parent)
        self.db = db
        self.action_manager = action_manager
        self.setWindowTitle("⚡ 클립보드 액션 자동화")
        self.setMinimumSize(600, 450)
        self.init_ui()
        self.load_actions()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # 설명
        info = QLabel("복사된 내용이 패턴과 일치하면 자동으로 액션을 실행합니다.")
        info.setStyleSheet("color: gray;")
        layout.addWidget(info)
        
        # 상단 버튼
        btn_layout = QHBoxLayout()
        btn_add = QPushButton("➕ 액션 추가")
        btn_add.clicked.connect(self.add_action)
        btn_layout.addWidget(btn_add)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 테이블
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["활성", "이름", "패턴", "액션", "삭제"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 60)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)
        
        # 기본 액션 추가 버튼
        default_layout = QHBoxLayout()
        btn_defaults = QPushButton("📋 기본 액션 추가")
        btn_defaults.clicked.connect(self.add_default_actions)
        default_layout.addWidget(btn_defaults)
        default_layout.addStretch()
        layout.addLayout(default_layout)
        
        # 닫기 버튼
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
    
    def load_actions(self):
        """액션 목록 로드"""
        actions = self.db.get_clipboard_actions()
        self.table.setRowCount(0)
        
        action_type_names = {
            "fetch_title": "🔗 제목 가져오기",
            "format_phone": "📞 전화번호 포맷",
            "format_email": "📧 이메일 정규화",
            "notify": "🔔 알림",
            "transform": "✍️ 텍스트 변환"
        }
        
        for row_idx, (aid, name, pattern, action_type, params, enabled, priority) in enumerate(actions):
            self.table.insertRow(row_idx)
            
            # 활성화 체크박스
            cb = QCheckBox()
            cb.setChecked(enabled == 1)
            cb.stateChanged.connect(lambda state, a=aid: self.toggle_action(a, state))
            cb_widget = QWidget()
            cb_layout = QHBoxLayout(cb_widget)
            cb_layout.addWidget(cb)
            cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row_idx, 0, cb_widget)
            
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, aid)
            self.table.setItem(row_idx, 1, name_item)
            
            self.table.setItem(row_idx, 2, QTableWidgetItem(pattern))
            self.table.setItem(row_idx, 3, QTableWidgetItem(action_type_names.get(action_type, action_type)))
            
            # 삭제 버튼
            btn_del = QPushButton("🗑")
            btn_del.clicked.connect(lambda checked, a=aid: self.delete_action(a))
            self.table.setCellWidget(row_idx, 4, btn_del)
    
    def add_action(self):
        """새 액션 추가 - v10.2: 정규식 패턴 유효성 검증 추가"""
        name, ok = QInputDialog.getText(self, "액션 추가", "액션 이름:")
        if not ok or not name.strip():
            return
        
        pattern, ok = QInputDialog.getText(self, "액션 추가", "패턴 (정규식):", text="https?://")
        if not ok or not pattern.strip():
            return
        
        # v10.2: 정규식 패턴 유효성 검증
        try:
            re.compile(pattern)
        except re.error as e:
            QMessageBox.warning(self, "패턴 오류", f"잘못된 정규식 패턴입니다:\n{e}")
            return
        
        action_types = ["fetch_title", "format_phone", "format_email", "notify", "transform"]
        action_labels = ["🔗 URL 제목 가져오기", "📞 전화번호 포맷팅", "📧 이메일 정규화", "🔔 알림 표시", "✍️ 텍스트 변환"]
        action, ok = QInputDialog.getItem(self, "액션 추가", "액션 유형:", action_labels, 0, False)
        
        if ok:
            idx = action_labels.index(action)
            self.db.add_clipboard_action(name.strip(), pattern.strip(), action_types[idx])
            self.action_manager.reload_actions()
            self.load_actions()
    
    def toggle_action(self, action_id, state):
        """액션 활성화/비활성화"""
        self.db.toggle_clipboard_action(action_id, 1 if state else 0)
        self.action_manager.reload_actions()
    
    def delete_action(self, action_id):
        """액션 삭제"""
        self.db.delete_clipboard_action(action_id)
        self.action_manager.reload_actions()
        self.load_actions()
    
    def add_default_actions(self):
        """기본 액션 추가"""
        defaults = [
            ("URL 제목 가져오기", r"https?://", "fetch_title"),
            ("전화번호 자동 포맷", r"^0\d{9,10}$", "format_phone"),
        ]
        for name, pattern, action_type in defaults:
            self.db.add_clipboard_action(name, pattern, action_type)
        self.action_manager.reload_actions()
        self.load_actions()
        QMessageBox.information(self, "완료", "기본 액션이 추가되었습니다.")


# --- v8.0: 내보내기 다이얼로그 ---
class ExportDialog(QDialog):
    """고급 내보내기 다이얼로그"""
    
    def __init__(self, parent, export_manager):
        super().__init__(parent)
        self.export_manager = export_manager
        self.setWindowTitle("📤 고급 내보내기")
        self.setMinimumSize(400, 300)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 포맷 선택
        format_group = QGroupBox("📁 내보내기 포맷")
        format_layout = QVBoxLayout(format_group)
        self.format_json = QCheckBox("JSON (.json) - 전체 데이터")
        self.format_csv = QCheckBox("CSV (.csv) - 엑셀 호환")
        self.format_md = QCheckBox("Markdown (.md) - 문서용")
        self.format_zip = QCheckBox("전체 백업 ZIP (.zip) - 이미지+메타 포함")
        self.format_json.setChecked(True)
        format_layout.addWidget(self.format_json)
        format_layout.addWidget(self.format_csv)
        format_layout.addWidget(self.format_md)
        format_layout.addWidget(self.format_zip)
        layout.addWidget(format_group)
        
        # 필터
        filter_group = QGroupBox("🔍 필터")
        filter_layout = QFormLayout(filter_group)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["전체", "텍스트만", "링크만", "코드만"])
        filter_layout.addRow("유형:", self.type_combo)
        layout.addWidget(filter_group)
        
        # 버튼
        btn_layout = QHBoxLayout()
        btn_export = QPushButton("📤 내보내기")
        btn_export.clicked.connect(self.do_export)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_export)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
    
    def do_export(self):
        """내보내기 실행"""
        type_map = {"전체": "all", "텍스트만": "TEXT", "링크만": "LINK", "코드만": "CODE"}
        filter_type = type_map.get(self.type_combo.currentText(), "all")
        
        exported_count = 0
        
        if self.format_json.isChecked():
            path, _ = QFileDialog.getSaveFileName(self, "JSON 저장", f"clipboard_export_{datetime.date.today()}.json", "JSON Files (*.json)")
            if path:
                count = self.export_manager.export_json(path, filter_type)
                if count >= 0:
                    exported_count += count
        
        if self.format_csv.isChecked():
            path, _ = QFileDialog.getSaveFileName(self, "CSV 저장", f"clipboard_export_{datetime.date.today()}.csv", "CSV Files (*.csv)")
            if path:
                count = self.export_manager.export_csv(path, filter_type)
                if count >= 0:
                    exported_count += count
        
        if self.format_md.isChecked():
            path, _ = QFileDialog.getSaveFileName(self, "Markdown 저장", f"clipboard_export_{datetime.date.today()}.md", "Markdown Files (*.md)")
            if path:
                count = self.export_manager.export_markdown(path, filter_type)
                if count >= 0:
                    exported_count += count

        if self.format_zip.isChecked():
            path, _ = QFileDialog.getSaveFileName(self, "전체 백업 ZIP 저장", f"clipboard_backup_{datetime.date.today()}.zip", "Zip Files (*.zip)")
            if path:
                try:
                    count = export_history_zip(self.export_manager.db, path)
                    if count >= 0:
                        exported_count += count
                except Exception as e:
                    logger.error(f"ZIP Export Error: {e}")

        if exported_count > 0:
            QMessageBox.information(self, "완료", f"✅ 내보내기가 완료되었습니다.")
            self.accept()


# --- v8.0: 가져오기 다이얼로그 ---
class ImportDialog(QDialog):
    """가져오기 다이얼로그"""
    
    def __init__(self, parent, export_manager):
        super().__init__(parent)
        self.export_manager = export_manager
        self.setWindowTitle("📥 가져오기")
        self.setMinimumSize(400, 200)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        info = QLabel("JSON 또는 CSV 파일에서 클립보드 히스토리를 가져옵니다.")
        layout.addWidget(info)
        
        # 파일 선택
        file_layout = QHBoxLayout()
        self.file_path = QLineEdit()
        self.file_path.setPlaceholderText("파일을 선택하세요...")
        self.file_path.setReadOnly(True)
        btn_browse = QPushButton("📂 찾아보기")
        btn_browse.clicked.connect(self.browse_file)
        file_layout.addWidget(self.file_path)
        file_layout.addWidget(btn_browse)
        layout.addLayout(file_layout)
        
        # 버튼
        btn_layout = QHBoxLayout()
        btn_import = QPushButton("📥 가져오기")
        btn_import.clicked.connect(self.do_import)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_import)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
    
    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "파일 선택",
            "",
            "지원 파일 (*.json *.csv *.zip);;JSON (*.json);;CSV (*.csv);;Zip (*.zip)",
        )
        if path:
            self.file_path.setText(path)
    
    def do_import(self):
        path = self.file_path.text()
        if not path:
            QMessageBox.warning(self, "경고", "파일을 선택하세요.")
            return
        
        if path.lower().endswith('.json'):
            count = self.export_manager.import_json(path)
        elif path.lower().endswith('.csv'):
            count = self.export_manager.import_csv(path)
        elif path.lower().endswith('.zip'):
            try:
                count = import_history_zip(self.export_manager.db, path, conflict="skip")
            except Exception as e:
                logger.error(f"ZIP Import Error: {e}")
                count = -1
        else:
            QMessageBox.warning(self, "경고", "지원하지 않는 파일 형식입니다.")
            return
        
        if count >= 0:
            QMessageBox.information(self, "완료", f"✅ {count}개 항목을 가져왔습니다.")
            self.accept()
        else:
            QMessageBox.critical(self, "오류", "가져오기에 실패했습니다.")


# --- v10.2: 휴지통 다이얼로그 ---
class TrashDialog(QDialog):
    """휴지통 관리 다이얼로그 - 삭제된 항목 복원/영구 삭제"""
    
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.parent_window = parent
        self.current_theme = parent.current_theme if hasattr(parent, 'current_theme') else 'dark'
        self.setWindowTitle("🗑️ 휴지통")
        self.setMinimumSize(550, 400)
        self.apply_dialog_theme()  # v10.2: 테마 적용
        self.init_ui()
        self.load_items()
    
    def apply_dialog_theme(self):
        """v10.2: 다이얼로그에 테마 적용"""
        theme = THEMES.get(self.current_theme, THEMES["dark"])
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme["background"]};
                color: {theme["text"]};
            }}
            QTableWidget {{
                background-color: {theme["surface"]};
                border: 1px solid {theme["border"]};
                border-radius: 8px;
                color: {theme["text"]};
            }}
            QTableWidget::item {{
                padding: 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {theme["primary"]};
            }}
            QHeaderView::section {{
                background-color: {theme["surface_variant"]};
                color: {theme["text"]};
                padding: 10px;
                border: none;
            }}
            QLabel {{
                color: {theme["text_secondary"]};
            }}
            QPushButton {{
                background-color: {theme["surface_variant"]};
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                color: {theme["text"]};
            }}
            QPushButton:hover {{
                background-color: {theme["primary"]};
                color: white;
            }}
        """)
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # 정보 라벨
        info = QLabel("삭제된 항목은 7일 후 자동으로 영구 삭제됩니다.")
        info.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(info)
        
        # 테이블
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["내용", "유형", "삭제일", "만료일"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 70)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 90)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)
        
        # 버튼
        btn_layout = QHBoxLayout()
        btn_restore = QPushButton("♻️ 복원")
        btn_restore.clicked.connect(self.restore_selected)
        btn_empty = QPushButton("🗑️ 휴지통 비우기")
        btn_empty.setStyleSheet("color: #ef4444;")
        btn_empty.clicked.connect(self.empty_trash)
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.close)
        
        btn_layout.addWidget(btn_restore)
        btn_layout.addWidget(btn_empty)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)
    
    def load_items(self):
        """휴지통 항목 로드"""
        items = self.db.get_deleted_items()
        self.table.setRowCount(len(items))
        
        TYPE_ICONS = {"TEXT": "📝", "LINK": "🔗", "IMAGE": "🖼️", "CODE": "💻", "COLOR": "🎨"}
        
        for row, (did, content, dtype, deleted_at, expires_at) in enumerate(items):
            display = (content or "[이미지]")[:50].replace('\n', ' ')
            if len(content or "") > 50:
                display += "..."
            
            content_item = QTableWidgetItem(display)
            content_item.setData(Qt.ItemDataRole.UserRole, did)
            content_item.setToolTip(content[:200] if content else "이미지 항목")
            self.table.setItem(row, 0, content_item)
            
            type_item = QTableWidgetItem(TYPE_ICONS.get(dtype, "📝"))
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, type_item)
            
            self.table.setItem(row, 2, QTableWidgetItem(deleted_at[:10] if deleted_at else ""))
            self.table.setItem(row, 3, QTableWidgetItem(expires_at[:10] if expires_at else ""))
        
        if not items:
            self.table.setRowCount(1)
            empty_item = QTableWidgetItem("🎉 휴지통이 비어 있습니다")
            empty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_item.setFlags(empty_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(0, 0, empty_item)
            self.table.setSpan(0, 0, 1, 4)
    
    def restore_selected(self):
        """선택된 항목 복원 - v10.2: 다중 선택 지원"""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "알림", "복원할 항목을 선택하세요.")
            return
        
        # v10.2: 모든 선택된 항목 복원
        restored_count = 0
        for row in rows:
            did = self.table.item(row.row(), 0).data(Qt.ItemDataRole.UserRole)
            if did and self.db.restore_item(did):
                restored_count += 1
        
        if restored_count > 0:
            self.load_items()
            if self.parent_window:
                self.parent_window.load_data()
                self.parent_window.statusBar().showMessage(f"♻️ {restored_count}개 항목이 복원되었습니다.", 2000)
    
    def empty_trash(self):
        """휴지통 비우기"""
        reply = QMessageBox.question(
            self, "휴지통 비우기",
            "휴지통의 모든 항목을 영구 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.empty_trash()
            self.load_items()
            if self.parent_window:
                self.parent_window.statusBar().showMessage("🗑️ 휴지통이 비워졌습니다.", 2000)


# --- v8.0: 플로팅 미니 창 ---
class FloatingMiniWindow(QWidget):
    """빠른 접근을 위한 플로팅 미니 창"""
    
    item_selected = pyqtSignal(int)  # 항목 선택 시그널
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.parent_window = parent
        self.setWindowTitle("📋 빠른 클립보드")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(280, 350)
        self.resize(300, 400)
        
        self.drag_pos = None
        self.init_ui()
    
    def init_ui(self):
        # v10.6: 메인 컨테이너 - 인스턴스 변수로 저장하여 테마 변경 시 업데이트 가능
        self.container = QFrame(self)
        self.container.setObjectName("MiniContainer")
        self.apply_mini_theme()  # 테마 적용
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # 헤더
        header = QHBoxLayout()
        self.title_label = QLabel("📋 빠른 클립보드")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(28, 28)
        self.btn_close.clicked.connect(self.hide)
        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(self.btn_close)
        layout.addLayout(header)
        
        # 리스트
        from PyQt6.QtWidgets import QListWidget, QListWidgetItem
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.list_widget)
        
        # 버튼
        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄")
        self.btn_refresh.setToolTip("새로고침")
        self.btn_refresh.clicked.connect(self.load_items)
        self.btn_main = QPushButton("📋 메인 창")
        self.btn_main.clicked.connect(self.open_main_window)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_main)
        layout.addLayout(btn_layout)
        
        # 메인 레이아웃
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)
    
    def apply_mini_theme(self):
        """v10.6: 부모 윈도우의 테마와 연동하여 스타일 적용"""
        # 부모에서 현재 테마 가져오기
        if self.parent_window and hasattr(self.parent_window, 'current_theme'):
            theme_name = self.parent_window.current_theme
        else:
            theme_name = "dark"
        
        theme = THEMES.get(theme_name, THEMES["dark"])
        glass = GLASS_STYLES.get(theme_name, GLASS_STYLES["dark"])
        
        self.container.setStyleSheet(f"""
            QFrame#MiniContainer {{
                background-color: {glass["glass_bg"]};
                border-radius: 14px;
                border: 1px solid {theme["border"]};
            }}
            QLabel {{ 
                color: {theme["text"]}; 
                background: transparent;
            }}
            QListWidget {{
                background-color: transparent;
                border: none;
                color: {theme["text"]};
                font-size: 13px;
            }}
            QListWidget::item {{
                padding: 10px 12px;
                border-radius: 8px;
                margin: 2px 4px;
            }}
            QListWidget::item:hover {{
                background-color: {theme["hover_bg"]};
                color: {theme["hover_text"]};
            }}
            QListWidget::item:selected {{
                background-color: {theme["primary"]};
                color: {theme["selected_text"]};
            }}
            QPushButton {{
                background-color: {theme["surface_variant"]};
                border: 1px solid {theme["border"]};
                border-radius: 8px;
                padding: 8px 14px;
                color: {theme["text"]};
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {theme["primary"]};
                border-color: {theme["primary"]};
                color: white;
            }}
        """)
    
    def load_items(self):
        """최근 10개 항목 로드"""
        from PyQt6.QtWidgets import QListWidgetItem
        self.list_widget.clear()
        
        try:
            items = self.db.get_items("", "전체")[:10]
        except Exception as e:
            logger.error(f"Mini window load error: {e}")
            items = []
        
        if not items:
            # 빈 목록 안내
            empty_item = QListWidgetItem("📭 클립보드 히스토리가 비어 있습니다")
            empty_item.setData(Qt.ItemDataRole.UserRole, None)
            self.list_widget.addItem(empty_item)
            return
        
        
        for pid, content, ptype, timestamp, pinned, use_count, pin_order in items:
            icon = TYPE_ICONS.get(ptype, "📝")  # v10.3: 상수 사용
            pin_mark = "📌 " if pinned else ""
            display = content.replace('\n', ' ')[:35] + ("..." if len(content) > 35 else "")
            
            item = QListWidgetItem(f"{pin_mark}{icon} {display}")
            item.setData(Qt.ItemDataRole.UserRole, pid)
            item.setToolTip(content[:200])
            self.list_widget.addItem(item)
    
    def on_item_double_clicked(self, item):
        """항목 더블클릭 - 복사 후 숨기기"""
        pid = item.data(Qt.ItemDataRole.UserRole)
        if not pid:
            return  # 빈 목록 안내 항목 클릭 시 무시
        
        try:
            data = self.db.get_content(pid)
            if data:
                content, blob, ptype = data
                clipboard = QApplication.clipboard()
                if ptype == "IMAGE" and blob:
                    pixmap = QPixmap()
                    pixmap.loadFromData(blob)
                    clipboard.setPixmap(pixmap)
                else:
                    clipboard.setText(content)
                self.db.increment_use_count(pid)
                self.hide()
                # 붙여넣기
                QTimer.singleShot(200, lambda: keyboard.send('ctrl+v'))
        except Exception as e:
            logger.error(f"Mini window copy error: {e}")
    
    def open_main_window(self):
        """메인 창 열기"""
        if self.parent_window:
            self.parent_window.show()
            self.parent_window.activateWindow()
        self.hide()
    
    def mousePressEvent(self, event):
        """드래그 시작"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """드래그 이동"""
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_pos:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()
    
    def showEvent(self, event):
        """표시될 때 항목 로드"""
        super().showEvent(event)
        self.load_items()


# --- v8.0: 핫키 설정 다이얼로그 ---
class HotkeySettingsDialog(QDialog):
    """커스텀 핫키 설정"""
    
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("⌨️ 핫키 설정")
        self.setMinimumSize(400, 250)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        info = QLabel("단축키를 설정하세요. (예: ctrl+shift+v, alt+v)")
        info.setStyleSheet("color: gray;")
        layout.addWidget(info)
        
        form = QFormLayout()
        
        # 현재 설정 로드
        hotkeys = json.loads(self.db.get_setting("hotkeys", json.dumps(DEFAULT_HOTKEYS)))
        
        self.input_main = QLineEdit(hotkeys.get("show_main", "ctrl+shift+v"))
        self.input_main.setPlaceholderText("ctrl+shift+v")
        form.addRow("메인 창 열기:", self.input_main)
        
        self.input_mini = QLineEdit(hotkeys.get("show_mini", "alt+v"))
        self.input_mini.setPlaceholderText("alt+v")
        form.addRow("미니 창 열기:", self.input_mini)
        
        self.input_paste = QLineEdit(hotkeys.get("paste_last", "ctrl+shift+z"))
        self.input_paste.setPlaceholderText("ctrl+shift+z")
        form.addRow("마지막 항목 붙여넣기:", self.input_paste)
        
        layout.addLayout(form)
        
        # 버튼
        btn_layout = QHBoxLayout()
        btn_reset = QPushButton("🔄 기본값")
        btn_reset.clicked.connect(self.reset_defaults)
        btn_save = QPushButton("저장")
        btn_save.clicked.connect(self.save_hotkeys)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
    
    def reset_defaults(self):
        """기본값 복원"""
        self.input_main.setText(DEFAULT_HOTKEYS["show_main"])
        self.input_mini.setText(DEFAULT_HOTKEYS["show_mini"])
        self.input_paste.setText(DEFAULT_HOTKEYS["paste_last"])
    
    def save_hotkeys(self):
        """핫키 저장"""
        hotkeys = {
            "show_main": self.input_main.text().strip().lower(),
            "show_mini": self.input_mini.text().strip().lower(),
            "paste_last": self.input_paste.text().strip().lower()
        }
        self.db.set_setting("hotkeys", json.dumps(hotkeys))
        QMessageBox.information(self, "저장 완료", "핫키 설정이 저장되었습니다.\n변경사항은 프로그램 재시작 후 적용됩니다.")
        self.accept()


# --- 스니펫 다이얼로그 ---
class SnippetDialog(QDialog):
    def __init__(self, parent, db, snippet=None):
        super().__init__(parent)
        self.db = db
        self.snippet = snippet
        self.setWindowTitle("📝 스니펫 추가" if not snippet else "📝 스니펫 편집")
        self.setMinimumSize(400, 300)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("스니펫 이름")
        form.addRow("이름:", self.name_input)
        
        self.category_input = QComboBox()
        self.category_input.setEditable(True)
        self.category_input.addItems(["일반", "코드", "이메일", "메모"])
        form.addRow("카테고리:", self.category_input)
        
        layout.addLayout(form)
        
        self.content_input = QTextEdit()
        self.content_input.setPlaceholderText("스니펫 내용을 입력하세요...")
        layout.addWidget(self.content_input)
        
        if self.snippet:
            self.name_input.setText(self.snippet[1])
            self.content_input.setPlainText(self.snippet[2])
            self.category_input.setCurrentText(self.snippet[4])
        
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("저장")
        btn_save.clicked.connect(self.save_snippet)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def save_snippet(self):
        """v10.2: 스니펫 저장 (생성/편집 모드 지원)"""
        name = self.name_input.text().strip()
        content = self.content_input.toPlainText().strip()
        category = self.category_input.currentText()
        
        if not name or not content:
            QMessageBox.warning(self, "경고", "이름과 내용을 입력해주세요.")
            return
        
        if self.snippet:  # 편집 모드
            if self.db.update_snippet(self.snippet[0], name, content, "", category):
                self.accept()
            else:
                QMessageBox.critical(self, "오류", "스니펫 수정에 실패했습니다.")
        else:  # 새로 만들기 모드
            if self.db.add_snippet(name, content, "", category):
                self.accept()
            else:
                QMessageBox.critical(self, "오류", "스니펫 저장에 실패했습니다.")


# --- 스니펫 관리자 다이얼로그 ---
class SnippetManagerDialog(QDialog):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.parent_window = parent
        self.setWindowTitle("📝 스니펫 관리")
        self.setMinimumSize(550, 450)
        self.init_ui()
        self.load_snippets()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # 상단 버튼
        btn_layout = QHBoxLayout()
        btn_add = QPushButton("➕ 새 스니펫")
        btn_add.clicked.connect(self.add_snippet)
        btn_layout.addWidget(btn_add)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 스니펫 테이블
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["이름", "카테고리", "내용 미리보기"])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(1, 80)
        
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.cellDoubleClicked.connect(self.use_snippet)
        layout.addWidget(self.table)
        
        # 하단 버튼 - v10.2: 편집 버튼 추가
        bottom_layout = QHBoxLayout()
        btn_use = QPushButton("📋 사용")
        btn_use.clicked.connect(self.use_snippet)
        btn_edit = QPushButton("✏️ 편집")
        btn_edit.clicked.connect(self.edit_snippet)
        btn_delete = QPushButton("🗑️ 삭제")
        btn_delete.clicked.connect(self.delete_snippet)
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.close)
        
        bottom_layout.addWidget(btn_use)
        bottom_layout.addWidget(btn_edit)
        bottom_layout.addWidget(btn_delete)
        bottom_layout.addStretch()
        bottom_layout.addWidget(btn_close)
        layout.addLayout(bottom_layout)
    
    def load_snippets(self):
        snippets = self.db.get_snippets()
        self.table.setRowCount(0)
        
        for row_idx, (sid, name, content, shortcut, category) in enumerate(snippets):
            self.table.insertRow(row_idx)
            
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, sid)
            self.table.setItem(row_idx, 0, name_item)
            
            cat_item = QTableWidgetItem(category)
            cat_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 1, cat_item)
            
            preview = content.replace('\n', ' ')[:50] + ("..." if len(content) > 50 else "")
            self.table.setItem(row_idx, 2, QTableWidgetItem(preview))
    
    def add_snippet(self):
        dialog = SnippetDialog(self, self.db)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_snippets()
    
    def get_selected_id(self):
        rows = self.table.selectionModel().selectedRows()
        if rows:
            return self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        return None
    
    def use_snippet(self):
        sid = self.get_selected_id()
        if not sid:
            return
        snippets = self.db.get_snippets()
        for s in snippets:
            if s[0] == sid:
                content = s[2]
                # 템플릿 변수 치환
                content = self.process_template(content)
                clipboard = QApplication.clipboard()
                clipboard.setText(content)
                self.parent_window.statusBar().showMessage("✅ 스니펫이 클립보드에 복사되었습니다.", 2000)
                self.close()
                break
    
    def process_template(self, text):
        """템플릿 변수 치환"""
        import random
        import string
        
        now = datetime.datetime.now()
        
        # 기본 변수
        text = text.replace("{{date}}", now.strftime("%Y-%m-%d"))
        text = text.replace("{{time}}", now.strftime("%H:%M:%S"))
        text = text.replace("{{datetime}}", now.strftime("%Y-%m-%d %H:%M:%S"))
        
        # 클립보드 변수
        if "{{clipboard}}" in text:
            current_clip = QApplication.clipboard().text() or ""
            text = text.replace("{{clipboard}}", current_clip)
        
        # 랜덤 변수 {{random:N}}
        import re
        random_pattern = r'\{\{random:(\d+)\}\}'
        matches = re.findall(random_pattern, text)
        for match in matches:
            length = int(match)
            random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
            text = re.sub(r'\{\{random:' + match + r'\}\}', random_str, text, count=1)
        
        return text
    
    def delete_snippet(self):
        sid = self.get_selected_id()
        if sid:
            reply = QMessageBox.question(
                self, "삭제 확인", 
                "이 스니펫을 삭제하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.db.delete_snippet(sid)
                self.load_snippets()
    
    def edit_snippet(self):
        """v10.2: 스니펫 편집"""
        sid = self.get_selected_id()
        if not sid:
            QMessageBox.information(self, "알림", "편집할 스니펫을 선택하세요.")
            return
        snippets = self.db.get_snippets()
        for s in snippets:
            if s[0] == sid:
                dialog = SnippetDialog(self, self.db, snippet=s)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    self.load_snippets()
                break


# --- 태그 편집 다이얼로그 ---
class TagEditDialog(QDialog):
    def __init__(self, parent, db, item_id, current_tags=""):
        super().__init__(parent)
        self.db = db
        self.item_id = item_id
        self.setWindowTitle("🏷️ 태그 편집")
        self.setMinimumWidth(350)
        self.init_ui(current_tags)
    
    def init_ui(self, current_tags):
        layout = QVBoxLayout(self)
        
        info_label = QLabel("쉼표로 구분하여 태그를 입력하세요:")
        layout.addWidget(info_label)
        
        self.tag_input = QLineEdit()
        self.tag_input.setText(current_tags)
        self.tag_input.setPlaceholderText("예: 업무, 중요, 코드")
        layout.addWidget(self.tag_input)
        
        # 자주 사용하는 태그 버튼
        common_tags = ["업무", "개인", "중요", "임시", "코드", "링크"]
        tag_btn_layout = QHBoxLayout()
        for tag in common_tags:
            btn = QPushButton(tag)
            btn.setMaximumWidth(60)
            btn.clicked.connect(lambda checked, t=tag: self.add_tag(t))
            tag_btn_layout.addWidget(btn)
        layout.addLayout(tag_btn_layout)
        
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("저장")
        btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
    
    def add_tag(self, tag):
        current = self.tag_input.text().strip()
        tags = [t.strip() for t in current.split(',') if t.strip()]
        if tag not in tags:
            tags.append(tag)
        self.tag_input.setText(', '.join(tags))
    
    def get_tags(self):
        return self.tag_input.text().strip()


# --- v11: 항목 편집 다이얼로그 ---
class EditItemDialog(QDialog):
    def __init__(self, parent, text: str):
        super().__init__(parent)
        self.setWindowTitle("✏️ 항목 편집")
        self.setMinimumSize(520, 420)
        self._init_ui(text)

    def _init_ui(self, text: str):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.editor = QTextEdit()
        self.editor.setPlainText(text or "")
        layout.addWidget(self.editor)

        self.retype_checkbox = QCheckBox("유형 자동 재분석 (LINK/CODE/COLOR 등)")
        self.retype_checkbox.setChecked(True)
        layout.addWidget(self.retype_checkbox)

        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("저장")
        btn_save.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def get_text(self) -> str | None:
        return self.editor.toPlainText()

    def should_retype(self) -> bool:
        return bool(self.retype_checkbox.isChecked())


# --- 히스토리 통계 다이얼로그 ---
class StatisticsDialog(QDialog):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("📊 히스토리 통계")
        self.setMinimumSize(450, 400)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        stats = self.db.get_statistics()
        
        # 요약 카드
        summary_frame = QFrame()
        summary_frame.setStyleSheet("background-color: #16213e; border-radius: 8px; padding: 10px;")
        summary_layout = QHBoxLayout(summary_frame)
        
        total_label = QLabel(f"📋 총 항목\n{stats['total']}")
        total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        total_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        pinned_label = QLabel(f"📌 고정\n{stats['pinned']}")
        pinned_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pinned_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        today_count = self.db.get_today_count()
        today_label = QLabel(f"📅 오늘\n{today_count}")
        today_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        today_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        summary_layout.addWidget(total_label)
        summary_layout.addWidget(pinned_label)
        summary_layout.addWidget(today_label)
        layout.addWidget(summary_frame)
        
        # 유형별 통계
        type_group = QGroupBox("📊 유형별 분포")
        type_layout = QVBoxLayout(type_group)
        type_icons = {"TEXT": "📝 텍스트", "LINK": "🔗 링크", "IMAGE": "🖼️ 이미지", "CODE": "💻 코드", "COLOR": "🎨 색상"}
        for type_key, count in stats.get('by_type', {}).items():
            label = QLabel(f"{type_icons.get(type_key, type_key)}: {count}개")
            type_layout.addWidget(label)
        if not stats.get('by_type'):
            type_layout.addWidget(QLabel("데이터 없음"))
        layout.addWidget(type_group)
        
        # Top 5 자주 복사
        top_group = QGroupBox("🔥 자주 복사한 항목 Top 5")
        top_layout = QVBoxLayout(top_group)
        top_items = self.db.get_top_items(5)
        for idx, (content, use_count) in enumerate(top_items, 1):
            preview = content[:40] + "..." if len(content) > 40 else content
            preview = preview.replace('\n', ' ')
            label = QLabel(f"{idx}. {preview} ({use_count}회)")
            top_layout.addWidget(label)
        if not top_items:
            top_layout.addWidget(QLabel("사용 기록 없음"))
        layout.addWidget(top_group)
        
        # 닫기 버튼
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)


# --- 복사 규칙 다이얼로그 ---
class CopyRulesDialog(QDialog):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("⚙️ 복사 규칙 관리")
        self.setMinimumSize(550, 400)
        self.init_ui()
        self.load_rules()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 상단 버튼
        btn_layout = QHBoxLayout()
        btn_add = QPushButton("➕ 규칙 추가")
        btn_add.clicked.connect(self.add_rule)
        btn_layout.addWidget(btn_add)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 규칙 테이블
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["활성", "이름", "패턴", "동작"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(3, 80)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)
        
        # 하단 버튼
        bottom_layout = QHBoxLayout()
        btn_delete = QPushButton("🗑️ 삭제")
        btn_delete.clicked.connect(self.delete_rule)
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.close)
        bottom_layout.addWidget(btn_delete)
        bottom_layout.addStretch()
        bottom_layout.addWidget(btn_close)
        layout.addLayout(bottom_layout)
    
    def load_rules(self):
        rules = self.db.get_copy_rules()
        self.table.setRowCount(0)
        for row_idx, (rid, name, pattern, action, replacement, enabled, priority) in enumerate(rules):
            self.table.insertRow(row_idx)
            
            # 활성화 체크박스
            cb = QCheckBox()
            cb.setChecked(enabled == 1)
            cb.stateChanged.connect(lambda state, r=rid: self.toggle_rule(r, state))
            cb_widget = QWidget()
            cb_layout = QHBoxLayout(cb_widget)
            cb_layout.addWidget(cb)
            cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row_idx, 0, cb_widget)
            
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, rid)
            self.table.setItem(row_idx, 1, name_item)
            self.table.setItem(row_idx, 2, QTableWidgetItem(pattern))
            self.table.setItem(row_idx, 3, QTableWidgetItem(action))
    
    def add_rule(self):
        name, ok = QInputDialog.getText(self, "규칙 추가", "규칙 이름:")
        if not ok or not name.strip():
            return
        pattern, ok = QInputDialog.getText(self, "규칙 추가", "패턴 (정규식):")
        if not ok or not pattern.strip():
            return
        actions = ["trim", "lowercase", "uppercase", "remove_newlines"]
        action, ok = QInputDialog.getItem(self, "규칙 추가", "동작:", actions, 0, False)
        if ok:
            self.db.add_copy_rule(name.strip(), pattern.strip(), action)
            self.load_rules()
            # v10.0: 캐시 무효화
            if hasattr(self.parent(), 'invalidate_rules_cache'):
                self.parent().invalidate_rules_cache()
    
    def toggle_rule(self, rule_id, state):
        self.db.toggle_copy_rule(rule_id, 1 if state else 0)
        # v10.0: 캐시 무효화
        if hasattr(self.parent(), 'invalidate_rules_cache'):
            self.parent().invalidate_rules_cache()
    
    def delete_rule(self):
        rows = self.table.selectionModel().selectedRows()
        if rows:
            rid = self.table.item(rows[0].row(), 1).data(Qt.ItemDataRole.UserRole)
            self.db.delete_copy_rule(rid)
            self.load_rules()
            # v10.0: 캐시 무효화
            if hasattr(self.parent(), 'invalidate_rules_cache'):
                self.parent().invalidate_rules_cache()


# --- 메인 윈도우 ---
class MainWindow(QMainWindow):
    # 스레드 안전한 UI 조작을 위한 시그널
    toggle_mini_signal = pyqtSignal()
    paste_last_signal = pyqtSignal()
    show_main_signal = pyqtSignal()
    
    def __init__(self, start_minimized=False):
        super().__init__()
        self.start_minimized = start_minimized
        self.is_data_dirty = True  # v10.4: Lazy loading flag
        self.is_monitoring_paused = False  # v10.6: 모니터링 일시정지 플래그
        try:
            self.db = ClipboardDB()
            self.clipboard = QApplication.clipboard()
            self.clipboard.dataChanged.connect(self.on_clipboard_change)
            self.is_internal_copy = False
            self.is_privacy_mode = False  # 프라이버시 모드 (모니터링 중지)
            
            # v8.0: 새 매니저들 초기화
            self.vault_manager = SecureVaultManager(self.db)
            self.action_manager = ClipboardActionManager(self.db)
            self.export_manager = ExportImportManager(self.db)
            
            # v10.5: 비동기 액션 시그널 연결
            self.action_manager.action_completed.connect(self.on_action_completed)
            
            self.settings = QSettings(ORG_NAME, APP_NAME)
            self.current_theme = self.db.get_setting("theme", "dark")
            
            self.setWindowTitle(f"스마트 클립보드 프로 v{VERSION}")
            self.restore_window_state()
            
            self.app_icon = self.create_app_icon()
            self.setWindowIcon(self.app_icon)
            
            # v10.5: 기본값 변경 - 항상 위 해제
            self.always_on_top = False
            self.current_tag_filter = None  # 태그 필터
            self.sort_column = 3  # 기본 정렬: 시간 컨럼
            self.sort_order = Qt.SortOrder.DescendingOrder  # 기본: 내림차순
            
            # v10.0: 복사 규칙 캐싱 (성능 최적화)
            self._rules_cache = None
            self._rules_cache_dirty = True
            self._rules_invalid_logged = set()
            
            # v10.8: 타이머/백그라운드 작업 상태
            self._clipboard_debounce_timer = QTimer(self)
            self._clipboard_debounce_timer.setSingleShot(True)
            self._clipboard_debounce_timer.timeout.connect(self.process_clipboard)
            self._load_data_timer = QTimer(self)
            self._load_data_timer.setSingleShot(True)
            self._load_data_timer.timeout.connect(self._flush_requested_load_data)
            self._pending_reload_reason = ""
            self._maintenance_running = False
            
            self.apply_theme()
            self.init_menu()
            self.init_ui()
            self.init_tray()
            self.init_shortcuts()
            
            # v8.0: 핫키 시그널 연결 (스레드 안전)
            self.toggle_mini_signal.connect(self._toggle_mini_window_slot)
            self.paste_last_signal.connect(self._paste_last_item_slot)
            self.show_main_signal.connect(self.show_window_from_tray)

            # v8.0: 플로팅 미니 창
            self.mini_window = FloatingMiniWindow(self.db, self)
            
            # 핫키 설정 로드 및 등록 (안정성을 위해 지연 초기화)
            QTimer.singleShot(1000, self.register_hotkeys)
            
            self.update_always_on_top()
            
            # v10.4: Lazy loading - started minimized면 로드 지연
            if not self.start_minimized:
                self.request_load_data("startup", delay_ms=0)
            
            self.update_status_bar()
            
            # v8.0: 보관함 자동 잠금 타이머
            self.vault_timer = QTimer(self)
            self.vault_timer.timeout.connect(self.check_vault_timeout)
            self.vault_timer.start(60000)  # 1분마다 타임아웃 체크
            
            # v10.2: 만료 항목 정리 타이머 (1시간마다)
            self.cleanup_timer = QTimer(self)
            self.cleanup_timer.timeout.connect(self.run_periodic_cleanup)
            self.cleanup_timer.start(3600000)  # 1시간 = 3600000ms
            
            # v10.8: 시작 시 유지보수 작업을 백그라운드로 실행
            QTimer.singleShot(3000, lambda: self._run_maintenance_async("startup_backup", include_backup=True, refresh_ui=False))
            
            # v10.2: 등록된 핫키 추적 (안전한 해제를 위해)
            self._registered_hotkeys = []
            
            # 앱 시작 시 5초 후 정리 작업 실행
            QTimer.singleShot(5000, self.run_periodic_cleanup)
            
            logger.info("SmartClipboard Pro v10.3 started")
        except Exception as e:
            logger.error(f"MainWindow Init Error: {e}", exc_info=True)
            raise e
    
    def register_hotkeys(self):
        """v10.2: 커스텀 핫키 등록 - 개선된 버전 (앱 전용 핫키만 관리)"""
        try:
            hotkeys = json.loads(self.db.get_setting("hotkeys", json.dumps(DEFAULT_HOTKEYS)))
            
            # v10.2: 이전에 등록된 핫키만 해제 (다른 앱 핫키 보호)
            if hasattr(self, '_registered_hotkeys') and self._registered_hotkeys:
                for hk in self._registered_hotkeys:
                    try:
                        keyboard.remove_hotkey(hk)
                    except Exception:
                        pass
            self._registered_hotkeys = []

            # 메인 창 열기 핫키 - 시그널 emit으로 메인 스레드에서 실행
            main_key = hotkeys.get("show_main", "ctrl+shift+v")
            hk1 = keyboard.add_hotkey(main_key, lambda: self.show_main_signal.emit())
            self._registered_hotkeys.append(hk1)
            
            # 미니 창 핫키 - 설정에서 활성화된 경우만 등록
            mini_enabled = self.db.get_setting("mini_window_enabled", "true").lower() == "true"
            if mini_enabled:
                mini_key = hotkeys.get("show_mini", "alt+v")
                hk2 = keyboard.add_hotkey(mini_key, lambda: self.toggle_mini_signal.emit())
                self._registered_hotkeys.append(hk2)
                logger.info(f"Mini window hotkey registered: {mini_key}")
            else:
                mini_key = "(비활성화)"
                logger.info("Mini window hotkey disabled by user setting")
            
            # 마지막 항목 즉시 붙여넣기 핫키 - 시그널 emit
            paste_key = hotkeys.get("paste_last", "ctrl+shift+z")
            hk3 = keyboard.add_hotkey(paste_key, lambda: self.paste_last_signal.emit())
            self._registered_hotkeys.append(hk3)
            
            logger.info(f"Hotkeys registered: {main_key}, {mini_key}, {paste_key}")
            
        except Exception as e:
            logger.warning(f"Hotkey registration error: {e}")
    
    def toggle_mini_window(self):
        """미니 창 토글 (외부에서 호출 시 시그널 사용)"""
        self.toggle_mini_signal.emit()
    
    def _toggle_mini_window_slot(self):
        """미니 창 토글 (메인 스레드에서 실행되는 슬롯)"""
        try:
            # 미니 창 비활성화 시 무시
            if self.db.get_setting("mini_window_enabled", "true").lower() != "true":
                return
            
            if self.mini_window.isVisible():
                self.mini_window.hide()
            else:
                # 커서 위치 근처에 표시
                from PyQt6.QtGui import QCursor
                cursor_pos = QCursor.pos()
                self.mini_window.move(cursor_pos.x() - 150, cursor_pos.y() - 200)
                self.mini_window.show()
                self.mini_window.activateWindow()
        except Exception as e:
            logger.error(f"Toggle mini window error: {e}")
    
    def paste_last_item(self):
        """마지막 항목 즉시 붙여넣기 (외부에서 호출 시 시그널 사용)"""
        self.paste_last_signal.emit()
    
    def _paste_last_item_slot(self):
        """마지막 항목 즉시 붙여넣기 (메인 스레드에서 실행되는 슬롯)"""
        try:
            items = self.db.get_items("", "전체", limit=1)
            if items:
                pid, content, ptype, *_ = items[0]
                data = self.db.get_content(pid)
                if data:
                    content, blob, ptype = data
                    self.is_internal_copy = True
                    if ptype == "IMAGE" and blob:
                        pixmap = QPixmap()
                        pixmap.loadFromData(blob)
                        self.clipboard.setPixmap(pixmap)
                    else:
                        self.clipboard.setText(content)
                    self.db.increment_use_count(pid)
                    QTimer.singleShot(100, lambda: keyboard.send('ctrl+v'))
        except Exception as e:
            logger.error(f"Paste last item error: {e}")
    
    def check_vault_timeout(self):
        """보관함 자동 잠금 체크"""
        if self.vault_manager.check_timeout():
            logger.info("Vault auto-locked due to inactivity")

    def request_load_data(self, reason: str = "", delay_ms: int = 30):
        """Coalesce frequent load requests to keep UI responsive."""
        self._pending_reload_reason = reason or self._pending_reload_reason
        if delay_ms <= 0:
            if self._load_data_timer.isActive():
                self._load_data_timer.stop()
            self._flush_requested_load_data()
            return
        self._load_data_timer.start(max(1, int(delay_ms)))

    def _flush_requested_load_data(self):
        reason = self._pending_reload_reason
        self._pending_reload_reason = ""
        if reason:
            logger.debug(f"load_data requested: reason={reason}")
        self.load_data()

    def _run_maintenance_job(self, include_backup: bool = False):
        started = time.perf_counter()
        backup_ok = None
        if include_backup:
            backup_ok = self.db.backup_db()
        expired_count = self.db.cleanup_expired_items()
        self.db.cleanup_expired_trash()
        self.db.cleanup()
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return {"expired_count": int(expired_count or 0), "backup_ok": backup_ok, "elapsed_ms": elapsed_ms}

    def _on_maintenance_result(self, reason: str, result: dict, refresh_ui: bool):
        expired_count = int((result or {}).get("expired_count") or 0)
        elapsed_ms = float((result or {}).get("elapsed_ms") or 0.0)
        logger.debug(f"maintenance_ms={elapsed_ms:.2f} reason={reason} expired={expired_count}")
        if expired_count > 0:
            logger.info(f"주기적 정리: 만료 항목 {expired_count}개 삭제됨")
            if refresh_ui:
                self.request_load_data("maintenance_expired", delay_ms=30)

    def _on_maintenance_error(self, reason: str, error_tuple):
        logger.debug(f"Periodic cleanup error: reason={reason}, error={error_tuple}")

    def _run_maintenance_async(self, reason: str, include_backup: bool = False, refresh_ui: bool = True):
        if self._maintenance_running:
            logger.debug(f"Maintenance skipped (already running): reason={reason}")
            return
        self._maintenance_running = True
        try:
            worker = Worker(self._run_maintenance_job, include_backup)
            worker.signals.result.connect(lambda res, r=reason, ui=refresh_ui: self._on_maintenance_result(r, res, ui))
            worker.signals.error.connect(lambda err, r=reason: self._on_maintenance_error(r, err))
            worker.signals.finished.connect(lambda: setattr(self, "_maintenance_running", False))
            QThreadPool.globalInstance().start(worker)
        except Exception:
            self._maintenance_running = False
            logger.exception(f"Failed to start maintenance worker: reason={reason}")
    
    def run_periodic_cleanup(self):
        """v10.2: 주기적 정리 작업 실행 (만료된 임시 항목 및 휴지통 정리)"""
        self._run_maintenance_async("periodic_cleanup", include_backup=False, refresh_ui=True)

    # v10.4: 화면 표시 시 데이터 갱신 (Lazy Loading)
    def showEvent(self, event):
        if self.is_data_dirty:
            self.request_load_data("show_event", delay_ms=0)
        super().showEvent(event)

    def restore_window_state(self):
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(650, 850)

    def keyPressEvent(self, event):
        """키보드 네비게이션"""
        key = event.key()
        
        # Esc: 검색 클리어 또는 창 숨기기
        if key == Qt.Key.Key_Escape:
            if self.search_input.text():
                self.search_input.clear()
            else:
                self.hide()
            return
        
        # 방향키로 테이블 네비게이션
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down) and not self.search_input.hasFocus():
            self.table.setFocus()
        
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        if self.tray_icon.isVisible():
            self.hide()
            self.tray_icon.showMessage(
                "스마트 클립보드", 
                "백그라운드에서 실행 중입니다. (Ctrl+Shift+V로 열기)", 
                QSystemTrayIcon.MessageIcon.Information, 1500
            )
            event.ignore()
        else:
            self.quit_app()
            event.accept()

    def quit_app(self):
        """v10.2: 앱 종료 및 리소스 정리 - 개선된 버전"""
        logger.info("앱 종료 시작...")
        
        try:
            # 1. 등록된 핫키만 해제 (다른 앱 핫키 보호)
            if hasattr(self, '_registered_hotkeys') and self._registered_hotkeys:
                for hk in self._registered_hotkeys:
                    try:
                        keyboard.remove_hotkey(hk)
                    except Exception:
                        pass
                self._registered_hotkeys = []
            logger.debug("핫키 훅 해제됨")
            
            # 2. 타이머들 중지
            if hasattr(self, 'vault_timer') and self.vault_timer.isActive():
                self.vault_timer.stop()
                logger.debug("보관함 타이머 중지됨")
            
            if hasattr(self, 'cleanup_timer') and self.cleanup_timer.isActive():
                self.cleanup_timer.stop()
                logger.debug("정리 타이머 중지됨")
            
            # 3. 플로팅 미니 창 닫기
            if hasattr(self, 'mini_window') and self.mini_window:
                self.mini_window.close()
                logger.debug("미니 창 닫힘")
                
        except Exception as e:
            logger.warning(f"Cleanup warning: {e}")
            
        # 4. DB 연결 종료
        try:
            self.db.close()
            logger.debug("DB 연결 종료됨")
        except Exception:
            pass
            
        logger.info("앱 종료 완료")
        # 5. Qt 앱 종료
        QApplication.quit()

    def toggle_privacy_mode(self):
        """프라이버시 모드 토글"""
        self.is_privacy_mode = not self.is_privacy_mode
        
        # UI 상태 동기화
        self.action_privacy.setChecked(self.is_privacy_mode)
        if hasattr(self, 'tray_privacy_action'):
            self.tray_privacy_action.setChecked(self.is_privacy_mode)
            
        self.update_status_bar()
        
        msg = "프라이버시 모드가 켜졌습니다.\n이제 클립보드 내용이 저장되지 않습니다." if self.is_privacy_mode else "프라이버시 모드가 꺼졌습니다.\n다시 클립보드 기록을 시작합니다."
        ToastNotification.show_toast(self, msg, duration=3000, toast_type="warning" if self.is_privacy_mode else "success")

    def toggle_debug_mode(self):
        """디버그 모드 토글 - 로그 레벨 변경"""
        if self.action_debug.isChecked():
            logging.getLogger().setLevel(logging.DEBUG)
            logger.info("디버그 모드 활성화됨 - 로그 레벨: DEBUG")
            self.statusBar().showMessage("🐛 디버그 모드 활성화", 2000)
            ToastNotification.show_toast(self, "디버그 모드 활성화\n상세 로그가 기록됩니다.", duration=2000, toast_type="info")
        else:
            logging.getLogger().setLevel(logging.INFO)
            logger.info("디버그 모드 비활성화됨 - 로그 레벨: INFO")
            self.statusBar().showMessage("디버그 모드 비활성화", 2000)

    def backup_data(self):
        """데이터베이스 백업"""
        file_name, _ = QFileDialog.getSaveFileName(self, "데이터 백업", f"backup_{datetime.date.today()}.db", "SQLite DB Files (*.db);;All Files (*)")
        if file_name:
            try:
                import shutil
                shutil.copy2(DB_FILE, file_name)
                QMessageBox.information(self, "백업 완료", f"데이터가 성공적으로 백업되었습니다:\n{file_name}")
            except Exception as e:
                QMessageBox.critical(self, "백업 오류", f"백업 중 오류가 발생했습니다:\n{e}")

    def restore_data(self):
        """데이터베이스 복원 - v10.2: 매니저 갱신 추가"""
        reply = QMessageBox.warning(self, "복원 경고", "데이터를 복원하면 현재 데이터가 모두 덮어씌워집니다.\n계속하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return
            
        file_name, _ = QFileDialog.getOpenFileName(self, "데이터 복원", "", "SQLite DB Files (*.db);;All Files (*)")
        if file_name:
            try:
                # DB 연결 종료 시도 (안전한 복사를 위해)
                self.db.conn.close()
                import shutil
                shutil.copy2(file_name, DB_FILE)
                QMessageBox.information(self, "복원 완료", "데이터가 복원되었습니다.\n프로그램을 재시작합니다.")
                self.quit_app()
            except Exception as e:
                QMessageBox.critical(self, "복원 오류", f"복원 중 오류가 발생했습니다:\n{e}")
                # v10.2: 연결 재수립 및 모든 매니저 갱신
                self.db = ClipboardDB()
                self.vault_manager = SecureVaultManager(self.db)
                self.action_manager = ClipboardActionManager(self.db)
                self.export_manager = ExportImportManager(self.db)
                logger.warning("복원 실패 후 DB 연결 및 매니저 재초기화됨")

    def create_app_icon(self):
        size = 64
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        theme = THEMES[self.current_theme]
        
        # 그라데이션 배경
        gradient = QLinearGradient(0, 0, size, size)
        gradient.setColorAt(0, QColor(theme["primary"]))
        gradient.setColorAt(1, QColor(theme["primary_variant"]))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, size, size, 16, 16)
        
        # 문서 아이콘
        painter.setBrush(QBrush(QColor("white")))
        rect_w, rect_h = 30, 36
        painter.drawRoundedRect((size-rect_w)//2, (size-rect_h)//2 + 4, rect_w, rect_h, 4, 4)
        
        # 클립
        painter.setBrush(QBrush(QColor("#333")))
        clip_w, clip_h = 18, 8
        painter.drawRoundedRect((size-clip_w)//2, (size-rect_h)//2 + 1, clip_w, clip_h, 2, 2)
        
        # 라인
        painter.setPen(QPen(QColor("#DDD"), 2))
        line_start_x = (size-rect_w)//2 + 6
        line_end_x = (size-rect_w)//2 + rect_w - 6
        y_start = (size-rect_h)//2 + 16
        for i in range(3):
            y = y_start + (i * 7)
            painter.drawLine(line_start_x, y, line_end_x, y)

        painter.end()
        return QIcon(pixmap)

    def apply_theme(self):
        theme = THEMES.get(self.current_theme, THEMES["dark"])
        glass = GLASS_STYLES.get(self.current_theme, GLASS_STYLES["dark"])
        style = f"""
        QMainWindow {{ 
            background-color: {theme["background"]}; 
        }}
        
        /* v9.0: 글래스모피즘 메뉴바 */
        QMenuBar {{ 
            background-color: {glass["glass_bg"]}; 
            color: {theme["text"]}; 
            font-family: 'Malgun Gothic', 'Segoe UI', sans-serif; 
            padding: 6px 4px;
            border-bottom: 1px solid {theme["border"]};
        }}
        QMenuBar::item {{ 
            padding: 6px 12px;
            border-radius: 6px;
            margin: 0 2px;
        }}
        QMenuBar::item:selected {{ 
            background-color: {theme["primary"]}; 
            border-radius: 6px;
        }}
        
        /* v9.0: 글래스모피즘 메뉴 */
        QMenu {{ 
            background-color: {glass["glass_bg"]}; 
            color: {theme["text"]}; 
            border: 1px solid {theme["border"]}; 
            border-radius: 12px;
            font-family: 'Malgun Gothic', 'Segoe UI', sans-serif; 
            padding: 8px;
        }}
        QMenu::item {{ 
            padding: 10px 24px; 
            border-radius: 8px;
            margin: 2px 4px;
        }}
        QMenu::item:selected {{ 
            background-color: {theme["primary"]}; 
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {theme["border"]};
            margin: 6px 12px;
        }}
        
        QWidget {{ 
            color: {theme["text"]}; 
            font-family: 'Malgun Gothic', 'Segoe UI', sans-serif; 
            font-size: 13px; 
        }}
        
        /* v9.0: 글래스모피즘 검색창 */
        QLineEdit, QComboBox {{ 
            background-color: {glass["glass_bg"]}; 
            border: 2px solid {theme["border"]}; 
            border-radius: 14px; 
            padding: 10px 18px; 
            color: {theme["text"]}; 
            selection-background-color: {theme["primary"]};
            font-size: 14px;
        }}
        QLineEdit:focus, QComboBox:focus {{ 
            border: 2px solid {theme["primary"]}; 
            background-color: {theme["surface_variant"]};
        }}
        QLineEdit:hover, QComboBox:hover {{
            border-color: {theme["primary_variant"]};
        }}
        QComboBox::drop-down {{ 
            border: none; 
            padding-right: 12px;
            width: 20px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {glass["glass_bg"]};
            border: 1px solid {theme["border"]};
            border-radius: 10px;
            selection-background-color: {theme["primary"]};
            padding: 4px;
        }}
        
        /* v9.0: 글래스모피즘 테이블 */
        QTableWidget {{ 
            background-color: {glass["glass_bg"]}; 
            border: none; 
            border-radius: 16px;
            selection-background-color: {theme["primary"]}; 
            gridline-color: transparent;
            outline: none;
            padding: 4px;
        }}
        /* v10.1: 개선된 테이블 항목 스타일 - 선택 시각화 강화 */
        QTableWidget::item {{
            padding: 14px 12px;
            border-bottom: 1px solid {theme["border"]};
            border-radius: 0px;
        }}
        QTableWidget::item:selected {{
            background-color: {theme["primary"]};
            color: {theme.get("selected_text", "#ffffff")};
            font-weight: 500;
            border-left: 4px solid {theme.get("gradient_end", theme["primary_variant"])};
            padding-left: 10px;
        }}
        QTableWidget::item:hover:!selected {{
            background-color: {theme.get("hover_bg", theme["surface_variant"])};
            color: {theme.get("hover_text", theme["text"])};
            border-left: 4px solid {theme["primary"]};
            padding-left: 8px;
        }}
        QTableWidget::item:focus {{
            outline: none;
            border: 2px solid {theme["primary"]};
            border-radius: 4px;
        }}
        
        /* v9.0: 개선된 헤더 */
        QHeaderView::section {{ 
            background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                stop:0 {theme["surface_variant"]}, stop:1 {theme["surface"]}); 
            padding: 12px 8px; 
            border: none; 
            border-bottom: 2px solid {theme["border"]};
            font-weight: 700; 
            font-size: 12px;
            color: {theme["text_secondary"]}; 
        }}
        QHeaderView::section:hover {{
            background-color: {theme["surface_variant"]};
            color: {theme["primary"]};
        }}
        
        /* v9.0: 글래스 텍스트 영역 */
        QTextEdit {{ 
            background-color: {glass["glass_bg"]}; 
            border: 2px solid {theme["border"]}; 
            border-radius: 14px; 
            padding: 14px; 
            font-family: 'Malgun Gothic', 'Cascadia Code', 'Consolas', 'D2Coding', monospace; 
            font-size: 14px;
            line-height: 1.5;
            selection-background-color: {theme["primary"]};
        }}
        QTextEdit:focus {{
            border-color: {theme["primary"]};
        }}
        
        QLabel#ImagePreview {{
            background-color: {glass["glass_bg"]}; 
            border: 2px solid {theme["border"]}; 
            border-radius: 16px;
        }}
        
        /* v10.6: 개선된 버튼 스타일 - 마이크로 인터랙션 및 일관성 강화 */
        QPushButton {{ 
            background-color: {theme["surface_variant"]}; 
            border: 2px solid {theme["border"]}; 
            border-radius: 12px; 
            padding: 12px 20px; 
            color: {theme["text"]}; 
            font-weight: 600;
            font-size: 13px;
            outline: none;
            min-height: 20px;
        }}
        QPushButton:hover {{ 
            background-color: {theme["primary"]}; 
            border-color: {theme["primary"]};
            color: white;
        }}
        QPushButton:focus {{
            border: 2px solid {theme["primary"]};
            background-color: {theme["surface_variant"]};
        }}
        QPushButton:pressed {{ 
            background-color: {theme["primary_variant"]}; 
            border-color: {theme["primary_variant"]};
            padding-left: 21px;
            padding-top: 13px;
        }}
        QPushButton:disabled {{
            background-color: {theme["surface"]};
            color: {theme["text_secondary"]};
            border-color: {theme["border"]};
            opacity: 0.6;
        }}
        
        /* v9.0: 그라데이션 Primary 버튼 */
        QPushButton#PrimaryBtn {{
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                stop:0 {theme.get("gradient_start", theme["primary"])}, 
                stop:1 {theme.get("gradient_end", theme["primary_variant"])});
            color: white;
            border: none;
            font-weight: bold;
            font-size: 14px;
        }}
        QPushButton#PrimaryBtn:hover {{
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                stop:0 {theme.get("gradient_end", theme["primary_variant"])}, 
                stop:1 {theme.get("gradient_start", theme["primary"])});
        }}
        
        /* v10.1: 개선된 아이콘 버튼 - 호버 피드백 강화 */
        QPushButton#ToolBtn {{
            background-color: transparent; 
            border: 2px solid {theme["border"]};
            font-size: 13px; 
            padding: 8px 14px;
            border-radius: 10px;
            min-width: 36px;
        }}
        QPushButton#ToolBtn:hover {{
            background-color: {theme["secondary"]};
            border-color: {theme["secondary"]};
            color: white;
        }}
        QPushButton#ToolBtn:focus {{
            border-color: {theme["primary"]};
            background-color: rgba(255, 255, 255, 0.05);
        }}
        QPushButton#ToolBtn:pressed {{
            background-color: {theme["primary"]};
            border-color: {theme["primary"]};
        }}
        
        /* v10.7: 퀵 액션 버튼 - 상단 바 전용 */
        QPushButton#QuickBtn {{
            background-color: {glass["glass_bg"]};
            border: 1px solid {theme["border"]};
            border-radius: 8px;
            padding: 6px 12px;
            font-size: 12px;
            font-weight: 500;
            min-width: 70px;
        }}
        QPushButton#QuickBtn:hover {{
            background-color: {theme["surface_variant"]};
            border-color: {theme["primary"]};
            color: {theme["primary"]};
        }}
        QPushButton#QuickBtn:pressed {{
            background-color: {theme["primary"]};
            color: white;
            border-color: {theme["primary"]};
        }}
        
        /* v10.7: 도구 버튼 그룹 컨테이너 */
        QFrame#ToolsGroup {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {theme["surface_variant"]}, stop:1 {theme["surface"]});
            border: 1px solid {theme["border"]};
            border-radius: 12px;
            padding: 4px 8px;
        }}
        
        /* v9.0: 경고 삭제 버튼 */
        QPushButton#DeleteBtn {{ 
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {theme["error"]}, stop:1 #dc2626); 
            color: white;
            border: none;
            font-weight: bold;
        }}
        QPushButton#DeleteBtn:hover {{ 
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #dc2626, stop:1 #b91c1c);
        }}
        
        /* v9.0: 카드 스타일 버튼 */
        QPushButton#CardBtn {{
            background-color: {glass["glass_bg"]};
            border: 1px solid {theme["border"]};
            border-radius: 14px;
            padding: 14px 18px;
            text-align: left;
        }}
        QPushButton#CardBtn:hover {{
            background-color: {theme["surface_variant"]};
            border-color: {theme["primary"]};
        }}
        
        /* v9.0: 스플리터 */
        QSplitter::handle {{
            background-color: {theme["border"]};
            height: 3px;
            border-radius: 1px;
        }}
        QSplitter::handle:hover {{
            background-color: {theme["primary"]};
        }}
        
        /* v9.0: 글래스 상태바 */
        QStatusBar {{
            background-color: {glass["glass_bg"]};
            color: {theme["text_secondary"]};
            border-top: 1px solid {theme["border"]};
            padding: 4px 8px;
            font-size: 12px;
        }}
        
        /* v9.0: 모던 탭 위젯 */
        QTabWidget::pane {{
            border: 1px solid {theme["border"]};
            border-radius: 12px;
            background-color: {glass["glass_bg"]};
        }}
        QTabBar::tab {{
            background-color: {theme["surface_variant"]};
            color: {theme["text_secondary"]};
            padding: 12px 24px;
            margin-right: 4px;
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
            font-weight: 500;
        }}
        QTabBar::tab:hover {{
            background-color: {theme["surface"]};
            color: {theme["text"]};
        }}
        QTabBar::tab:selected {{
            background-color: {theme["primary"]};
            color: white;
            font-weight: 600;
        }}
        
        /* v10.6: 울트라 슬림 스크롤바 - 부드러운 호버 효과 */
        QScrollBar:vertical {{
            background-color: transparent;
            width: 6px;
            border-radius: 3px;
            margin: 4px 2px;
        }}
        QScrollBar:vertical:hover {{
            width: 10px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {theme["border"]};
            border-radius: 3px;
            min-height: 40px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {theme["primary"]};
            border-radius: 5px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            background-color: transparent;
            height: 8px;
            border-radius: 4px;
        }}
        QScrollBar::handle:horizontal {{
            background-color: {theme["border"]};
            border-radius: 4px;
            min-width: 40px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background-color: {theme["primary"]};
        }}
        
        /* v9.0: 다이얼로그 스타일 */
        QDialog {{
            background-color: {theme["background"]};
        }}
        
        /* v9.0: 그룹박스 */
        QGroupBox {{
            background-color: {glass["glass_bg"]};
            border: 1px solid {theme["border"]};
            border-radius: 12px;
            margin-top: 12px;
            padding-top: 12px;
            font-weight: 600;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 12px;
            padding: 0 8px;
            color: {theme["text"]};
        }}
        
        /* v9.0: 스핀박스 */
        QSpinBox {{
            background-color: {glass["glass_bg"]};
            border: 2px solid {theme["border"]};
            border-radius: 10px;
            padding: 8px 12px;
            color: {theme["text"]};
        }}
        QSpinBox:focus {{
            border-color: {theme["primary"]};
        }}
        
        /* v9.0: 체크박스 */
        QCheckBox {{
            spacing: 8px;
        }}
        QCheckBox::indicator {{
            width: 20px;
            height: 20px;
            border-radius: 6px;
            border: 2px solid {theme["border"]};
        }}
        QCheckBox::indicator:checked {{
            background-color: {theme["primary"]};
            border-color: {theme["primary"]};
        }}
        QCheckBox::indicator:hover {{
            border-color: {theme["primary_variant"]};
        }}
        
        /* v10.6: 도구 버튼 그룹 컨테이너 */
        QFrame#ToolsGroup {{
            background-color: {glass["glass_bg"]};
            border: 1px solid {theme["border"]};
            border-radius: 10px;
            padding: 4px 8px;
        }}
        
        /* v10.6: 필터 콤보박스 강조 */
        QComboBox#FilterCombo {{
            background-color: {theme["surface_variant"]};
            font-weight: 600;
            min-width: 130px;
        }}
        QComboBox#FilterCombo:hover {{
            background-color: {theme["surface"]};
            border-color: {theme["primary"]};
        }}
        
        /* v10.6: 향상된 플레이스홀더 스타일 */
        QLineEdit::placeholder {{
            color: {theme["text_secondary"]};
            font-style: italic;
        }}
        """
        self.setStyleSheet(style)
        # Note: 단축키는 init_shortcuts()에서 등록됨 (중복 방지)

    def eventFilter(self, source, event):
        """드래그 앤 드롭 이벤트 처리 (고정 항목 순서 변경)"""
        if source != self.table.viewport():
            return super().eventFilter(source, event)
        
        # DragEnter: 드래그 시작 허용 여부
        if event.type() == QEvent.Type.DragEnter:
            if event.source() == self.table:
                event.acceptProposedAction()
                return True
            return False
        
        # DragMove: 드래그 중
        if event.type() == QEvent.Type.DragMove:
            event.acceptProposedAction()
            return True
        
        # Drop: 드래그 완료
        if event.type() == QEvent.Type.Drop:
            return self._handle_drop_event(event)
        
        return super().eventFilter(source, event)

    def _handle_drop_event(self, event) -> bool:
        """드롭 이벤트 처리 - 고정 항목끼리만 순서 변경 허용"""
        try:
            # 드롭 위치 확인
            target_row = self.table.rowAt(int(event.position().y()))
            if target_row == -1:
                event.ignore()
                return True  # 이벤트 소비 (Qt 기본 동작 막기)
            
            # 선택된 행 (드래그 중인 행)
            selected_rows = self.table.selectionModel().selectedRows()
            if not selected_rows:
                event.ignore()
                return True
            source_row = selected_rows[0].row()
            
            # 같은 위치면 무시
            if source_row == target_row:
                event.ignore()
                return True
            
            # 소스/타겟 항목 확인
            source_item = self.table.item(source_row, 0)
            target_item = self.table.item(target_row, 0)
            
            if not source_item or not target_item:
                event.ignore()
                return True
            
            # 고정 항목 확인
            is_source_pinned = source_item.text() == "📌"
            is_target_pinned = target_item.text() == "📌"
            
            if not (is_source_pinned and is_target_pinned):
                # 비고정 항목 드래그 시도 시 토스트 알림
                self.statusBar().showMessage("📌 고정 항목끼리만 순서를 변경할 수 있습니다.", 2000)
                event.ignore()
                return True
            
            # 고정 항목 순서 재정렬
            source_pid = source_item.data(Qt.ItemDataRole.UserRole)
            
            # 현재 고정된 항목들의 ID 목록 (화면 순서)
            pinned_ids = []
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item and item.text() == "📌":
                    pid = item.data(Qt.ItemDataRole.UserRole)
                    if pid != source_pid:  # 드래그 중인 항목 제외
                        pinned_ids.append(pid)
            
            # 삽입 위치 계산
            insert_idx = 0
            for r in range(target_row):
                item = self.table.item(r, 0)
                if item and item.text() == "📌":
                    pid = item.data(Qt.ItemDataRole.UserRole)
                    if pid != source_pid:
                        insert_idx += 1
            
            # 위에서 아래로 드래그 시 인덱스 조정
            if source_row < target_row:
                pinned_ids.insert(insert_idx, source_pid)
            else:
                pinned_ids.insert(insert_idx, source_pid)
            
            # DB 업데이트
            success = True
            for idx, pid in enumerate(pinned_ids):
                if not self.db.update_pin_order(pid, idx):
                    success = False
                    break
            
            if success:
                # 성공 시 UI 갱신 (딜레이로 드롭 애니메이션 방지)
                QTimer.singleShot(50, self.load_data)
                self.statusBar().showMessage("✅ 고정 항목 순서가 변경되었습니다.", 2000)
            else:
                self.statusBar().showMessage("⚠️ 순서 변경 중 오류가 발생했습니다.", 2000)
            
            event.accept()
            return True  # 이벤트 소비
            
        except Exception as e:
            logger.error(f"Drop event error: {e}")
            event.ignore()
            return True


    def init_menu(self):
        menubar = self.menuBar()
        
        # 파일 메뉴
        file_menu = menubar.addMenu("파일")
        
        action_export = QAction("💾 텍스트 내보내기", self)
        action_export.triggered.connect(self.export_history)
        file_menu.addAction(action_export)
        
        file_menu.addSeparator()
        
        action_backup = QAction("📦 데이터 백업...", self)
        action_backup.triggered.connect(self.backup_data)
        file_menu.addAction(action_backup)
        
        action_restore = QAction("♻️ 데이터 복원...", self)
        action_restore.triggered.connect(self.restore_data)
        file_menu.addAction(action_restore)
        
        file_menu.addSeparator()
        
        action_quit = QAction("❌ 종료", self)
        action_quit.setShortcut("Ctrl+Q")
        action_quit.triggered.connect(self.quit_app)
        file_menu.addAction(action_quit)

        # 편집 메뉴
        edit_menu = menubar.addMenu("편집")
        
        action_clear = QAction("🗑️ 기록 전체 삭제", self)
        action_clear.triggered.connect(self.clear_all_history)
        edit_menu.addAction(action_clear)
        
        edit_menu.addSeparator()
        
        action_snippets = QAction("📝 스니펫 관리...", self)
        action_snippets.triggered.connect(self.show_snippet_manager)
        edit_menu.addAction(action_snippets)
        
        # v8.0: 내보내기/가져오기
        edit_menu.addSeparator()
        
        action_export_adv = QAction("📤 고급 내보내기...", self)
        action_export_adv.triggered.connect(self.show_export_dialog)
        edit_menu.addAction(action_export_adv)
        
        action_import = QAction("📥 가져오기...", self)
        action_import.triggered.connect(self.show_import_dialog)
        edit_menu.addAction(action_import)
        
        edit_menu.addSeparator()
        
        # v10.2: 휴지통 메뉴
        action_trash = QAction("🗑️ 휴지통...", self)
        action_trash.triggered.connect(self.show_trash)
        edit_menu.addAction(action_trash)

        # 보기 메뉴
        view_menu = menubar.addMenu("보기")
        
        action_stats = QAction("📊 히스토리 통계...", self)
        action_stats.triggered.connect(self.show_statistics)
        view_menu.addAction(action_stats)
        
        # v8.0: 미니 창
        action_mini = QAction("📋 빠른 클립보드 (미니 창)", self)
        action_mini.setShortcut("Alt+V")
        action_mini.triggered.connect(self.toggle_mini_window)
        view_menu.addAction(action_mini)
        
        view_menu.addSeparator()
        
        self.action_ontop = QAction("📌 항상 위 고정", self, checkable=True)
        self.action_ontop.setChecked(True)
        self.action_ontop.triggered.connect(self.toggle_always_on_top)
        view_menu.addAction(self.action_ontop)
        
        view_menu.addSeparator()
        
        # 테마 서브메뉴
        theme_menu = view_menu.addMenu("🎨 테마")
        for key, theme in THEMES.items():
            action = QAction(theme["name"], self)
            action.setData(key)
            action.triggered.connect(lambda checked, k=key: self.change_theme(k))
            theme_menu.addAction(action)

        # 설정 메뉴
        settings_menu = menubar.addMenu("설정")
        
        self.action_startup = QAction("🚀 시작 시 자동 실행", self, checkable=True)
        self.action_startup.setChecked(self.check_startup_registry())
        self.action_startup.triggered.connect(self.toggle_startup)
        settings_menu.addAction(self.action_startup)
        
        settings_menu.addSeparator()
        
        action_rules = QAction("⚙️ 복사 규칙 관리...", self)
        action_rules.triggered.connect(self.show_copy_rules)
        settings_menu.addAction(action_rules)
        
        # v8.0: 클립보드 액션 자동화
        action_actions = QAction("⚡ 액션 자동화...", self)
        action_actions.triggered.connect(self.show_clipboard_actions)
        settings_menu.addAction(action_actions)
        
        # v8.0: 핫키 설정
        action_hotkeys = QAction("⌨️ 핫키 설정...", self)
        action_hotkeys.triggered.connect(self.show_hotkey_settings)
        settings_menu.addAction(action_hotkeys)
        
        action_settings = QAction("⚙️ 설정...", self)
        action_settings.triggered.connect(self.show_settings)
        settings_menu.addAction(action_settings)
        
        settings_menu.addSeparator()
        
        # v8.0: 보안 보관함
        action_vault = QAction("🔒 보안 보관함...", self)
        action_vault.triggered.connect(self.show_secure_vault)
        settings_menu.addAction(action_vault)
        
        settings_menu.addSeparator()
        
        self.action_privacy = QAction("🔒 프라이버시 모드 (기록 중지)", self, checkable=True)
        self.action_privacy.triggered.connect(self.toggle_privacy_mode)
        settings_menu.addAction(self.action_privacy)
        
        self.action_debug = QAction("🐛 디버그 모드", self, checkable=True)
        self.action_debug.triggered.connect(self.toggle_debug_mode)
        settings_menu.addAction(self.action_debug)
        
        # 도움말 메뉴
        help_menu = menubar.addMenu("도움말")
        
        action_shortcuts = QAction("⌨️ 키보드 단축키", self)
        action_shortcuts.triggered.connect(self.show_shortcuts_dialog)
        help_menu.addAction(action_shortcuts)
        
        help_menu.addSeparator()
        
        action_about = QAction("ℹ️ 정보", self)
        action_about.triggered.connect(self.show_about_dialog)
        help_menu.addAction(action_about)

    def change_theme(self, theme_key):
        self.current_theme = theme_key
        self.db.set_setting("theme", theme_key)
        self.apply_theme()
        if hasattr(self, 'tray_menu'):
            self.update_tray_theme()
        # v10.6: 미니 창 테마 연동
        if hasattr(self, 'mini_window') and self.mini_window:
            self.mini_window.apply_mini_theme()
        self.load_data()  # 테마 변경 시 테이블 색상 반영
        self.statusBar().showMessage(f"✅ 테마 변경: {THEMES[theme_key]['name']}", 2000)

    def show_settings(self):
        dialog = SettingsDialog(self, self.db, self.current_theme)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_theme = dialog.get_selected_theme()
            if new_theme != self.current_theme:
                self.change_theme(new_theme)
            self.statusBar().showMessage("✅ 설정이 저장되었습니다.", 2000)

    def show_snippet_manager(self):
        """스니펫 관리 창 표시"""
        dialog = SnippetManagerDialog(self, self.db)
        dialog.exec()

    def show_statistics(self):
        """히스토리 통계 창 표시"""
        dialog = StatisticsDialog(self, self.db)
        dialog.exec()

    def show_copy_rules(self):
        """복사 규칙 관리 창 표시"""
        dialog = CopyRulesDialog(self, self.db)
        dialog.exec()
    
    # --- v8.0: 새 다이얼로그 핸들러 ---
    def show_secure_vault(self):
        """보안 보관함 표시"""
        if not HAS_CRYPTO:
            QMessageBox.warning(self, "라이브러리 필요", 
                "암호화 기능을 사용하려면 cryptography 라이브러리가 필요합니다.\n\npip install cryptography")
            return
        dialog = SecureVaultDialog(self, self.db, self.vault_manager)
        dialog.exec()
    
    def show_clipboard_actions(self):
        """클립보드 액션 자동화 관리"""
        dialog = ClipboardActionsDialog(self, self.db, self.action_manager)
        dialog.exec()
    
    def show_export_dialog(self):
        """고급 내보내기 다이얼로그"""
        dialog = ExportDialog(self, self.export_manager)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.statusBar().showMessage("✅ 내보내기 완료", 3000)
    
    def show_import_dialog(self):
        """가져오기 다이얼로그"""
        dialog = ImportDialog(self, self.export_manager)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_data()
            self.statusBar().showMessage("✅ 가져오기 완료", 3000)
    
    def show_trash(self):
        """v10.2: 휴지통 다이얼로그 표시"""
        dialog = TrashDialog(self, self.db)
        dialog.exec()
    
    def show_hotkey_settings(self):
        """핫키 설정 다이얼로그"""
        dialog = HotkeySettingsDialog(self, self.db)
        dialog.exec()
    
    def show_shortcuts_dialog(self):
        """키보드 단축키 안내 다이얼로그"""
        shortcuts_text = """
<h2>⌨️ 키보드 단축키</h2>
<table cellspacing="8">
<tr><td><b>Ctrl+Shift+V</b></td><td>창 표시/숨기기 (글로벌)</td></tr>
<tr><td><b>Ctrl+C</b></td><td>선택 항목 복사</td></tr>
<tr><td><b>Enter</b></td><td>복사 후 붙여넣기</td></tr>
<tr><td><b>Delete</b></td><td>선택 항목 삭제</td></tr>
<tr><td><b>Ctrl+P</b></td><td>고정/해제 토글</td></tr>
<tr><td><b>Ctrl+F</b></td><td>검색창 포커스</td></tr>
<tr><td><b>Ctrl/Shift+클릭</b></td><td>다중 선택</td></tr>
<tr><td><b>Escape</b></td><td>검색 클리어 / 창 숨기기</td></tr>
<tr><td><b>↑↓</b></td><td>테이블 네비게이션</td></tr>
<tr><td><b>Ctrl+Q</b></td><td>프로그램 종료</td></tr>
</table>
<br>
<p><b>💡 Tip:</b> 헤더를 클릭하면 정렬할 수 있습니다!</p>
"""
        QMessageBox.information(self, "키보드 단축키", shortcuts_text)
    
    def show_about_dialog(self):
        """프로그램 정보 다이얼로그"""
        about_text = f"""
<h2>📋 스마트 클립보드 프로 v{VERSION}</h2>
<p>고급 클립보드 매니저 - PyQt6 기반</p>
<br>
<p><b>주요 기능:</b></p>
<ul>
<li>클립보드 히스토리 자동 저장</li>
<li>텍스트, 이미지, 링크, 코드 분류</li>
<li>태그 시스템 및 스니펫 관리</li>
<li>복사 규칙 자동화</li>
<li>다크/라이트/오션 테마</li>
</ul>
<br>
<p>© 2025-2026 MySmartTools</p>
"""
        QMessageBox.about(self, f"스마트 클립보드 프로 v{VERSION}", about_text)

    def edit_tag(self):
        """선택 항목 태그 편집"""
        pid = self.get_selected_id()
        if not pid:
            return
        current_tags = self.db.get_item_tags(pid)
        dialog = TagEditDialog(self, self.db, pid, current_tags)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_tags = dialog.get_tags()
            self.db.set_item_tags(pid, new_tags)
            self.statusBar().showMessage("✅ 태그가 저장되었습니다.", 2000)

    def merge_selected(self):
        """선택된 여러 항목 병합"""
        rows = self.table.selectionModel().selectedRows()
        if len(rows) < 2:
            QMessageBox.information(self, "알림", "병합하려면 2개 이상의 항목을 선택하세요.")
            return
        
        # 구분자 선택
        separators = {"줄바꿈": "\n", "콤마": ", ", "공백": " ", "탭": "\t"}
        sep_name, ok = QInputDialog.getItem(self, "병합", "구분자 선택:", list(separators.keys()), 0, False)
        if not ok:
            return
        
        separator = separators[sep_name]
        contents = []
        for row_idx in sorted([r.row() for r in rows]):
            pid = self.table.item(row_idx, 0).data(Qt.ItemDataRole.UserRole)
            data = self.db.get_content(pid)
            if data and data[2] != "IMAGE":
                contents.append(data[0])
        
        if contents:
            merged = separator.join(contents)
            self.is_internal_copy = True
            self.clipboard.setText(merged)
            self.statusBar().showMessage(f"✅ {len(contents)}개 항목 병합 완료", 2000)

    def show_tag_filter_menu(self):
        """태그 필터 메뉴 표시"""
        menu = QMenu(self)
        theme = THEMES.get(self.current_theme, THEMES["dark"])
        menu.setStyleSheet(f"""
            QMenu {{ background-color: {theme["surface"]}; color: {theme["text"]}; border: 1px solid {theme["border"]}; padding: 5px; }}
            QMenu::item {{ padding: 8px 20px; }}
            QMenu::item:selected {{ background-color: {theme["primary"]}; }}
        """)
        
        # 태그 없음 (초기화)
        clear_action = menu.addAction("🔄 모든 항목 표시")
        clear_action.triggered.connect(lambda: self.filter_by_tag(None))
        
        menu.addSeparator()
        
        # 태그 목록
        tags = self.db.get_all_tags()
        if tags:
            for tag in tags:
                action = menu.addAction(f"🏷️ {tag}")
                action.triggered.connect(lambda checked, t=tag: self.filter_by_tag(t))
        else:
            no_tag_action = menu.addAction("(태그 없음)")
            no_tag_action.setEnabled(False)
        
        menu.exec(self.btn_tag_filter.mapToGlobal(self.btn_tag_filter.rect().bottomLeft()))
    
    def filter_by_tag(self, tag):
        """태그로 필터링"""
        self.current_tag_filter = tag
        if tag:
            self.statusBar().showMessage(f"🏷️ '{tag}' 태그 필터 적용", 2000)
        self.load_data()

    def on_header_clicked(self, section):
        """헤더 클릭 시 정렬 토글"""
        # 📌(0) 컬럼은 정렬 비활성화
        if section == 0:
            return
        
        # 같은 컬럼 클릭: 정렬 순서 토글
        if self.sort_column == section:
            if self.sort_order == Qt.SortOrder.AscendingOrder:
                self.sort_order = Qt.SortOrder.DescendingOrder
            else:
                self.sort_order = Qt.SortOrder.AscendingOrder
        else:
            self.sort_column = section
            self.sort_order = Qt.SortOrder.AscendingOrder
        
        # 헤더 라벨 업데이트 (정렬 표시자)
        header_labels = ["📌", "유형", "내용", "시간", "사용"]
        for i in range(len(header_labels)):
            if i == section:
                indicator = "▲" if self.sort_order == Qt.SortOrder.AscendingOrder else "▼"
                header_labels[i] = f"{header_labels[i]} {indicator}"
        self.table.setHorizontalHeaderLabels(header_labels)
        
        self.load_data()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # v10.7: 상단 퀵 액션 바 (자주 사용하는 기능 빠른 접근)
        quick_bar = QHBoxLayout()
        quick_bar.setSpacing(8)
        
        btn_vault = QPushButton("🔒 보관함")
        btn_vault.setObjectName("QuickBtn")
        btn_vault.setToolTip("보안 보관함 열기")
        btn_vault.clicked.connect(self.show_secure_vault)
        
        btn_snippets = QPushButton("📝 스니펫")
        btn_snippets.setObjectName("QuickBtn")
        btn_snippets.setToolTip("스니펫 관리")
        btn_snippets.clicked.connect(self.show_snippet_manager)
        
        btn_trash = QPushButton("🗑️ 휴지통")
        btn_trash.setObjectName("QuickBtn")
        btn_trash.setToolTip("휴지통 열기")
        btn_trash.clicked.connect(self.show_trash)
        
        btn_settings = QPushButton("⚙️ 설정")
        btn_settings.setObjectName("QuickBtn")
        btn_settings.setToolTip("설정 열기")
        btn_settings.clicked.connect(self.show_settings)
        
        quick_bar.addWidget(btn_vault)
        quick_bar.addWidget(btn_snippets)
        quick_bar.addWidget(btn_trash)
        quick_bar.addWidget(btn_settings)
        quick_bar.addStretch()
        
        # 프라이버시 모드 인디케이터
        self.privacy_indicator = QLabel("")
        self.privacy_indicator.setStyleSheet("font-size: 12px; color: #fbbf24;")
        quick_bar.addWidget(self.privacy_indicator)
        
        main_layout.addLayout(quick_bar)

        # v9.0: 상단 필터/검색 영역 (개선된 레이아웃)
        top_layout = QHBoxLayout()
        top_layout.setSpacing(12)
        
        self.filter_combo = QComboBox()
        self.filter_combo.setObjectName("FilterCombo")  # v10.6: 스타일 연결용
        self.filter_combo.addItems(["전체", "📌 고정", "⭐ 북마크", "📝 텍스트", "🖼️ 이미지", "🔗 링크", "💻 코드", "🎨 색상", "📁 파일"])
        self.filter_combo.setFixedWidth(150)
        self.filter_combo.setToolTip("유형별 필터")
        self.filter_combo.currentTextChanged.connect(self.load_data)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 검색어 입력... (Ctrl+F)")
        # Debounced search to avoid UI stutter on large DBs.
        self._search_debounce_timer = QTimer(self)
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.setInterval(200)
        self._search_debounce_timer.timeout.connect(self.load_data)
        self._search_fallback_notified = False

        self.search_input.textChanged.connect(self.on_search_text_changed)
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumHeight(40)
        
        # v9.0: 태그 필터 버튼 개선
        self.btn_tag_filter = QPushButton("🏷️")
        self.btn_tag_filter.setObjectName("ToolBtn")
        self.btn_tag_filter.setToolTip("태그 필터")
        self.btn_tag_filter.setFixedSize(44, 40)
        self.btn_tag_filter.clicked.connect(self.show_tag_filter_menu)
        
        top_layout.addWidget(self.filter_combo)
        top_layout.addWidget(self.search_input, 1)  # stretch factor 1
        top_layout.addWidget(self.btn_tag_filter)
        main_layout.addLayout(top_layout)

        # 메인 스플리터
        splitter = QSplitter(Qt.Orientation.Vertical)

        # v9.0: 개선된 테이블
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["📌", "유형", "내용", "시간", "사용"])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(1, 60)
        self.table.setColumnWidth(3, 95)
        self.table.setColumnWidth(4, 50)
        
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(42)  # v9.0: 행 높이 증가
        
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)  # 다중 선택 지원
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.cellDoubleClicked.connect(self.on_double_click_paste)
        
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        # 헤더 클릭 정렬
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self.on_header_clicked)
        
        # 드래그 앤 드롭 (고정 항목 재정렬용)
        # DragDrop 모드: Qt 자동 행 삭제 방지, 커스텀 eventFilter에서 처리
        self.table.setDragEnabled(True)
        self.table.setAcceptDrops(True)
        self.table.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.table.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.table.setDragDropOverwriteMode(False)
        self.table.viewport().installEventFilter(self)

        splitter.addWidget(self.table)

        # 상세 영역
        detail_container = QWidget()
        detail_layout = QVBoxLayout(detail_container)
        detail_layout.setContentsMargins(0, 10, 0, 0)
        detail_layout.setSpacing(10)
        
        # 도구 버튼
        self.tools_layout = QHBoxLayout()
        self.tools_layout.setSpacing(6)
        self.tools_layout.addStretch()
        
        self.btn_save_img = QPushButton("💾 저장")
        self.btn_save_img.setObjectName("ToolBtn")
        self.btn_save_img.clicked.connect(self.save_image_to_file)
        self.btn_save_img.setVisible(False)
        
        self.btn_google = QPushButton("🔍 구글")
        self.btn_google.setObjectName("ToolBtn")
        self.btn_google.setToolTip("구글에서 검색 (Ctrl+G)")
        self.btn_google.clicked.connect(self.search_google)
        
        self.btn_qr = QPushButton("📱 QR")
        self.btn_qr.setObjectName("ToolBtn")
        self.btn_qr.setToolTip("QR 코드 생성")
        self.btn_qr.clicked.connect(self.generate_qr)
        
        self.btn_upper = QPushButton("ABC")
        self.btn_upper.setObjectName("ToolBtn")
        self.btn_upper.setToolTip("대문자 변환")
        self.btn_upper.clicked.connect(lambda: self.transform_text("upper"))
        
        self.btn_lower = QPushButton("abc")
        self.btn_lower.setObjectName("ToolBtn")
        self.btn_lower.setToolTip("소문자 변환")
        self.btn_lower.clicked.connect(lambda: self.transform_text("lower"))
        
        self.btn_strip = QPushButton("✂️")
        self.btn_strip.setObjectName("ToolBtn")
        self.btn_strip.setToolTip("공백 제거")
        self.btn_strip.clicked.connect(lambda: self.transform_text("strip"))
        
        self.btn_normalize = QPushButton("📋")
        self.btn_normalize.setObjectName("ToolBtn")
        self.btn_normalize.setToolTip("줄바꿈 정리")
        self.btn_normalize.clicked.connect(lambda: self.transform_text("normalize"))
        
        self.btn_json = QPushButton("{ }")
        self.btn_json.setObjectName("ToolBtn")
        self.btn_json.setToolTip("JSON 포맷팅")
        self.btn_json.clicked.connect(lambda: self.transform_text("json"))

        self.tools_layout.addWidget(self.btn_save_img)
        self.tools_layout.addWidget(self.btn_google)
        if HAS_QRCODE:
            self.tools_layout.addWidget(self.btn_qr)
        
        # 그룹 구분선 1: 검색/공유 | 대소문자
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setFixedWidth(2)
        sep1.setStyleSheet("background-color: rgba(128,128,128,0.4);")
        self.tools_layout.addWidget(sep1)
        
        self.tools_layout.addWidget(self.btn_upper)
        self.tools_layout.addWidget(self.btn_lower)
        
        # 그룹 구분선 2: 대소문자 | 공백/포맷
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setFixedWidth(2)
        sep2.setStyleSheet("background-color: rgba(128,128,128,0.4);")
        self.tools_layout.addWidget(sep2)
        
        self.tools_layout.addWidget(self.btn_strip)
        self.tools_layout.addWidget(self.btn_normalize)
        self.tools_layout.addWidget(self.btn_json)
        detail_layout.addLayout(self.tools_layout)

        # 상세 보기 스택
        self.detail_stack = QStackedWidget()
        
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_stack.addWidget(self.detail_text)
        
        self.detail_image_lbl = QLabel()
        self.detail_image_lbl.setObjectName("ImagePreview")
        self.detail_image_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_stack.addWidget(self.detail_image_lbl)
        
        detail_layout.addWidget(self.detail_stack)

        # v10.6: 하단 액션 버튼 - 통일된 높이와 완성된 디자인
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        self.btn_copy = QPushButton("📄 복사")
        self.btn_copy.setMinimumHeight(44)
        self.btn_copy.setObjectName("PrimaryBtn")
        self.btn_copy.setToolTip("클립보드에 복사 (Enter)")
        self.btn_copy.clicked.connect(self.copy_item)
        
        self.btn_link = QPushButton("🔗 링크 열기")
        self.btn_link.setMinimumHeight(44)
        self.btn_link.setToolTip("브라우저에서 링크 열기 (Ctrl+L)")
        self.btn_link.clicked.connect(self.open_link)
        
        self.btn_pin = QPushButton("📌 고정")
        self.btn_pin.setMinimumHeight(44)
        self.btn_pin.setToolTip("항목 고정/해제 (Ctrl+P)")
        self.btn_pin.clicked.connect(self.toggle_pin)
        
        self.btn_del = QPushButton("🗑 삭제")
        self.btn_del.setMinimumHeight(44)
        self.btn_del.setObjectName("DeleteBtn")
        self.btn_del.setToolTip("항목 삭제 (Delete)")
        self.btn_del.clicked.connect(self.delete_item)

        btn_layout.addWidget(self.btn_copy, 3)
        btn_layout.addWidget(self.btn_link, 2)
        btn_layout.addWidget(self.btn_pin, 2)
        btn_layout.addWidget(self.btn_del, 1)
        detail_layout.addLayout(btn_layout)

        splitter.addWidget(detail_container)
        splitter.setStretchFactor(0, 7)  # v9.0: 테이블 영역 더 크게
        splitter.setStretchFactor(1, 3)
        main_layout.addWidget(splitter)
        
        self.update_ui_state(False)

    # --- v10.5: 비동기 액션 완료 핸들러 ---
    def on_action_completed(self, action_name, result):
        """비동기 액션 완료 처리"""
        try:
            res_type = result.get("type")
            if res_type == "title":
                title = result.get("title")
                if title:
                    try:
                        self.clipboard.dataChanged.disconnect(self.on_clipboard_change)  # 일시적 연결 해제
                    except (TypeError, RuntimeError):
                        pass  # 이미 연결 해제된 경우
                    self.show_toast("🔗 링크 제목 발견", f"{title}")
                    # UI 입력 중이 아닐 때만 데이터 다시 로드
                    if not self.search_input.hasFocus():
                        self.request_load_data("action_completed", delay_ms=30)
                    self.clipboard.dataChanged.connect(self.on_clipboard_change)
        except Exception as e:
            logger.error(f"Action Handler Error: {e}")

    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.app_icon)
        self.tray_icon.setToolTip(f"스마트 클립보드 프로 v{VERSION}")
        
        self.tray_menu = QMenu()
        self.update_tray_theme()
        
        show_action = QAction("📋 열기", self)
        show_action.triggered.connect(self.show_window_from_tray)
        
        self.tray_privacy_action = QAction("🔒 프라이버시 모드", self, checkable=True)
        self.tray_privacy_action.triggered.connect(self.toggle_privacy_mode)

        # v10.6: 모니터링 일시정지 액션
        self.tray_pause_action = QAction("⏸ 모니터링 일시정지", self, checkable=True)
        self.tray_pause_action.triggered.connect(self.toggle_monitoring_pause)
        
        quit_action = QAction("❌ 종료", self)
        quit_action.triggered.connect(self.quit_app)

        adv_menu = QMenu("고급")
        adv_menu.addAction("설정 초기화", self.reset_settings)
        adv_menu.addAction("클립보드 모니터 재시작", self.reset_clipboard_monitor)
        
        self.tray_menu.addAction(show_action)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.tray_privacy_action)
        self.tray_menu.addAction(self.tray_pause_action)
        self.tray_menu.addSeparator()
        self.tray_menu.addMenu(adv_menu)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def toggle_monitoring_pause(self):
        """v10.6: 모니터링 일시정지 토글"""
        self.is_monitoring_paused = not self.is_monitoring_paused
        
        # 액션 체크 상태 동기화
        self.tray_pause_action.setChecked(self.is_monitoring_paused)
        
        if self.is_monitoring_paused:
            self.show_toast("⏸ 모니터링 일시정지", "클립보드 수집이 잠시 중단됩니다.")
            self.tray_icon.setToolTip(f"스마트 클립보드 프로 v{VERSION} (일시정지됨)")
        else:
            self.show_toast("▶ 모니터링 재개", "클립보드 수집을 다시 시작합니다.")
            self.tray_icon.setToolTip(f"스마트 클립보드 프로 v{VERSION}")
            
        self.update_status_bar()

    def init_shortcuts(self):
        """앱 내 키보드 단축키 설정"""
        # Escape: 창 숨기기
        shortcut_escape = QShortcut(QKeySequence("Escape"), self)
        shortcut_escape.activated.connect(self.hide)
        
        # Ctrl+F: 검색창 포커스
        shortcut_search = QShortcut(QKeySequence("Ctrl+F"), self)
        shortcut_search.activated.connect(lambda: self.search_input.setFocus())
        
        # Ctrl+P: 고정 토글
        shortcut_pin = QShortcut(QKeySequence("Ctrl+P"), self)
        shortcut_pin.activated.connect(self.toggle_pin)
        
        # Delete: 삭제
        shortcut_delete = QShortcut(QKeySequence("Delete"), self)
        shortcut_delete.activated.connect(self.delete_item)
        
        # Shift+Delete: 다중 삭제
        shortcut_multi_delete = QShortcut(QKeySequence("Shift+Delete"), self)
        shortcut_multi_delete.activated.connect(self.delete_selected_items)
        
        # Return: 붙여넣기
        shortcut_paste = QShortcut(QKeySequence("Return"), self)
        shortcut_paste.activated.connect(self.paste_selected)
        
        # Ctrl+C: 복사
        shortcut_copy = QShortcut(QKeySequence("Ctrl+C"), self)
        shortcut_copy.activated.connect(self.copy_item)

    def update_tray_theme(self):
        """트레이 메뉴에 현재 테마 적용"""
        theme = THEMES.get(self.current_theme, THEMES["dark"])
        self.tray_menu.setStyleSheet(f"""
            QMenu {{ 
                background-color: {theme["surface"]}; 
                color: {theme["text"]}; 
                border: 1px solid {theme["border"]}; 
                padding: 5px; 
            }}
            QMenu::item {{ padding: 8px 20px; }}
            QMenu::item:selected {{ background-color: {theme["primary"]}; }}
        """)

    def update_status_bar(self, selection_count=0):
        """상태바 업데이트 - 통계 및 선택 정보 표시"""
        # v10.7: 프라이버시 인디케이터 업데이트
        if hasattr(self, 'privacy_indicator'):
            if self.is_privacy_mode:
                self.privacy_indicator.setText("🔒 프라이버시")
            elif self.is_monitoring_paused:
                self.privacy_indicator.setText("⏸ 일시정지")
            else:
                self.privacy_indicator.setText("")
        
        # 프라이버시 모드 표시
        if self.is_privacy_mode:
            self.statusBar().showMessage("🔒 프라이버시 모드 활성화됨 (클립보드 기록 중지)")
            return
            
        stats = self.db.get_statistics()
        today_count = self.db.get_today_count()
        
        # 기본 통계
        status_parts = [
            f"📊 총 {stats['total']}개",
            f"📌 고정 {stats['pinned']}개",
            f"📅 오늘 {today_count}개"
        ]
        
        # 모니터링 일시정지 표시
        if self.is_monitoring_paused:
             status_parts.append("⏸ [일시정지됨]")
        
        # 현재 필터 상태
        current_filter = self.filter_combo.currentText() if hasattr(self, 'filter_combo') else "전체"
        if current_filter != "전체":
            status_parts.append(f"🔍 {current_filter}")

        # 검색 결과 수
        search_query = self.search_input.text() if hasattr(self, "search_input") else ""
        if search_query.strip():
            shown = getattr(self, "_last_display_count", None)
            if shown is not None:
                status_parts.append(f"🔎 검색 {shown}개")
        
        # 선택된 항목 수
        if selection_count > 0:
            status_parts.append(f"✅ {selection_count}개 선택")
        
        # 정렬 상태
        if hasattr(self, 'sort_column') and self.sort_column > 0:
            sort_names = {1: "유형", 2: "내용", 3: "시간", 4: "사용"}
            order = "▲" if self.sort_order == Qt.SortOrder.AscendingOrder else "▼"
            status_parts.append(f"{sort_names.get(self.sort_column, '')}{order}")
        
        self.statusBar().showMessage(" | ".join(status_parts))

    # --- 기능 로직 ---
    def toggle_always_on_top(self):
        self.always_on_top = self.action_ontop.isChecked()
        self.update_always_on_top()

    def update_always_on_top(self):
        if self.always_on_top:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
        self.show()

    def check_startup_registry(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return True
        except WindowsError:
            return False

    def toggle_startup(self):
        enable = self.action_startup.isChecked()
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE)
            if enable:
                if getattr(sys, 'frozen', False):
                    # 패키징된 EXE 경로 (절대 경로 보장)
                    exe_path = f'"{os.path.abspath(sys.executable)}" --minimized'
                else:
                    # 개발 환경: pythonw.exe 경로를 정확히 찾기
                    python_dir = os.path.dirname(sys.executable)
                    pythonw_path = os.path.join(python_dir, "pythonw.exe")
                    if not os.path.exists(pythonw_path):
                        # pythonw.exe가 없으면 python.exe 사용 (콘솔 창 표시됨)
                        pythonw_path = sys.executable
                        logger.warning("pythonw.exe not found, using python.exe")
                    script_path = os.path.abspath(__file__)
                    exe_path = f'"{pythonw_path}" "{script_path}" --minimized'
                
                logger.info(f"Setting startup registry: {exe_path}")
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
                self.statusBar().showMessage("✅ 시작 시 자동 실행 설정됨", 2000)
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                    self.statusBar().showMessage("✅ 자동 실행 해제됨", 2000)
                    logger.info("Startup registry removed")
                except WindowsError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            logger.error(f"레지스트리 설정 실패: {e}")
            QMessageBox.critical(self, "오류", f"레지스트리 설정 실패: {e}")
            self.action_startup.setChecked(not enable)

    def reset_settings(self):
        confirm = QMessageBox.question(
            self, "설정 초기화", 
            "모든 설정을 기본값으로 되돌리시겠습니까?\n(데이터는 삭제되지 않습니다)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.db.set_setting("theme", "dark")
            self.db.set_setting("opacity", "1.0")
            self.current_theme = "dark"
            self.apply_theme()
            QMessageBox.information(self, "완료", "설정이 초기화되었습니다.")

    def reset_clipboard_monitor(self):
        """v10.5: 클립보드 모니터링 강제 재시작"""
        try:
            self.clipboard.dataChanged.disconnect(self.on_clipboard_change)
            # 잠시 대기 후 재연결
            QTimer.singleShot(500, lambda: self.clipboard.dataChanged.connect(self.on_clipboard_change))
            self.statusBar().showMessage("✅ 클립보드 모니터 재시작됨", 2000)
            logger.info("Clipboard monitor restarted manually")
        except Exception as e:
            logger.exception("Monitor reset failed")
            self.statusBar().showMessage(f"❌ 재시작 실패: {e}", 2000)

    def clear_all_history(self):
        reply = QMessageBox.question(
            self, "초기화", 
            "고정된 항목을 제외한 모든 기록을 삭제하시겠습니까?", 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.clear_all()
            self.load_data()
            self.update_ui_state(False)
            self.update_status_bar()
            self.statusBar().showMessage("✅ 기록이 삭제되었습니다.", 2000)
            
    def export_history(self):
        data = self.db.get_all_text_content()
        if not data:
            QMessageBox.information(self, "알림", "내보낼 텍스트 기록이 없습니다.")
            return

        file_name, _ = QFileDialog.getSaveFileName(self, "기록 내보내기", "", "Text Files (*.txt);;All Files (*)")
        if file_name:
            try:
                with open(file_name, 'w', encoding='utf-8') as f:
                    f.write(f"Smart Clipboard History (Exported: {datetime.datetime.now()})\n")
                    f.write("=" * 50 + "\n\n")
                    for content, timestamp in data:
                        f.write(f"[{timestamp}]\n{content}\n")
                        f.write("-" * 30 + "\n")
                self.statusBar().showMessage("✅ 기록이 저장되었습니다.", 2000)
            except Exception as e:
                logger.error(f"Export Error: {e}")
                QMessageBox.critical(self, "오류", f"저장 중 오류 발생: {e}")

    def save_image_to_file(self):
        pid = self.get_selected_id()
        if not pid: return
        
        data = self.db.get_content(pid)
        if data:
            _, blob, ptype = data
            if ptype == "IMAGE" and blob:
                file_name, _ = QFileDialog.getSaveFileName(
                    self, "이미지 저장", 
                    f"image_{int(time.time())}.png", 
                    "Images (*.png);;All Files (*)"
                )
                if file_name:
                    try:
                        pixmap = QPixmap()
                        pixmap.loadFromData(blob)
                        pixmap.save(file_name, "PNG")
                        self.statusBar().showMessage("✅ 이미지가 저장되었습니다.", 2000)
                    except Exception as e:
                        logger.error(f"Image Save Error: {e}")
                        QMessageBox.critical(self, "오류", f"이미지 저장 실패: {e}")

    def search_google(self):
        text = self.detail_text.toPlainText()
        if text:
            # v10.3: URL 인코딩 추가 - 특수문자 처리
            url = f"https://www.google.com/search?q={quote(text)}"
            webbrowser.open(url)

    def generate_qr(self):
        if not HAS_QRCODE:
            QMessageBox.warning(self, "오류", "qrcode 라이브러리가 설치되지 않았습니다.\npip install qrcode[pil]")
            return

        text = self.detail_text.toPlainText()
        if not text: return

        try:
            qr = qrcode.QRCode(box_size=10, border=4)
            qr.add_data(text)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            im_data = img.convert("RGBA").tobytes("raw", "RGBA")
            qim = QImage(im_data, img.size[0], img.size[1], QImage.Format.Format_RGBA8888)
            pixmap = QPixmap.fromImage(qim)
            
            self.detail_stack.setCurrentIndex(1)
            
            w, h = self.detail_image_lbl.width(), self.detail_image_lbl.height()
            if w > 0 and h > 0:
                self.detail_image_lbl.setPixmap(pixmap.scaled(QSize(w-10, h-10), Qt.AspectRatioMode.KeepAspectRatio))
            else:
                self.detail_image_lbl.setPixmap(pixmap)
                
            self.statusBar().showMessage("✅ QR 코드가 생성되었습니다.", 3000)
            
        except Exception as e:
            logger.error(f"QR Error: {e}")
            QMessageBox.warning(self, "QR 오류", str(e))

    def on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            if self.isVisible():
                self.hide()
            else:
                self.show_window_from_tray()

    def show_window_from_tray(self):
        self.show()
        self.activateWindow()
        self.raise_()
        self.search_input.setFocus()
        self.update_status_bar()

    def on_clipboard_change(self):
        """클립보드 변경 감지 - v10.3: 디바운스 개선"""
        # 프라이버시 모드나 내부 복사면 무시
        if self.is_privacy_mode or self.is_internal_copy:
            self.is_internal_copy = False # 내부 복사 플래그는 한 번 사용 후 초기화
            return

        # v10.8: 타이머 인스턴스 재사용 (중복 생성/삭제 제거)
        if self._clipboard_debounce_timer.isActive():
            self._clipboard_debounce_timer.stop()
        self._clipboard_debounce_timer.start(100)

    def process_clipboard(self):
        # v10.6: 모니터링 일시정지 상태면 무시
        if self.is_monitoring_paused:
            return
             
        try:
            mime_data = self.clipboard.mimeData()
            # v11: file/folder clipboard capture (Explorer copy)
            if mime_data.hasUrls():
                local_paths = []
                for u in mime_data.urls() or []:
                    try:
                        if u and u.isLocalFile():
                            p = u.toLocalFile()
                            if p:
                                local_paths.append(p)
                    except Exception:
                        continue
                if local_paths:
                    self._process_file_clipboard(local_paths)
                    return

            if mime_data.hasImage():
                self._process_image_clipboard(mime_data)
                return
             
            if mime_data.hasText():
                self._process_text_clipboard(mime_data)
        except Exception as e:
            logger.exception("Clipboard access error")

    def _process_file_clipboard(self, paths: list[str]):
        """v11: 로컬 파일/폴더 경로 클립보드 처리."""
        try:
            # 중복 방지 (경로 목록 기준)
            joined = "\0".join(paths)
            fhash = hashlib.md5(joined.encode("utf-8", errors="ignore")).hexdigest()
            if hasattr(self, "_last_file_hash") and self._last_file_hash == fhash:
                logger.debug("Duplicate file list skipped")
                return
            self._last_file_hash = fhash

            item_id = self.db.add_file_item(paths)
            if item_id:
                if self.isVisible():
                    self.request_load_data("file_clipboard", delay_ms=30)
                    self.update_status_bar()
                else:
                    self.is_data_dirty = True
        except Exception:
            logger.exception("File clipboard processing error")

    def _process_image_clipboard(self, mime_data):
        """v10.5: 이미지 클립보드 처리 로직 분리"""
        try:
            image = self.clipboard.image()
            if image.isNull():
                return

            ba = QByteArray()
            buffer = QBuffer(ba)
            buffer.open(QBuffer.OpenModeFlag.WriteOnly)
            image.save(buffer, "PNG")
            blob_data = ba.data()
            
            # v10.2: 이미지 크기 제한 (5MB)
            MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
            if len(blob_data) > MAX_IMAGE_SIZE:
                logger.warning(f"Image too large ({len(blob_data)} bytes), skipping")
                ToastNotification.show_toast(
                    self, f"⚠️ 이미지가 너무 큽니다 (최대 5MB)",
                    duration=2500, toast_type="warning"
                )
                return
            
            # v10.0: 이미지 중복 체크 (해시 기반)
            img_hash = hashlib.md5(blob_data).hexdigest()
            if hasattr(self, '_last_image_hash') and self._last_image_hash == img_hash:
                logger.debug("Duplicate image skipped")
                return
            self._last_image_hash = img_hash
            
            if self.db.add_item("[이미지 캡처됨]", blob_data, "IMAGE"):
                # v10.4: UI 업데이트 최적화 (보이는 경우에만)
                if self.isVisible():
                    self.request_load_data("image_clipboard", delay_ms=30)
                    self.update_status_bar()
                else:
                    self.is_data_dirty = True
        except Exception as e:
            logger.exception("Image processing error")

    def _process_text_clipboard(self, mime_data):
        """v10.5: 텍스트 클립보드 처리 로직 분리"""
        try:
            raw_text = mime_data.text()
            if not raw_text:
                return
            
            # 복사 규칙 적용 (원본 텍스트 기반)
            text = self.apply_copy_rules(raw_text)
            normalized_text = text.strip()
            if not normalized_text:
                return
            
            tag = self.analyze_text(normalized_text)
            item_id = self.db.add_item(text, None, tag)
            if item_id:
                # v8.0: 클립보드 액션 자동화 실행
                self._process_actions(normalized_text, item_id)
                
                # v10.4: UI 업데이트 최적화
                if self.isVisible():
                    self.request_load_data("text_clipboard", delay_ms=30)
                    self.update_status_bar()
                else:
                    self.is_data_dirty = True
        except Exception as e:
            logger.exception("Text processing error")

    def _process_actions(self, text, item_id):
        """v10.5: 액션 처리 로직 분리"""
        try:
            # 성능 최적화: add_item이 반환한 ID 직접 사용 (get_items 호출 제거)
            action_results = self.action_manager.process(text, item_id)
            for action_name, result in action_results:
                if result and result.get("type") == "notify":
                    ToastNotification.show_toast(
                        self, f"⚡ {action_name}: {result.get('message', '')}",
                        duration=3000, toast_type="info"
                    )
                elif result and result.get("type") == "title":
                    title = result.get("title")
                    if title:
                        ToastNotification.show_toast(
                            self, f"🔗 {title[:50]}...",
                            duration=2500, toast_type="info"
                        )
        except Exception as action_err:
            logger.debug(f"Action processing error: {action_err}")

    def apply_copy_rules(self, text):
        """활성화된 복사 규칙 적용 - 캐싱으로 성능 최적화"""
        # v10.8: 캐시 리프레시 시 정규식을 사전 컴파일해 반복 비용을 줄임
        if self._rules_cache_dirty or self._rules_cache is None:
            compiled_rules = []
            raw_rules = self.db.get_copy_rules()
            invalid_ids = set()
            for rid, name, pattern, action, replacement, enabled, priority in raw_rules:
                if not enabled:
                    continue
                if not pattern:
                    logger.warning(f"Empty pattern in copy rule '{name}' (id={rid}), skipping")
                    continue
                try:
                    compiled = re.compile(pattern)
                    compiled_rules.append((rid, name, compiled, action, replacement or "", priority))
                except re.error as e:
                    invalid_ids.add(rid)
                    if rid not in self._rules_invalid_logged:
                        logger.warning(f"Invalid regex in rule '{name}' (id={rid}): {e}")
                        self._rules_invalid_logged.add(rid)

            # 규칙이 수정/정상화되면 재로그 가능하도록 이전 invalid 집합과 동기화
            self._rules_invalid_logged.intersection_update(invalid_ids)
            self._rules_cache = compiled_rules
            self._rules_cache_dirty = False
            logger.debug("Copy rules cache refreshed")

        applied_count = 0
        for rid, name, compiled, action, replacement, priority in self._rules_cache:
            if not compiled.search(text):
                continue
            if action == "trim":
                text = text.strip()
            elif action == "lowercase":
                text = text.lower()
            elif action == "uppercase":
                text = text.upper()
            elif action == "remove_newlines":
                text = text.replace('\n', ' ').replace('\r', '')
            elif action == "custom_replace":
                text = compiled.sub(replacement, text)
            applied_count += 1
            logger.debug(f"Rule '{name}' applied")

        logger.debug(f"rules_applied_count={applied_count}")
        return text
    
    def invalidate_rules_cache(self):
        """v10.0: 규칙 캐시 무효화 (규칙 변경 시 호출)"""
        self._rules_cache = None
        self._rules_cache_dirty = True
        logger.debug("Copy rules cache invalidated")

    def analyze_text(self, text):
        """텍스트 유형 분석 - 사전 컴파일된 정규식 사용 (성능 최적화)"""
        # URL 패턴 (사전 컴파일된 정규식 사용)
        if RE_URL.match(text): 
            return "LINK"
        # 확장된 색상 패턴 (사전 컴파일된 정규식 사용)
        if RE_HEX_COLOR.match(text): 
            return "COLOR"
        if RE_RGB_COLOR.match(text):
            return "COLOR"
        if RE_HSL_COLOR.match(text):
            return "COLOR"
        # 코드 패턴 (전역 상수 사용)
        if any(x in text for x in CODE_INDICATORS): 
            return "CODE"
        return "TEXT"

    def load_data(self):
        """데이터 로드 및 테이블 갱신 - 리팩토링된 버전"""
        started = time.perf_counter()
        try:
            selected_id = self.get_selected_id()
            items = self._get_display_items()
            self._last_display_count = len(items)
            self._last_search_query = self.search_input.text() if hasattr(self, "search_input") else ""

            if (
                getattr(self, "_last_search_query", "").strip()
                and getattr(self.db, "_last_search_fallback", False)
                and not getattr(self, "_search_fallback_notified", False)
            ):
                self._search_fallback_notified = True
                self.statusBar().showMessage("⚠️ 고급 검색 오류로 일반 검색으로 전환했습니다.", 2500)
            
            # v10.4: 데이터 로드 완료로 플래그 리셋
            self.is_data_dirty = False

            sorting_was_enabled = self.table.isSortingEnabled()
            self.table.setSortingEnabled(False)
            self.table.setUpdatesEnabled(False)
            try:
                blocker = QSignalBlocker(self.table)
                self.table.clearSpans()
                self.table.setRowCount(0)
                theme = THEMES.get(self.current_theme, THEMES["dark"])
            
                if not items:
                    self._show_empty_state(theme)
                else:
                    self._populate_table(items, theme)
                del blocker
            finally:
                self.table.setSortingEnabled(sorting_was_enabled)
                self.table.setUpdatesEnabled(True)

            if items and selected_id:
                self._restore_selection_by_id(selected_id)
            self.update_status_bar()
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            logger.debug(f"load_data_ms={elapsed_ms:.2f} rows={len(items)}")
        except Exception as e:
            logger.exception("Data loading error")

    def _restore_selection_by_id(self, item_id):
        for row in range(self.table.rowCount()):
            pin_item = self.table.item(row, 0)
            if pin_item and pin_item.data(Qt.ItemDataRole.UserRole) == item_id:
                self.table.setCurrentCell(row, 2)
                self.table.selectRow(row)
                return True
        return False

    def on_search_text_changed(self, text):
        # Reset fallback notification on clear, so we can notify again later if needed.
        if not (text or "").strip():
            self._search_fallback_notified = False
        self._search_debounce_timer.start()

    def _get_display_items(self):
        """표시할 항목 조회 및 정렬"""
        query_started = time.perf_counter()
        raw_query = self.search_input.text()
        parsed = parse_search_query(raw_query)

        search_query = parsed.query
        filter_type = self.filter_combo.currentText()
        tag_filter = self.current_tag_filter
        bookmarked = filter_type == "⭐ 북마크"
        collection_id = None
        limit = None

        if parsed.tag:
            tag_filter = parsed.tag

        type_map = {
            "text": "📝 텍스트",
            "image": "🖼️ 이미지",
            "link": "🔗 링크",
            "code": "💻 코드",
            "color": "🎨 색상",
            "file": "📁 파일",
            "all": "전체",
        }
        if parsed.type:
            filter_type = type_map.get(parsed.type, filter_type)

        if parsed.is_pinned:
            filter_type = "📌 고정"
        if parsed.is_bookmark:
            filter_type = "⭐ 북마크"
            bookmarked = True

        if parsed.col:
            try:
                wanted = parsed.col.casefold()
                for cid, cname, cicon, ccolor, _ in self.db.get_collections():
                    if (cname or "").casefold() == wanted:
                        collection_id = cid
                        break
            except Exception:
                collection_id = None

        if parsed.limit:
            limit = int(parsed.limit)

        # 1. DB 조회 (FTS-backed unified search if available)
        if hasattr(self.db, "search_items"):
            items = self.db.search_items(
                search_query,
                type_filter=filter_type,
                tag_filter=tag_filter,
                bookmarked=bookmarked,
                collection_id=collection_id,
                limit=limit,
            )
        else:
            if tag_filter:
                items = self.db.get_items_by_tag(tag_filter)
                if search_query:
                    items = [i for i in items if search_query.lower() in (i[1] or "").lower()]
            elif bookmarked:
                items = self.db.get_bookmarked_items()
                if search_query:
                    items = [i for i in items if search_query.lower() in (i[1] or "").lower()]
            else:
                items = self.db.get_items(search_query, filter_type)
            
        # 2. 정렬 (고정 항목은 항상 상단)
        if items and self.sort_column > 0:
            def get_sort_key(item):
                pid, content, ptype, timestamp, pinned, use_count, pin_order = item
                col = self.sort_column
                if col == 1: return (not pinned, ptype or "")
                elif col == 2: return (not pinned, (content or "").lower())
                elif col == 3: return (not pinned, timestamp or "")
                elif col == 4: return (not pinned, use_count or 0)
                return (not pinned, 0)
            
            reverse = self.sort_order == Qt.SortOrder.DescendingOrder
            items = sorted(items, key=get_sort_key, reverse=reverse)
        
        query_ms = (time.perf_counter() - query_started) * 1000.0
        logger.debug(f"query_ms={query_ms:.2f} rows={len(items)}")
        return items

    def _show_empty_state(self, theme):
        """빈 결과 상태 표시"""
        search_query = self.search_input.text()
        self.table.setRowCount(1)
        
        if search_query:
            empty_msg = f"🔍 '{search_query}'에 대한 검색 결과가 없습니다\n\n다른 검색어를 입력하거나 필터를 변경해보세요"
        elif self.current_tag_filter:
            empty_msg = f"🏷️ '{self.current_tag_filter}' 태그가 없습니다\n\n항목을 선택하고 마우스 오른쪽 버튼으로 태그를 추가하세요"
        else:
            empty_msg = "📋 클립보드 히스토리가 비어있습니다\n\n"
            empty_msg += "💡 시작 방법:\n"
            empty_msg += "• 텍스트나 이미지를 복사하면 자동 저장\n"
            empty_msg += "• Ctrl+Shift+V: 클립보드 창 열기\n"
            empty_msg += "• Alt+V: 미니 창 열기\n"
            empty_msg += "• 더블클릭으로 항목 붙여넣기"
            
        empty_item = QTableWidgetItem(empty_msg)
        empty_item.setForeground(QColor(theme["text_secondary"]))
        empty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_item.setFlags(empty_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.table.setItem(0, 0, empty_item)
        self.table.setSpan(0, 0, 1, 5)
        self.table.setRowHeight(0, 150)

    def _populate_table(self, items, theme):
        """테이블 행 생성"""
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)

        expiry_map = {}
        try:
            if hasattr(self.db, "get_expires_at_map"):
                expiry_map = self.db.get_expires_at_map([row[0] for row in items])
        except Exception:
            expiry_map = {}

        self.table.setRowCount(len(items))
        for row_idx, item_data in enumerate(items):
            pid, content, ptype, timestamp, pinned, use_count, pin_order = item_data
            content_text = content or ""
            
            # 1. 고정 아이콘
            pin_item = QTableWidgetItem("📌" if pinned else "")
            pin_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            pin_item.setData(Qt.ItemDataRole.UserRole, pid)
            if pinned:
                pin_item.setBackground(QColor(theme["primary"]).lighter(170))
            self.table.setItem(row_idx, 0, pin_item)
            
            # 2. 유형
            type_item = QTableWidgetItem(TYPE_ICONS.get(ptype, "📝"))
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            type_item.setToolTip(ptype)
            type_item.setData(Qt.ItemDataRole.UserRole + 1, ptype)
            self.table.setItem(row_idx, 1, type_item)
            
            # 3. 내용
            display = content_text.replace('\n', ' ').strip()
            if len(display) > 45: display = display[:45] + "..."
            expires_at = expiry_map.get(pid)
            if expires_at:
                display = "⏱️ " + display
            content_item = QTableWidgetItem(display)
            
            if ptype == "IMAGE":
                content_item.setToolTip("🖼️ 이미지 항목 - 더블클릭으로 미리보기")
            else:
                tip = content_text[:500] if len(content_text) > 500 else content_text
                if expires_at:
                    tip = f"{tip}\n\n⏱️ 만료: {expires_at}"
                content_item.setToolTip(tip)
                
            if ptype == "LINK": content_item.setForeground(QColor(theme["secondary"]))
            elif ptype == "CODE": content_item.setForeground(QColor(theme["success"]))
            elif ptype == "COLOR": content_item.setForeground(QColor(content_text) if content_text.startswith("#") else QColor(theme["warning"]))
            
            content_item.setData(Qt.ItemDataRole.UserRole + 1, content_text)
            self.table.setItem(row_idx, 2, content_item)
            
            # 4. 시간
            try:
                dt = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                if dt.date() == today: time_str = dt.strftime("%H:%M")
                elif dt.date() == yesterday: time_str = f"어제 {dt.hour}시"
                else: time_str = f"{dt.month}/{dt.day} {dt.hour}시"
            except (ValueError, TypeError):
                time_str = timestamp
            
            time_item = QTableWidgetItem(time_str)
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            time_item.setForeground(QColor(theme["text_secondary"]))
            time_item.setData(Qt.ItemDataRole.UserRole + 1, timestamp)
            self.table.setItem(row_idx, 3, time_item)
            
            # 5. 사용 횟수
            if use_count and use_count >= 10: use_display = f"🔥 {use_count}"
            elif use_count and use_count >= 5: use_display = f"⭐ {use_count}"
            elif use_count: use_display = str(use_count)
            else: use_display = "-"
            
            use_item = QTableWidgetItem(use_display)
            use_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            use_item.setForeground(QColor(theme["text_secondary"]))
            use_item.setData(Qt.ItemDataRole.UserRole + 1, use_count or 0)
            self.table.setItem(row_idx, 4, use_item)


    def on_selection_changed(self):
        # 선택된 항목 수 계산 및 상태바 업데이트
        selected_count = len(self.table.selectionModel().selectedRows())
        self.update_status_bar(selected_count)
        
        pid = self.get_selected_id()
        if not pid:
            self.update_ui_state(False)
            return
            
        data = self.db.get_content(pid)
        if data:
            content, blob, ptype = data
            theme = THEMES.get(self.current_theme, THEMES["dark"])
            
            if ptype == "IMAGE" and blob:
                self.detail_stack.setCurrentIndex(1)
                pixmap = QPixmap()
                pixmap.loadFromData(blob)
                w, h = self.detail_image_lbl.width(), self.detail_image_lbl.height()
                if w > 0 and h > 0:
                    self.detail_image_lbl.setPixmap(pixmap.scaled(QSize(w-10, h-10), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                else:
                    self.detail_image_lbl.setPixmap(pixmap)
                
                self.tools_layout_visible(False)
                self.btn_save_img.setVisible(True)
                
                self.btn_link.setEnabled(False)
                self.btn_google.setEnabled(False)
                if HAS_QRCODE: self.btn_qr.setEnabled(False)
            else:
                self.detail_stack.setCurrentIndex(0)
                self.detail_text.setPlainText(content)
                self.tools_layout_visible(True)
                self.btn_save_img.setVisible(False)
                
                self.btn_link.setEnabled(ptype == "LINK")
                self.btn_google.setEnabled(True)
                if HAS_QRCODE: self.btn_qr.setEnabled(True)
                
                if ptype == "COLOR" and content.startswith("#"):
                    self.detail_text.setStyleSheet(f"background-color: {content}; color: {'black' if self.is_light_color(content) else 'white'};")
                else:
                    self.detail_text.setStyleSheet(f"background-color: {theme['surface_variant']}; color: {theme['text']}; border: 2px solid {theme['border']};")

            self.btn_copy.setEnabled(True)
            self.btn_pin.setEnabled(True)
            self.btn_del.setEnabled(True)
            
            is_pinned = self.table.item(self.table.currentRow(), 0).text() == "📌"
            self.btn_pin.setText("📌 해제" if is_pinned else "📌 고정")

    def is_light_color(self, hex_color):
        """색상이 밝은지 판단"""
        try:
            hex_color = hex_color.lstrip('#')
            if len(hex_color) == 3:
                hex_color = ''.join([c*2 for c in hex_color])
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            return luminance > 0.5
        except (ValueError, IndexError) as e:
            logger.debug(f"Color parse error: {e}")
            return False

    def tools_layout_visible(self, visible):
        self.btn_upper.setVisible(visible)
        self.btn_lower.setVisible(visible)
        self.btn_strip.setVisible(visible)
        self.btn_normalize.setVisible(visible)
        self.btn_json.setVisible(visible)
        self.btn_google.setVisible(visible)
        if HAS_QRCODE: self.btn_qr.setVisible(visible)

    def transform_text(self, mode):
        text = self.detail_text.toPlainText()
        if not text: return
        new_text = text
        mode_text = mode
        
        if mode == "upper": 
            new_text = text.upper()
            mode_text = "대문자"
        elif mode == "lower": 
            new_text = text.lower()
            mode_text = "소문자"
        elif mode == "strip": 
            new_text = " ".join(text.split())
            mode_text = "공백 제거"
        elif mode == "normalize":
            # 줄바꿈 정규화: CRLF→LF, 연속 빈줄 제거, 앞뒤 공백 제거
            new_text = text.replace('\r\n', '\n').replace('\r', '\n')
            lines = new_text.split('\n')
            cleaned = []
            prev_blank = False
            for line in lines:
                is_blank = line.strip() == ''
                if is_blank and prev_blank:
                    continue
                cleaned.append(line.rstrip())
                prev_blank = is_blank
            new_text = '\n'.join(cleaned).strip()
            mode_text = "줄바꿈 정리"
        elif mode == "json":
            try:
                parsed = json.loads(text)
                new_text = json.dumps(parsed, indent=2, ensure_ascii=False)
                mode_text = "JSON 포맷팅"
            except json.JSONDecodeError:
                self.statusBar().showMessage("❌ 유효한 JSON이 아닙니다", 2000)
                return
        
        self.is_internal_copy = True
        self.clipboard.setText(new_text)
        self.detail_text.setPlainText(new_text)
        
        mode_text = {"upper": "대문자", "lower": "소문자", "strip": "공백 제거"}.get(mode, mode)
        self.statusBar().showMessage(f"✅ 변환 완료 ({mode_text})", 2000)

    def copy_item(self):
        pid = self.get_selected_id()
        if not pid: return
        data = self.db.get_content(pid)
        if data:
            content, blob, ptype = data
            self.is_internal_copy = True
            if ptype == "FILE":
                paths = []
                try:
                    paths = self.db.get_file_paths(pid)
                except Exception:
                    paths = []
                if paths:
                    mime = QMimeData()
                    mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
                    mime.setText("\n".join(paths))
                    self.clipboard.setMimeData(mime)
                else:
                    self.clipboard.setText(content)
            elif ptype == "IMAGE" and blob:
                pixmap = QPixmap()
                pixmap.loadFromData(blob)
                self.clipboard.setPixmap(pixmap)
            else:
                self.clipboard.setText(content)
            self.db.increment_use_count(pid)
            
            # 복사 시각 피드백
            rows = self.table.selectionModel().selectedRows()
            if rows:
                row = rows[0].row()
                theme = THEMES.get(self.current_theme, THEMES["dark"])
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item:
                        original_bg = item.background()
                        item.setBackground(QColor(theme["success"]))
                        QTimer.singleShot(300, lambda i=item, bg=original_bg: i.setBackground(bg))
            
            self.statusBar().showMessage("✅ 복사됨", 2000)

    def paste_selected(self):
        """Enter키로 붙여넣기"""
        self.copy_item()
        self.hide()
        QTimer.singleShot(200, lambda: keyboard.send('ctrl+v'))
    
    def on_double_click_paste(self, row, col):
        self.paste_selected()

    def delete_item(self):
        """선택된 항목 삭제 (단일 또는 다중)"""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        
        if len(rows) > 1:
            self.delete_selected_items()
        else:
            pid = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
            if pid:
                self.db.soft_delete(pid)  # v10.0: 휴지통으로 이동
                self.load_data()
                self.update_ui_state(False)
                self.update_status_bar()
    
    def delete_selected_items(self):
        """다중 선택 항목 삭제 (확인 다이얼로그 포함)"""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        
        count = len(rows)
        if count > 1:
            reply = QMessageBox.question(
                self, "다중 삭제 확인",
                f"{count}개의 항목을 삭제하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # 삭제 실행
        for row in rows:
            pid = self.table.item(row.row(), 0).data(Qt.ItemDataRole.UserRole)
            if pid:
                self.db.soft_delete(pid)  # v10.0: 휴지통으로 이동
        
        self.load_data()
        self.update_ui_state(False)
        self.update_status_bar()
        self.statusBar().showMessage(f"✅ {count}개 항목이 삭제되었습니다.", 2000)
    
    def toggle_pin(self):
        pid = self.get_selected_id()
        if pid:
            self.db.toggle_pin(pid)
            self.load_data()
            self.on_selection_changed()
            self.update_status_bar()

    # --- v10.0: 북마크 ---
    def toggle_bookmark(self):
        pid = self.get_selected_id()
        if pid:
            new_status = self.db.toggle_bookmark(pid)
            status_text = "북마크 추가" if new_status else "북마크 해제"
            self.statusBar().showMessage(f"⭐ {status_text}", 2000)
            self.load_data()
    
    # --- v10.0: 메모 ---
    def edit_note(self):
        pid = self.get_selected_id()
        if not pid:
            return
        current_note = self.db.get_note(pid)
        note, ok = QInputDialog.getMultiLineText(
            self, "📝 메모 편집", "이 항목에 대한 메모:", current_note
        )
        if ok:
            self.db.set_note(pid, note)
            self.statusBar().showMessage("📝 메모가 저장되었습니다.", 2000)
    
    # --- v10.0: 컬렉션 ---
    def create_collection(self):
        name, ok = QInputDialog.getText(self, "📁 새 컬렉션", "컬렉션 이름:")
        if ok and name:
            icons = ["📁", "📂", "🗂️", "📦", "💼", "🎯", "⭐", "❤️", "🔖", "📌"]
            icon, _ = QInputDialog.getItem(self, "아이콘 선택", "아이콘:", icons, 0, False)
            self.db.add_collection(name, icon or "📁")
            self.statusBar().showMessage(f"📁 '{name}' 컬렉션이 생성되었습니다.", 2000)
    
    def move_to_collection(self, collection_id):
        pid = self.get_selected_id()
        if pid:
            self.db.move_to_collection(pid, collection_id)
            if collection_id:
                self.statusBar().showMessage("📁 컬렉션으로 이동됨", 2000)
            else:
                self.statusBar().showMessage("🚫 컬렉션에서 제거됨", 2000)
            self.load_data()

    def _bulk_move_to_collection(self, collection_id):
        ids = self.get_selected_ids()
        if not ids:
            return
        try:
            self.db.set_collection_many(ids, collection_id)
        except Exception:
            for pid in ids:
                try:
                    self.db.move_to_collection(pid, collection_id)
                except Exception:
                    pass
        self.load_data()
        self.update_status_bar()

    def _set_item_expiry(self, item_id: int, minutes: int):
        try:
            dt = (datetime.datetime.now() + datetime.timedelta(minutes=int(minutes))).strftime("%Y-%m-%d %H:%M:%S")
            self.db.set_expires_at(int(item_id), dt)
            self.statusBar().showMessage("⏱️ 만료 시간이 설정되었습니다.", 2000)
            self.load_data()
        except Exception as e:
            logger.debug(f"Set expiry failed: {e}")

    def edit_item_content(self):
        pid = self.get_selected_id()
        if not pid:
            return
        data = self.db.get_content(pid)
        if not data:
            return
        content, blob, ptype = data
        if ptype in ["IMAGE", "FILE"]:
            return

        dialog = EditItemDialog(self, content or "")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_text = dialog.get_text()
        if new_text is None:
            return
        new_text = new_text.rstrip("\n")
        if not new_text.strip():
            return

        new_type = None
        if dialog.should_retype():
            try:
                new_type = self.analyze_text(new_text.strip())
            except Exception:
                new_type = None

        self.db.update_item_content(pid, new_text, type_tag=new_type)
        self.statusBar().showMessage("✏️ 항목이 수정되었습니다.", 2000)
        self.load_data()
        self.on_selection_changed()

    def open_link(self):
        text = self.detail_text.toPlainText()
        if text: webbrowser.open(text)

    def update_ui_state(self, enabled):
        self.btn_copy.setEnabled(enabled)
        self.btn_pin.setEnabled(enabled)
        self.btn_del.setEnabled(enabled)
        self.btn_link.setEnabled(False)
        self.tools_layout_visible(False)
        self.btn_save_img.setVisible(False)
        if not enabled:
            self.detail_text.clear()
            self.detail_image_lbl.clear()

    def get_selected_id(self):
        rows = self.table.selectionModel().selectedRows()
        return self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole) if rows else None

    def get_selected_ids(self) -> list[int]:
        rows = self.table.selectionModel().selectedRows()
        ids: list[int] = []
        for r in rows:
            try:
                pid = self.table.item(r.row(), 0).data(Qt.ItemDataRole.UserRole)
            except Exception:
                pid = None
            if pid:
                ids.append(int(pid))
        return ids

    def show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item: return
        
        theme = THEMES.get(self.current_theme, THEMES["dark"])
        menu = QMenu()
        menu.setStyleSheet(f"""
            QMenu {{ background-color: {theme["surface"]}; color: {theme["text"]}; border: 1px solid {theme["border"]}; padding: 5px; }}
            QMenu::item {{ padding: 8px 20px; }}
            QMenu::item:selected {{ background-color: {theme["primary"]}; }}
        """)
        
        copy_action = menu.addAction("📄 복사")
        copy_action.triggered.connect(self.copy_item)
        
        paste_action = menu.addAction("📋 붙여넣기")
        paste_action.triggered.connect(self.paste_selected)
        
        menu.addSeparator()
        
        # 링크 항목인 경우 Open With 서브메뉴 추가
        pid = self.get_selected_id()
        if pid:
            data = self.db.get_content(pid)
            if data and data[2] == "LINK":
                url = data[0]
                open_menu = menu.addMenu("🌐 링크 열기")
                
                open_default = open_menu.addAction("🔗 기본 브라우저로 열기")
                open_default.triggered.connect(lambda: webbrowser.open(url))
                
                open_menu.addSeparator()
                
                copy_url = open_menu.addAction("📋 URL 복사")
                copy_url.triggered.connect(lambda: self.clipboard.setText(url))
                
                search_action = open_menu.addAction("🔍 Google에서 검색")
                search_action.triggered.connect(lambda: webbrowser.open(f"https://www.google.com/search?q={url}"))
                
                menu.addSeparator()

            if data and data[2] == "FILE":
                paths = []
                try:
                    paths = self.db.get_file_paths(pid)
                except Exception:
                    paths = []

                file_menu = menu.addMenu("📁 파일")
                copy_paths = file_menu.addAction("📋 경로만 복사")
                copy_paths.triggered.connect(lambda: self.clipboard.setText("\n".join(paths)))

                open_folder = file_menu.addAction("📂 폴더 열기")

                def _open_parent():
                    if not paths:
                        return
                    p0 = paths[0]
                    try:
                        target = p0
                        if os.path.isfile(p0):
                            target = os.path.dirname(p0)
                        os.startfile(target)
                    except Exception as e:
                        logger.debug(f"Open folder failed: {e}")

                open_folder.triggered.connect(_open_parent)
                menu.addSeparator()
        
        pin_action = menu.addAction("📌 고정/해제")
        pin_action.triggered.connect(self.toggle_pin)
        
        # v10.0: 북마크
        bookmark_action = menu.addAction("⭐ 북마크 토글")
        bookmark_action.triggered.connect(self.toggle_bookmark)
        
        tag_action = menu.addAction("🏷️ 태그 편집")
        tag_action.triggered.connect(self.edit_tag)
        
        # v10.0: 메모
        note_action = menu.addAction("📝 메모 추가/편집")
        note_action.triggered.connect(self.edit_note)
        
        # v10.0: 컬렉션 서브메뉴
        collection_menu = menu.addMenu("📁 컬렉션으로 이동")
        collections = self.db.get_collections()
        if collections:
            for cid, cname, cicon, ccolor, _ in collections:  # created_at 무시
                c_action = collection_menu.addAction(f"{cicon} {cname}")
                c_action.triggered.connect(lambda checked, col_id=cid: self.move_to_collection(col_id))
            collection_menu.addSeparator()
        new_col_action = collection_menu.addAction("➕ 새 컬렉션 만들기")
        new_col_action.triggered.connect(self.create_collection)
        remove_col_action = collection_menu.addAction("🚫 컬렉션에서 제거")
        remove_col_action.triggered.connect(lambda: self.move_to_collection(None))
        
        menu.addSeparator()
        
        # 다중 선택 시 병합 옵션
        selected_count = len(self.table.selectionModel().selectedRows())
        if selected_count >= 2:
            bulk_menu = menu.addMenu("🧰 일괄 작업")

            # Tags
            tag_add = bulk_menu.addAction("🏷️ 태그 추가...")
            tag_remove = bulk_menu.addAction("🏷️ 태그 제거...")

            def _parse_tags(text: str) -> list[str]:
                raw = (text or "").replace("，", ",")
                return [t.strip() for t in raw.split(",") if t.strip()]

            def _bulk_add_tags():
                ids = self.get_selected_ids()
                if not ids:
                    return
                text, ok = QInputDialog.getText(self, "🏷️ 태그 추가", "추가할 태그(쉼표로 구분):")
                if not ok:
                    return
                add_tags = _parse_tags(text)
                if not add_tags:
                    return
                for pid2 in ids:
                    cur = self.db.get_item_tags(pid2) or ""
                    existing = [t.strip() for t in cur.replace("，", ",").split(",") if t.strip()]
                    seen = set(existing)
                    for t in add_tags:
                        if t not in seen:
                            existing.append(t)
                            seen.add(t)
                    self.db.set_item_tags(pid2, ", ".join(existing))
                self.load_data()
                self.update_status_bar()

            def _bulk_remove_tags():
                ids = self.get_selected_ids()
                if not ids:
                    return
                text, ok = QInputDialog.getText(self, "🏷️ 태그 제거", "제거할 태그(쉼표로 구분):")
                if not ok:
                    return
                remove_tags = set(_parse_tags(text))
                if not remove_tags:
                    return
                for pid2 in ids:
                    cur = self.db.get_item_tags(pid2) or ""
                    existing = [t.strip() for t in cur.replace("，", ",").split(",") if t.strip()]
                    kept = [t for t in existing if t not in remove_tags]
                    self.db.set_item_tags(pid2, ", ".join(kept))
                self.load_data()
                self.update_status_bar()

            tag_add.triggered.connect(_bulk_add_tags)
            tag_remove.triggered.connect(_bulk_remove_tags)

            bulk_menu.addSeparator()

            # Bookmark
            bm_on = bulk_menu.addAction("⭐ 북마크 켜기")
            bm_off = bulk_menu.addAction("⭐ 북마크 끄기")
            bm_toggle = bulk_menu.addAction("⭐ 북마크 토글")

            def _bulk_set_bm(value: int):
                ids = self.get_selected_ids()
                if not ids:
                    return
                try:
                    self.db.set_bookmarks(ids, value)
                except Exception:
                    for pid2 in ids:
                        if value:
                            self.db.toggle_bookmark(pid2) if getattr(self.db, "toggle_bookmark", None) else None
                        else:
                            # best-effort: toggle until off is hard; ignore in fallback
                            self.db.toggle_bookmark(pid2) if getattr(self.db, "toggle_bookmark", None) else None
                self.load_data()
                self.update_status_bar()

            def _bulk_toggle_bm():
                ids = self.get_selected_ids()
                if not ids:
                    return
                placeholders = ",".join(["?"] * len(ids))
                with self.db.lock:
                    cur = self.db.conn.cursor()
                    cur.execute(f"SELECT id, bookmark FROM history WHERE id IN ({placeholders})", ids)
                    rows = cur.fetchall()
                to_on = [int(i) for (i, b) in rows if not b]
                to_off = [int(i) for (i, b) in rows if b]
                if to_on:
                    self.db.set_bookmarks(to_on, 1)
                if to_off:
                    self.db.set_bookmarks(to_off, 0)
                self.load_data()
                self.update_status_bar()

            bm_on.triggered.connect(lambda: _bulk_set_bm(1))
            bm_off.triggered.connect(lambda: _bulk_set_bm(0))
            bm_toggle.triggered.connect(_bulk_toggle_bm)

            bulk_menu.addSeparator()

            # Collections
            bulk_col_menu = bulk_menu.addMenu("📁 컬렉션으로 이동")
            collections2 = self.db.get_collections()
            if collections2:
                for cid, cname, cicon, ccolor, _ in collections2:
                    c_action = bulk_col_menu.addAction(f"{cicon} {cname}")
                    c_action.triggered.connect(lambda checked, col_id=cid: self._bulk_move_to_collection(col_id))
                bulk_col_menu.addSeparator()
            remove_col2 = bulk_col_menu.addAction("🚫 컬렉션에서 제거")
            remove_col2.triggered.connect(lambda: self._bulk_move_to_collection(None))

            menu.addSeparator()
            merge_action = menu.addAction(f"🔗 {selected_count}개 병합")
            merge_action.triggered.connect(self.merge_selected)
            menu.addSeparator()

        # v11: single-item actions
        if pid:
            data = self.db.get_content(pid)
            if data and data[2] not in ["IMAGE", "FILE"]:
                edit_action = menu.addAction("✏️ 내용 편집...")
                edit_action.triggered.connect(self.edit_item_content)
                menu.addSeparator()

            expiry_menu = menu.addMenu("⏱️ 만료 설정")
            expiry_menu.addAction("30분").triggered.connect(lambda: self._set_item_expiry(pid, minutes=30))
            expiry_menu.addAction("1시간").triggered.connect(lambda: self._set_item_expiry(pid, minutes=60))
            expiry_menu.addAction("1일").triggered.connect(lambda: self._set_item_expiry(pid, minutes=60 * 24))
            expiry_menu.addAction("7일").triggered.connect(lambda: self._set_item_expiry(pid, minutes=60 * 24 * 7))
            clear_exp = menu.addAction("⏱️ 만료 해제")
            clear_exp.triggered.connect(lambda: self.db.set_expires_at(pid, None))
            menu.addSeparator()
        
        delete_action = menu.addAction("🗑️ 삭제 (휴지통)")
        delete_action.triggered.connect(self.delete_item)
        
        # 텍스트 변환 서브메뉴 (텍스트 항목인 경우)
        if pid:
            data = self.db.get_content(pid)
            if data and data[2] not in ["IMAGE"]:
                menu.addSeparator()
                transform_menu = menu.addMenu("✍️ 텍스트 변환")
                
                upper_action = transform_menu.addAction("ABC 대문자 변환")
                upper_action.triggered.connect(lambda: self.transform_text("upper"))
                
                lower_action = transform_menu.addAction("abc 소문자 변환")
                lower_action.triggered.connect(lambda: self.transform_text("lower"))
                
                strip_action = transform_menu.addAction("✂️ 공백 제거")
                strip_action.triggered.connect(lambda: self.transform_text("strip"))
                
                normalize_action = transform_menu.addAction("📋 줄바꿈 정리")
                normalize_action.triggered.connect(lambda: self.transform_text("normalize"))
                
                json_action = transform_menu.addAction("{ } JSON 포맷팅")
                json_action.triggered.connect(lambda: self.transform_text("json"))
        
        menu.exec(self.table.viewport().mapToGlobal(pos))


if __name__ == "__main__":
    # 전역 예외 처리기
    def global_exception_handler(exctype, value, traceback):
        # KeyboardInterrupt와 SystemExit은 정상 종료 신호이므로 에러 표시 안함
        if issubclass(exctype, (KeyboardInterrupt, SystemExit)):
            sys.__excepthook__(exctype, value, traceback)
            return
        
        logger.error("Uncaught exception", exc_info=(exctype, value, traceback))
        error_msg = f"{exctype.__name__}: {value}"
        
        # GUI가 살아있다면 메시지 박스 표시
        if QApplication.instance():
            QMessageBox.critical(None, "Critical Error", f"An unexpected error occurred:\n{error_msg}")
        
        sys.__excepthook__(exctype, value, traceback)

    sys.excepthook = global_exception_handler

    try:
        # HiDPI 지원
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
        
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        
        font = QFont("Malgun Gothic", 10)
        font.setStyleHint(QFont.StyleHint.SansSerif)
        app.setFont(font)

        # v10.4: CLI 인자 처리
        start_minimized = "--minimized" in sys.argv
        
        window = MainWindow(start_minimized=start_minimized)
        
        if start_minimized:
            # 트레이 실행 알림
            if window.tray_icon:
                window.tray_icon.showMessage(
                    "SmartClipboard Pro", 
                    "백그라운드에서 실행 중입니다.", 
                    QSystemTrayIcon.MessageIcon.Information, 
                    2000
                )
        else:
            window.show()
        
        # 정상 시작 시 이전 에러 로그 삭제
        error_log_path = os.path.join(APP_DIR, "debug_startup_error.log")
        if os.path.exists(error_log_path):
            try:
                os.remove(error_log_path)
                logger.info("이전 에러 로그 정리됨")
            except Exception:
                pass
        
        sys.exit(app.exec())
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        # APP_DIR 기반 절대 경로로 로그 저장 (Windows 시작 시 CWD 문제 해결)
        error_log_path = os.path.join(APP_DIR, "debug_startup_error.log")
        with open(error_log_path, "w", encoding="utf-8") as f:
            f.write(error_msg)
            f.write(f"\nError: {e}")
        # MessageBox로도 표시 시도 (Qt가 로드되었다면)
        try:
            from PyQt6.QtWidgets import QMessageBox
            if not QApplication.instance():
                app = QApplication(sys.argv)
            QMessageBox.critical(None, "Startup Error", f"An error occurred:\n{e}\n\nSee {error_log_path} for details.")
        except Exception:
            print(f"Critical Error:\n{error_msg}")
        
        # 콘솔 창이 바로 꺼지지 않도록 대기
        input("Press Enter to close...")
        sys.exit(1)


