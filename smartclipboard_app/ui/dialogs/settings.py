"""Settings dialog module."""

from __future__ import annotations

import logging

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

logger = logging.getLogger(__name__)

FALLBACK_THEMES = {
    "dark": {
        "name": "Dark",
        "background": "#0f0f14",
        "surface": "#1a1a24",
        "surface_variant": "#252532",
        "primary": "#6366f1",
        "text": "#f1f5f9",
        "text_secondary": "#94a3b8",
        "border": "#334155",
    }
}


class SettingsDialog(QDialog):
    def __init__(self, parent, db, current_theme, themes=None, max_history=100, logger_=None):
        super().__init__(parent)
        self.db = db
        self.current_theme = current_theme
        self.themes = themes or FALLBACK_THEMES
        self.max_history = max_history
        self.logger = logger_ or logger
        self.setWindowTitle("⚙️ 설정")
        self.setMinimumSize(450, 400)
        self.apply_dialog_theme()
        self.init_ui()

    def apply_dialog_theme(self):
        theme = self.themes.get(self.current_theme, self.themes["dark"])
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {theme["background"]};
                color: {theme["text"]};
            }}
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {theme["border"]};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
                color: {theme["primary"]};
            }}
            QComboBox, QSpinBox, QLineEdit {{
                background-color: {theme["surface_variant"]};
                border: 1px solid {theme["border"]};
                border-radius: 6px;
                padding: 6px;
                color: {theme["text"]};
            }}
            QLabel {{
                color: {theme["text"]};
            }}
            QPushButton {{
                background-color: {theme["surface_variant"]};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: {theme["text"]};
            }}
            QPushButton:hover {{
                background-color: {theme["primary"]};
                color: white;
            }}
            QTabWidget::pane {{
                border: 1px solid {theme["border"]};
                border-radius: 6px;
                background-color: {theme["surface"]};
            }}
            QTabBar::tab {{
                background-color: {theme["surface_variant"]};
                color: {theme["text_secondary"]};
                padding: 8px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
            QTabBar::tab:selected {{
                background-color: {theme["primary"]};
                color: white;
            }}
            """
        )

    def init_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)

        theme_group = QGroupBox("🎨 테마")
        theme_layout = QFormLayout(theme_group)
        self.theme_combo = QComboBox()
        for key, theme in self.themes.items():
            self.theme_combo.addItem(theme["name"], key)
        self.theme_combo.setCurrentIndex(list(self.themes.keys()).index(self.current_theme))
        theme_layout.addRow("테마 선택:", self.theme_combo)
        general_layout.addWidget(theme_group)

        history_group = QGroupBox("📋 히스토리")
        history_layout = QFormLayout(history_group)
        self.max_history_spin = QSpinBox()
        self.max_history_spin.setRange(10, 500)
        self.max_history_spin.setValue(int(self.db.get_setting("max_history", self.max_history)))
        history_layout.addRow("최대 저장 개수:", self.max_history_spin)
        general_layout.addWidget(history_group)

        mini_window_group = QGroupBox("🔲 미니 창")
        mini_window_layout = QFormLayout(mini_window_group)
        self.mini_window_enabled = QCheckBox("미니 클립보드 창 활성화")
        self.mini_window_enabled.setChecked(self.db.get_setting("mini_window_enabled", "true").lower() == "true")
        self.mini_window_enabled.setToolTip("비활성화하면 Alt+V 단축키로 미니 창이 열리지 않습니다.")
        mini_window_layout.addRow(self.mini_window_enabled)
        general_layout.addWidget(mini_window_group)

        logging_group = QGroupBox("📝 로깅")
        logging_layout = QFormLayout(logging_group)
        self.log_level_combo = QComboBox()
        log_levels = [
            ("DEBUG - 상세 디버깅", "DEBUG"),
            ("INFO - 일반 정보", "INFO"),
            ("WARNING - 경고만", "WARNING"),
            ("ERROR - 오류만", "ERROR"),
        ]
        for name, value in log_levels:
            self.log_level_combo.addItem(name, value)
        current_level = self.db.get_setting("log_level", "INFO")
        level_values = [v for _, v in log_levels]
        if current_level in level_values:
            self.log_level_combo.setCurrentIndex(level_values.index(current_level))
        logging_layout.addRow("로깅 레벨:", self.log_level_combo)
        general_layout.addWidget(logging_group)

        general_layout.addStretch()
        tabs.addTab(general_tab, "일반")

        shortcut_tab = QWidget()
        shortcut_layout = QVBoxLayout(shortcut_tab)
        shortcut_info = QLabel(
            """
<b>키보드 단축키</b><br><br>
<b>Ctrl+Shift+V</b> - 창 표시/숨기기<br>
<b>Ctrl+C</b> - 선택 항목 복사<br>
<b>Delete</b> - 선택 항목 삭제<br>
<b>Ctrl+P</b> - 고정/해제 토글<br>
<b>Enter</b> - 붙여넣기<br>
<b>Escape</b> - 창 숨기기<br>
<b>Ctrl+F</b> - 검색창 포커스<br>
<b>↑/↓</b> - 리스트 탐색
        """
        )
        shortcut_info.setWordWrap(True)
        shortcut_layout.addWidget(shortcut_info)
        shortcut_layout.addStretch()
        tabs.addTab(shortcut_tab, "단축키")
        layout.addWidget(tabs)

        btn_layout = QHBoxLayout()
        btn_save = QPushButton("저장")
        btn_save.clicked.connect(self.save_settings)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def save_settings(self):
        selected_theme = self.theme_combo.currentData()
        current_theme = self.current_theme

        self.db.set_setting("theme", selected_theme)
        self.db.set_setting("max_history", self.max_history_spin.value())

        mini_enabled = "true" if self.mini_window_enabled.isChecked() else "false"
        self.db.set_setting("mini_window_enabled", mini_enabled)
        if self.parent() and hasattr(self.parent(), "register_hotkeys"):
            self.parent().register_hotkeys()

        selected_log_level = self.log_level_combo.currentData()
        self.db.set_setting("log_level", selected_log_level)
        log_level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
        }
        if selected_log_level in log_level_map:
            self.logger.setLevel(log_level_map[selected_log_level])
            for handler in self.logger.handlers:
                handler.setLevel(log_level_map[selected_log_level])

        if selected_theme != current_theme:
            QMessageBox.information(self, "테마 변경", "설정한 테마가 적용되었습니다.")
            if self.parent():
                self.parent().change_theme(selected_theme)

        self.accept()

    def get_selected_theme(self):
        return self.theme_combo.currentData()


__all__ = ["SettingsDialog", "FALLBACK_THEMES"]
