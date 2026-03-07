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
        self.setWindowTitle("📥 가져오기")
        self.setMinimumSize(400, 200)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        info = QLabel("지원 형식: JSON, CSV")
        layout.addWidget(info)

        file_layout = QHBoxLayout()
        self.file_path = QLineEdit()
        self.file_path.setPlaceholderText("파일을 선택하세요...")
        self.file_path.setReadOnly(True)
        btn_browse = QPushButton("📂 찾아보기")
        btn_browse.clicked.connect(self.browse_file)
        file_layout.addWidget(self.file_path)
        file_layout.addWidget(btn_browse)
        layout.addLayout(file_layout)

        btn_layout = QHBoxLayout()
        btn_import = QPushButton("📥 가져오기")
        btn_import.clicked.connect(self.do_import)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_import)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "파일 선택",
            "",
            "지원 파일 (*.json *.csv);;JSON (*.json);;CSV (*.csv)",
        )
        if path:
            self.file_path.setText(path)

    def do_import(self):
        path = self.file_path.text()
        if not path:
            QMessageBox.warning(self, "경고", "파일을 선택하세요.")
            return

        if path.lower().endswith(".json"):
            count = self.export_manager.import_json(path)
        elif path.lower().endswith(".csv"):
            count = self.export_manager.import_csv(path)
        else:
            QMessageBox.warning(self, "경고", "지원하지 않는 파일 형식입니다.")
            return

        if count >= 0:
            QMessageBox.information(self, "완료", f"✅ {count}개 항목을 가져왔습니다.")
            self.accept()
        else:
            QMessageBox.critical(self, "오류", "가져오기에 실패했습니다.")


__all__ = ["ImportDialog"]
