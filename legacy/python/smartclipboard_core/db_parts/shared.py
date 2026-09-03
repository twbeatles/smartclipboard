from __future__ import annotations

import logging

from smartclipboard_core.app_paths import get_app_directory



APP_DIR = get_app_directory()
DEFAULT_MAX_HISTORY = 100
CLEANUP_INTERVAL = 10
FILTER_TAG_MAP = {
    "📝 텍스트": "TEXT",
    "🖼️ 이미지": "IMAGE",
    "🔗 링크": "LINK",
    "💻 코드": "CODE",
    "🎨 색상": "COLOR",
    "📎 파일": "FILE",
}

logger = logging.getLogger(__name__)


def history_order_by(alias: str = "") -> str:
    prefix = f"{alias}." if alias else ""
    return (
        f"ORDER BY {prefix}pinned DESC, {prefix}pin_order ASC, "
        f"{prefix}timestamp DESC, {prefix}id DESC"
    )
