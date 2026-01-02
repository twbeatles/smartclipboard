"""
SmartClipboard Pro v8.0
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
    QSystemTrayIcon, QMenu, QStackedWidget, QSizePolicy, QStyle,
    QMenuBar, QFileDialog, QComboBox, QDialog, QFormLayout, QSpinBox,
    QCheckBox, QTabWidget, QGroupBox, QSlider, QFrame, QInputDialog
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QByteArray, QBuffer, 
    QSettings, QPropertyAnimation, QEasingCurve, QPoint, QEvent
)
from PyQt6.QtGui import (
    QColor, QFont, QIcon, QAction, QPixmap, QImage, QClipboard, 
    QPainter, QBrush, QPen, QKeySequence, QShortcut, QLinearGradient
)

# --- 로깅 설정 ---
LOG_FILE = "clipboard_manager.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- 설정 ---
DB_FILE = "clipboard_history_v6.db"
MAX_HISTORY = 100 
HOTKEY = "ctrl+shift+v"
APP_NAME = "SmartClipboardPro"
ORG_NAME = "MySmartTools"
VERSION = "8.0"

# 기본 핫키 설정
DEFAULT_HOTKEYS = {
    "show_main": "ctrl+shift+v",
    "show_mini": "alt+v",
    "paste_last": "ctrl+shift+z",
}

# --- 테마 정의 ---
# v8.0: hover_bg, hover_text 추가로 호버 시 가독성 보장
THEMES = {
    "dark": {
        "name": "🌙 다크 모드",
        "background": "#1a1a2e",
        "surface": "#16213e",
        "surface_variant": "#0f3460",
        "primary": "#e94560",
        "primary_variant": "#ff6b6b",
        "secondary": "#4ecdc4",
        "text": "#eaeaea",
        "text_secondary": "#a0a0a0",
        "border": "#2a2a4a",
        "success": "#4ade80",
        "warning": "#fbbf24",
        "error": "#ef4444",
        "gradient_start": "#e94560",
        "gradient_end": "#ff6b6b",
        "glow": "rgba(233, 69, 96, 0.3)",
        # 호버 전용 색상
        "hover_bg": "#2a3a5e",
        "hover_text": "#ffffff",
        "selected_text": "#ffffff",
    },
    "light": {
        "name": "☀️ 라이트 모드",
        "background": "#f8fafc",
        "surface": "#ffffff",
        "surface_variant": "#f1f5f9",
        "primary": "#6366f1",
        "primary_variant": "#818cf8",
        "secondary": "#06b6d4",
        "text": "#1e293b",
        "text_secondary": "#64748b",
        "border": "#e2e8f0",
        "success": "#22c55e",
        "warning": "#f59e0b",
        "error": "#ef4444",
        "gradient_start": "#6366f1",
        "gradient_end": "#818cf8",
        "glow": "rgba(99, 102, 241, 0.2)",
        # 호버 전용 색상 - 라이트 모드에서 가독성 보장
        "hover_bg": "#e0e7ff",
        "hover_text": "#1e293b",
        "selected_text": "#ffffff",
    },
    "ocean": {
        "name": "🌊 오션 모드",
        "background": "#0d1f3c",
        "surface": "#152642",
        "surface_variant": "#1e3a5f",
        "primary": "#00e5c7",
        "primary_variant": "#00ffd9",
        "secondary": "#ffb347",
        "text": "#e8f0ff",
        "text_secondary": "#a8c0d8",
        "border": "#2a4a6d",
        "success": "#4ade80",
        "warning": "#fbbf24",
        "error": "#ff6b6b",
        "gradient_start": "#00e5c7",
        "gradient_end": "#00ffd9",
        "glow": "rgba(0, 229, 199, 0.25)",
        # 호버 전용 색상 - 오션 모드 명도 개선
        "hover_bg": "#2a4a6d",
        "hover_text": "#ffffff",
        "selected_text": "#0d1f3c",
    },
    "purple": {
        "name": "💜 퍼플 모드",
        "background": "#13111c",
        "surface": "#1c1a29",
        "surface_variant": "#2a2640",
        "primary": "#a855f7",
        "primary_variant": "#c084fc",
        "secondary": "#f472b6",
        "text": "#e8e8e8",
        "text_secondary": "#9ca3af",
        "border": "#3f3a5a",
        "success": "#4ade80",
        "warning": "#fbbf24",
        "error": "#f87171",
        "gradient_start": "#a855f7",
        "gradient_end": "#f472b6",
        "glow": "rgba(168, 85, 247, 0.3)",
        # 호버 전용 색상
        "hover_bg": "#3d3660",
        "hover_text": "#ffffff",
        "selected_text": "#ffffff",
    },
    "midnight": {
        "name": "🌌 미드나잇",
        "background": "#0f0f1a",
        "surface": "#1a1a2e",
        "surface_variant": "#252545",
        "primary": "#00d9ff",
        "primary_variant": "#00f5ff",
        "secondary": "#ff6b9d",
        "text": "#ffffff",
        "text_secondary": "#b0b0c0",
        "border": "#303050",
        "success": "#00ff88",
        "warning": "#ffcc00",
        "error": "#ff4466",
        "gradient_start": "#00d9ff",
        "gradient_end": "#00f5ff",
        "glow": "rgba(0, 217, 255, 0.25)",
        # 호버 전용 색상
        "hover_bg": "#353565",
        "hover_text": "#ffffff",
        "selected_text": "#0f0f1a",
    }
}

# --- 데이터베이스 클래스 ---
class ClipboardDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.lock = threading.Lock()
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
            self.conn.commit()
            logger.info("DB 테이블 초기화 완료 (v8.0)")
        except sqlite3.Error as e:
            logger.error(f"DB Init Error: {e}")

    def add_item(self, content, image_data, type_tag):
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
                self.cleanup()
                logger.debug(f"항목 추가: {type_tag}")
                return True
            except sqlite3.Error as e:
                logger.error(f"DB Add Error: {e}")
                self.conn.rollback()
                return False

    def get_items(self, search_query="", type_filter="전체"):
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
                elif type_filter != "전체":
                    tag_map = {"텍스트": "TEXT", "이미지": "IMAGE", "링크": "LINK", "코드": "CODE", "색상": "COLOR"}
                    target_tag = tag_map.get(type_filter, "TEXT")
                    sql += " AND type = ?"
                    params.append(target_tag)

                sql += " ORDER BY pinned DESC, pin_order ASC, id DESC"
                cursor.execute(sql, params)
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.error(f"DB Get Error: {e}")
                return []

    def toggle_pin(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT pinned FROM history WHERE id=?", (item_id,))
                current = cursor.fetchone()
                if current:
                    new_status = 0 if current[0] else 1
                    cursor.execute("UPDATE history SET pinned = ? WHERE id = ?", (new_status, item_id))
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
            except sqlite3.Error as e:
                logger.error(f"Snippet Delete Error: {e}")

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

    def cleanup(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM history WHERE pinned = 0")
            result = cursor.fetchone()
            if not result: return
            
            count = result[0]
            if count > MAX_HISTORY:
                diff = count - MAX_HISTORY
                cursor.execute(f"DELETE FROM history WHERE id IN (SELECT id FROM history WHERE pinned = 0 ORDER BY id ASC LIMIT {diff})")
                self.conn.commit()
                logger.info(f"오래된 항목 {diff}개 정리")
        except sqlite3.Error as e:
            logger.error(f"DB Cleanup Error: {e}")

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

    def get_items_by_tag(self, tag):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT id, content, type, timestamp, pinned, use_count, pin_order FROM history WHERE tags LIKE ? ORDER BY pinned DESC, pin_order ASC, id DESC", (f"%{tag}%",))
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
    
    def toggle_copy_rule(self, rule_id, enabled):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE copy_rules SET enabled = ? WHERE id = ?", (enabled, rule_id))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Rule Toggle Error: {e}")
    
    def delete_copy_rule(self, rule_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM copy_rules WHERE id = ?", (rule_id,))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Rule Delete Error: {e}")
    
    def update_pin_order(self, item_id, new_order):
        """고정 항목 순서 업데이트"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE history SET pin_order = ? WHERE id = ?", (new_order, item_id))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Pin Order Update Error: {e}")

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
    
    def delete_clipboard_action(self, action_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM clipboard_actions WHERE id = ?", (action_id,))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Action Delete Error: {e}")
    
    # --- v8.0: URL 제목 캐시 ---
    def update_url_title(self, item_id, title):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE history SET url_title = ? WHERE id = ?", (title, item_id))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"URL Title Update Error: {e}")

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
        """보관함 잠금 해제"""
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
        except Exception as e:
            logger.debug(f"Vault unlock failed: {e}")
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
class ClipboardActionManager:
    """복사된 내용에 따라 자동 액션을 수행하는 관리자"""
    
    def __init__(self, db):
        self.db = db
        self.actions_cache = []
        self.reload_actions()
    
    def reload_actions(self):
        """액션 규칙 캐시 갱신"""
        self.actions_cache = self.db.get_clipboard_actions()
    
    def process(self, text, item_id=None):
        """텍스트에 매칭되는 액션 실행"""
        results = []
        for action in self.actions_cache:
            aid, name, pattern, action_type, params_json, enabled, priority = action
            if not enabled:
                continue
            try:
                if re.search(pattern, text):
                    params = json.loads(params_json) if params_json else {}
                    result = self.execute_action(action_type, text, params, item_id)
                    if result:
                        results.append((name, result))
            except re.error as e:
                logger.warning(f"Invalid regex in action '{name}': {e}")
        return results
    
    def execute_action(self, action_type, text, params, item_id):
        """액션 실행"""
        if action_type == "fetch_title":
            return self.fetch_url_title(text, item_id)
        elif action_type == "format_phone":
            return self.format_phone(text)
        elif action_type == "format_email":
            return self.format_email(text)
        elif action_type == "notify":
            return {"type": "notify", "message": params.get("message", "패턴 매칭됨")}
        elif action_type == "transform":
            return self.transform_text(text, params.get("mode", "trim"))
        return None
    
    def fetch_url_title(self, url, item_id):
        """URL에서 제목 가져오기"""
        if not HAS_WEB:
            return None
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.string if soup.title else None
            if title and item_id:
                self.db.update_url_title(item_id, title.strip())
            return {"type": "title", "title": title.strip() if title else None}
        except Exception as e:
            logger.debug(f"Fetch title error: {e}")
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
        """JSON으로 내보내기"""
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
                    type_icon = {"TEXT": "📝", "LINK": "🔗", "CODE": "💻", "COLOR": "🎨", "FILE": "📁"}.get(ptype, "📝")
                    
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
        """JSON에서 가져오기"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            imported = 0
            for item in data.get("items", []):
                content = item.get("content", "")
                ptype = item.get("type", "TEXT")
                if content:
                    self.db.add_item(content, None, ptype)
                    imported += 1
            return imported
        except Exception as e:
            logger.error(f"JSON Import Error: {e}")
            return -1
    
    def import_csv(self, path):
        """CSV에서 가져오기"""
        try:
            imported = 0
            with open(path, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                next(reader)  # 헤더 건너뛰기
                for row in reader:
                    if len(row) >= 2:
                        content, ptype = row[0], row[1]
                        if content:
                            self.db.add_item(content, None, ptype)
                            imported += 1
            return imported
        except Exception as e:
            logger.error(f"CSV Import Error: {e}")
            return -1
class HotkeyListener(QThread):
    show_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._running = True

    def run(self):
        try:
            keyboard.add_hotkey(HOTKEY, self.show_signal.emit)
            while self._running:
                time.sleep(0.1)
        except Exception as e:
            logger.error(f"Hotkey Error: {e}")

    def stop(self):
        self._running = False
        try:
            keyboard.remove_hotkey(HOTKEY)
        except Exception as e:
            logger.debug(f"Hotkey remove: {e}")


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
            # 최초 설정
            if len(password) < 4:
                QMessageBox.warning(self, "경고", "비밀번호는 최소 4자 이상이어야 합니다.")
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
        """새 액션 추가"""
        name, ok = QInputDialog.getText(self, "액션 추가", "액션 이름:")
        if not ok or not name.strip():
            return
        
        pattern, ok = QInputDialog.getText(self, "액션 추가", "패턴 (정규식):", text="https?://")
        if not ok or not pattern.strip():
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
        self.format_json.setChecked(True)
        format_layout.addWidget(self.format_json)
        format_layout.addWidget(self.format_csv)
        format_layout.addWidget(self.format_md)
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
        path, _ = QFileDialog.getOpenFileName(self, "파일 선택", "", "지원 파일 (*.json *.csv);;JSON (*.json);;CSV (*.csv)")
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
        else:
            QMessageBox.warning(self, "경고", "지원하지 않는 파일 형식입니다.")
            return
        
        if count >= 0:
            QMessageBox.information(self, "완료", f"✅ {count}개 항목을 가져왔습니다.")
            self.accept()
        else:
            QMessageBox.critical(self, "오류", "가져오기에 실패했습니다.")


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
        # 메인 컨테이너
        container = QFrame(self)
        container.setObjectName("MiniContainer")
        container.setStyleSheet("""
            QFrame#MiniContainer {
                background-color: rgba(26, 26, 46, 0.95);
                border-radius: 12px;
                border: 1px solid #2a2a4a;
            }
            QLabel { color: #eaeaea; }
            QListWidget {
                background-color: transparent;
                border: none;
                color: #eaeaea;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 6px;
                margin: 2px;
            }
            QListWidget::item:hover {
                background-color: rgba(233, 69, 96, 0.3);
            }
            QListWidget::item:selected {
                background-color: #e94560;
            }
            QPushButton {
                background-color: #16213e;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                color: #eaeaea;
            }
            QPushButton:hover {
                background-color: #e94560;
            }
        """)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # 헤더
        header = QHBoxLayout()
        title = QLabel("📋 빠른 클립보드")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.clicked.connect(self.hide)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(btn_close)
        layout.addLayout(header)
        
        # 리스트
        from PyQt6.QtWidgets import QListWidget, QListWidgetItem
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.list_widget)
        
        # 버튼
        btn_layout = QHBoxLayout()
        btn_refresh = QPushButton("🔄")
        btn_refresh.setToolTip("새로고침")
        btn_refresh.clicked.connect(self.load_items)
        btn_main = QPushButton("📋 메인 창")
        btn_main.clicked.connect(self.open_main_window)
        btn_layout.addWidget(btn_refresh)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_main)
        layout.addLayout(btn_layout)
        
        # 메인 레이아웃
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)
    
    def load_items(self):
        """최근 10개 항목 로드"""
        from PyQt6.QtWidgets import QListWidgetItem
        self.list_widget.clear()
        items = self.db.get_items("", "전체")[:10]
        
        type_icons = {"TEXT": "📝", "LINK": "🔗", "IMAGE": "🖼️", "CODE": "💻", "COLOR": "🎨", "FILE": "📁"}
        
        for pid, content, ptype, timestamp, pinned, use_count, pin_order in items:
            icon = type_icons.get(ptype, "📝")
            pin_mark = "📌 " if pinned else ""
            display = content.replace('\n', ' ')[:35] + ("..." if len(content) > 35 else "")
            
            item = QListWidgetItem(f"{pin_mark}{icon} {display}")
            item.setData(Qt.ItemDataRole.UserRole, pid)
            item.setToolTip(content[:200])
            self.list_widget.addItem(item)
    
    def on_item_double_clicked(self, item):
        """항목 더블클릭 - 복사 후 숨기기"""
        pid = item.data(Qt.ItemDataRole.UserRole)
        if pid:
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
        name = self.name_input.text().strip()
        content = self.content_input.toPlainText().strip()
        category = self.category_input.currentText()
        
        if not name or not content:
            QMessageBox.warning(self, "경고", "이름과 내용을 입력해주세요.")
            return
        
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
        
        # 하단 버튼
        bottom_layout = QHBoxLayout()
        btn_use = QPushButton("📋 사용")
        btn_use.clicked.connect(self.use_snippet)
        btn_delete = QPushButton("🗑️ 삭제")
        btn_delete.clicked.connect(self.delete_snippet)
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.close)
        
        bottom_layout.addWidget(btn_use)
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
    
    def toggle_rule(self, rule_id, state):
        self.db.toggle_copy_rule(rule_id, 1 if state else 0)
    
    def delete_rule(self):
        rows = self.table.selectionModel().selectedRows()
        if rows:
            rid = self.table.item(rows[0].row(), 1).data(Qt.ItemDataRole.UserRole)
            self.db.delete_copy_rule(rid)
            self.load_rules()


# --- 메인 윈도우 ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
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
            
            self.settings = QSettings(ORG_NAME, APP_NAME)
            self.current_theme = self.db.get_setting("theme", "dark")
            
            self.setWindowTitle(f"스마트 클립보드 프로 v{VERSION}")
            self.restore_window_state()
            
            self.app_icon = self.create_app_icon()
            self.setWindowIcon(self.app_icon)
            
            self.always_on_top = True
            self.current_tag_filter = None  # 태그 필터
            self.sort_column = 3  # 기본 정렬: 시간 컨럼
            self.sort_order = Qt.SortOrder.DescendingOrder  # 기본: 내림차순
            
            self.apply_theme()
            self.init_menu()
            self.init_ui()
            self.init_tray()
            self.init_shortcuts()
            
            # v8.0: 플로팅 미니 창
            self.mini_window = FloatingMiniWindow(self.db, self)
            
            # 핫키 설정 로드 및 등록
            self.register_hotkeys()
            
            self.update_always_on_top()
            self.load_data()
            self.update_status_bar()
            
            # v8.0: 보관함 자동 잠금 타이머
            self.vault_timer = QTimer(self)
            self.vault_timer.timeout.connect(self.check_vault_timeout)
            self.vault_timer.start(60000)  # 1분마다 체크
            
            logger.info("SmartClipboard Pro v8.0 started")
        except Exception as e:
            logger.error(f"MainWindow Init Error: {e}", exc_info=True)
            raise e
    
    def register_hotkeys(self):
        """v8.0: 커스텀 핫키 등록"""
        try:
            hotkeys = json.loads(self.db.get_setting("hotkeys", json.dumps(DEFAULT_HOTKEYS)))
            
            self.hotkey_thread = HotkeyListener()
            self.hotkey_thread.show_signal.connect(self.show_window_from_tray)
            self.hotkey_thread.start()
            
            # 미니 창 핫키
            mini_key = hotkeys.get("show_mini", "alt+v")
            keyboard.add_hotkey(mini_key, self.toggle_mini_window)
            
            # 마지막 항목 즉시 붙여넣기 핫키
            paste_key = hotkeys.get("paste_last", "ctrl+shift+z")
            keyboard.add_hotkey(paste_key, self.paste_last_item)
            
        except Exception as e:
            logger.warning(f"Hotkey registration error: {e}")
    
    def toggle_mini_window(self):
        """미니 창 토글"""
        if self.mini_window.isVisible():
            self.mini_window.hide()
        else:
            # 커서 위치 근처에 표시
            from PyQt6.QtGui import QCursor
            cursor_pos = QCursor.pos()
            self.mini_window.move(cursor_pos.x() - 150, cursor_pos.y() - 200)
            self.mini_window.show()
            self.mini_window.activateWindow()
    
    def paste_last_item(self):
        """마지막 항목 즉시 붙여넣기"""
        items = self.db.get_items("", "전체")
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
    
    def check_vault_timeout(self):
        """보관함 자동 잠금 체크"""
        if self.vault_manager.check_timeout():
            logger.info("Vault auto-locked due to inactivity")

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
        try:
            self.hotkey_thread.stop()
            self.hotkey_thread.wait(1000)  # 최대 1초 대기
            keyboard.unhook_all()
        except Exception as e:
            logger.warning(f"Cleanup warning: {e}")
        self.db.close()
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
        """데이터베이스 복원"""
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
                # 연결 재수립 시도
                self.db = ClipboardDB()

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
        style = f"""
        QMainWindow {{ 
            background-color: {theme["background"]}; 
        }}
        QMenuBar {{ 
            background-color: {theme["surface"]}; 
            color: {theme["text"]}; 
            font-family: 'Malgun Gothic'; 
            padding: 4px;
        }}
        QMenuBar::item:selected {{ 
            background-color: {theme["primary"]}; 
            border-radius: 4px;
        }}
        QMenu {{ 
            background-color: {theme["surface"]}; 
            color: {theme["text"]}; 
            border: 1px solid {theme["border"]}; 
            font-family: 'Malgun Gothic'; 
            padding: 5px;
        }}
        QMenu::item {{ 
            padding: 8px 20px; 
            border-radius: 4px;
        }}
        QMenu::item:selected {{ 
            background-color: {theme["primary"]}; 
        }}
        
        QWidget {{ 
            color: {theme["text"]}; 
            font-family: 'Malgun Gothic'; 
            font-size: 13px; 
        }}
        
        QLineEdit, QComboBox {{ 
            background-color: {theme["surface_variant"]}; 
            border: 2px solid {theme["border"]}; 
            border-radius: 12px; 
            padding: 8px 16px; 
            color: {theme["text"]}; 
            selection-background-color: {theme["primary"]};
        }}
        QLineEdit:focus, QComboBox:focus {{ 
            border: 2px solid {theme["primary"]}; 
        }}
        QComboBox::drop-down {{ 
            border: none; 
            padding-right: 10px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {theme["surface"]};
            border: 1px solid {theme["border"]};
            selection-background-color: {theme["primary"]};
        }}
        
        QTableWidget {{ 
            background-color: {theme["surface"]}; 
            border: none; 
            border-radius: 8px;
            selection-background-color: {theme["primary"]}; 
            gridline-color: transparent;
            outline: none;
        }}
        QTableWidget::item {{
            padding: 8px;
            border-bottom: 1px solid {theme["border"]};
            color: {theme["text"]};
        }}
        QTableWidget::item:selected {{
            background-color: {theme["primary"]};
            color: {theme.get("selected_text", "#ffffff")};
        }}
        QTableWidget::item:hover:!selected {{
            background-color: {theme.get("hover_bg", theme["surface_variant"])};
            color: {theme.get("hover_text", theme["text"])};
        }}
        QHeaderView::section {{ 
            background-color: {theme["surface_variant"]}; 
            padding: 10px; 
            border: none; 
            font-weight: bold; 
            color: {theme["text_secondary"]}; 
        }}
        
        QTextEdit {{ 
            background-color: {theme["surface_variant"]}; 
            border: 2px solid {theme["border"]}; 
            border-radius: 8px; 
            padding: 12px; 
            font-family: 'Consolas', 'Malgun Gothic', monospace; 
            font-size: 14px;
            selection-background-color: {theme["primary"]};
        }}
        
        QLabel#ImagePreview {{
            background-color: {theme["surface_variant"]}; 
            border: 2px solid {theme["border"]}; 
            border-radius: 12px;
        }}
        
        QPushButton {{ 
            background-color: {theme["surface_variant"]}; 
            border: 1px solid {theme["border"]}; 
            border-radius: 10px; 
            padding: 10px 18px; 
            color: {theme["text"]}; 
            font-weight: 600;
            font-size: 13px;
        }}
        QPushButton:hover {{ 
            background-color: {theme["primary"]}; 
            border-color: {theme["primary"]};
            color: white;
        }}
        QPushButton:pressed {{ 
            background-color: {theme["primary_variant"]}; 
        }}
        QPushButton:disabled {{
            background-color: {theme["surface"]};
            color: {theme["text_secondary"]};
            border-color: {theme["border"]};
        }}
        
        QPushButton#PrimaryBtn {{
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {theme.get("gradient_start", theme["primary"])}, stop:1 {theme.get("gradient_end", theme["primary_variant"])});
            color: white;
            border: none;
            font-weight: bold;
        }}
        QPushButton#PrimaryBtn:hover {{
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {theme.get("gradient_end", theme["primary_variant"])}, stop:1 {theme.get("gradient_start", theme["primary"])});
        }}
        
        QPushButton#ToolBtn {{
            background-color: {theme["surface"]}; 
            font-size: 12px; 
            padding: 8px 14px;
            border-radius: 8px;
            border: 1px solid {theme["border"]};
        }}
        QPushButton#ToolBtn:hover {{
            background-color: {theme["secondary"]};
            border-color: {theme["secondary"]};
            color: white;
        }}
        
        QPushButton#DeleteBtn {{ 
            background-color: {theme["error"]}; 
            color: white;
            border: none;
        }}
        QPushButton#DeleteBtn:hover {{ 
            background-color: #dc2626; 
        }}
        
        /* v8.0 Enhanced Card Style */
        QPushButton#CardBtn {{
            background-color: {theme["surface"]};
            border: 1px solid {theme["border"]};
            border-radius: 12px;
            padding: 12px 16px;
            text-align: left;
        }}
        QPushButton#CardBtn:hover {{
            background-color: {theme["surface_variant"]};
            border-color: {theme["primary"]};
        }}
        
        QSplitter::handle {{
            background-color: {theme["border"]};
            height: 2px;
        }}
        
        QStatusBar {{
            background-color: {theme["surface"]};
            color: {theme["text_secondary"]};
            border-top: 1px solid {theme["border"]};
        }}
        
        QTabWidget::pane {{
            border: 1px solid {theme["border"]};
            border-radius: 8px;
            background-color: {theme["surface"]};
        }}
        QTabBar::tab {{
            background-color: {theme["surface_variant"]};
            color: {theme["text_secondary"]};
            padding: 10px 20px;
            margin-right: 2px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        }}
        QTabBar::tab:selected {{
            background-color: {theme["primary"]};
            color: white;
        }}
        
        QScrollBar:vertical {{
            background-color: {theme["surface"]};
            width: 10px;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {theme["border"]};
            border-radius: 5px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {theme["primary"]};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        """
        self.setStyleSheet(style)

        QShortcut(QKeySequence("Escape"), self, self.hide)
        QShortcut(QKeySequence("Ctrl+F"), self, lambda: self.search_input.setFocus())
        QShortcut(QKeySequence("Delete"), self, self.delete_item)
        QShortcut(QKeySequence("Shift+Delete"), self, self.delete_selected_items)  # 다중 삭제
        QShortcut(QKeySequence("Ctrl+P"), self, self.toggle_pin)
        QShortcut(QKeySequence("Return"), self, self.paste_selected)
        QShortcut(QKeySequence("Ctrl+C"), self, self.copy_item)

    def eventFilter(self, source, event):
        """드래그 앤 드롭 이벤트 처리 (고정 항목 순서 변경)"""
        if source == self.table.viewport() and event.type() == QEvent.Type.Drop:
            # 드롭 위치 확인
            target_row = self.table.rowAt(event.position().y())
            if target_row == -1:
                return False
                
            # 선택된 행 (드래그 중인 행)
            selected_rows = self.table.selectionModel().selectedRows()
            if not selected_rows:
                return False
            source_row = selected_rows[0].row()
            
            if source_row == target_row:
                return False
            
            # 고정 항목끼리만 이동 가능
            source_item = self.table.item(source_row, 0)
            target_item = self.table.item(target_row, 0)
            
            # 📌 표시가 있는지 확인
            is_source_pinned = source_item.text() == "📌"
            is_target_pinned = target_item.text() == "📌"
            
            if is_source_pinned and is_target_pinned:
                # DB 업데이트 로직
                source_pid = source_item.data(Qt.ItemDataRole.UserRole)
                target_pid = target_item.data(Qt.ItemDataRole.UserRole)
                
                # 순서 swap 또는 재정렬
                # 간단하게: source를 target 위치로 이동하고, 나머지를 밀어내는 방식
                # 여기서는 간단히 두 항목의 pin_order를 교체하는 것이 아니라,
                # 전체 핀 목록을 가져와서 재정렬하는 것이 안전함.
                
                # 현재 고정된 항목들의 ID 목록 가져오기 (화면 순서대로)
                pinned_ids = []
                for row in range(self.table.rowCount()):
                    item = self.table.item(row, 0)
                    if item.text() == "📌":
                        pinned_ids.append(item.data(Qt.ItemDataRole.UserRole))
                
                if source_pid in pinned_ids:
                    pinned_ids.remove(source_pid)
                    # 타겟 위치 계산 (위로 드래그 vs 아래로 드래그)
                    # row 인덱스 기준이므로 pinned_ids 내에서의 인덱스를 찾아야 함
                    
                    # 타겟 row가 pinned_ids에서 몇 번째인지 찾기
                    target_idx = -1
                    current_row = 0
                    for pid in pinned_ids: # source가 빠진 상태
                        # 원래 테이블에서의 row를 찾아야 정확하지만, 
                        # 여기서는 화면상의 타겟 row가 몇번째 핀인지 추정
                        pass
                        
                    # 간단한 방법: 화면상 타겟 row가 전체 핀 중 몇 번째인지 확인
                    pin_count = 0
                    insert_idx = 0
                    for r in range(self.table.rowCount()):
                        if r == target_row:
                            insert_idx = pin_count
                            break
                        if r == source_row: 
                            continue # 자기 자신은 건너뜀
                        if self.table.item(r, 0).text() == "📌":
                            pin_count += 1
                            
                    if source_row > target_row: # 아래에서 위로
                        pinned_ids.insert(insert_idx, source_pid)
                    else: # 위에서 아래로
                        pinned_ids.insert(insert_idx + 1, source_pid)

                    # DB 업데이트
                    for idx, pid in enumerate(pinned_ids):
                        self.db.update_pin_order(pid, idx)
                    
                    # 딜레이 후 리로드 (드롭 애니메이션 간섭 방지)
                    QTimer.singleShot(50, self.load_data)
                    return True # 이벤트 소비 (기본 동작 막기)
            
        return super().eventFilter(source, event)

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
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        # 상단 필터/검색 영역
        top_layout = QHBoxLayout()
        top_layout.setSpacing(10)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["전체", "📌 고정", "텍스트", "이미지", "링크", "코드", "색상"])
        self.filter_combo.setFixedWidth(130)
        self.filter_combo.currentTextChanged.connect(self.load_data)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 검색어 입력 (Ctrl+F)")
        self.search_input.textChanged.connect(self.load_data)
        self.search_input.setClearButtonEnabled(True)
        
        # 태그 필터 버튼
        self.btn_tag_filter = QPushButton("🏷️")
        self.btn_tag_filter.setToolTip("태그 필터")
        self.btn_tag_filter.setFixedWidth(40)
        self.btn_tag_filter.clicked.connect(self.show_tag_filter_menu)
        
        top_layout.addWidget(self.filter_combo)
        top_layout.addWidget(self.search_input)
        top_layout.addWidget(self.btn_tag_filter)
        main_layout.addLayout(top_layout)

        # 메인 스플리터
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 테이블
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["📌", "유형", "내용", "시간", "사용"])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        
        self.table.setColumnWidth(0, 35)
        self.table.setColumnWidth(1, 55)
        self.table.setColumnWidth(3, 90)  # 시간 컨럼 넓이 증가 (12/25 13시 표시)
        self.table.setColumnWidth(4, 45)
        
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        
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
        self.table.setDragEnabled(True)
        self.table.setAcceptDrops(True)
        self.table.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.table.setDefaultDropAction(Qt.DropAction.MoveAction)
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
        self.btn_google.clicked.connect(self.search_google)
        
        self.btn_qr = QPushButton("📱 QR")
        self.btn_qr.setObjectName("ToolBtn")
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
        self.tools_layout.addWidget(self.btn_upper)
        self.tools_layout.addWidget(self.btn_lower)
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

        # 하단 액션 버튼
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.btn_copy = QPushButton("📄 복사")
        self.btn_copy.setMinimumHeight(44)
        self.btn_copy.setObjectName("PrimaryBtn")
        self.btn_copy.clicked.connect(self.copy_item)
        
        self.btn_link = QPushButton("🔗 링크 열기")
        self.btn_link.setMinimumHeight(44)
        self.btn_link.clicked.connect(self.open_link)
        
        self.btn_pin = QPushButton("📌 고정")
        self.btn_pin.setMinimumHeight(44)
        self.btn_pin.clicked.connect(self.toggle_pin)
        
        self.btn_del = QPushButton("🗑 삭제")
        self.btn_del.setMinimumHeight(44)
        self.btn_del.setObjectName("DeleteBtn")
        self.btn_del.clicked.connect(self.delete_item)

        btn_layout.addWidget(self.btn_copy, 2)
        btn_layout.addWidget(self.btn_link, 2)
        btn_layout.addWidget(self.btn_pin, 1)
        btn_layout.addWidget(self.btn_del, 1)
        detail_layout.addLayout(btn_layout)

        splitter.addWidget(detail_container)
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 4)
        main_layout.addWidget(splitter)
        
        self.update_ui_state(False)

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
        
        quit_action = QAction("❌ 종료", self)
        quit_action.triggered.connect(self.quit_app)
        
        self.tray_menu.addAction(show_action)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.tray_privacy_action)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def init_shortcuts(self):
        """앱 내 키보드 단축키 설정"""
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
        # 프라이버시 모드 표시
        if self.is_privacy_mode:
            self.statusBar().showMessage("🔒 프라이버시 모드 활성화됨 (클립보드 기록 중지)")
            return
            
        stats = self.db.get_statistics()
        
        # 기본 통계
        status_parts = [f"📊 총 {stats['total']}개", f"📌 고정 {stats['pinned']}개"]
        
        # 현재 필터 상태
        current_filter = self.filter_combo.currentText() if hasattr(self, 'filter_combo') else "전체"
        if current_filter != "전체":
            status_parts.append(f"🔍 {current_filter}")
        
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
                    exe_path = f'"{sys.executable}"'
                else:
                    python_exe = sys.executable.replace("python.exe", "pythonw.exe")
                    script_path = os.path.abspath(__file__)
                    exe_path = f'"{python_exe}" "{script_path}"'
                
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
                self.statusBar().showMessage("✅ 시작 시 자동 실행 설정됨", 2000)
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                    self.statusBar().showMessage("✅ 자동 실행 해제됨", 2000)
                except WindowsError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            logger.error(f"레지스트리 설정 실패: {e}")
            QMessageBox.critical(self, "오류", f"레지스트리 설정 실패: {e}")
            self.action_startup.setChecked(not enable)

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
            url = f"https://www.google.com/search?q={text}"
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
        """클립보드 변경 감지"""
        # 프라이버시 모드나 내부 복사면 무시
        if self.is_privacy_mode or self.is_internal_copy:
            self.is_internal_copy = False # 내부 복사 플래그는 한 번 사용 후 초기화
            return
            
        QTimer.singleShot(100, self.process_clipboard)

    def process_clipboard(self):
        try:
            mime_data = self.clipboard.mimeData()
            if mime_data.hasImage():
                image = self.clipboard.image()
                if not image.isNull():
                    ba = QByteArray()
                    buffer = QBuffer(ba)
                    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
                    image.save(buffer, "PNG")
                    blob_data = ba.data()
                    if self.db.add_item("[이미지 캡처됨]", blob_data, "IMAGE"):
                        self.load_data()
                        self.update_status_bar()
                return
            if mime_data.hasText():
                text = mime_data.text().strip()
                if not text: return
                
                # 복사 규칙 적용
                text = self.apply_copy_rules(text)
                
                tag = self.analyze_text(text)
                if self.db.add_item(text, None, tag):
                    self.load_data()
                    self.update_status_bar()
        except Exception as e:
            logger.debug(f"Clipboard access: {e}")

    def apply_copy_rules(self, text):
        """활성화된 복사 규칙 적용"""
        rules = self.db.get_copy_rules()
        for rule in rules:
            rid, name, pattern, action, replacement, enabled, priority = rule
            if not enabled:
                continue
            try:
                if re.search(pattern, text):
                    if action == "trim":
                        text = text.strip()
                    elif action == "lowercase":
                        text = text.lower()
                    elif action == "uppercase":
                        text = text.upper()
                    elif action == "remove_newlines":
                        text = text.replace('\n', ' ').replace('\r', '')
                    elif action == "custom_replace" and replacement:
                        text = re.sub(pattern, replacement, text)
                    logger.debug(f"Rule '{name}' applied")
            except re.error as e:
                logger.warning(f"Invalid regex in rule '{name}': {e}")
        return text

    def analyze_text(self, text):
        # URL 패턴
        if re.match(r'https?://', text): 
            return "LINK"
        # 확장된 색상 패턴
        if re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', text): 
            return "COLOR"
        if re.match(r'^rgb\s*\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)$', text, re.I):
            return "COLOR"
        if re.match(r'^hsl\s*\(\s*\d+\s*,\s*\d+%?\s*,\s*\d+%?\s*\)$', text, re.I):
            return "COLOR"
        # 코드 패턴
        code_indicators = ["def ", "class ", "function ", "const ", "let ", "var ", "{", "}", "=>", "import ", "from "]
        if any(x in text for x in code_indicators): 
            return "CODE"
        return "TEXT"

    def load_data(self):
        search_query = self.search_input.text()
        filter_type = self.filter_combo.currentText()
        
        # 태그 필터 적용
        if self.current_tag_filter:
            items = self.db.get_items_by_tag(self.current_tag_filter)
            # 추가 필터 적용
            if search_query:
                items = [i for i in items if search_query.lower() in (i[1] or '').lower()]
        else:
            items = self.db.get_items(search_query, filter_type)
        
        # 정렬 적용 (고정 항목은 항상 상단)
        if items and self.sort_column > 0:
            def get_sort_key(item):
                pid, content, ptype, timestamp, pinned, use_count, pin_order = item
                col = self.sort_column
                if col == 1:  # 유형
                    return (not pinned, ptype or "")
                elif col == 2:  # 내용
                    return (not pinned, (content or "").lower())
                elif col == 3:  # 시간
                    return (not pinned, timestamp or "")
                elif col == 4:  # 사용
                    return (not pinned, use_count or 0)
                return (not pinned, 0)
            
            reverse = self.sort_order == Qt.SortOrder.DescendingOrder
            items = sorted(items, key=get_sort_key, reverse=reverse)
        
        self.table.setRowCount(0)
        
        theme = THEMES.get(self.current_theme, THEMES["dark"])
        
        # 빈 결과 상태 표시 (개선된 UI)
        if not items:
            self.table.setRowCount(1)
            if search_query:
                empty_msg = f"🔍 '{search_query}'에 대한 검색 결과가 없습니다"
            elif self.current_tag_filter:
                empty_msg = f"🏷️ '{self.current_tag_filter}' 태그를 가진 항목이 없습니다"
            else:
                empty_msg = "📋 클립보드 히스토리가 비어있습니다\n\n텍스트나 이미지를 복사하면 자동으로 저장됩니다\n⌨️ Ctrl+Shift+V로 언제든 호출 가능"
            empty_item = QTableWidgetItem(empty_msg)
            empty_item.setForeground(QColor(theme["text_secondary"]))
            empty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_item.setFlags(empty_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(0, 0, empty_item)
            self.table.setSpan(0, 0, 1, 5)
            self.table.setRowHeight(0, 100)  # 빈 상태 행 높이 증가
            return
        
        # 날짜 비교용
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        
        for row_idx, (pid, content, ptype, timestamp, pinned, use_count, pin_order) in enumerate(items):
            self.table.insertRow(row_idx)
            
            # 고정 아이콘
            pin_item = QTableWidgetItem("📌" if pinned else "")
            pin_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            pin_item.setData(Qt.ItemDataRole.UserRole, pid)
            self.table.setItem(row_idx, 0, pin_item)
            
            # 타입 (색상 코드화)
            type_icons = {"TEXT": "📝", "LINK": "🔗", "IMAGE": "🖼️", "CODE": "💻", "COLOR": "🎨"}
            type_item = QTableWidgetItem(type_icons.get(ptype, "📝"))
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            type_item.setToolTip(ptype)
            type_item.setData(Qt.ItemDataRole.UserRole + 1, ptype)  # 정렬용 원본 데이터
            self.table.setItem(row_idx, 1, type_item)
            
            # 내용 + 툴팁
            display = content.replace('\n', ' ').strip()
            if len(display) > 45: 
                display = display[:45] + "..."
            content_item = QTableWidgetItem(display)
            # 툴팁에 전체 내용 표시 (최대 500자)
            if ptype == "IMAGE":
                content_item.setToolTip("🖼️ 이미지 항목 - 더블클릭으로 미리보기")
            else:
                tooltip_text = content[:500] if len(content) > 500 else content
                content_item.setToolTip(tooltip_text)
            if ptype == "LINK":
                content_item.setForeground(QColor(theme["secondary"]))
            elif ptype == "CODE":
                content_item.setForeground(QColor(theme["success"]))
            elif ptype == "COLOR":
                content_item.setForeground(QColor(content) if content.startswith("#") else QColor(theme["warning"]))
            content_item.setData(Qt.ItemDataRole.UserRole + 1, content)  # 정렬용 원본 데이터
            self.table.setItem(row_idx, 2, content_item)
            
            # 시간 (개선된 형식)
            try:
                dt = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                if dt.date() == today:
                    time_str = dt.strftime("%H:%M")  # 오늘: "14:30"
                elif dt.date() == yesterday:
                    time_str = f"어제 {dt.hour}시"  # 어제: "어제 13시"
                else:
                    time_str = f"{dt.month}/{dt.day} {dt.hour}시"  # 그 외: "12/25 13시"
            except (ValueError, TypeError) as e:
                logger.debug(f"Timestamp parse error: {e}")
                time_str = timestamp
            
            time_item = QTableWidgetItem(time_str)
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            time_item.setForeground(QColor(theme["text_secondary"]))
            time_item.setData(Qt.ItemDataRole.UserRole + 1, timestamp)  # 정렬용 원본 타임스탬프
            self.table.setItem(row_idx, 3, time_item)
            
            # 사용 횟수
            use_item = QTableWidgetItem(str(use_count) if use_count else "-")
            use_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            use_item.setForeground(QColor(theme["text_secondary"]))
            use_item.setData(Qt.ItemDataRole.UserRole + 1, use_count or 0)  # 정렬용 원본 데이터
            self.table.setItem(row_idx, 4, use_item)
            
        # 상태바 업데이트
        self.update_status_bar()

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
            if ptype == "IMAGE" and blob:
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
                self.db.delete_item(pid)
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
                self.db.delete_item(pid)
        
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
        
        pin_action = menu.addAction("📌 고정/해제")
        pin_action.triggered.connect(self.toggle_pin)
        
        tag_action = menu.addAction("🏷️ 태그 편집")
        tag_action.triggered.connect(self.edit_tag)
        
        menu.addSeparator()
        
        # 다중 선택 시 병합 옵션
        selected_count = len(self.table.selectionModel().selectedRows())
        if selected_count >= 2:
            merge_action = menu.addAction(f"🔗 {selected_count}개 병합")
            merge_action.triggered.connect(self.merge_selected)
            menu.addSeparator()
        
        delete_action = menu.addAction("🗑️ 삭제")
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

        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        with open("debug_startup_error.log", "w", encoding="utf-8") as f:
            f.write(error_msg)
            f.write(f"\nError: {e}")
        # MessageBox로도 표시 시도 (Qt가 로드되었다면)
        try:
            from PyQt6.QtWidgets import QMessageBox
            if not QApplication.instance():
                app = QApplication(sys.argv)
            QMessageBox.critical(None, "Startup Error", f"An error occurred:\n{e}\n\nSee debug_startup_error.log for details.")
        except:
            print(f"Critical Error:\n{error_msg}")
        
        # 콘솔 창이 바로 꺼지지 않도록 대기
        input("Press Enter to close...")
        sys.exit(1)


