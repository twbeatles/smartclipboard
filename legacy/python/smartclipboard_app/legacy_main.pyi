from __future__ import annotations

from logging import Logger
from typing import Any

APP_DIR: str
DB_FILE: str
LEGACY_IMPL_ACTIVE: str
LEGACY_IMPL_FALLBACK_REASON: str | None
LEGACY_IMPL_REQUESTED: str
logger: Logger


class MainWindow:
    tray_icon: Any

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def show(self) -> None: ...

