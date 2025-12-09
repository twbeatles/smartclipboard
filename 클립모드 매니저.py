"""
SmartClipboard Pro v6.0
고급 클립보드 매니저 - 리팩토링 버전
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
    QCheckBox, QTabWidget, QGroupBox, QSlider, QFrame
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QByteArray, QBuffer, 
    QSettings, QPropertyAnimation, QEasingCurve, QPoint
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
VERSION = "6.0"

# --- 테마 정의 ---
THEMES = {
    "dark": {
        "name": "다크 모드",
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
    },
    "light": {
        "name": "라이트 모드",
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
    },
    "ocean": {
        "name": "오션 모드",
        "background": "#0a192f",
        "surface": "#112240",
        "surface_variant": "#1d3557",
        "primary": "#64ffda",
        "primary_variant": "#7efff5",
        "secondary": "#ffd166",
        "text": "#ccd6f6",
        "text_secondary": "#8892b0",
        "border": "#233554",
        "success": "#4ade80",
        "warning": "#fbbf24",
        "error": "#ff6b6b",
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
            self.conn.commit()
            logger.info("DB 테이블 초기화 완료")
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
                sql = "SELECT id, content, type, timestamp, pinned, use_count FROM history WHERE 1=1"
                params = []

                if search_query:
                    sql += " AND content LIKE ?"
                    params.append(f"%{search_query}%")
                
                if type_filter != "전체":
                    tag_map = {"텍스트": "TEXT", "이미지": "IMAGE", "링크": "LINK", "코드": "CODE", "색상": "COLOR"}
                    target_tag = tag_map.get(type_filter, "TEXT")
                    sql += " AND type = ?"
                    params.append(target_tag)

                sql += " ORDER BY pinned DESC, id DESC"
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
            return 0

    def increment_use_count(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE history SET use_count = use_count + 1 WHERE id = ?", (item_id,))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"DB Use Count Error: {e}")

    def delete_item(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM history WHERE id = ?", (item_id,))
                self.conn.commit()
                logger.info(f"항목 삭제: {item_id}")
            except sqlite3.Error as e:
                logger.error(f"DB Delete Error: {e}")

    def clear_all(self):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM history WHERE pinned = 0")
                self.conn.commit()
                logger.info("고정되지 않은 모든 항목 삭제")
            except sqlite3.Error as e:
                logger.error(f"DB Clear Error: {e}")

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
            except sqlite3.Error:
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

    def close(self):
        if self.conn:
            self.conn.close()
            logger.info("DB 연결 종료")


# --- 핫키 리스너 ---
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


# --- 설정 다이얼로그 ---
class SettingsDialog(QDialog):
    def __init__(self, parent, db, current_theme):
        super().__init__(parent)
        self.db = db
        self.current_theme = current_theme
        self.setWindowTitle("⚙️ 설정")
        self.setMinimumSize(450, 400)
        self.init_ui()

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
        self.db.set_setting("theme", self.theme_combo.currentData())
        self.db.set_setting("max_history", self.max_history_spin.value())
        self.accept()

    def get_selected_theme(self):
        return self.theme_combo.currentData()


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


# --- 메인 윈도우 ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = ClipboardDB()
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_change)
        self.is_internal_copy = False
        
        self.settings = QSettings(ORG_NAME, APP_NAME)
        self.current_theme = self.db.get_setting("theme", "dark")
        
        self.setWindowTitle(f"스마트 클립보드 프로 v{VERSION}")
        self.restore_window_state()
        
        self.app_icon = self.create_app_icon()
        self.setWindowIcon(self.app_icon)
        
        self.always_on_top = True
        
        self.apply_theme()
        self.init_menu()
        self.init_ui()
        self.init_tray()
        self.init_shortcuts()
        
        self.hotkey_thread = HotkeyListener()
        self.hotkey_thread.show_signal.connect(self.show_window_from_tray)
        self.hotkey_thread.start()
        
        self.update_always_on_top()
        self.load_data()
        self.update_status_bar()
        
        logger.info("SmartClipboard Pro 시작됨")

    def restore_window_state(self):
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(650, 850)

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
            keyboard.unhook_all()
        except Exception as e:
            logger.warning(f"Cleanup warning: {e}")
        self.db.close()
        QApplication.quit()

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
        }}
        QTableWidget::item:selected {{
            background-color: {theme["primary"]};
            color: white;
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
            border-radius: 8px;
        }}
        
        QPushButton {{ 
            background-color: {theme["surface_variant"]}; 
            border: none; 
            border-radius: 8px; 
            padding: 10px 16px; 
            color: {theme["text"]}; 
            font-weight: bold;
        }}
        QPushButton:hover {{ 
            background-color: {theme["primary"]}; 
            color: white;
        }}
        QPushButton:pressed {{ 
            background-color: {theme["primary_variant"]}; 
        }}
        
        QPushButton#PrimaryBtn {{
            background-color: {theme["primary"]};
            color: white;
        }}
        QPushButton#PrimaryBtn:hover {{
            background-color: {theme["primary_variant"]};
        }}
        
        QPushButton#ToolBtn {{
            background-color: {theme["surface"]}; 
            font-size: 12px; 
            padding: 6px 12px;
            border-radius: 6px;
        }}
        QPushButton#ToolBtn:hover {{
            background-color: {theme["secondary"]};
            color: white;
        }}
        
        QPushButton#DeleteBtn {{ 
            background-color: {theme["error"]}; 
            color: white;
        }}
        QPushButton#DeleteBtn:hover {{ 
            background-color: #dc2626; 
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

    def init_shortcuts(self):
        """키보드 단축키 설정"""
        QShortcut(QKeySequence("Escape"), self, self.hide)
        QShortcut(QKeySequence("Ctrl+F"), self, lambda: self.search_input.setFocus())
        QShortcut(QKeySequence("Delete"), self, self.delete_item)
        QShortcut(QKeySequence("Ctrl+P"), self, self.toggle_pin)
        QShortcut(QKeySequence("Return"), self, self.paste_selected)
        QShortcut(QKeySequence("Ctrl+C"), self, self.copy_item)

    def init_menu(self):
        menubar = self.menuBar()
        
        # 파일 메뉴
        file_menu = menubar.addMenu("파일")
        
        action_export = QAction("💾 텍스트 내보내기", self)
        action_export.triggered.connect(self.export_history)
        file_menu.addAction(action_export)
        
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

        # 보기 메뉴
        view_menu = menubar.addMenu("보기")
        
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
        
        action_settings = QAction("⚙️ 설정...", self)
        action_settings.triggered.connect(self.show_settings)
        settings_menu.addAction(action_settings)

    def change_theme(self, theme_key):
        self.current_theme = theme_key
        self.db.set_setting("theme", theme_key)
        self.apply_theme()
        self.statusBar().showMessage(f"✅ 테마 변경: {THEMES[theme_key]['name']}", 2000)

    def show_settings(self):
        dialog = SettingsDialog(self, self.db, self.current_theme)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_theme = dialog.get_selected_theme()
            if new_theme != self.current_theme:
                self.change_theme(new_theme)
            self.statusBar().showMessage("✅ 설정이 저장되었습니다.", 2000)

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
        self.filter_combo.addItems(["전체", "텍스트", "이미지", "링크", "코드", "색상"])
        self.filter_combo.setFixedWidth(110)
        self.filter_combo.currentTextChanged.connect(self.load_data)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 검색...")
        self.search_input.textChanged.connect(self.load_data)
        self.search_input.setClearButtonEnabled(True)
        
        top_layout.addWidget(self.filter_combo)
        top_layout.addWidget(self.search_input)
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
        self.table.setColumnWidth(3, 70)
        self.table.setColumnWidth(4, 45)
        
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.cellDoubleClicked.connect(self.on_double_click_paste)
        
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

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

        self.tools_layout.addWidget(self.btn_save_img)
        self.tools_layout.addWidget(self.btn_google)
        if HAS_QRCODE:
            self.tools_layout.addWidget(self.btn_qr)
        self.tools_layout.addWidget(self.btn_upper)
        self.tools_layout.addWidget(self.btn_lower)
        self.tools_layout.addWidget(self.btn_strip)
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
        
        tray_menu = QMenu()
        tray_menu.setStyleSheet("""
            QMenu { background-color: #1a1a2e; color: #eaeaea; border: 1px solid #2a2a4a; padding: 5px; }
            QMenu::item { padding: 8px 20px; }
            QMenu::item:selected { background-color: #e94560; }
        """)
        
        show_action = QAction("📋 열기", self)
        show_action.triggered.connect(self.show_window_from_tray)
        quit_action = QAction("❌ 종료", self)
        quit_action.triggered.connect(self.quit_app)
        
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def update_status_bar(self):
        stats = self.db.get_statistics()
        status_text = f"📊 총 {stats['total']}개 | 📌 고정 {stats['pinned']}개"
        if stats['by_type']:
            type_info = " | ".join([f"{k}: {v}" for k, v in stats['by_type'].items()])
            status_text += f" | {type_info}"
        self.statusBar().showMessage(status_text)

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
        if self.is_internal_copy:
            self.is_internal_copy = False
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
                tag = self.analyze_text(text)
                if self.db.add_item(text, None, tag):
                    self.load_data()
                    self.update_status_bar()
        except Exception as e:
            logger.debug(f"Clipboard access: {e}")

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
        
        items = self.db.get_items(search_query, filter_type)
        self.table.setRowCount(0)
        
        theme = THEMES.get(self.current_theme, THEMES["dark"])
        
        for row_idx, (pid, content, ptype, timestamp, pinned, use_count) in enumerate(items):
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
            self.table.setItem(row_idx, 1, type_item)
            
            # 내용
            display = content.replace('\n', ' ').strip()
            if len(display) > 45: 
                display = display[:45] + "..."
            content_item = QTableWidgetItem(display)
            if ptype == "LINK":
                content_item.setForeground(QColor(theme["secondary"]))
            elif ptype == "CODE":
                content_item.setForeground(QColor(theme["success"]))
            elif ptype == "COLOR":
                content_item.setForeground(QColor(content) if content.startswith("#") else QColor(theme["warning"]))
            self.table.setItem(row_idx, 2, content_item)
            
            # 시간
            try:
                dt = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                time_str = dt.strftime("%H:%M") if dt.date() == datetime.date.today() else dt.strftime("%m/%d")
            except:
                time_str = timestamp
            
            time_item = QTableWidgetItem(time_str)
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            time_item.setForeground(QColor(theme["text_secondary"]))
            self.table.setItem(row_idx, 3, time_item)
            
            # 사용 횟수
            use_item = QTableWidgetItem(str(use_count) if use_count else "-")
            use_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            use_item.setForeground(QColor(theme["text_secondary"]))
            self.table.setItem(row_idx, 4, use_item)

    def on_selection_changed(self):
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
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            return luminance > 0.5
        except:
            return False

    def tools_layout_visible(self, visible):
        self.btn_upper.setVisible(visible)
        self.btn_lower.setVisible(visible)
        self.btn_strip.setVisible(visible)
        self.btn_google.setVisible(visible)
        if HAS_QRCODE: self.btn_qr.setVisible(visible)

    def transform_text(self, mode):
        text = self.detail_text.toPlainText()
        if not text: return
        new_text = text
        if mode == "upper": new_text = text.upper()
        elif mode == "lower": new_text = text.lower()
        elif mode == "strip": new_text = " ".join(text.split())
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
            self.statusBar().showMessage("✅ 복사됨", 2000)

    def paste_selected(self):
        """Enter키로 붙여넣기"""
        self.copy_item()
        self.hide()
        QTimer.singleShot(200, lambda: keyboard.send('ctrl+v'))
    
    def on_double_click_paste(self, row, col):
        self.paste_selected()

    def delete_item(self):
        pid = self.get_selected_id()
        if pid:
            self.db.delete_item(pid)
            self.load_data()
            self.update_ui_state(False)
            self.update_status_bar()
    
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
        
        pin_action = menu.addAction("📌 고정/해제")
        pin_action.triggered.connect(self.toggle_pin)
        
        menu.addSeparator()
        
        delete_action = menu.addAction("🗑️ 삭제")
        delete_action.triggered.connect(self.delete_item)
        
        menu.exec(self.table.viewport().mapToGlobal(pos))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    font = QFont("Malgun Gothic", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


