"""Floating mini window widget module."""

from __future__ import annotations

import logging
from typing import Protocol, cast

from PyQt6.QtCore import QPoint, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QPixmap, QShowEvent
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from smartclipboard_app.ui.clipboard_guard import mark_internal_copy, restore_file_clipboard
from smartclipboard_core.file_paths import (
    build_file_paths_tooltip,
    describe_file_paths_with_status,
    file_paths_from_content,
)

logger = logging.getLogger(__name__)

FALLBACK_THEMES = {
    "dark": {
        "text": "#f1f5f9",
        "border": "#334155",
        "hover_bg": "#2d2d3d",
        "hover_text": "#ffffff",
        "selected_text": "#ffffff",
        "primary": "#6366f1",
        "surface_variant": "#252532",
    }
}
FALLBACK_GLASS_STYLES = {"dark": {"glass_bg": "rgba(22, 33, 62, 0.85)"}}
FALLBACK_TYPE_ICONS = {"TEXT": "📝", "LINK": "🔗", "IMAGE": "🖼️", "CODE": "💻", "COLOR": "🎨", "FILE": "📎"}


class _MiniParent(Protocol):
    current_theme: str

    def show(self) -> None: ...
    def activateWindow(self) -> None: ...


class _KeyboardSender(Protocol):
    def send(self, hotkey: str) -> object: ...


def _mini_parent(value: object | None) -> _MiniParent | None:
    if value is not None and hasattr(value, "show") and hasattr(value, "activateWindow"):
        return cast(_MiniParent, value)
    return None


class FloatingMiniWindow(QWidget):
    """Floating quick-access clipboard widget."""

    item_selected = pyqtSignal(int)

    def __init__(
        self,
        db,
        parent=None,
        themes=None,
        glass_styles=None,
        type_icons=None,
        logger_=None,
        keyboard_module=None,
    ):
        super().__init__(parent)
        self.db = db
        self.parent_window = parent
        self.themes = themes or FALLBACK_THEMES
        self.glass_styles = glass_styles or FALLBACK_GLASS_STYLES
        self.type_icons = type_icons or FALLBACK_TYPE_ICONS
        self.logger = logger_ or logger
        self.keyboard = cast(_KeyboardSender | None, keyboard_module)
        self.setWindowTitle("📋 빠른 클립보드")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(280, 350)
        self.resize(300, 400)
        self.drag_pos: QPoint | None = None
        self.init_ui()

    def init_ui(self):
        self.container = QFrame(self)
        self.container.setObjectName("MiniContainer")
        self.apply_mini_theme()

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

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

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.list_widget)

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

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)

    def apply_mini_theme(self):
        parent = _mini_parent(self.parent_window)
        theme_name = parent.current_theme if parent is not None else "dark"
        theme = self.themes.get(theme_name, self.themes["dark"])
        glass = self.glass_styles.get(theme_name, self.glass_styles["dark"])

        self.container.setStyleSheet(
            f"""
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
            """
        )

    def load_items(self):
        self.list_widget.clear()
        try:
            items = self.db.get_items("", "전체")[:10]
        except Exception as exc:
            self.logger.error("Mini window load error: %s", exc)
            items = []

        if not items:
            empty_item = QListWidgetItem("📭 클립보드 히스토리가 비어 있습니다")
            empty_item.setData(Qt.ItemDataRole.UserRole, None)
            self.list_widget.addItem(empty_item)
            return

        for pid, content, ptype, _timestamp, pinned, _use_count, _pin_order in items:
            icon = self.type_icons.get(ptype, "📝")
            pin_mark = "📌 " if pinned else ""
            if ptype == "FILE":
                display = describe_file_paths_with_status(file_paths_from_content(content))
            else:
                display = content.replace("\n", " ")[:35] + ("..." if len(content) > 35 else "")
            item = QListWidgetItem(f"{pin_mark}{icon} {display}")
            item.setData(Qt.ItemDataRole.UserRole, pid)
            if ptype == "FILE":
                file_paths = file_paths_from_content(content)
                item.setToolTip(build_file_paths_tooltip(file_paths))
            else:
                item.setToolTip(content[:200])
            self.list_widget.addItem(item)

    def on_item_double_clicked(self, item):
        pid = item.data(Qt.ItemDataRole.UserRole)
        if not pid:
            return
        try:
            data = self.db.get_content(pid)
            if data:
                content, blob, ptype = data
                clipboard = QApplication.clipboard()
                if clipboard is None:
                    return
                if ptype == "IMAGE" and blob:
                    mark_internal_copy(self.parent_window)
                    pixmap = QPixmap()
                    pixmap.loadFromData(blob)
                    clipboard.setPixmap(pixmap)
                elif ptype == "FILE":
                    restore_result = restore_file_clipboard(self.parent_window, clipboard, file_paths_from_content(content))
                    if not restore_result["applied"]:
                        return
                    if restore_result["missing_paths"]:
                        parent = _mini_parent(self.parent_window)
                        if parent is not None and hasattr(parent, "statusBar"):
                            status_bar = parent.statusBar()
                            if status_bar is not None:
                                status_bar.showMessage(
                                    f"⚠️ 일부 파일이 없어 {len(restore_result['available_paths'])}개만 복원했습니다.",
                                    2500,
                                )
                else:
                    mark_internal_copy(self.parent_window)
                    clipboard.setText(content)
                self.db.increment_use_count(pid)
                self.hide()
                keyboard = self.keyboard
                if keyboard is not None:
                    QTimer.singleShot(200, lambda: keyboard.send("ctrl+v"))
        except Exception as exc:
            self.logger.error("Mini window copy error: %s", exc)

    def open_main_window(self):
        parent = _mini_parent(self.parent_window)
        if parent is not None:
            parent.show()
            parent.activateWindow()
        self.hide()

    def mousePressEvent(self, a0: QMouseEvent | None) -> None:
        if a0 is not None and a0.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = a0.globalPosition().toPoint() - self.frameGeometry().topLeft()
            a0.accept()

    def mouseMoveEvent(self, a0: QMouseEvent | None) -> None:
        if a0 is not None and a0.buttons() == Qt.MouseButton.LeftButton and self.drag_pos is not None:
            self.move(a0.globalPosition().toPoint() - self.drag_pos)
            a0.accept()

    def showEvent(self, a0: QShowEvent | None) -> None:
        super().showEvent(a0)
        self.load_items()


__all__ = ["FloatingMiniWindow", "FALLBACK_THEMES", "FALLBACK_GLASS_STYLES", "FALLBACK_TYPE_ICONS"]
