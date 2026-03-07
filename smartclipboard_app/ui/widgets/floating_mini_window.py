"""Floating mini window widget module."""

from __future__ import annotations

import logging

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
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
FALLBACK_TYPE_ICONS = {"TEXT": "📝", "LINK": "🔗", "IMAGE": "🖼️", "CODE": "💻", "COLOR": "🎨"}


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
        self.keyboard = keyboard_module
        self.setWindowTitle("📋 빠른 클립보드")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(280, 350)
        self.resize(300, 400)
        self.drag_pos = None
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
        theme_name = self.parent_window.current_theme if self.parent_window and hasattr(self.parent_window, "current_theme") else "dark"
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
            display = content.replace("\n", " ")[:35] + ("..." if len(content) > 35 else "")
            item = QListWidgetItem(f"{pin_mark}{icon} {display}")
            item.setData(Qt.ItemDataRole.UserRole, pid)
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
                if ptype == "IMAGE" and blob:
                    pixmap = QPixmap()
                    pixmap.loadFromData(blob)
                    clipboard.setPixmap(pixmap)
                else:
                    clipboard.setText(content)
                self.db.increment_use_count(pid)
                self.hide()
                if self.keyboard is not None:
                    QTimer.singleShot(200, lambda: self.keyboard.send("ctrl+v"))
        except Exception as exc:
            self.logger.error("Mini window copy error: %s", exc)

    def open_main_window(self):
        if self.parent_window:
            self.parent_window.show()
            self.parent_window.activateWindow()
        self.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_pos:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def showEvent(self, event):
        super().showEvent(event)
        self.load_items()


__all__ = ["FloatingMiniWindow", "FALLBACK_THEMES", "FALLBACK_GLASS_STYLES", "FALLBACK_TYPE_ICONS"]
