"""Statistics dialog module."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QFrame, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class StatisticsDialog(QDialog):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("📊 히스토리 통계")
        self.setMinimumSize(450, 400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        stats = self.db.get_statistics()

        summary_frame = QFrame()
        summary_frame.setStyleSheet("background-color: #16213e; border-radius: 8px; padding: 10px;")
        summary_layout = QHBoxLayout(summary_frame)

        total_label = QLabel(f"📋 총 항목\n{stats['total']}")
        total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        total_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        pinned_label = QLabel(f"📌 고정\n{stats['pinned']}")
        pinned_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pinned_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        today_count = self.db.get_today_count()
        today_label = QLabel(f"📅 오늘\n{today_count}")
        today_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        today_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        summary_layout.addWidget(total_label)
        summary_layout.addWidget(pinned_label)
        summary_layout.addWidget(today_label)
        layout.addWidget(summary_frame)

        type_group = QGroupBox("📊 유형별 분포")
        type_layout = QVBoxLayout(type_group)
        type_icons = {"TEXT": "📝 텍스트", "LINK": "🔗 링크", "IMAGE": "🖼️ 이미지", "CODE": "💻 코드", "COLOR": "🎨 색상", "FILE": "📎 파일"}
        for type_key, count in stats.get("by_type", {}).items():
            label = QLabel(f"{type_icons.get(type_key, type_key)}: {count}개")
            type_layout.addWidget(label)
        if not stats.get("by_type"):
            type_layout.addWidget(QLabel("데이터 없음"))
        layout.addWidget(type_group)

        top_group = QGroupBox("🔥 자주 복사한 항목 Top 5")
        top_layout = QVBoxLayout(top_group)
        top_items = self.db.get_top_items(5)
        for idx, (content, use_count) in enumerate(top_items, 1):
            preview = content[:40] + "..." if len(content) > 40 else content
            preview = preview.replace("\n", " ")
            label = QLabel(f"{idx}. {preview} ({use_count}회)")
            top_layout.addWidget(label)
        if not top_items:
            top_layout.addWidget(QLabel("사용 기록 없음"))
        layout.addWidget(top_group)

        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)


__all__ = ["StatisticsDialog"]
