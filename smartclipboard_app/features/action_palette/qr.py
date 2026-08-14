"""QR 렌더. 기존 generate_qr와 같은 qrcode/PIL 경로를 사용한다."""

from __future__ import annotations

from typing import Any

from PyQt6.QtGui import QImage, QPixmap

try:
    import qrcode
except ImportError:
    qrcode = None

from smartclipboard_core.action_palette.builtins.url import QR_MAX_CHARS, qr_text_is_supported


def has_qrcode() -> bool:
    return qrcode is not None


def render_qr_pixmap(text: str) -> QPixmap | None:
    if qrcode is None or not qr_text_is_supported(text):
        return None
    try:
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(text)
        qr.make(fit=True)
        img: Any = qr.make_image(fill_color="black", back_color="white")
        im_data = img.convert("RGBA").tobytes("raw", "RGBA")
        qim = QImage(im_data, img.size[0], img.size[1], QImage.Format.Format_RGBA8888)
        return QPixmap.fromImage(qim)
    except Exception:
        return None


__all__ = ["QR_MAX_CHARS", "has_qrcode", "qr_text_is_supported", "render_qr_pixmap"]
