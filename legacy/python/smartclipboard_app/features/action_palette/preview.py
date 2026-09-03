"""원본/결과 Preview 다이얼로그."""

from __future__ import annotations

from typing import Mapping

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from smartclipboard_core.action_palette import ActionContext, ActionResult

from .qr import render_qr_pixmap


class ActionPreviewDialog(QDialog):
    def __init__(self, parent, result: ActionResult, context: ActionContext, themes: Mapping | None = None):
        super().__init__(parent)
        self.action_result = result
        self.context = context
        self.themes = themes or {}
        self.copied = False
        self.setWindowTitle(self.action_result.title or "결과 미리보기")
        self.setMinimumSize(640, 360)
        self._apply_theme(parent)
        self._init_ui()

    def _apply_theme(self, parent) -> None:
        theme_name = getattr(parent, "current_theme", "dark")
        theme = self.themes.get(theme_name) or self.themes.get("dark") or {}
        if not theme:
            return
        self.setStyleSheet(
            f"""
            QDialog {{ background-color: {theme["background"]}; color: {theme["text"]}; }}
            QLabel {{ color: {theme["text_secondary"]}; }}
            QTextEdit {{
                background-color: {theme["surface"]};
                color: {theme["text"]};
                border: 1px solid {theme["border"]};
                border-radius: 8px;
            }}
            QPushButton {{
                background-color: {theme.get("surface_variant", theme["surface"])};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: {theme["text"]};
            }}
            QPushButton:hover {{ background-color: {theme["primary"]}; color: white; }}
            """
        )

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        columns = QHBoxLayout()
        original_box = QVBoxLayout()
        original_box.addWidget(QLabel("원본"))
        original = QTextEdit()
        original.setReadOnly(True)
        original.setPlainText(self.context.raw_text)
        original_box.addWidget(original)
        result_box = QVBoxLayout()
        result_box.addWidget(QLabel("결과"))
        if self.action_result.kind == "qr":
            image = QLabel()
            image.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pixmap = render_qr_pixmap(self.action_result.value)
            if pixmap is not None:
                image.setPixmap(pixmap)
            else:
                image.setText("QR 코드를 만들지 못했습니다. 내용이 너무 길거나 qrcode가 없습니다.")
            result_box.addWidget(image)
        else:
            result_view = QTextEdit()
            result_view.setReadOnly(True)
            result_view.setPlainText(self.action_result.value)
            result_box.addWidget(result_view)
        columns.addLayout(original_box)
        columns.addLayout(result_box)
        layout.addLayout(columns)

        buttons = QHBoxLayout()
        buttons.addStretch()
        if self.action_result.kind == "qr":
            copy_btn = QPushButton("원문 복사")
        else:
            copy_btn = QPushButton("복사")
        copy_btn.clicked.connect(self._copy)
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.reject)
        buttons.addWidget(copy_btn)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

    def _copy(self) -> None:
        self.copied = True
        self.accept()


__all__ = ["ActionPreviewDialog"]
