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
    QMenuBar, QFileDialog, QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QByteArray, QBuffer, QSettings
from PyQt6.QtGui import (
    QColor, QFont, QIcon, QAction, QPixmap, QImage, QClipboard, 
    QPainter, QBrush, QPen
)

# --- 설정 ---
DB_FILE = "clipboard_history_v5.db"
MAX_HISTORY = 100 
HOTKEY = "ctrl+shift+v"
APP_NAME = "SmartClipboardPro"
ORG_NAME = "MySmartTools"

# --- 데이터베이스 클래스 ---
class ClipboardDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.create_table()

    def create_table(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT,
                    image_data BLOB,
                    type TEXT,
                    timestamp TEXT,
                    pinned INTEGER DEFAULT 0
                )
            """)
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"DB Init Error: {e}")

    def add_item(self, content, image_data, type_tag):
        """
        항목 추가 로직 개선:
        1. 이미 존재하는 텍스트라면 기존 항목 삭제 후 최상단에 재등록 (끌어올리기 효과)
        2. 이미지(IMAGE)는 중복 체크 제외 (바이너리 비교 비용 절감)
        """
        try:
            cursor = self.conn.cursor()
            
            # 1. 텍스트 중복 체크 및 끌어올리기
            if type_tag != "IMAGE":
                # 내용이 같고, 고정되지 않은 항목이 있는지 확인
                cursor.execute("SELECT id FROM history WHERE content = ? AND pinned = 0", (content,))
                existing = cursor.fetchone()
                if existing:
                    # 기존 항목 삭제 (ID를 갱신하여 상단으로 보내기 위함)
                    cursor.execute("DELETE FROM history WHERE id = ?", (existing[0],))
            
            # 2. 새 항목 삽입
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO history (content, image_data, type, timestamp) VALUES (?, ?, ?, ?)", 
                        (content, image_data, type_tag, timestamp))
            
            self.conn.commit()
            self.cleanup()
            return True
            
        except sqlite3.Error as e:
            print(f"DB Add Error: {e}")
            self.conn.rollback() # 에러 발생 시 롤백
            return False

    def get_items(self, search_query="", type_filter="전체"):
        try:
            cursor = self.conn.cursor()
            
            sql = "SELECT id, content, type, timestamp, pinned FROM history WHERE 1=1"
            params = []

            if search_query:
                sql += " AND content LIKE ?"
                params.append(f"%{search_query}%")
            
            if type_filter != "전체":
                tag_map = {"텍스트": "TEXT", "이미지": "IMAGE", "링크": "LINK", "코드": "CODE", "색상": "COLOR"}
                target_tag = tag_map.get(type_filter, "TEXT")
                sql += " AND type = ?"
                params.append(target_tag)

            # 고정된 것 우선, 그 다음 최신 순
            sql += " ORDER BY pinned DESC, id DESC"
            
            cursor.execute(sql, params)
            return cursor.fetchall()
        except sqlite3.Error:
            return []

    def toggle_pin(self, item_id):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT pinned FROM history WHERE id=?", (item_id,))
            current = cursor.fetchone()
            if current:
                new_status = 0 if current[0] else 1
                cursor.execute("UPDATE history SET pinned = ? WHERE id = ?", (new_status, item_id))
                self.conn.commit()
                return new_status
        except sqlite3.Error:
            pass
        return 0

    def delete_item(self, item_id):
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM history WHERE id = ?", (item_id,))
            self.conn.commit()
        except sqlite3.Error:
            pass

    def clear_all(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM history WHERE pinned = 0") 
            self.conn.commit()
        except sqlite3.Error:
            pass

    def get_content(self, item_id):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT content, image_data, type FROM history WHERE id=?", (item_id,))
            return cursor.fetchone()
        except sqlite3.Error:
            return None
    
    def get_all_text_content(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT content, timestamp FROM history WHERE type != 'IMAGE' ORDER BY id DESC")
            return cursor.fetchall()
        except sqlite3.Error:
            return []

    def cleanup(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM history WHERE pinned = 0")
            result = cursor.fetchone()
            if not result: return
            
            count = result[0]
            if count > MAX_HISTORY:
                diff = count - MAX_HISTORY
                # 오래된 순서대로 삭제
                cursor.execute(f"DELETE FROM history WHERE id IN (SELECT id FROM history WHERE pinned = 0 ORDER BY id ASC LIMIT {diff})")
                self.conn.commit()
        except sqlite3.Error:
            pass

    def close(self):
        if self.conn:
            self.conn.close()

# --- 핫키 리스너 ---
class HotkeyListener(QThread):
    show_signal = pyqtSignal()

    def run(self):
        try:
            keyboard.add_hotkey(HOTKEY, self.show_signal.emit)
            keyboard.wait()
        except Exception as e:
            print(f"Hotkey Error: {e}")

# --- 메인 윈도우 ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = ClipboardDB()
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_change)
        self.is_internal_copy = False
        
        self.settings = QSettings(ORG_NAME, APP_NAME)
        
        self.setWindowTitle("스마트 클립보드 프로 v5.2")
        self.restore_window_state()
        
        self.app_icon = self.create_app_icon()
        self.setWindowIcon(self.app_icon)
        
        self.always_on_top = True
        
        self.apply_stylesheet()
        self.init_menu() 
        self.init_ui()
        self.init_tray()
        
        # 데몬 스레드로 설정하여 메인 프로세스 종료 시 자동 소멸 유도
        self.hotkey_thread = HotkeyListener()
        self.hotkey_thread.daemon = True 
        self.hotkey_thread.show_signal.connect(self.show_window_from_tray)
        self.hotkey_thread.start()
        
        self.update_always_on_top()
        self.load_data()

    def restore_window_state(self):
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(600, 800)

    def closeEvent(self, event):
        # 닫기 버튼 누르면 트레이로 숨김
        self.settings.setValue("geometry", self.saveGeometry())
        
        if self.tray_icon.isVisible():
            self.hide()
            self.tray_icon.showMessage("스마트 클립보드", "백그라운드에서 실행 중입니다.", QSystemTrayIcon.MessageIcon.Information, 1000)
            event.ignore()
        else:
            self.quit_app()
            event.accept()

    def quit_app(self):
        try:
            keyboard.unhook_all()
        except:
            pass
        self.db.close()
        QApplication.quit()

    def create_app_icon(self):
        size = 64
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 배경 (파란색)
        painter.setBrush(QBrush(QColor("#4A90E2")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, size, size)
        
        # 문서
        painter.setBrush(QBrush(QColor("white")))
        rect_w, rect_h = 32, 40
        painter.drawRoundedRect((size-rect_w)//2, (size-rect_h)//2 + 4, rect_w, rect_h, 4, 4)
        
        # 클립
        painter.setBrush(QBrush(QColor("#333")))
        clip_w, clip_h = 20, 10
        painter.drawRoundedRect((size-clip_w)//2, (size-rect_h)//2, clip_w, clip_h, 2, 2)
        
        # 라인
        painter.setPen(QPen(QColor("#DDD"), 2))
        line_start_x = (size-rect_w)//2 + 6
        line_end_x = (size-rect_w)//2 + rect_w - 6
        y_start = (size-rect_h)//2 + 18
        for i in range(3):
            y = y_start + (i * 8)
            painter.drawLine(line_start_x, y, line_end_x, y)

        painter.end()
        return QIcon(pixmap)

    def apply_stylesheet(self):
        style = """
        QMainWindow { background-color: #2E2E2E; }
        QMenuBar { background-color: #252525; color: #DDD; font-family: 'Malgun Gothic'; }
        QMenuBar::item:selected { background-color: #4A90E2; }
        QMenu { background-color: #333; color: white; border: 1px solid #555; font-family: 'Malgun Gothic'; }
        QMenu::item:selected { background-color: #4A90E2; }
        
        QWidget { color: #E0E0E0; font-family: 'Malgun Gothic'; font-size: 13px; }
        
        QLineEdit, QComboBox { 
            background-color: #3E3E3E; border: 1px solid #555; 
            border-radius: 15px; padding: 6px 15px; color: #FFF; 
        }
        QLineEdit:focus, QComboBox:focus { border: 1px solid #4A90E2; }
        QComboBox::drop-down { border: none; }
        
        QTableWidget { 
            background-color: #363636; border: none; 
            selection-background-color: #4A90E2; 
            gridline-color: #444;
        }
        QHeaderView::section { 
            background-color: #252525; padding: 5px; border: none; font-weight: bold; color: #AAA; 
        }
        
        QTextEdit { 
            background-color: #1E1E1E; border: 1px solid #444; border-radius: 5px; padding: 10px; 
            font-family: 'Malgun Gothic', monospace; font-size: 14px;
        }
        
        QLabel#ImagePreview {
            background-color: #1E1E1E; border: 1px solid #444; border-radius: 5px;
        }
        
        QPushButton { 
            background-color: #444; border: none; border-radius: 4px; padding: 8px 12px; color: white; 
        }
        QPushButton:hover { background-color: #555; }
        QPushButton:pressed { background-color: #333; }
        
        QPushButton#ToolBtn {
            background-color: #3E3E3E; font-size: 12px; padding: 5px 10px;
        }
        QPushButton#DeleteBtn { background-color: #D32F2F; }
        QPushButton#DeleteBtn:hover { background-color: #B71C1C; }
        """
        self.setStyleSheet(style)

    def init_menu(self):
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("파일")
        
        action_export = QAction("💾 텍스트 내보내기 (.txt)", self)
        action_export.triggered.connect(self.export_history)
        file_menu.addAction(action_export)

        action_quit = QAction("❌ 종료", self)
        action_quit.triggered.connect(self.quit_app)
        file_menu.addAction(action_quit)

        settings_menu = menubar.addMenu("설정")
        
        self.action_ontop = QAction("📌 항상 위 고정", self, checkable=True)
        self.action_ontop.setChecked(True)
        self.action_ontop.triggered.connect(self.toggle_always_on_top)
        settings_menu.addAction(self.action_ontop)
        
        self.action_startup = QAction("🚀 윈도우 시작 시 자동 실행", self, checkable=True)
        self.action_startup.setChecked(self.check_startup_registry())
        self.action_startup.triggered.connect(self.toggle_startup)
        settings_menu.addAction(self.action_startup)
        
        settings_menu.addSeparator()
        
        action_clear = QAction("🗑️ 기록 전체 삭제", self)
        action_clear.triggered.connect(self.clear_all_history)
        settings_menu.addAction(action_clear)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        top_layout = QHBoxLayout()
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["전체", "텍스트", "이미지", "링크", "코드", "색상"])
        self.filter_combo.setFixedWidth(100)
        self.filter_combo.currentTextChanged.connect(self.load_data)
        
        search_icon = QLabel("🔍")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("검색...")
        self.search_input.textChanged.connect(self.load_data)
        
        top_layout.addWidget(self.filter_combo)
        top_layout.addWidget(search_icon)
        top_layout.addWidget(self.search_input)
        main_layout.addLayout(top_layout)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["📌", "유형", "내용", "시간"])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        
        self.table.setColumnWidth(0, 30)
        self.table.setColumnWidth(1, 60)
        self.table.setColumnWidth(3, 80)
        
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setShowGrid(False)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.cellDoubleClicked.connect(self.on_double_click_paste)
        
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        splitter.addWidget(self.table)

        detail_container = QWidget()
        detail_layout = QVBoxLayout(detail_container)
        detail_layout.setContentsMargins(0, 10, 0, 0)
        
        self.tools_layout = QHBoxLayout()
        self.tools_layout.setSpacing(5)
        self.tools_layout.addStretch()
        
        self.btn_save_img = QPushButton("💾 이미지 저장")
        self.btn_save_img.setObjectName("ToolBtn")
        self.btn_save_img.clicked.connect(self.save_image_to_file)
        self.btn_save_img.setVisible(False)
        
        self.btn_google = QPushButton("구글 검색")
        self.btn_google.setObjectName("ToolBtn")
        self.btn_google.clicked.connect(self.search_google)
        
        self.btn_qr = QPushButton("QR 코드")
        self.btn_qr.setObjectName("ToolBtn")
        self.btn_qr.clicked.connect(self.generate_qr)
        
        self.btn_upper = QPushButton("대문자")
        self.btn_upper.setObjectName("ToolBtn")
        self.btn_upper.clicked.connect(lambda: self.transform_text("upper"))
        
        self.btn_lower = QPushButton("소문자")
        self.btn_lower.setObjectName("ToolBtn")
        self.btn_lower.clicked.connect(lambda: self.transform_text("lower"))
        
        self.btn_strip = QPushButton("공백 제거")
        self.btn_strip.setObjectName("ToolBtn")
        self.btn_strip.clicked.connect(lambda: self.transform_text("strip"))

        self.tools_layout.addWidget(self.btn_save_img)
        self.tools_layout.addWidget(self.btn_google)
        if HAS_QRCODE:
            self.tools_layout.addWidget(self.btn_qr)
        self.tools_layout.addWidget(self.btn_upper)
        self.tools_layout.addWidget(self.btn_lower)
        self.tools_layout.addWidget(self.btn_strip)
        detail_layout.addLayout(self.tools_layout)

        self.detail_stack = QStackedWidget()
        
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_stack.addWidget(self.detail_text)
        
        self.detail_image_lbl = QLabel()
        self.detail_image_lbl.setObjectName("ImagePreview")
        self.detail_image_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_stack.addWidget(self.detail_image_lbl)
        
        detail_layout.addWidget(self.detail_stack)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.btn_copy = QPushButton("📄 복사")
        self.btn_copy.setMinimumHeight(40)
        self.btn_copy.clicked.connect(self.copy_item)
        
        self.btn_link = QPushButton("🔗 링크 열기")
        self.btn_link.setMinimumHeight(40)
        self.btn_link.clicked.connect(self.open_link)
        
        self.btn_pin = QPushButton("📌 고정")
        self.btn_pin.setMinimumHeight(40)
        self.btn_pin.clicked.connect(self.toggle_pin)
        
        self.btn_del = QPushButton("🗑 삭제")
        self.btn_del.setMinimumHeight(40)
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
        
        tray_menu = QMenu()
        show_action = QAction("열기", self)
        show_action.triggered.connect(self.show_window_from_tray)
        quit_action = QAction("종료", self)
        quit_action.triggered.connect(self.quit_app)
        
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

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
                QMessageBox.information(self, "설정", "윈도우 시작 시 자동 실행됩니다.")
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                    QMessageBox.information(self, "설정", "자동 실행이 해제되었습니다.")
                except WindowsError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"레지스트리 설정 실패: {e}")
            self.action_startup.setChecked(not enable)

    def clear_all_history(self):
        if QMessageBox.question(self, "초기화", "고정된 항목을 제외한 모든 기록을 삭제하시겠습니까?", 
                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.db.clear_all()
            self.load_data()
            self.update_ui_state(False)
            
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
                    f.write("="*50 + "\n\n")
                    for content, timestamp in data:
                        f.write(f"[{timestamp}]\n{content}\n")
                        f.write("-" * 30 + "\n")
                QMessageBox.information(self, "성공", "기록이 성공적으로 저장되었습니다.")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"저장 중 오류 발생: {e}")

    def save_image_to_file(self):
        pid = self.get_selected_id()
        if not pid: return
        
        data = self.db.get_content(pid)
        if data:
            _, blob, ptype = data
            if ptype == "IMAGE" and blob:
                file_name, _ = QFileDialog.getSaveFileName(self, "이미지 저장", f"image_{int(time.time())}.png", "Images (*.png);;All Files (*)")
                if file_name:
                    try:
                        pixmap = QPixmap()
                        pixmap.loadFromData(blob)
                        pixmap.save(file_name, "PNG")
                        QMessageBox.information(self, "성공", "이미지가 저장되었습니다.")
                    except Exception as e:
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
            QMessageBox.warning(self, "QR 오류", str(e))

    def on_tray_activated(self, reason):
        # [수정] 싱글 클릭/더블 클릭 모두 창 토글
        if reason == QSystemTrayIcon.ActivationReason.Trigger or \
           reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show_window_from_tray()

    def show_window_from_tray(self):
        self.show()
        self.activateWindow()
        self.raise_()
        self.search_input.setFocus()

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
                return
            if mime_data.hasText():
                text = mime_data.text().strip()
                if not text: return
                tag = self.analyze_text(text)
                if self.db.add_item(text, None, tag):
                    self.load_data()
        except Exception as e:
            # 타 프로그램이 클립보드 점유 중일 때 안전하게 무시
            pass

    def analyze_text(self, text):
        if re.match(r'http[s]?://', text): return "LINK"
        if re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', text): return "COLOR"
        if any(x in text for x in ["def ", "class ", "{", "}", "=>"]): return "CODE"
        return "TEXT"

    def load_data(self):
        search_query = self.search_input.text()
        filter_type = self.filter_combo.currentText()
        
        items = self.db.get_items(search_query, filter_type)
        self.table.setRowCount(0)
        
        for row_idx, (pid, content, ptype, timestamp, pinned) in enumerate(items):
            self.table.insertRow(row_idx)
            
            pin_item = QTableWidgetItem("📌" if pinned else "")
            pin_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            pin_item.setData(Qt.ItemDataRole.UserRole, pid)
            self.table.setItem(row_idx, 0, pin_item)
            
            type_item = QTableWidgetItem(ptype)
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if ptype == "LINK": type_item.setForeground(QColor("#4A90E2"))
            elif ptype == "IMAGE": type_item.setForeground(QColor("#E91E63"))
            elif ptype == "CODE": type_item.setForeground(QColor("#98C379"))
            self.table.setItem(row_idx, 1, type_item)
            
            display = content.replace('\n', ' ').strip()
            if len(display) > 50: display = display[:50] + "..."
            self.table.setItem(row_idx, 2, QTableWidgetItem(display))
            
            try:
                dt = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                time_str = dt.strftime("%H:%M") if dt.date() == datetime.date.today() else dt.strftime("%m-%d")
            except:
                time_str = timestamp
            
            time_item = QTableWidgetItem(time_str)
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            time_item.setForeground(QColor("#888"))
            self.table.setItem(row_idx, 3, time_item)

    def on_selection_changed(self):
        pid = self.get_selected_id()
        if not pid:
            self.update_ui_state(False)
            return
            
        data = self.db.get_content(pid)
        if data:
            content, blob, ptype = data
            
            if ptype == "IMAGE" and blob:
                self.detail_stack.setCurrentIndex(1)
                pixmap = QPixmap()
                pixmap.loadFromData(blob)
                w, h = self.detail_image_lbl.width(), self.detail_image_lbl.height()
                if w > 0 and h > 0:
                    self.detail_image_lbl.setPixmap(pixmap.scaled(QSize(w-10, h-10), Qt.AspectRatioMode.KeepAspectRatio))
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
                
                if ptype == "COLOR":
                    self.detail_text.setStyleSheet(f"background-color: {content}; color: black;")
                else:
                    self.detail_text.setStyleSheet("background-color: #1E1E1E; color: #E0E0E0; border: 1px solid #444;")

            self.btn_copy.setEnabled(True)
            self.btn_pin.setEnabled(True)
            self.btn_del.setEnabled(True)
            
            is_pinned = self.table.item(self.table.currentRow(), 0).text() == "📌"
            self.btn_pin.setText("📌 해제" if is_pinned else "📌 고정")

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
        elif mode == "strip": new_text = text.strip().replace("  ", " ")
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
            self.statusBar().showMessage("✅ 복사됨", 2000)
    
    def on_double_click_paste(self, row, col):
        self.copy_item()
        self.hide()
        QTimer.singleShot(200, lambda: keyboard.send('ctrl+v'))

    def delete_item(self):
        pid = self.get_selected_id()
        if pid:
            self.db.delete_item(pid)
            self.load_data()
            self.update_ui_state(False)
    
    def toggle_pin(self):
        pid = self.get_selected_id()
        if pid:
            self.db.toggle_pin(pid)
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

    def show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item: return
        menu = QMenu()
        menu.addAction("복사").triggered.connect(self.copy_item)
        menu.addAction("삭제").triggered.connect(self.delete_item)
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
