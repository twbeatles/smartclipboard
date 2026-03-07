"""Copy rules dialog module."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


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
        actions = ["trim", "lowercase", "uppercase", "remove_newlines"]
        action, ok = QInputDialog.getItem(self, "규칙 추가", "동작:", actions, 0, False)
        if ok:
            self.db.add_copy_rule(name.strip(), pattern.strip(), action)
            self.load_rules()
            if hasattr(self.parent(), "invalidate_rules_cache"):
                self.parent().invalidate_rules_cache()

    def toggle_rule(self, rule_id, state):
        self.db.toggle_copy_rule(rule_id, 1 if state else 0)
        if hasattr(self.parent(), "invalidate_rules_cache"):
            self.parent().invalidate_rules_cache()

    def delete_rule(self):
        rows = self.table.selectionModel().selectedRows()
        if rows:
            rid = self.table.item(rows[0].row(), 1).data(Qt.ItemDataRole.UserRole)
            self.db.delete_copy_rule(rid)
            self.load_rules()
            if hasattr(self.parent(), "invalidate_rules_cache"):
                self.parent().invalidate_rules_cache()


__all__ = ["CopyRulesDialog"]
