"""Contextual Action Palette 다이얼로그."""

from __future__ import annotations

from typing import Mapping

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from smartclipboard_core.action_palette import ActionContext, ActionRegistry, ClipboardPaletteAction

_CATEGORY_LABELS = {
    "url": "URL",
    "phone": "전화번호",
    "text": "텍스트",
    "developer": "개발",
    "search": "검색",
}
_TYPE_LABELS = {
    "url": "URL",
    "phone": "전화번호",
    "json": "JSON",
    "text": "텍스트",
    "code": "코드",
    "color": "색상",
    "image": "이미지",
    "file": "파일",
    "files": "파일",
}
_SPECIFIC = {
    "phone": {"phone"},
    "url": {"url"},
    "json": {"developer"},
    "code": {"developer"},
}


class ActionPaletteDialog(QDialog):
    def __init__(
        self,
        parent,
        context: ActionContext,
        registry: ActionRegistry,
        themes: Mapping | None = None,
    ):
        super().__init__(parent)
        self.context = context
        self.registry = registry
        self.themes = themes or {}
        self.selected_action: ClipboardPaletteAction | None = None
        self.setWindowTitle("작업 실행")
        self.setMinimumWidth(560)
        self.setMaximumWidth(620)
        self.resize(580, 420)
        self._apply_theme(parent)
        self._init_ui()
        self._rebuild_list("")
        self.search_input.setFocus()

    def _apply_theme(self, parent) -> None:
        theme_name = getattr(parent, "current_theme", "dark")
        theme = self.themes.get(theme_name) or self.themes.get("dark") or {}
        if not theme:
            return
        self.setStyleSheet(
            f"""
            QDialog {{ background-color: {theme["background"]}; color: {theme["text"]}; }}
            QLabel {{ color: {theme["text"]}; }}
            QLineEdit {{
                background-color: {theme.get("surface_variant", theme["surface"])};
                color: {theme["text"]};
                border: 1px solid {theme["border"]};
                border-radius: 6px;
                padding: 8px;
            }}
            QListWidget {{
                background-color: {theme["surface"]};
                color: {theme["text"]};
                border: 1px solid {theme["border"]};
                border-radius: 8px;
            }}
            QListWidget::item {{ padding: 8px 12px; }}
            QListWidget::item:selected {{
                background-color: {theme["primary"]};
                color: {theme.get("selected_text", "white")};
            }}
            """
        )

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        preview = self.context.raw_text.replace("\n", " ").strip() or "(내용 없음)"
        self.preview_label = QLabel(preview[:120] + ("..." if len(preview) > 120 else ""))
        self.preview_label.setWordWrap(True)
        layout.addWidget(self.preview_label)

        type_bits = [_TYPE_LABELS.get(self.context.content_type, self.context.content_type)]
        if self.context.domain:
            type_bits.append(self.context.domain)
        self.meta_label = QLabel(" · ".join(type_bits))
        layout.addWidget(self.meta_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("작업 검색")
        self.search_input.textChanged.connect(self._rebuild_list)
        self.search_input.returnPressed.connect(self.accept_current)
        layout.addWidget(self.search_input)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.itemActivated.connect(self._activate_item)
        self.list_widget.itemDoubleClicked.connect(self._activate_item)
        layout.addWidget(self.list_widget)

    def _rebuild_list(self, query: str = "") -> None:
        self.list_widget.clear()
        actions = self.registry.get_applicable(self.context, query=self.search_input.text() if hasattr(self, "search_input") else query)
        if not actions:
            empty = QListWidgetItem("이 항목에 사용할 수 있는 작업이 없습니다.")
            empty.setFlags(empty.flags() & ~Qt.ItemFlag.ItemIsSelectable & ~Qt.ItemFlag.ItemIsEnabled)
            self.list_widget.addItem(empty)
            return
        for heading, group in _group_actions(actions, self.context):
            header = QListWidgetItem(heading)
            header.setFlags(header.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.list_widget.addItem(header)
            for action in group:
                item = QListWidgetItem(f"  {action.title}")
                item.setToolTip(action.description)
                item.setData(Qt.ItemDataRole.UserRole, action.id)
                self.list_widget.addItem(item)
        self._select_first_action()

    def _select_first_action(self) -> None:
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            if item is not None and item.data(Qt.ItemDataRole.UserRole):
                self.list_widget.setCurrentItem(item)
                return

    def current_action(self) -> ClipboardPaletteAction | None:
        item = self.list_widget.currentItem()
        if item is None:
            return None
        action_id = item.data(Qt.ItemDataRole.UserRole)
        if not action_id:
            return None
        return self.registry.get(str(action_id))

    def accept_current(self) -> None:
        action = self.current_action()
        if action is None:
            return
        self.selected_action = action
        self.accept()

    def _activate_item(self, item: QListWidgetItem) -> None:
        if item is None or not item.data(Qt.ItemDataRole.UserRole):
            return
        self.list_widget.setCurrentItem(item)
        self.accept_current()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0 is None:
            return
        key = a0.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept_current()
            return
        if key == Qt.Key.Key_Escape:
            self.reject()
            return
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down) and self.search_input.hasFocus():
            self.list_widget.setFocus()
            super().keyPressEvent(a0)
            return
        super().keyPressEvent(a0)


def _group_actions(actions, context: ActionContext):
    specific = _SPECIFIC.get(context.content_type, set())
    recommended = [action for action in actions if action.category in specific]
    rest = [action for action in actions if action not in recommended]
    groups = []
    if recommended:
        groups.append(("추천", recommended))
    buckets: dict[str, list] = {}
    for action in rest:
        buckets.setdefault(action.category, []).append(action)
    for category, items in buckets.items():
        groups.append((_CATEGORY_LABELS.get(category, category), items))
    return groups


__all__ = ["ActionPaletteDialog"]
