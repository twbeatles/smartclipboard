"""Clipboard actions dialog module."""

from __future__ import annotations

import json
import re
from typing import TypeVar

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

ACTION_TYPE_NAMES = {
    "fetch_title": "🔗 제목 가져오기",
    "format_phone": "📱 전화번호 포맷",
    "format_email": "✉ 이메일 포맷",
    "notify": "🔔 알림",
    "transform": "📝 텍스트 변환",
}

TRANSFORM_MODE_NAMES = {
    "trim": "공백 제거",
    "upper": "대문자",
    "lower": "소문자",
}


def _ensure(value: T | None) -> T:
    assert value is not None
    return value


class ClipboardActionEditDialog(QDialog):
    def __init__(self, parent, db, action=None):
        super().__init__(parent)
        self.db = db
        self.action = action
        self.setWindowTitle("액션 추가" if action is None else "액션 편집")
        self.setMinimumWidth(440)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.name_input = QLineEdit()
        self.pattern_input = QLineEdit()
        self.action_combo = QComboBox()
        for key, label in ACTION_TYPE_NAMES.items():
            self.action_combo.addItem(label, key)
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("알림 메시지")
        self.transform_combo = QComboBox()
        for key, label in TRANSFORM_MODE_NAMES.items():
            self.transform_combo.addItem(label, key)

        form.addRow("이름:", self.name_input)
        form.addRow("패턴:", self.pattern_input)
        form.addRow("액션:", self.action_combo)
        form.addRow("알림 메시지:", self.message_input)
        form.addRow("변환 모드:", self.transform_combo)
        layout.addLayout(form)

        self.action_combo.currentIndexChanged.connect(self._sync_param_state)

        btn_layout = QHBoxLayout()
        btn_save = QPushButton("저장")
        btn_save.clicked.connect(self.save_action)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        if self.action is not None:
            _aid, name, pattern, action_type, params_json, _enabled, _priority = self.action
            self.name_input.setText(name)
            self.pattern_input.setText(pattern)
            idx = self.action_combo.findData(action_type)
            if idx >= 0:
                self.action_combo.setCurrentIndex(idx)
            try:
                params = json.loads(params_json or "{}")
                if not isinstance(params, dict):
                    params = {}
            except Exception:
                params = {}
            self.message_input.setText(str(params.get("message", "")))
            transform_idx = self.transform_combo.findData(params.get("mode", "trim"))
            if transform_idx >= 0:
                self.transform_combo.setCurrentIndex(transform_idx)

        self._sync_param_state()

    def _sync_param_state(self):
        action_type = self.action_combo.currentData()
        self.message_input.setEnabled(action_type == "notify")
        self.transform_combo.setEnabled(action_type == "transform")
        if action_type != "notify":
            self.message_input.clear()

    def _build_params_json(self, action_type):
        if action_type == "notify":
            return json.dumps({"message": self.message_input.text().strip()}, ensure_ascii=False)
        if action_type == "transform":
            return json.dumps({"mode": self.transform_combo.currentData()}, ensure_ascii=False)
        return "{}"

    def save_action(self):
        name = self.name_input.text().strip()
        pattern = self.pattern_input.text().strip()
        action_type = self.action_combo.currentData()
        action_params = self._build_params_json(action_type)

        if not name or not pattern:
            QMessageBox.warning(self, "경고", "이름과 패턴을 입력하세요.")
            return

        try:
            re.compile(pattern)
        except re.error as exc:
            QMessageBox.warning(self, "패턴 오류", f"잘못된 정규식 패턴입니다.\n{exc}")
            return

        if action_type == "notify" and not self.message_input.text().strip():
            QMessageBox.warning(self, "경고", "알림 액션에는 메시지가 필요합니다.")
            return

        exclude_id = self.action[0] if self.action is not None else None
        if hasattr(self.db, "is_duplicate_clipboard_action") and self.db.is_duplicate_clipboard_action(
            pattern,
            action_type,
            action_params,
            exclude_id=exclude_id,
        ):
            QMessageBox.information(self, "중복 액션", "동일한 패턴/유형의 액션이 이미 존재합니다.")
            return

        ok = False
        if self.action is None:
            ok = self.db.add_clipboard_action(name, pattern, action_type, action_params)
        else:
            ok = self.db.update_clipboard_action(self.action[0], name, pattern, action_type, action_params)

        if not ok:
            QMessageBox.critical(self, "오류", "액션 저장에 실패했습니다.")
            return
        self.accept()


class ClipboardActionsDialog(QDialog):
    """Manage clipboard automation action rules."""

    def __init__(self, parent, db, action_manager):
        super().__init__(parent)
        self.db = db
        self.action_manager = action_manager
        self.actions = []
        self.setWindowTitle("⚡ 클립보드 액션")
        self.setMinimumSize(760, 420)
        self.init_ui()
        self.load_actions()

    def init_ui(self):
        layout = QVBoxLayout(self)

        btn_layout = QHBoxLayout()
        btn_add = QPushButton("➕ 액션 추가")
        btn_add.clicked.connect(self.add_action)
        btn_edit = QPushButton("✏️ 편집")
        btn_edit.clicked.connect(self.edit_action)
        btn_up = QPushButton("⬆ 우선순위")
        btn_up.clicked.connect(lambda: self.move_selected(-1))
        btn_down = QPushButton("⬇ 우선순위")
        btn_down.clicked.connect(lambda: self.move_selected(1))
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_up)
        btn_layout.addWidget(btn_down)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["활성", "이름", "패턴", "액션", "파라미터", "순서", "삭제"])
        header = _ensure(self.table.horizontalHeader())
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 140)
        self.table.setColumnWidth(3, 130)
        self.table.setColumnWidth(4, 150)
        self.table.setColumnWidth(5, 60)
        self.table.setColumnWidth(6, 60)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.cellDoubleClicked.connect(lambda *_args: self.edit_action())
        vertical_header = self.table.verticalHeader()
        if vertical_header is not None:
            vertical_header.setVisible(False)
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

    def _selected_row(self):
        selection_model = self.table.selectionModel()
        if selection_model is None:
            return None
        rows = selection_model.selectedRows()
        return rows[0].row() if rows else None

    def _selected_action(self):
        row = self._selected_row()
        if row is None or row >= len(self.actions):
            return None
        return self.actions[row]

    def _reload_manager(self):
        self.action_manager.reload_actions()

    def _param_summary(self, action_type, params_json):
        try:
            params = json.loads(params_json or "{}")
            if not isinstance(params, dict):
                params = {}
        except Exception:
            params = {}
        if action_type == "notify":
            return params.get("message", "-") or "-"
        if action_type == "transform":
            mode = params.get("mode", "trim")
            return TRANSFORM_MODE_NAMES.get(mode, str(mode))
        return "-"

    def load_actions(self):
        self.actions = list(self.db.get_clipboard_actions())
        self.table.setRowCount(0)

        for row_idx, (aid, name, pattern, action_type, params_json, enabled, _priority) in enumerate(self.actions):
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
            self.table.setItem(row_idx, 3, QTableWidgetItem(ACTION_TYPE_NAMES.get(action_type, action_type)))
            self.table.setItem(row_idx, 4, QTableWidgetItem(self._param_summary(action_type, params_json)))
            order_item = QTableWidgetItem(str(row_idx + 1))
            order_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 5, order_item)

            btn_del = QPushButton("❌")
            btn_del.clicked.connect(lambda checked, a=aid: self.delete_action(a))
            self.table.setCellWidget(row_idx, 6, btn_del)

    def add_action(self):
        dialog = ClipboardActionEditDialog(self, self.db)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._reload_manager()
            self.load_actions()

    def edit_action(self):
        action = self._selected_action()
        if action is None:
            QMessageBox.information(self, "알림", "편집할 액션을 선택하세요.")
            return
        dialog = ClipboardActionEditDialog(self, self.db, action=action)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._reload_manager()
            self.load_actions()

    def move_selected(self, direction: int):
        row = self._selected_row()
        if row is None:
            return
        target = row + direction
        if target < 0 or target >= len(self.actions):
            return
        self.actions[row], self.actions[target] = self.actions[target], self.actions[row]
        ordered_ids = [action[0] for action in self.actions]
        if hasattr(self.db, "update_clipboard_action_priorities") and self.db.update_clipboard_action_priorities(ordered_ids):
            self._reload_manager()
            self.load_actions()
            self.table.selectRow(target)

    def toggle_action(self, action_id, state):
        self.db.toggle_clipboard_action(action_id, 1 if state else 0)
        self._reload_manager()

    def delete_action(self, action_id):
        self.db.delete_clipboard_action(action_id)
        self._reload_manager()
        self.load_actions()

    def add_default_actions(self):
        defaults = [
            ("URL 제목 가져오기", r"https?://", "fetch_title", "{}"),
            ("전화번호 자동 포맷", r"^0\d{9,10}$", "format_phone", "{}"),
        ]
        added = 0
        skipped = 0
        failed = 0
        for name, pattern, action_type, action_params in defaults:
            if hasattr(self.db, "is_duplicate_clipboard_action") and self.db.is_duplicate_clipboard_action(
                pattern, action_type, action_params
            ):
                skipped += 1
                continue
            if self.db.add_clipboard_action(name, pattern, action_type, action_params):
                added += 1
            else:
                failed += 1
        self._reload_manager()
        self.load_actions()
        summary = f"기본 액션 처리 완료\n추가: {added}개\n중복 건너뜀: {skipped}개"
        if failed:
            summary += f"\n추가 실패: {failed}개"
        QMessageBox.information(self, "완료", summary)


__all__ = ["ClipboardActionEditDialog", "ClipboardActionsDialog"]
