"""Toast widget module."""

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QTimer, Qt
from PyQt6.QtGui import QColor, QShowEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout


def _normalize_duration(duration) -> int:
    try:
        duration_ms = int(duration)
    except (TypeError, ValueError):
        return 2000
    return duration_ms if duration_ms > 0 else 2000


def _compose_message(message, detail) -> str:
    title_text = str(message or "").strip()
    detail_text = str(detail or "").strip()
    if title_text and detail_text:
        return f"{title_text}\n{detail_text}"
    return title_text or detail_text


# Accent colour + glyph per toast type. The card itself stays on a neutral dark
# glass surface so the coloured accent reads as a status cue rather than a wall
# of colour — consistent across every app theme.
_ACCENTS = {
    "info": "#3b82f6",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "error": "#ef4444",
}
_ICONS = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}

_SURFACE = "rgba(24, 28, 40, 0.97)"
_BORDER = "rgba(255, 255, 255, 0.08)"
_TITLE_COLOR = "#f8fafc"
_DETAIL_COLOR = "#cbd5e1"


class ToastNotification(QFrame):
    """플로팅 토스트 알림 위젯 (슬라이드 애니메이션 + 스택 지원)"""

    _active_toasts = []

    def __init__(self, parent, message, detail=None, duration=2000, toast_type="info"):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.duration = _normalize_duration(duration)
        self.parent_window = parent

        accent = _ACCENTS.get(toast_type, _ACCENTS["info"])
        icon = _ICONS.get(toast_type, _ICONS["info"])

        self.setStyleSheet(
            f"""
            QFrame#ToastCard {{
                background-color: {_SURFACE};
                border: 1px solid {_BORDER};
                border-left: 4px solid {accent};
                border-radius: 14px;
            }}
            QLabel {{
                background: transparent;
            }}
            QLabel#ToastTitle {{
                color: {_TITLE_COLOR};
                font-size: 13px;
                font-weight: 700;
            }}
            QLabel#ToastDetail {{
                color: {_DETAIL_COLOR};
                font-size: 12px;
                font-weight: 500;
            }}
            QLabel#ToastIcon {{
                font-size: 18px;
            }}
            """
        )
        self.setObjectName("ToastCard")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 18, 12)
        layout.setSpacing(12)

        icon_label = QLabel(icon)
        icon_label.setObjectName("ToastIcon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(icon_label)

        title_text = str(message or "").strip()
        detail_text = str(detail or "").strip()

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(3)

        title_label = QLabel(title_text or detail_text)
        title_label.setObjectName("ToastTitle")
        title_label.setWordWrap(True)
        title_label.setMaximumWidth(360)
        text_column.addWidget(title_label)

        if title_text and detail_text:
            detail_label = QLabel(detail_text)
            detail_label.setObjectName("ToastDetail")
            detail_label.setWordWrap(True)
            detail_label.setMaximumWidth(360)
            text_column.addWidget(detail_label)

        layout.addLayout(text_column, 1)

        self.adjustSize()

        from PyQt6.QtWidgets import QGraphicsDropShadowEffect

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setXOffset(0)
        shadow.setYOffset(6)
        shadow.setColor(QColor(0, 0, 0, 110))
        self.setGraphicsEffect(shadow)

        if parent:
            parent_rect = parent.geometry()
            self.target_x = parent_rect.right() - self.width() - 20
            stack_offset = len(ToastNotification._active_toasts) * (self.height() + 12)
            self.target_y = parent_rect.bottom() - self.height() - 50 - stack_offset
            self.move(parent_rect.right() + 10, self.target_y)

        ToastNotification._active_toasts.append(self)

        self.slide_in_animation = QPropertyAnimation(self, b"pos")
        self.slide_in_animation.setDuration(320)
        self.slide_in_animation.setStartValue(self.pos())
        self.slide_in_animation.setEndValue(QPoint(self.target_x, self.target_y))
        self.slide_in_animation.setEasingCurve(QEasingCurve.Type.OutBack)

        from PyQt6.QtWidgets import QGraphicsOpacityEffect

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(1.0)

        QTimer.singleShot(self.duration, self.fade_out)

    def showEvent(self, a0: QShowEvent | None) -> None:
        super().showEvent(a0)
        self.slide_in_animation.start()

    def fade_out(self):
        self.slide_out_animation = QPropertyAnimation(self, b"pos")
        self.slide_out_animation.setDuration(220)
        self.slide_out_animation.setStartValue(self.pos())
        if self.parent_window:
            parent_rect = self.parent_window.geometry()
            self.slide_out_animation.setEndValue(QPoint(parent_rect.right() + 10, self.pos().y()))
        self.slide_out_animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self.slide_out_animation.finished.connect(self._cleanup)
        self.slide_out_animation.start()

    def _cleanup(self):
        if self in ToastNotification._active_toasts:
            ToastNotification._active_toasts.remove(self)
        self.close()
        self.deleteLater()

    @staticmethod
    def show_toast(parent, message, detail=None, duration=2000, toast_type="info"):
        toast = ToastNotification(parent, message, detail=detail, duration=duration, toast_type=toast_type)
        toast.show()
        return toast


__all__ = ["ToastNotification"]
