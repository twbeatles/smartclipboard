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
import winreg
import logging
import json
import shutil
import base64
import uuid
import csv
import hashlib  # v10.1: 모듈 레벨 import로 이동 (성능 최적화)
from urllib.parse import quote  # v10.3: URL 인코딩용

try:
    import keyboard
except ImportError:
    class _KeyboardStub:
        def __getattr__(self, _name):
            def _noop(*_args, **_kwargs):
                return None

            return _noop

    keyboard = _KeyboardStub()

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
    QFileDialog, QComboBox, QDialog, QFormLayout, QSpinBox, QDateEdit,
    QCheckBox, QTabWidget, QGroupBox, QFrame, QInputDialog
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QByteArray, QBuffer,
    QSettings, QPropertyAnimation, QEasingCurve, QPoint, QEvent, QDate,
    QObject, QRunnable, QThreadPool, pyqtSlot
)
from PyQt6.QtGui import (
    QColor, QFont, QIcon, QAction, QPixmap, QImage,
    QPainter, QKeySequence, QShortcut, QLinearGradient, QBrush, QPen
)

from smartclipboard_core import (
    ClipboardActionManager as CoreClipboardActionManager,
    ClipboardDB as CoreClipboardDB,
    Worker as CoreWorker,
    WorkerSignals as CoreWorkerSignals,
)
from smartclipboard_core.actions import extract_first_url as core_extract_first_url
from smartclipboard_app.managers.export_import import ExportImportManager as AppExportImportManager
from smartclipboard_app.managers.secure_vault import SecureVaultManager as AppSecureVaultManager
from smartclipboard_app.ui.dialogs.snippets import (
    SnippetDialog as AppSnippetDialog,
    SnippetManagerDialog as AppSnippetManagerDialog,
)
from smartclipboard_app.ui.dialogs.clipboard_actions import ClipboardActionsDialog as AppClipboardActionsDialog
from smartclipboard_app.ui.dialogs.copy_rules import CopyRulesDialog as AppCopyRulesDialog
from smartclipboard_app.ui.dialogs.export_dialog import ExportDialog as AppExportDialog
from smartclipboard_app.ui.dialogs.hotkeys import HotkeySettingsDialog as AppHotkeySettingsDialog
from smartclipboard_app.ui.dialogs.import_dialog import ImportDialog as AppImportDialog
from smartclipboard_app.ui.dialogs.secure_vault import SecureVaultDialog as AppSecureVaultDialog
from smartclipboard_app.ui.dialogs.settings import SettingsDialog as AppSettingsDialog
from smartclipboard_app.ui.dialogs.statistics import StatisticsDialog as AppStatisticsDialog
from smartclipboard_app.ui.dialogs.tags import TagEditDialog as AppTagEditDialog
from smartclipboard_app.ui.dialogs.trash_dialog import TrashDialog as AppTrashDialog
from smartclipboard_app.ui.mainwindow_parts import (
    analyze_text_impl,
    apply_theme_impl,
    apply_copy_rules_impl,
    check_vault_timeout_impl,
    event_filter_impl,
    get_display_items_impl,
    handle_drop_event_impl,
    init_menu_impl,
    init_tray_impl,
    init_ui_impl,
    load_data_impl,
    on_clipboard_change_impl,
    on_tray_activated_impl,
    on_selection_changed_impl,
    paste_last_item_slot_impl,
    populate_table_impl,
    process_actions_impl,
    process_clipboard_impl,
    process_image_clipboard_impl,
    process_text_clipboard_impl,
    quit_app_impl,
    register_hotkeys_impl,
    run_periodic_cleanup_impl,
    show_context_menu_impl,
    show_window_from_tray_impl,
    show_empty_state_impl,
    toggle_mini_window_slot_impl,
    update_status_bar_impl,
    update_tray_theme_impl,
)
from smartclipboard_app.ui.widgets.floating_mini_window import FloatingMiniWindow as AppFloatingMiniWindow
from smartclipboard_app.ui.widgets.toast import ToastNotification as AppToastNotification


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
VERSION = "10.6"

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
    "🎨 색상": "COLOR"
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
TYPE_ICONS = {"TEXT": "📝", "LINK": "🔗", "IMAGE": "🖼️", "CODE": "💻", "COLOR": "🎨"}

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
class WorkerSignals(CoreWorkerSignals):
    """Compatibility export backed by smartclipboard_core.worker."""


class Worker(CoreWorker):
    """Compatibility export backed by smartclipboard_core.worker."""


class ClipboardDB(CoreClipboardDB):
    """Compatibility export backed by smartclipboard_core.database."""

    def __init__(self):
        super().__init__(db_file=DB_FILE, app_dir=APP_DIR)

    def cleanup(self):
        return super().cleanup()


class SecureVaultManager(AppSecureVaultManager):
    """Compatibility export backed by smartclipboard_app.managers.secure_vault."""

    def __init__(self, db):
        super().__init__(db=db, logger_=logger)


# --- v8.0: 클립보드 액션 자동화 관리자 ---
class ClipboardActionManager(CoreClipboardActionManager):
    """Compatibility export backed by smartclipboard_core.actions."""

    def process(self, text, item_id=None):
        results = super().process(text, item_id=item_id)
        if results:
            return results

        for action in self.actions_cache:
            if not action.get("enabled") or action.get("type") != "fetch_title":
                continue
            try:
                compiled = action.get("compiled")
                if compiled is None or not compiled.search(text):
                    continue
            except re.error:
                continue

            if core_extract_first_url(text):
                return [
                    (
                        action.get("name", "fetch_title"),
                        {"type": "notify", "message": "URL 제목 가져오기를 요청했습니다."},
                    )
                ]

        return results

    def fetch_url_title(self, url, item_id):
        # Kept for legacy compatibility.
        return None


class ExportImportManager(AppExportImportManager):
    """Compatibility export backed by smartclipboard_app.managers.export_import."""

    def __init__(self, db):
        super().__init__(db=db, version=VERSION, type_icons=TYPE_ICONS, logger_=logger)

# --- (레거시 HotkeyListener 클래스 제거됨 - MainWindow.register_hotkeys()로 대체) ---


# --- 토스트 알림 ---
class ToastNotification(AppToastNotification):
    """Compatibility export backed by smartclipboard_app.ui.widgets.toast."""


# --- 설정 다이얼로그 ---
class SettingsDialog(AppSettingsDialog):
    """Compatibility export backed by smartclipboard_app.ui.dialogs.settings."""

    def __init__(self, parent, db, current_theme):
        super().__init__(
            parent=parent,
            db=db,
            current_theme=current_theme,
            themes=THEMES,
            max_history=MAX_HISTORY,
            logger_=logger,
        )


# --- v8.0: 보안 보관함 다이얼로그 ---
class SecureVaultDialog(AppSecureVaultDialog):
    """Compatibility export backed by smartclipboard_app.ui.dialogs.secure_vault."""


# --- v8.0: 클립보드 액션 다이얼로그 ---
class ClipboardActionsDialog(AppClipboardActionsDialog):
    """Compatibility export backed by smartclipboard_app.ui.dialogs.clipboard_actions."""


# --- v8.0: 내보내기 다이얼로그 ---
class ExportDialog(AppExportDialog):
    """Compatibility export backed by smartclipboard_app.ui.dialogs.export_dialog."""


# --- v8.0: 가져오기 다이얼로그 ---
class ImportDialog(AppImportDialog):
    """Compatibility export backed by smartclipboard_app.ui.dialogs.import_dialog."""


# --- v10.2: 휴지통 다이얼로그 ---
class TrashDialog(AppTrashDialog):
    """Compatibility export backed by smartclipboard_app.ui.dialogs.trash_dialog."""

    def __init__(self, parent, db):
        super().__init__(parent=parent, db=db, themes=THEMES)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)


# --- v8.0: 플로팅 미니 창 ---
class FloatingMiniWindow(AppFloatingMiniWindow):
    """Compatibility export backed by smartclipboard_app.ui.widgets.floating_mini_window."""

    def __init__(self, db, parent=None):
        super().__init__(
            db=db,
            parent=parent,
            themes=THEMES,
            glass_styles=GLASS_STYLES,
            type_icons=TYPE_ICONS,
            logger_=logger,
            keyboard_module=keyboard,
        )


# --- v8.0: 핫키 설정 다이얼로그 ---
class HotkeySettingsDialog(AppHotkeySettingsDialog):
    """Compatibility export backed by smartclipboard_app.ui.dialogs.hotkeys."""

    def __init__(self, parent, db):
        super().__init__(parent=parent, db=db, default_hotkeys=DEFAULT_HOTKEYS, logger_=logger)


# --- 스니펫 다이얼로그 ---
class SnippetDialog(AppSnippetDialog):
    """Compatibility export backed by smartclipboard_app.ui.dialogs.snippets."""


# --- 스니펫 관리자 다이얼로그 ---
class SnippetManagerDialog(AppSnippetManagerDialog):
    """Compatibility export backed by smartclipboard_app.ui.dialogs.snippets."""


# --- 태그 편집 다이얼로그 ---
class TagEditDialog(AppTagEditDialog):
    """Compatibility export backed by smartclipboard_app.ui.dialogs.tags."""


# --- 히스토리 통계 다이얼로그 ---
class StatisticsDialog(AppStatisticsDialog):
    """Compatibility export backed by smartclipboard_app.ui.dialogs.statistics."""


# --- 복사 규칙 다이얼로그 ---
class CopyRulesDialog(AppCopyRulesDialog):
    """Compatibility export backed by smartclipboard_app.ui.dialogs.copy_rules."""


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
            self.apply_saved_log_level()
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
            self.current_collection_filter = "__all__"  # 컬렉션 필터
            self.sort_column = 3  # 기본 정렬: 시간 컨럼
            self.sort_order = Qt.SortOrder.DescendingOrder  # 기본: 내림차순
            
            # v10.0: 복사 규칙 캐싱 (성능 최적화)
            self._rules_cache = None
            self._rules_cache_dirty = True
            
            # v10.3: 클립보드 디바운스 타이머 (중복 호출 방지)
            self._clipboard_debounce_timer = None
            
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
                self.load_data()
            
            self.update_status_bar()
            
            # v8.0: 보관함 자동 잠금 타이머
            self.vault_timer = QTimer(self)
            self.vault_timer.timeout.connect(self.check_vault_timeout)
            self.vault_timer.start(60000)  # 1분마다 타임아웃 체크
            
            # v10.2: 만료 항목 정리 타이머 (1시간마다)
            self.cleanup_timer = QTimer(self)
            self.cleanup_timer.timeout.connect(self.run_periodic_cleanup)
            self.cleanup_timer.start(3600000)  # 1시간 = 3600000ms
            
            # v10.7: 일일 자동 백업 (실행 중 날짜 변경 포함)
            self.backup_timer = QTimer(self)
            self.backup_timer.timeout.connect(self.run_daily_backup_if_needed)
            self.backup_timer.start(3600000)  # 1시간마다 확인
            QTimer.singleShot(3000, self.run_daily_backup_if_needed)
            
            # v10.2: 등록된 핫키 추적 (안전한 해제를 위해)
            self._registered_hotkeys = []
            
            # 앱 시작 시 5초 후 정리 작업 실행
            QTimer.singleShot(5000, self.run_periodic_cleanup)
            
            logger.info("SmartClipboard Pro v10.3 started")
        except Exception as e:
            logger.error(f"MainWindow Init Error: {e}", exc_info=True)
            raise e

    def apply_saved_log_level(self):
        """저장된 로그 레벨을 root/logger에 반영."""
        try:
            raw_level = self.db.get_setting("log_level", "INFO")
            level_name = str(raw_level or "INFO").upper()
            level_map = {
                "DEBUG": logging.DEBUG,
                "INFO": logging.INFO,
                "WARNING": logging.WARNING,
                "ERROR": logging.ERROR,
            }
            level = level_map.get(level_name, logging.INFO)
            root_logger = logging.getLogger()
            root_logger.setLevel(level)
            for handler in root_logger.handlers:
                handler.setLevel(level)
            logger.setLevel(level)
        except Exception as log_level_exc:
            logger.debug(f"Failed to apply saved log level: {log_level_exc}")

    def register_hotkeys(self):
        """v10.2: custom hotkey registration."""
        return register_hotkeys_impl(self, logger, keyboard, json, DEFAULT_HOTKEYS)
    
    def toggle_mini_window(self):
        """미니 창 토글 (외부에서 호출 시 시그널 사용)"""
        self.toggle_mini_signal.emit()
    
    def _toggle_mini_window_slot(self):
        """Mini window toggle slot on main thread."""
        return toggle_mini_window_slot_impl(self, logger)
    
    def paste_last_item(self):
        """마지막 항목 즉시 붙여넣기 (외부에서 호출 시 시그널 사용)"""
        self.paste_last_signal.emit()
    
    def _paste_last_item_slot(self):
        """Paste last clipboard item slot on main thread."""
        return paste_last_item_slot_impl(self, logger, QPixmap, QTimer, keyboard)
    
    def check_vault_timeout(self):
        """Auto-lock secure vault on inactivity."""
        return check_vault_timeout_impl(self, logger)
    
    def run_periodic_cleanup(self):
        """Periodic cleanup for expired data and trash."""
        return run_periodic_cleanup_impl(self, logger)

    def run_daily_backup_if_needed(self):
        """하루 1회 자동 백업 실행 (앱 재시작 없이 날짜 변경 대응)."""
        try:
            today = datetime.date.today().strftime("%Y%m%d")
            last_backup = self.db.get_setting("last_auto_backup_date", "")
            if last_backup == today:
                return
            if self.db.backup_db():
                self.db.set_setting("last_auto_backup_date", today)
                logger.info(f"Daily backup completed: {today}")
        except Exception as e:
            logger.warning(f"Daily backup check failed: {e}")

    # v10.4: 화면 표시 시 데이터 갱신 (Lazy Loading)
    def showEvent(self, event):
        if self.is_data_dirty:
            self.load_data()
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
        """Shutdown app and cleanup resources."""
        return quit_app_impl(self, logger, keyboard, QApplication)

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
                if self.db.backup_db(target_path=file_name, force=True):
                    QMessageBox.information(self, "백업 완료", f"데이터가 성공적으로 백업되었습니다:\n{file_name}")
                else:
                    QMessageBox.critical(self, "백업 오류", "백업 파일 생성에 실패했습니다.")
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
                target_db_file = getattr(self.db, "db_file", DB_FILE)
                shutil.copy2(file_name, target_db_file)
                QMessageBox.information(self, "복원 완료", "데이터가 복원되었습니다.\n프로그램을 재시작합니다.")
                self.quit_app()
            except Exception as e:
                QMessageBox.critical(self, "복원 오류", f"복원 중 오류가 발생했습니다:\n{e}")
                # v10.2: 연결 재수립 및 모든 매니저 갱신
                self.db = ClipboardDB()
                self.vault_manager = SecureVaultManager(self.db)
                self.action_manager = ClipboardActionManager(self.db)
                self.action_manager.action_completed.connect(self.on_action_completed)
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
        return apply_theme_impl(self, THEMES, GLASS_STYLES)
        # Note: 단축키는 init_shortcuts()에서 등록됨 (중복 방지)

    def eventFilter(self, source, event):
        return event_filter_impl(
            self,
            source,
            event,
            lambda event_source, event_obj: QMainWindow.eventFilter(self, event_source, event_obj),
        )

    def _handle_drop_event(self, event):
        return handle_drop_event_impl(self, event, THEMES, logger)


    def init_menu(self):
        return init_menu_impl(self, THEMES)

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

    def refresh_collection_filter_options(self):
        """컬렉션 필터 콤보 항목 갱신."""
        if not hasattr(self, "collection_filter_combo"):
            return
        current = getattr(self, "current_collection_filter", "__all__")
        self.collection_filter_combo.blockSignals(True)
        try:
            self.collection_filter_combo.clear()
            self.collection_filter_combo.addItem("📂 전체 컬렉션", "__all__")
            self.collection_filter_combo.addItem("🧺 미분류", "__uncategorized__")
            for cid, cname, cicon, _ccolor, _created_at in self.db.get_collections():
                self.collection_filter_combo.addItem(f"{cicon} {cname}", cid)

            idx = self.collection_filter_combo.findData(current)
            if idx < 0:
                idx = 0
                current = "__all__"
            self.current_collection_filter = current
            self.collection_filter_combo.setCurrentIndex(idx)
        finally:
            self.collection_filter_combo.blockSignals(False)

    def on_collection_filter_changed(self, _index):
        if not hasattr(self, "collection_filter_combo"):
            return
        self.current_collection_filter = self.collection_filter_combo.currentData()
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
        return init_ui_impl(self, HAS_QRCODE)

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
                    ToastNotification.show_toast(self, "🔗 링크 제목 발견", f"{title}")
                    # UI 입력 중이 아닐 때만 데이터 다시 로드
                    if not self.search_input.hasFocus():
                        self.load_data()
                    self.clipboard.dataChanged.connect(self.on_clipboard_change)
        except Exception as e:
            logger.error(f"Action Handler Error: {e}")

    def init_tray(self):
        return init_tray_impl(self, VERSION, QAction, QMenu, QSystemTrayIcon)

    def toggle_monitoring_pause(self):
        """v10.6: 모니터링 일시정지 토글"""
        self.is_monitoring_paused = not self.is_monitoring_paused
        
        # 액션 체크 상태 동기화
        self.tray_pause_action.setChecked(self.is_monitoring_paused)
        
        if self.is_monitoring_paused:
            ToastNotification.show_toast(self, "⏸ 모니터링 일시정지", "클립보드 수집이 잠시 중단됩니다.")
            self.tray_icon.setToolTip(f"스마트 클립보드 프로 v{VERSION} (일시정지됨)")
        else:
            ToastNotification.show_toast(self, "▶ 모니터링 재개", "클립보드 수집을 다시 시작합니다.")
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
        """Apply active theme to tray menu."""
        return update_tray_theme_impl(self, THEMES)

    def update_status_bar(self, selection_count=0):
        """Refresh status bar message."""
        return update_status_bar_impl(self, selection_count, Qt)

    # --- 기능 로직 ---
    def toggle_always_on_top(self):
        self.always_on_top = self.action_ontop.isChecked()
        self.update_always_on_top()

    def update_always_on_top(self):
        was_visible = self.isVisible()
        if self.always_on_top:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
        if was_visible:
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
        return on_tray_activated_impl(self, reason, QSystemTrayIcon)

    def show_window_from_tray(self):
        return show_window_from_tray_impl(self)

    def on_clipboard_change(self):
        """Clipboard changed callback with debounce."""
        return on_clipboard_change_impl(self, QTimer)

    def process_clipboard(self):
        return process_clipboard_impl(self, logger)

    def _process_image_clipboard(self, mime_data):
        return process_image_clipboard_impl(self, mime_data, logger, QByteArray, QBuffer, hashlib, ToastNotification)

    def _process_text_clipboard(self, mime_data):
        return process_text_clipboard_impl(self, mime_data, logger)

    def _process_actions(self, text, item_id):
        return process_actions_impl(self, text, item_id, logger, ToastNotification)

    def apply_copy_rules(self, text):
        return apply_copy_rules_impl(self, text, logger, re)
    
    def invalidate_rules_cache(self):
        """v10.0: 규칙 캐시 무효화 (규칙 변경 시 호출)"""
        self._rules_cache_dirty = True
        logger.debug("Copy rules cache invalidated")

    def analyze_text(self, text):
        return analyze_text_impl(text, RE_URL, RE_HEX_COLOR, RE_RGB_COLOR, RE_HSL_COLOR, CODE_INDICATORS)

    def load_data(self):
        return load_data_impl(self, THEMES, logger)

    def on_search_text_changed(self, text):
        # Reset fallback notification on clear, so we can notify again later if needed.
        if not (text or "").strip():
            self._search_fallback_notified = False
        self._search_debounce_timer.start()

    def _get_display_items(self):
        return get_display_items_impl(self)

    def _show_empty_state(self, theme):
        return show_empty_state_impl(self, theme)

    def _populate_table(self, items, theme):
        return populate_table_impl(self, items, theme, TYPE_ICONS)


    def on_selection_changed(self):
        return on_selection_changed_impl(self, HAS_QRCODE, THEMES)

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
            created_id = self.db.add_collection(name, icon or "📁")
            if created_id:
                self.refresh_collection_filter_options()
                if hasattr(self, "collection_filter_combo"):
                    idx = self.collection_filter_combo.findData(created_id)
                    if idx >= 0:
                        self.collection_filter_combo.setCurrentIndex(idx)
                self.statusBar().showMessage(f"📁 '{name}' 컬렉션이 생성되었습니다.", 2000)
            else:
                self.statusBar().showMessage("⚠️ 컬렉션 생성에 실패했습니다.", 2000)
    
    def move_to_collection(self, collection_id):
        item_ids = self.get_selected_ids()
        if item_ids:
            moved_count = 0
            if hasattr(self.db, "move_items_to_collection"):
                moved_count = self.db.move_items_to_collection(item_ids, collection_id)
            else:
                for item_id in item_ids:
                    if self.db.move_to_collection(item_id, collection_id):
                        moved_count += 1

            if collection_id:
                self.statusBar().showMessage(f"📁 {moved_count}개 항목을 컬렉션으로 이동했습니다.", 2000)
            else:
                self.statusBar().showMessage(f"🚫 {moved_count}개 항목을 컬렉션에서 제거했습니다.", 2000)
            self.refresh_collection_filter_options()
            self.load_data()

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

    def get_selected_ids(self):
        selection_model = self.table.selectionModel()
        if selection_model is None:
            return []
        rows = selection_model.selectedRows()
        item_ids = []
        for row in rows:
            item = self.table.item(row.row(), 0)
            if item is None:
                continue
            item_id = item.data(Qt.ItemDataRole.UserRole)
            if item_id:
                item_ids.append(item_id)
        return item_ids

    def get_selected_id(self):
        item_ids = self.get_selected_ids()
        return item_ids[0] if item_ids else None

    def show_context_menu(self, pos):
        return show_context_menu_impl(self, pos, THEMES, webbrowser)


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


