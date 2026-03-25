"""Snippet dialogs module."""

from __future__ import annotations

import datetime
import json
from typing import Callable, Protocol, TypeVar, cast

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QHeaderView,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from smartclipboard_app.ui.clipboard_guard import mark_internal_copy
from smartclipboard_app.ui.dialogs.hotkeys import DEFAULT_HOTKEYS

T = TypeVar("T")

APP_LOCAL_SHORTCUTS = {
    "escape_hide": "Escape",
    "search_focus": "Ctrl+F",
    "pin_toggle": "Ctrl+P",
    "delete_selected": "Delete",
    "multi_delete": "Shift+Delete",
    "paste_selected": "Return",
    "copy_selected": "Ctrl+C",
    "quit": "Ctrl+Q",
}


class _SnippetWindow(Protocol):
    def statusBar(self) -> QStatusBar | None: ...

    def refresh_snippet_shortcuts(self) -> None: ...


def _canonical_shortcut_text(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    sequence = QKeySequence(raw)
    canonical = sequence.toString(QKeySequence.SequenceFormat.PortableText).strip()
    return canonical


def _load_global_hotkeys(db) -> dict[str, str]:
    raw = db.get_setting("hotkeys", json.dumps(DEFAULT_HOTKEYS))
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("hotkeys must be a JSON object")
    except Exception:
        parsed = dict(DEFAULT_HOTKEYS)
    return {
        "show_main": str(parsed.get("show_main", DEFAULT_HOTKEYS["show_main"])),
        "show_mini": str(parsed.get("show_mini", DEFAULT_HOTKEYS["show_mini"])),
        "paste_last": str(parsed.get("paste_last", DEFAULT_HOTKEYS["paste_last"])),
    }


def validate_snippet_shortcut(db, shortcut: str, exclude_snippet_id=None) -> str | None:
    canonical = _canonical_shortcut_text(shortcut)
    if not shortcut:
        return None
    if not canonical:
        return "유효한 단축키 형식이 아닙니다."

    reserved = {
        _canonical_shortcut_text(value): label
        for label, value in APP_LOCAL_SHORTCUTS.items()
    }
    reserved.update(
        {
            _canonical_shortcut_text(value): f"글로벌 핫키 ({label})"
            for label, value in _load_global_hotkeys(db).items()
        }
    )
    if canonical in reserved:
        return f"'{canonical}' 단축키는 이미 {reserved[canonical]}에 사용 중입니다."

    for snippet_id, name, _content, other_shortcut, _category in db.get_snippets():
        if exclude_snippet_id is not None and snippet_id == exclude_snippet_id:
            continue
        other_canonical = _canonical_shortcut_text(other_shortcut)
        if other_canonical and other_canonical == canonical:
            return f"'{canonical}' 단축키는 이미 스니펫 '{name}'에 사용 중입니다."
    return None


def process_snippet_template(text: str) -> str:
    import random
    import re
    import string

    now = datetime.datetime.now()
    text = text.replace("{{date}}", now.strftime("%Y-%m-%d"))
    text = text.replace("{{time}}", now.strftime("%H:%M:%S"))
    text = text.replace("{{datetime}}", now.strftime("%Y-%m-%d %H:%M:%S"))

    if "{{clipboard}}" in text:
        clipboard = QApplication.clipboard()
        current_clip = clipboard.text() if clipboard is not None else ""
        text = text.replace("{{clipboard}}", current_clip)

    random_pattern = r"\{\{random:(\d+)\}\}"
    matches = re.findall(random_pattern, text)
    for match in matches:
        length = int(match)
        random_str = "".join(random.choices(string.ascii_letters + string.digits, k=length))
        text = re.sub(r"\{\{random:" + match + r"\}\}", random_str, text, count=1)

    return text


def _snippet_window(value: object | None) -> _SnippetWindow | None:
    if value is not None and hasattr(value, "statusBar") and hasattr(value, "refresh_snippet_shortcuts"):
        return cast(_SnippetWindow, value)
    return None


def _refresh_snippet_shortcuts(parent_window: object | None) -> None:
    window = _snippet_window(parent_window)
    if window is None:
        return
    try:
        window.refresh_snippet_shortcuts()
    except Exception:
        pass


class SnippetDialog(QDialog):
    def __init__(self, parent, db, snippet=None):
        super().__init__(parent)
        self.db = db
        self.snippet = snippet
        self.setWindowTitle("📝 스니펫 추가" if not snippet else "📝 스니펫 편집")
        self.setMinimumSize(420, 320)
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

        self.shortcut_input = QLineEdit()
        self.shortcut_input.setPlaceholderText("예: Ctrl+Alt+1 (선택)")
        form.addRow("단축키:", self.shortcut_input)

        layout.addLayout(form)

        self.content_input = QTextEdit()
        self.content_input.setPlaceholderText("스니펫 내용을 입력하세요...")
        layout.addWidget(self.content_input)

        if self.snippet:
            self.name_input.setText(self.snippet[1])
            self.content_input.setPlainText(self.snippet[2])
            self.shortcut_input.setText(self.snippet[3] or "")
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
        """v10.2: 스니펫 저장 (생성/편집 모드 지원)"""
        name = self.name_input.text().strip()
        content = self.content_input.toPlainText().strip()
        category = self.category_input.currentText().strip() or "일반"
        shortcut = _canonical_shortcut_text(self.shortcut_input.text())

        if not name or not content:
            QMessageBox.warning(self, "경고", "이름과 내용을 입력해주세요.")
            return

        conflict = validate_snippet_shortcut(
            self.db,
            shortcut,
            exclude_snippet_id=self.snippet[0] if self.snippet else None,
        )
        if conflict:
            QMessageBox.warning(self, "단축키 충돌", conflict)
            return

        if self.snippet:
            if self.db.update_snippet(self.snippet[0], name, content, shortcut, category):
                self.accept()
            else:
                QMessageBox.critical(self, "오류", "스니펫 수정에 실패했습니다.")
        else:
            if self.db.add_snippet(name, content, shortcut, category):
                self.accept()
            else:
                QMessageBox.critical(self, "오류", "스니펫 저장에 실패했습니다.")


class SnippetManagerDialog(QDialog):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.parent_window = parent
        self.setWindowTitle("📝 스니펫 관리")
        self.setMinimumSize(640, 460)
        self.init_ui()
        self.load_snippets()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        btn_layout = QHBoxLayout()
        btn_add = QPushButton("➕ 새 스니펫")
        btn_add.clicked.connect(self.add_snippet)
        btn_layout.addWidget(btn_add)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["이름", "카테고리", "단축키", "내용 미리보기"])

        header = self.table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 140)
        self.table.setColumnWidth(1, 90)
        self.table.setColumnWidth(2, 130)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        vertical_header = self.table.verticalHeader()
        if vertical_header is not None:
            vertical_header.setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.cellDoubleClicked.connect(self.use_snippet)
        layout.addWidget(self.table)

        bottom_layout = QHBoxLayout()
        btn_use = QPushButton("📋 사용")
        btn_use.clicked.connect(self.use_snippet)
        btn_edit = QPushButton("✏️ 편집")
        btn_edit.clicked.connect(self.edit_snippet)
        btn_delete = QPushButton("🗑️ 삭제")
        btn_delete.clicked.connect(self.delete_snippet)
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.close)

        bottom_layout.addWidget(btn_use)
        bottom_layout.addWidget(btn_edit)
        bottom_layout.addWidget(btn_delete)
        bottom_layout.addStretch()
        bottom_layout.addWidget(btn_close)
        layout.addLayout(bottom_layout)

    def load_snippets(self):
        snippets = self.db.get_snippets()
        self.table.setRowCount(0)

        for row_idx, (sid, name, content, shortcut, category) in enumerate(snippets):
            self.table.insertRow(row_idx)

            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, sid)
            self.table.setItem(row_idx, 0, name_item)

            cat_item = QTableWidgetItem(category)
            cat_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 1, cat_item)

            shortcut_item = QTableWidgetItem(shortcut or "-")
            shortcut_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 2, shortcut_item)

            preview = content.replace("\n", " ")[:50] + ("..." if len(content) > 50 else "")
            self.table.setItem(row_idx, 3, QTableWidgetItem(preview))

    def add_snippet(self):
        dialog = SnippetDialog(self, self.db)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_snippets()
            _refresh_snippet_shortcuts(self.parent_window)

    def get_selected_id(self):
        selection_model = self.table.selectionModel()
        if selection_model is None:
            return None
        rows = selection_model.selectedRows()
        if rows:
            item = self.table.item(rows[0].row(), 0)
            if item is not None:
                return item.data(Qt.ItemDataRole.UserRole)
        return None

    def use_snippet(self, *_args):
        sid = self.get_selected_id()
        if not sid:
            return
        snippets = self.db.get_snippets()
        for s in snippets:
            if s[0] == sid:
                content = process_snippet_template(s[2])
                clipboard = QApplication.clipboard()
                if clipboard is None:
                    return
                mark_internal_copy(self.parent_window)
                clipboard.setText(content)
                if self.parent_window:
                    status_bar_getter = cast(
                        Callable[[], QStatusBar | None] | None,
                        getattr(self.parent_window, "statusBar", None),
                    )
                    if status_bar_getter is not None:
                        status_bar = status_bar_getter()
                        if status_bar is not None:
                            status_bar.showMessage("✅ 스니펫이 클립보드에 복사되었습니다.", 2000)
                self.close()
                break

    def process_template(self, text):
        """템플릿 변수 치환"""
        return process_snippet_template(text)

    def delete_snippet(self):
        sid = self.get_selected_id()
        if sid:
            reply = QMessageBox.question(
                self,
                "삭제 확인",
                "이 스니펫을 삭제하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.db.delete_snippet(sid)
                self.load_snippets()
                _refresh_snippet_shortcuts(self.parent_window)

    def edit_snippet(self):
        """v10.2: 스니펫 편집"""
        sid = self.get_selected_id()
        if not sid:
            QMessageBox.information(self, "알림", "편집할 스니펫을 선택하세요.")
            return
        snippets = self.db.get_snippets()
        for s in snippets:
            if s[0] == sid:
                dialog = SnippetDialog(self, self.db, snippet=s)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    self.load_snippets()
                    _refresh_snippet_shortcuts(self.parent_window)
                break


__all__ = [
    "APP_LOCAL_SHORTCUTS",
    "SnippetDialog",
    "SnippetManagerDialog",
    "process_snippet_template",
    "validate_snippet_shortcut",
]
