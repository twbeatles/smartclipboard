"""Snippet dialogs module."""

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)
from PyQt6.QtCore import Qt

import datetime


class SnippetDialog(QDialog):
    def __init__(self, parent, db, snippet=None):
        super().__init__(parent)
        self.db = db
        self.snippet = snippet
        self.setWindowTitle("📝 스니펫 추가" if not snippet else "📝 스니펫 편집")
        self.setMinimumSize(400, 300)
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

        layout.addLayout(form)

        self.content_input = QTextEdit()
        self.content_input.setPlaceholderText("스니펫 내용을 입력하세요...")
        layout.addWidget(self.content_input)

        if self.snippet:
            self.name_input.setText(self.snippet[1])
            self.content_input.setPlainText(self.snippet[2])
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
        category = self.category_input.currentText()

        if not name or not content:
            QMessageBox.warning(self, "경고", "이름과 내용을 입력해주세요.")
            return

        if self.snippet:
            if self.db.update_snippet(self.snippet[0], name, content, "", category):
                self.accept()
            else:
                QMessageBox.critical(self, "오류", "스니펫 수정에 실패했습니다.")
        else:
            if self.db.add_snippet(name, content, "", category):
                self.accept()
            else:
                QMessageBox.critical(self, "오류", "스니펫 저장에 실패했습니다.")


class SnippetManagerDialog(QDialog):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.parent_window = parent
        self.setWindowTitle("📝 스니펫 관리")
        self.setMinimumSize(550, 450)
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
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["이름", "카테고리", "내용 미리보기"])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(1, 80)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
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

            preview = content.replace("\n", " ")[:50] + ("..." if len(content) > 50 else "")
            self.table.setItem(row_idx, 2, QTableWidgetItem(preview))

    def add_snippet(self):
        dialog = SnippetDialog(self, self.db)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_snippets()

    def get_selected_id(self):
        rows = self.table.selectionModel().selectedRows()
        if rows:
            return self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        return None

    def use_snippet(self, *_args):
        sid = self.get_selected_id()
        if not sid:
            return
        snippets = self.db.get_snippets()
        for s in snippets:
            if s[0] == sid:
                content = s[2]
                content = self.process_template(content)
                clipboard = QApplication.clipboard()
                clipboard.setText(content)
                if self.parent_window and hasattr(self.parent_window, "statusBar"):
                    self.parent_window.statusBar().showMessage("✅ 스니펫이 클립보드에 복사되었습니다.", 2000)
                self.close()
                break

    def process_template(self, text):
        """템플릿 변수 치환"""
        import random
        import re
        import string

        now = datetime.datetime.now()
        text = text.replace("{{date}}", now.strftime("%Y-%m-%d"))
        text = text.replace("{{time}}", now.strftime("%H:%M:%S"))
        text = text.replace("{{datetime}}", now.strftime("%Y-%m-%d %H:%M:%S"))

        if "{{clipboard}}" in text:
            current_clip = QApplication.clipboard().text() or ""
            text = text.replace("{{clipboard}}", current_clip)

        random_pattern = r"\{\{random:(\d+)\}\}"
        matches = re.findall(random_pattern, text)
        for match in matches:
            length = int(match)
            random_str = "".join(random.choices(string.ascii_letters + string.digits, k=length))
            text = re.sub(r"\{\{random:" + match + r"\}\}", random_str, text, count=1)

        return text

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
                break


__all__ = ["SnippetDialog", "SnippetManagerDialog"]
