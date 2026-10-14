"""Tag dialog module."""

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout


class TagEditDialog(QDialog):
    def __init__(self, parent, db, item_id, current_tags=""):
        super().__init__(parent)
        self.db = db
        self.item_id = item_id
        self.setWindowTitle("🏷️ 태그 편집")
        self.setMinimumWidth(350)
        self.init_ui(current_tags)

    def init_ui(self, current_tags):
        layout = QVBoxLayout(self)

        info_label = QLabel("쉼표로 구분하여 태그를 입력하세요:")
        layout.addWidget(info_label)

        self.tag_input = QLineEdit()
        self.tag_input.setText(current_tags)
        self.tag_input.setPlaceholderText("예: 업무, 중요, 코드")
        layout.addWidget(self.tag_input)

        common_tags = ["업무", "개인", "중요", "임시", "코드", "링크"]
        tag_btn_layout = QHBoxLayout()
        for tag in common_tags:
            btn = QPushButton(tag)
            btn.setMaximumWidth(60)
            btn.clicked.connect(lambda checked, t=tag: self.add_tag(t))
            tag_btn_layout.addWidget(btn)
        layout.addLayout(tag_btn_layout)

        btn_layout = QHBoxLayout()
        btn_save = QPushButton("저장")
        btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def add_tag(self, tag):
        current = self.tag_input.text().strip()
        tags = [t.strip() for t in current.split(",") if t.strip()]
        if tag not in tags:
            tags.append(tag)
        self.tag_input.setText(", ".join(tags))

    def get_tags(self):
        return self.tag_input.text().strip()


__all__ = ["TagEditDialog"]
