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
        self.setWindowTitle("고급 내보내기")
        self.setMinimumSize(420, 320)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        format_group = QGroupBox("내보내기 형식")
        format_layout = QVBoxLayout(format_group)
        self.format_json = QCheckBox("JSON (.json) - 전체 데이터")
        self.format_csv = QCheckBox("CSV (.csv) - 텍스트 호환")
        self.format_md = QCheckBox("Markdown (.md) - 문서형")
        self.format_json.setChecked(True)
        format_layout.addWidget(self.format_json)
        format_layout.addWidget(self.format_csv)
        format_layout.addWidget(self.format_md)
        self.json_migration_mode = QCheckBox("JSON migration 모드 (히스토리 메타데이터 + 컬렉션 포함)")
        self.json_migration_mode.setToolTip(
            "태그, 메모, 북마크, 컬렉션 정보를 함께 내보냅니다. 보안 보관함과 앱 설정은 포함되지 않습니다."
        )
        format_layout.addWidget(self.json_migration_mode)
        layout.addWidget(format_group)

        filter_group = QGroupBox("필터")
        filter_layout = QFormLayout(filter_group)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["전체", "텍스트만", "링크만", "이미지만", "코드만", "색상만", "파일만"])
        filter_layout.addRow("유형:", self.type_combo)
        self.date_filter_enabled = QCheckBox("시작일 이후 항목만 내보내기")
        self.date_from_input = QDateEdit()
        self.date_from_input.setDate(QDate.currentDate())
        self.date_from_input.setCalendarPopup(True)
        self.date_from_input.setEnabled(False)
        self.date_filter_enabled.toggled.connect(self.date_from_input.setEnabled)
        filter_layout.addRow(self.date_filter_enabled)
        filter_layout.addRow("시작일:", self.date_from_input)
        layout.addWidget(filter_group)

        btn_layout = QHBoxLayout()
        btn_export = QPushButton("내보내기")
        btn_export.clicked.connect(self.do_export)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_export)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    @staticmethod
    def _build_export_summary(reports: list[dict]) -> str:
        lines = []
        for report in reports:
            fmt = str(report.get("format", "")).upper()
            lines.append(
                f"{fmt}: 내보냄 {report.get('exported', 0)}개, 건너뜀 {report.get('skipped', 0)}개"
            )
            if report.get("path"):
                lines.append(f"저장 경로: {report['path']}")
            warnings = report.get("warnings", []) or []
            if warnings:
                lines.extend(f"- {warning}" for warning in warnings[:3])
                if len(warnings) > 3:
                    lines.append(f"- 추가 경고 {len(warnings) - 3}건")
            lines.append("")
        return "\n".join(lines).strip()

    @staticmethod
    def _build_error_summary(reports: list[dict]) -> str:
        lines = []
        for report in reports:
            fmt = str(report.get("format", "")).upper()
            lines.append(f"{fmt}: {report.get('error') or '내보내기 실패'}")
            if report.get("path"):
                lines.append(f"대상 경로: {report['path']}")
            lines.append("")
        return "\n".join(lines).strip()

    def do_export(self):
        type_map = {
            "전체": "all",
            "텍스트만": "TEXT",
            "링크만": "LINK",
            "이미지만": "IMAGE",
            "코드만": "CODE",
            "색상만": "COLOR",
            "파일만": "FILE",
        }
        filter_type = type_map.get(self.type_combo.currentText(), "all")
        date_from = self.date_from_input.date().toPyDate() if self.date_filter_enabled.isChecked() else None

        if not any([self.format_json.isChecked(), self.format_csv.isChecked(), self.format_md.isChecked()]):
            QMessageBox.warning(self, "경고", "하나 이상의 내보내기 형식을 선택하세요.")
            return

        success_reports: list[dict] = []
        failed_reports: list[dict] = []

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
                report = dict(getattr(self.export_manager, "last_export_report", {}) or {})
                if count >= 0 and report.get("success"):
                    success_reports.append(report)
                else:
                    failed_reports.append(report)

        if self.format_csv.isChecked():
            path, _ = QFileDialog.getSaveFileName(
                self,
                "CSV 저장",
                f"clipboard_export_{datetime.date.today()}.csv",
                "CSV Files (*.csv)",
            )
            if path:
                count = self.export_manager.export_csv(path, filter_type, date_from=date_from)
                report = dict(getattr(self.export_manager, "last_export_report", {}) or {})
                if count >= 0 and report.get("success"):
                    success_reports.append(report)
                else:
                    failed_reports.append(report)

        if self.format_md.isChecked():
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Markdown 저장",
                f"clipboard_export_{datetime.date.today()}.md",
                "Markdown Files (*.md)",
            )
            if path:
                count = self.export_manager.export_markdown(path, filter_type, date_from=date_from)
                report = dict(getattr(self.export_manager, "last_export_report", {}) or {})
                if count >= 0 and report.get("success"):
                    success_reports.append(report)
                else:
                    failed_reports.append(report)

        if success_reports and failed_reports:
            QMessageBox.warning(
                self,
                "일부 내보내기 완료",
                f"{self._build_export_summary(success_reports)}\n\n실패:\n{self._build_error_summary(failed_reports)}",
            )
            self.accept()
            return

        if success_reports:
            QMessageBox.information(self, "내보내기 완료", self._build_export_summary(success_reports))
            self.accept()
            return

        if failed_reports:
            QMessageBox.critical(self, "오류", self._build_error_summary(failed_reports))
            return

        QMessageBox.information(self, "안내", "내보낼 파일 경로를 선택하지 않았습니다.")


__all__ = ["ExportDialog"]
