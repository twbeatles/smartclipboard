"""Import dialog module."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class ImportDialog(QDialog):
    """Import clipboard data from JSON/CSV."""

    def __init__(self, parent, export_manager):
        super().__init__(parent)
        self.export_manager = export_manager
        self.setWindowTitle("불러오기")
        self.setMinimumSize(460, 240)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        info = QLabel("지원 형식: JSON, CSV")
        layout.addWidget(info)

        self.format_hint = QLabel("파일을 선택하면 형식별 안내가 표시됩니다.")
        self.format_hint.setWordWrap(True)
        layout.addWidget(self.format_hint)

        file_layout = QHBoxLayout()
        self.file_path = QLineEdit()
        self.file_path.setPlaceholderText("파일을 선택하세요...")
        self.file_path.setReadOnly(True)
        btn_browse = QPushButton("찾아보기")
        btn_browse.clicked.connect(self.browse_file)
        file_layout.addWidget(self.file_path)
        file_layout.addWidget(btn_browse)
        layout.addLayout(file_layout)

        btn_layout = QHBoxLayout()
        btn_import = QPushButton("불러오기")
        btn_import.clicked.connect(self.do_import)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_import)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _set_format_hint(self, path: str) -> None:
        lower_path = path.lower()
        if lower_path.endswith(".json"):
            self.format_hint.setText(
                "JSON은 이미지 바이너리와 메타데이터를 포함해 가장 충실하게 복원합니다."
            )
        elif lower_path.endswith(".csv"):
            self.format_hint.setText(
                "CSV는 텍스트 위주 형식입니다. 이미지 바이너리와 일부 메타데이터는 복원되지 않을 수 있습니다."
            )
        else:
            self.format_hint.setText("파일을 선택하면 형식별 안내가 표시됩니다.")

    @staticmethod
    def _build_import_summary(report: dict) -> str:
        collection_summary = report.get("collection_summary", {})
        lines = [
            f"가져온 항목: {report.get('imported', 0)}개",
            f"건너뛴 항목: {report.get('skipped', 0)}개",
        ]
        backup_path = report.get("backup_path")
        if backup_path:
            lines.append(f"사전 백업: {backup_path}")

        remapped = int(collection_summary.get("remapped", 0) or 0)
        cleared = int(collection_summary.get("cleared", 0) or 0)
        created = int(collection_summary.get("created", 0) or 0)
        reused = int(collection_summary.get("reused", 0) or 0)
        if any((created, reused, remapped, cleared)):
            lines.append(
                "컬렉션 처리: "
                f"생성 {created}개, 재사용 {reused}개, remap {remapped}개, 해제 {cleared}개"
            )

        warnings = report.get("warnings", []) or []
        if warnings:
            lines.append("")
            lines.append("주의:")
            lines.extend(f"- {warning}" for warning in warnings[:4])
            if len(warnings) > 4:
                lines.append(f"- 추가 경고 {len(warnings) - 4}건")
        return "\n".join(lines)

    @staticmethod
    def _build_import_error(report: dict) -> str:
        message = report.get("error") or "가져오기에 실패했습니다."
        backup_path = report.get("backup_path")
        if backup_path:
            return f"{message}\n\n사전 백업: {backup_path}"
        return message

    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "파일 선택",
            "",
            "지원 파일 (*.json *.csv);;JSON (*.json);;CSV (*.csv)",
        )
        if path:
            self.file_path.setText(path)
            self._set_format_hint(path)

    def do_import(self):
        path = self.file_path.text().strip()
        if not path:
            QMessageBox.warning(self, "경고", "파일을 선택하세요.")
            return

        lower_path = path.lower()
        if lower_path.endswith(".json"):
            count = self.export_manager.import_json(path)
        elif lower_path.endswith(".csv"):
            confirm = QMessageBox.question(
                self,
                "CSV 가져오기 확인",
                "CSV는 이미지 바이너리와 일부 메타데이터를 복원하지 못할 수 있습니다.\n계속할까요?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            count = self.export_manager.import_csv(path)
        else:
            QMessageBox.warning(self, "경고", "지원하지 않는 파일 형식입니다.")
            return

        report = getattr(self.export_manager, "last_import_report", {}) or {}
        if count >= 0 and report.get("success"):
            QMessageBox.information(self, "불러오기 완료", self._build_import_summary(report))
            self.accept()
        else:
            QMessageBox.critical(self, "오류", self._build_import_error(report))


__all__ = ["ImportDialog"]
