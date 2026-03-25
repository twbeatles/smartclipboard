"""Hotkey settings dialog module."""

from __future__ import annotations

import json
import logging
from typing import Protocol, cast

from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

logger = logging.getLogger(__name__)

DEFAULT_HOTKEYS = {
    "show_main": "ctrl+shift+v",
    "show_mini": "alt+v",
    "paste_last": "ctrl+shift+z",
}


class _HotkeyParent(Protocol):
    _last_hotkey_error: str

    def register_hotkeys(self, hotkeys_override=None, persist: bool = False) -> bool: ...


def _hotkey_parent(value: object | None) -> _HotkeyParent | None:
    if value is not None and hasattr(value, "register_hotkeys"):
        return cast(_HotkeyParent, value)
    return None


class HotkeySettingsDialog(QDialog):
    """Custom hotkey settings."""

    def __init__(self, parent, db, default_hotkeys=None, logger_=None):
        super().__init__(parent)
        self.db = db
        self.default_hotkeys = default_hotkeys or DEFAULT_HOTKEYS
        self.logger = logger_ or logger
        self.setWindowTitle("⌨️ 핫키 설정")
        self.setMinimumSize(400, 250)
        self.init_ui()

    def _load_hotkeys(self) -> dict[str, str]:
        raw = self.db.get_setting("hotkeys", json.dumps(self.default_hotkeys))
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("hotkeys setting is not a JSON object")
        except Exception as exc:
            self.logger.warning("Invalid hotkeys setting; restoring defaults: %s", exc)
            parsed = dict(self.default_hotkeys)
            self.db.set_setting("hotkeys", json.dumps(parsed))

        return {
            "show_main": str(parsed.get("show_main", self.default_hotkeys["show_main"])),
            "show_mini": str(parsed.get("show_mini", self.default_hotkeys["show_mini"])),
            "paste_last": str(parsed.get("paste_last", self.default_hotkeys["paste_last"])),
        }

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        info = QLabel("단축키를 설정하세요. (예: ctrl+shift+v, alt+v)")
        info.setStyleSheet("color: gray;")
        layout.addWidget(info)

        form = QFormLayout()
        hotkeys = self._load_hotkeys()

        self.input_main = QLineEdit(hotkeys.get("show_main", "ctrl+shift+v"))
        self.input_main.setPlaceholderText("ctrl+shift+v")
        form.addRow("메인 창 열기:", self.input_main)

        self.input_mini = QLineEdit(hotkeys.get("show_mini", "alt+v"))
        self.input_mini.setPlaceholderText("alt+v")
        form.addRow("미니 창 열기:", self.input_mini)

        self.input_paste = QLineEdit(hotkeys.get("paste_last", "ctrl+shift+z"))
        self.input_paste.setPlaceholderText("ctrl+shift+z")
        form.addRow("마지막 항목 붙여넣기:", self.input_paste)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_reset = QPushButton("🔄 기본값")
        btn_reset.clicked.connect(self.reset_defaults)
        btn_save = QPushButton("저장")
        btn_save.clicked.connect(self.save_hotkeys)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def reset_defaults(self):
        self.input_main.setText(self.default_hotkeys["show_main"])
        self.input_mini.setText(self.default_hotkeys["show_mini"])
        self.input_paste.setText(self.default_hotkeys["paste_last"])

    def save_hotkeys(self):
        hotkeys = {
            "show_main": self.input_main.text().strip().lower(),
            "show_mini": self.input_mini.text().strip().lower(),
            "paste_last": self.input_paste.text().strip().lower(),
        }
        parent = _hotkey_parent(self.parent())
        if parent is not None:
            try:
                ok = parent.register_hotkeys(hotkeys_override=hotkeys, persist=True)
                if not ok:
                    message = getattr(parent, "_last_hotkey_error", "") or "핫키 적용에 실패했습니다."
                    QMessageBox.warning(self, "설정 실패", message)
                    return
            except Exception as exc:
                self.logger.warning("Hotkey apply error: %s", exc)
                QMessageBox.warning(self, "설정 실패", f"핫키 적용에 실패했습니다.\n{exc}")
                return
        else:
            self.db.set_setting("hotkeys", json.dumps(hotkeys))
        self.accept()


__all__ = ["HotkeySettingsDialog", "DEFAULT_HOTKEYS"]
