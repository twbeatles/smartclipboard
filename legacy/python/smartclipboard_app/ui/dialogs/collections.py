"""Collection management dialogs."""

from __future__ import annotations

from typing import Protocol, TypeVar, cast

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
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
)

T = TypeVar("T")

DEFAULT_COLLECTION_ICONS = ["📁", "📂", "🗂️", "📦", "💼", "🎯", "⭐", "❤️", "🔖", "📌"]


class _CollectionParent(Protocol):
    def refresh_collection_filter_options(self) -> None: ...

    def load_data(self) -> None: ...


def _ensure(value: T | None) -> T:
    assert value is not None
    return value


def _collection_parent(value: object | None) -> _CollectionParent | None:
    if value is not None and hasattr(value, "refresh_collection_filter_options") and hasattr(value, "load_data"):
        return cast(_CollectionParent, value)
    return None


class CollectionEditDialog(QDialog):
    def __init__(self, parent, db, collection=None):
        super().__init__(parent)
        self.db = db
        self.collection = collection
        self.saved_collection_id = collection[0] if collection is not None else None
        self.setWindowTitle("컬렉션 추가" if collection is None else "컬렉션 편집")
        self.setMinimumWidth(360)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.icon_input = QComboBox()
        self.icon_input.setEditable(True)
        self.icon_input.addItems(DEFAULT_COLLECTION_ICONS)
        self.color_input = QLineEdit()
        self.color_input.setPlaceholderText("#6366f1")

        form.addRow("이름:", self.name_input)
        form.addRow("아이콘:", self.icon_input)
        form.addRow("색상:", self.color_input)
        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_save = QPushButton("저장")
        btn_save.clicked.connect(self.save_collection)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        if self.collection is not None:
            _cid, name, icon, color, _created_at = self.collection
            self.name_input.setText(name)
            self.icon_input.setCurrentText(icon or "📁")
            self.color_input.setText(color or "#6366f1")
        else:
            self.icon_input.setCurrentText("📁")
            self.color_input.setText("#6366f1")

    def save_collection(self):
        name = self.name_input.text().strip()
        icon = self.icon_input.currentText().strip() or "📁"
        color = self.color_input.text().strip() or "#6366f1"

        if not name:
            QMessageBox.warning(self, "경고", "컬렉션 이름을 입력하세요.")
            return
        if hasattr(self.db, "is_duplicate_collection_name") and self.db.is_duplicate_collection_name(
            name,
            exclude_id=self.collection[0] if self.collection is not None else None,
        ):
            QMessageBox.warning(self, "중복 이름", "같은 이름의 컬렉션이 이미 존재합니다.")
            return

        ok = False
        if self.collection is None:
            created_id = self.db.add_collection(name, icon, color)
            ok = bool(created_id)
            if ok:
                self.saved_collection_id = created_id
        else:
            ok = self.db.update_collection(self.collection[0], name, icon, color)
            if ok:
                self.saved_collection_id = self.collection[0]
        if not ok:
            QMessageBox.critical(self, "오류", "컬렉션 저장에 실패했습니다.")
            return
        self.accept()


class CollectionManagerDialog(QDialog):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.collections = []
        self.setWindowTitle("📁 컬렉션 관리")
        self.setMinimumSize(500, 360)
        self.init_ui()
        self.load_collections()

    def init_ui(self):
        layout = QVBoxLayout(self)

        top_layout = QHBoxLayout()
        btn_add = QPushButton("➕ 추가")
        btn_add.clicked.connect(self.add_collection)
        btn_edit = QPushButton("✏️ 수정")
        btn_edit.clicked.connect(self.edit_collection)
        btn_delete = QPushButton("🗑️ 삭제")
        btn_delete.clicked.connect(self.delete_collection)
        top_layout.addWidget(btn_add)
        top_layout.addWidget(btn_edit)
        top_layout.addWidget(btn_delete)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["아이콘", "이름", "색상", "생성일"])
        header = _ensure(self.table.horizontalHeader())
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 70)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 110)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.cellDoubleClicked.connect(lambda *_args: self.edit_collection())
        vertical_header = self.table.verticalHeader()
        if vertical_header is not None:
            vertical_header.setVisible(False)
        layout.addWidget(self.table)

        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _notify_parent(self):
        parent = _collection_parent(self.parent())
        if parent is not None:
            parent.refresh_collection_filter_options()
            parent.load_data()

    def _selected_collection(self):
        selection_model = self.table.selectionModel()
        if selection_model is None:
            return None
        rows = selection_model.selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        if row >= len(self.collections):
            return None
        return self.collections[row]

    def load_collections(self):
        self.collections = list(self.db.get_collections())
        self.table.setRowCount(0)
        for row_idx, collection in enumerate(self.collections):
            cid, name, icon, color, created_at = collection
            self.table.insertRow(row_idx)
            icon_item = QTableWidgetItem(icon or "📁")
            icon_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_item.setData(Qt.ItemDataRole.UserRole, cid)
            self.table.setItem(row_idx, 0, icon_item)
            self.table.setItem(row_idx, 1, QTableWidgetItem(name))
            self.table.setItem(row_idx, 2, QTableWidgetItem(color or "#6366f1"))
            self.table.setItem(row_idx, 3, QTableWidgetItem((created_at or "")[:10]))

    def add_collection(self):
        dialog = CollectionEditDialog(self, self.db)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_collections()
            self._notify_parent()

    def edit_collection(self):
        collection = self._selected_collection()
        if collection is None:
            QMessageBox.information(self, "알림", "수정할 컬렉션을 선택하세요.")
            return
        dialog = CollectionEditDialog(self, self.db, collection=collection)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_collections()
            self._notify_parent()

    def delete_collection(self):
        collection = self._selected_collection()
        if collection is None:
            return
        reply = QMessageBox.question(
            self,
            "삭제 확인",
            f"'{collection[1]}' 컬렉션을 삭제하시겠습니까?\n연결된 항목은 미분류로 남습니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if not self.db.delete_collection(collection[0]):
            QMessageBox.critical(self, "오류", "컬렉션 삭제에 실패했습니다.")
            return
        self.load_collections()
        self._notify_parent()


__all__ = ["CollectionEditDialog", "CollectionManagerDialog"]
