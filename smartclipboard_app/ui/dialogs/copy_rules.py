"""Copy rules dialog module."""

from __future__ import annotations

import re
from typing import Protocol, TypeVar, cast

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

T = TypeVar("T")


class _RulesParent(Protocol):
    def invalidate_rules_cache(self) -> None: ...


def _ensure(value: T | None) -> T:
    assert value is not None
    return value


def _rules_parent(value: object | None) -> _RulesParent | None:
    if value is not None and hasattr(value, "invalidate_rules_cache"):
        return cast(_RulesParent, value)
    return None


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

        btn_layout = QHBoxLayout()
        btn_add = QPushButton("➕ 규칙 추가")
        btn_add.clicked.connect(self.add_rule)
        btn_layout.addWidget(btn_add)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["활성", "이름", "패턴", "동작"])
        header = _ensure(self.table.horizontalHeader())
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(3, 80)
        vertical_header = self.table.verticalHeader()
        if vertical_header is not None:
            vertical_header.setVisible(False)
        layout.addWidget(self.table)

        bottom_layout = QHBoxLayout()
        btn_delete = QPushButton("❌ 삭제")
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
        for row_idx, (rid, name, pattern, action, _replacement, enabled, _priority) in enumerate(rules):
            self.table.insertRow(row_idx)

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
        try:
            re.compile(pattern.strip())
        except re.error as exc:
            QMessageBox.warning(self, "패턴 오류", f"잘못된 정규식 패턴입니다.\n{exc}")
            return
        actions = ["trim", "lowercase", "uppercase", "remove_newlines"]
        action, ok = QInputDialog.getItem(self, "규칙 추가", "동작:", actions, 0, False)
        if ok:
            if hasattr(self.db, "is_duplicate_copy_rule") and self.db.is_duplicate_copy_rule(
                pattern.strip(), action, ""
            ):
                QMessageBox.information(self, "중복 규칙", "동일한 패턴/동작 규칙이 이미 존재합니다.")
                return
            if not self.db.add_copy_rule(name.strip(), pattern.strip(), action):
                QMessageBox.critical(self, "오류", "규칙 추가에 실패했습니다.")
                return
            self.load_rules()
            parent = _rules_parent(self.parent())
            if parent is not None:
                parent.invalidate_rules_cache()

    def toggle_rule(self, rule_id, state):
        self.db.toggle_copy_rule(rule_id, 1 if state else 0)
        parent = _rules_parent(self.parent())
        if parent is not None:
            parent.invalidate_rules_cache()

    def delete_rule(self):
        selection_model = self.table.selectionModel()
        if selection_model is None:
            return
        rows = selection_model.selectedRows()
        if rows:
            item = self.table.item(rows[0].row(), 1)
            if item is None:
                return
            rid = item.data(Qt.ItemDataRole.UserRole)
            self.db.delete_copy_rule(rid)
            self.load_rules()
            parent = _rules_parent(self.parent())
            if parent is not None:
                parent.invalidate_rules_cache()


__all__ = ["CopyRulesDialog"]
