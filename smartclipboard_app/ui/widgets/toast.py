"""Toast widget module."""

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QTimer, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel


class ToastNotification(QFrame):
    """플로팅 토스트 알림 위젯 (슬라이드 애니메이션 + 스택 지원)"""

    _active_toasts = []

    def __init__(self, parent, message, duration=2000, toast_type="info"):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.duration = duration
        self.parent_window = parent

        colors = {
            "info": "#3b82f6",
            "success": "#22c55e",
            "warning": "#f59e0b",
            "error": "#ef4444",
        }
        icons = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}

        color = colors.get(toast_type, colors["info"])
        icon = icons.get(toast_type, icons["info"])

        self.setStyleSheet(
            f"""
            QFrame {{
                background-color: {color};
                border-radius: 10px;
            }}
            QLabel {{
                color: white;
                font-size: 13px;
                font-weight: bold;
                background: transparent;
            }}
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 16px; background: transparent;")
        layout.addWidget(icon_label)

        msg_label = QLabel(message)
        msg_label.setStyleSheet("background: transparent;")
        layout.addWidget(msg_label)

        self.adjustSize()

        from PyQt6.QtWidgets import QGraphicsDropShadowEffect

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

        if parent:
            parent_rect = parent.geometry()
            self.target_x = parent_rect.right() - self.width() - 20
            stack_offset = len(ToastNotification._active_toasts) * (self.height() + 12)
            self.target_y = parent_rect.bottom() - self.height() - 50 - stack_offset
            self.move(parent_rect.right() + 10, self.target_y)

        ToastNotification._active_toasts.append(self)

        self.slide_in_animation = QPropertyAnimation(self, b"pos")
        self.slide_in_animation.setDuration(300)
        self.slide_in_animation.setStartValue(self.pos())
        self.slide_in_animation.setEndValue(QPoint(self.target_x, self.target_y))
        self.slide_in_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        from PyQt6.QtWidgets import QGraphicsOpacityEffect

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(1.0)

        QTimer.singleShot(duration, self.fade_out)

    def showEvent(self, event):
        super().showEvent(event)
        self.slide_in_animation.start()

    def fade_out(self):
        self.slide_out_animation = QPropertyAnimation(self, b"pos")
        self.slide_out_animation.setDuration(200)
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
    def show_toast(parent, message, duration=2000, toast_type="info"):
        toast = ToastNotification(parent, message, duration, toast_type)
        toast.show()
        return toast


__all__ = ["ToastNotification"]
