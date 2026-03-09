"""Trash dialog module."""

from __future__ import annotations

from typing import Protocol, TypeVar, cast

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

FALLBACK_THEMES = {
    "dark": {
        "background": "#0f0f14",
        "surface": "#1a1a24",
        "surface_variant": "#252532",
        "primary": "#6366f1",
        "text": "#f1f5f9",
        "text_secondary": "#94a3b8",
        "border": "#334155",
    }
}

T = TypeVar("T")


class _TrashParent(Protocol):
    def load_data(self) -> None: ...
    def statusBar(self) -> QStatusBar | None: ...


def _ensure(value: T | None) -> T:
    assert value is not None
    return value


def _trash_parent(value: object | None) -> _TrashParent | None:
    if value is not None and hasattr(value, "load_data") and hasattr(value, "statusBar"):
        return cast(_TrashParent, value)
    return None


class TrashDialog(QDialog):
    """Restore or permanently delete items from trash."""

    def __init__(self, parent, db, themes=None):
        super().__init__(parent)
        self.db = db
        self.parent_window = parent
        self.themes = themes or FALLBACK_THEMES
        self.current_theme = parent.current_theme if hasattr(parent, "current_theme") else "dark"
        self.setWindowTitle("🗑️ 휴지통")
        self.setMinimumSize(550, 400)
        self.apply_dialog_theme()
        self.init_ui()
        self.load_items()

    def apply_dialog_theme(self):
        theme = self.themes.get(self.current_theme, self.themes["dark"])
        self.setStyleSheet(
            f"""
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
            """
        )

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info = QLabel("삭제된 항목은 7일 후 자동으로 영구 삭제됩니다.")
        info.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(info)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["내용", "유형", "삭제일", "만료일"])
        header = _ensure(self.table.horizontalHeader())
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 70)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 90)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        vertical_header = self.table.verticalHeader()
        if vertical_header is not None:
            vertical_header.setVisible(False)
        layout.addWidget(self.table)

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
        items = self.db.get_deleted_items()
        self.table.setRowCount(len(items))
        type_icons = {"TEXT": "📝", "LINK": "🔗", "IMAGE": "🖼️", "CODE": "💻", "COLOR": "🎨"}

        for row, (did, content, dtype, deleted_at, expires_at) in enumerate(items):
            display = (content or "[이미지]")[:50].replace("\n", " ")
            if len(content or "") > 50:
                display += "..."
            content_item = QTableWidgetItem(display)
            content_item.setData(Qt.ItemDataRole.UserRole, did)
            content_item.setToolTip(content[:200] if content else "이미지 항목")
            self.table.setItem(row, 0, content_item)

            type_item = QTableWidgetItem(type_icons.get(dtype, "📝"))
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
        selection_model = self.table.selectionModel()
        if selection_model is None:
            return
        rows = selection_model.selectedRows()
        if not rows:
            QMessageBox.information(self, "알림", "복원할 항목을 선택하세요.")
            return

        restored_count = 0
        for row in rows:
            item = self.table.item(row.row(), 0)
            if item is None:
                continue
            did = item.data(Qt.ItemDataRole.UserRole)
            if did and self.db.restore_item(did):
                restored_count += 1

        if restored_count > 0:
            self.load_items()
            parent = _trash_parent(self.parent_window)
            if parent is not None:
                parent.load_data()
                status_bar = parent.statusBar()
                if status_bar is not None:
                    status_bar.showMessage(f"♻️ {restored_count}개 항목이 복원되었습니다.", 2000)

    def empty_trash(self):
        reply = QMessageBox.question(
            self,
            "휴지통 비우기",
            "휴지통의 모든 항목을 영구 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.empty_trash()
            self.load_items()
            parent = _trash_parent(self.parent_window)
            if parent is not None:
                status_bar = parent.statusBar()
                if status_bar is not None:
                    status_bar.showMessage("🗑️ 휴지통이 비워졌습니다.", 2000)


__all__ = ["TrashDialog", "FALLBACK_THEMES"]
