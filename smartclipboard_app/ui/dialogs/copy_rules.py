"""Copy rules dialog module."""

from __future__ import annotations

import re
from typing import Protocol, TypeVar, cast

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
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


class CopyRuleEditDialog(QDialog):
    ACTIONS = {
        "trim": "공백 제거",
        "lowercase": "소문자 변환",
        "uppercase": "대문자 변환",
        "remove_newlines": "줄바꿈 제거",
        "custom_replace": "정규식 치환",
    }

    def __init__(self, parent, db, rule=None):
        super().__init__(parent)
        self.db = db
        self.rule = rule
        self.setWindowTitle("규칙 추가" if rule is None else "규칙 편집")
        self.setMinimumWidth(420)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.name_input = QLineEdit()
        self.pattern_input = QLineEdit()
        self.action_combo = QComboBox()
        for key, label in self.ACTIONS.items():
            self.action_combo.addItem(label, key)
        self.replacement_input = QLineEdit()
        self.replacement_input.setPlaceholderText("치환 문자열")

        form.addRow("이름:", self.name_input)
        form.addRow("패턴:", self.pattern_input)
        form.addRow("동작:", self.action_combo)
        form.addRow("치환값:", self.replacement_input)
        layout.addLayout(form)

        self.action_combo.currentIndexChanged.connect(self._sync_replacement_state)

        btn_layout = QHBoxLayout()
        btn_save = QPushButton("저장")
        btn_save.clicked.connect(self.save_rule)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        if self.rule is not None:
            _rid, name, pattern, action, replacement, _enabled, _priority = self.rule
            self.name_input.setText(name)
            self.pattern_input.setText(pattern)
            idx = self.action_combo.findData(action)
            if idx >= 0:
                self.action_combo.setCurrentIndex(idx)
            self.replacement_input.setText(replacement or "")
        self._sync_replacement_state()

    def _sync_replacement_state(self):
        is_replace = self.action_combo.currentData() == "custom_replace"
        self.replacement_input.setEnabled(is_replace)
        if not is_replace:
            self.replacement_input.clear()

    def save_rule(self):
        name = self.name_input.text().strip()
        pattern = self.pattern_input.text().strip()
        action = self.action_combo.currentData()
        replacement = self.replacement_input.text()

        if not name or not pattern:
            QMessageBox.warning(self, "경고", "이름과 패턴을 입력하세요.")
            return

        try:
            re.compile(pattern)
        except re.error as exc:
            QMessageBox.warning(self, "패턴 오류", f"잘못된 정규식 패턴입니다.\n{exc}")
            return

        if action == "custom_replace" and replacement == "":
            QMessageBox.warning(self, "경고", "정규식 치환에는 치환값이 필요합니다.")
            return

        exclude_id = self.rule[0] if self.rule is not None else None
        if hasattr(self.db, "is_duplicate_copy_rule") and self.db.is_duplicate_copy_rule(
            pattern, action, replacement if action == "custom_replace" else "", exclude_id=exclude_id
        ):
            QMessageBox.information(self, "중복 규칙", "동일한 패턴/동작 규칙이 이미 존재합니다.")
            return

        ok = False
        if self.rule is None:
            ok = self.db.add_copy_rule(name, pattern, action, replacement if action == "custom_replace" else "")
        else:
            ok = self.db.update_copy_rule(
                self.rule[0],
                name,
                pattern,
                action,
                replacement if action == "custom_replace" else "",
            )

        if not ok:
            QMessageBox.critical(self, "오류", "규칙 저장에 실패했습니다.")
            return
        self.accept()


class CopyRulesDialog(QDialog):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.rules = []
        self.setWindowTitle("⚙️ 복사 규칙 관리")
        self.setMinimumSize(680, 420)
        self.init_ui()
        self.load_rules()

    def init_ui(self):
        layout = QVBoxLayout(self)

        top_layout = QHBoxLayout()
        btn_add = QPushButton("➕ 규칙 추가")
        btn_add.clicked.connect(self.add_rule)
        btn_edit = QPushButton("✏️ 편집")
        btn_edit.clicked.connect(self.edit_rule)
        btn_up = QPushButton("⬆ 우선순위")
        btn_up.clicked.connect(lambda: self.move_selected(-1))
        btn_down = QPushButton("⬇ 우선순위")
        btn_down.clicked.connect(lambda: self.move_selected(1))
        top_layout.addWidget(btn_add)
        top_layout.addWidget(btn_edit)
        top_layout.addWidget(btn_up)
        top_layout.addWidget(btn_down)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["활성", "이름", "패턴", "동작", "치환값", "순서"])
        header = _ensure(self.table.horizontalHeader())
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 130)
        self.table.setColumnWidth(3, 120)
        self.table.setColumnWidth(4, 120)
        self.table.setColumnWidth(5, 60)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.cellDoubleClicked.connect(lambda *_args: self.edit_rule())
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

    def _notify_parent(self):
        parent = _rules_parent(self.parent())
        if parent is not None:
            parent.invalidate_rules_cache()

    def _selected_row(self):
        selection_model = self.table.selectionModel()
        if selection_model is None:
            return None
        rows = selection_model.selectedRows()
        return rows[0].row() if rows else None

    def _selected_rule(self):
        row = self._selected_row()
        if row is None or row >= len(self.rules):
            return None
        return self.rules[row]

    def load_rules(self):
        self.rules = list(self.db.get_copy_rules())
        self.table.setRowCount(0)
        action_labels = CopyRuleEditDialog.ACTIONS
        for row_idx, (rid, name, pattern, action, replacement, enabled, _priority) in enumerate(self.rules):
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
            self.table.setItem(row_idx, 3, QTableWidgetItem(action_labels.get(action, action)))
            self.table.setItem(row_idx, 4, QTableWidgetItem(replacement or "-"))
            order_item = QTableWidgetItem(str(row_idx + 1))
            order_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 5, order_item)

    def add_rule(self):
        dialog = CopyRuleEditDialog(self, self.db)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_rules()
            self._notify_parent()

    def edit_rule(self):
        rule = self._selected_rule()
        if rule is None:
            QMessageBox.information(self, "알림", "편집할 규칙을 선택하세요.")
            return
        dialog = CopyRuleEditDialog(self, self.db, rule=rule)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_rules()
            self._notify_parent()

    def move_selected(self, direction: int):
        row = self._selected_row()
        if row is None:
            return
        target = row + direction
        if target < 0 or target >= len(self.rules):
            return
        self.rules[row], self.rules[target] = self.rules[target], self.rules[row]
        ordered_ids = [rule[0] for rule in self.rules]
        if hasattr(self.db, "update_copy_rule_priorities") and self.db.update_copy_rule_priorities(ordered_ids):
            self.load_rules()
            self.table.selectRow(target)
            self._notify_parent()

    def toggle_rule(self, rule_id, state):
        self.db.toggle_copy_rule(rule_id, 1 if state else 0)
        self._notify_parent()

    def delete_rule(self):
        rule = self._selected_rule()
        if rule is None:
            return
        reply = QMessageBox.question(
            self,
            "삭제 확인",
            "이 규칙을 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_copy_rule(rule[0])
        self.load_rules()
        self._notify_parent()


__all__ = ["CopyRuleEditDialog", "CopyRulesDialog"]
