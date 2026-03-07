"""Export dialog module."""

from __future__ import annotations

import datetime

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class ExportDialog(QDialog):
    """Advanced export dialog."""

    def __init__(self, parent, export_manager):
        super().__init__(parent)
        self.export_manager = export_manager
        self.setWindowTitle("📤 고급 내보내기")
        self.setMinimumSize(400, 300)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        format_group = QGroupBox("📁 내보내기 형식")
        format_layout = QVBoxLayout(format_group)
        self.format_json = QCheckBox("JSON (.json) - 전체 데이터")
        self.format_csv = QCheckBox("CSV (.csv) - 텍스트 호환")
        self.format_md = QCheckBox("Markdown (.md) - 문서용")
        self.format_json.setChecked(True)
        format_layout.addWidget(self.format_json)
        format_layout.addWidget(self.format_csv)
        format_layout.addWidget(self.format_md)
        self.json_migration_mode = QCheckBox("JSON 마이그레이션 모드 (태그/메모/북마크/컬렉션 포함)")
        self.json_migration_mode.setToolTip("JSON 내보내기에 메타데이터를 포함합니다.")
        format_layout.addWidget(self.json_migration_mode)
        layout.addWidget(format_group)

        filter_group = QGroupBox("🔍 필터")
        filter_layout = QFormLayout(filter_group)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["전체", "텍스트만", "링크만", "코드만"])
        filter_layout.addRow("유형:", self.type_combo)
        self.date_filter_enabled = QCheckBox("시작일 이후 항목만 내보내기 (JSON)")
        self.date_from_input = QDateEdit()
        self.date_from_input.setDate(QDate.currentDate())
        self.date_from_input.setCalendarPopup(True)
        self.date_from_input.setEnabled(False)
        self.date_filter_enabled.toggled.connect(self.date_from_input.setEnabled)
        filter_layout.addRow(self.date_filter_enabled)
        filter_layout.addRow("시작일:", self.date_from_input)
        layout.addWidget(filter_group)

        btn_layout = QHBoxLayout()
        btn_export = QPushButton("📤 내보내기")
        btn_export.clicked.connect(self.do_export)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_export)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def do_export(self):
        type_map = {"전체": "all", "텍스트만": "TEXT", "링크만": "LINK", "코드만": "CODE"}
        filter_type = type_map.get(self.type_combo.currentText(), "all")
        date_from = self.date_from_input.date().toPyDate() if self.date_filter_enabled.isChecked() else None
        exported_count = 0

        if self.format_json.isChecked():
            path, _ = QFileDialog.getSaveFileName(
                self,
                "JSON 저장",
                f"clipboard_export_{datetime.date.today()}.json",
                "JSON Files (*.json)",
            )
            if path:
                count = self.export_manager.export_json(
                    path,
                    filter_type,
                    date_from=date_from,
                    include_metadata=self.json_migration_mode.isChecked(),
                )
                if count >= 0:
                    exported_count += count

        if self.format_csv.isChecked():
            path, _ = QFileDialog.getSaveFileName(
                self,
                "CSV 저장",
                f"clipboard_export_{datetime.date.today()}.csv",
                "CSV Files (*.csv)",
            )
            if path:
                count = self.export_manager.export_csv(path, filter_type)
                if count >= 0:
                    exported_count += count

        if self.format_md.isChecked():
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Markdown 저장",
                f"clipboard_export_{datetime.date.today()}.md",
                "Markdown Files (*.md)",
            )
            if path:
                count = self.export_manager.export_markdown(path, filter_type)
                if count >= 0:
                    exported_count += count

        if exported_count > 0:
            QMessageBox.information(self, "완료", "내보내기가 완료되었습니다.")
            self.accept()


__all__ = ["ExportDialog"]
