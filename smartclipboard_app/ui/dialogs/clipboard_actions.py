"""Clipboard actions dialog module."""

from __future__ import annotations

import re

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ClipboardActionsDialog(QDialog):
    """Manage clipboard automation action rules."""

    def __init__(self, parent, db, action_manager):
        super().__init__(parent)
        self.db = db
        self.action_manager = action_manager
        self.setWindowTitle("⚡ 클립보드 액션")
        self.setMinimumSize(600, 400)
        self.init_ui()
        self.load_actions()

    def init_ui(self):
        layout = QVBoxLayout(self)

        btn_layout = QHBoxLayout()
        btn_add = QPushButton("➕ 액션 추가")
        btn_add.clicked.connect(self.add_action)
        btn_layout.addWidget(btn_add)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

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

        default_layout = QHBoxLayout()
        btn_defaults = QPushButton("📦 기본 액션 추가")
        btn_defaults.clicked.connect(self.add_default_actions)
        default_layout.addWidget(btn_defaults)
        default_layout.addStretch()
        layout.addLayout(default_layout)

        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def load_actions(self):
        actions = self.db.get_clipboard_actions()
        self.table.setRowCount(0)

        action_type_names = {
            "fetch_title": "🔗 제목 가져오기",
            "format_phone": "📱 전화번호 포맷",
            "format_email": "✉ 이메일 포맷",
            "notify": "🔔 알림",
            "transform": "📝 텍스트 변환",
        }

        for row_idx, (aid, name, pattern, action_type, _params, enabled, _priority) in enumerate(actions):
            self.table.insertRow(row_idx)

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

            btn_del = QPushButton("❌")
            btn_del.clicked.connect(lambda checked, a=aid: self.delete_action(a))
            self.table.setCellWidget(row_idx, 4, btn_del)

    def add_action(self):
        name, ok = QInputDialog.getText(self, "액션 추가", "액션 이름:")
        if not ok or not name.strip():
            return

        pattern, ok = QInputDialog.getText(self, "액션 추가", "패턴 (정규식):", text="https?://")
        if not ok or not pattern.strip():
            return

        try:
            re.compile(pattern)
        except re.error as exc:
            QMessageBox.warning(self, "패턴 오류", f"잘못된 정규식 패턴입니다.\n{exc}")
            return

        action_types = ["fetch_title", "format_phone", "format_email", "notify", "transform"]
        action_labels = ["🔗 URL 제목 가져오기", "📱 전화번호 포맷", "✉ 이메일 포맷", "🔔 알림 표시", "📝 텍스트 변환"]
        action, ok = QInputDialog.getItem(self, "액션 추가", "액션 유형:", action_labels, 0, False)
        if ok:
            idx = action_labels.index(action)
            self.db.add_clipboard_action(name.strip(), pattern.strip(), action_types[idx])
            self.action_manager.reload_actions()
            self.load_actions()

    def toggle_action(self, action_id, state):
        self.db.toggle_clipboard_action(action_id, 1 if state else 0)
        self.action_manager.reload_actions()

    def delete_action(self, action_id):
        self.db.delete_clipboard_action(action_id)
        self.action_manager.reload_actions()
        self.load_actions()

    def add_default_actions(self):
        defaults = [
            ("URL 제목 가져오기", r"https?://", "fetch_title"),
            ("전화번호 자동 포맷", r"^0\\d{9,10}$", "format_phone"),
        ]
        for name, pattern, action_type in defaults:
            self.db.add_clipboard_action(name, pattern, action_type)
        self.action_manager.reload_actions()
        self.load_actions()
        QMessageBox.information(self, "완료", "기본 액션이 추가되었습니다.")


__all__ = ["ClipboardActionsDialog"]
