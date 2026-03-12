"""Core database layer for SmartClipboard."""

from __future__ import annotations

import os
import sqlite3
import threading
from typing import Optional

from .db_parts import (
    HistoryOpsMixin,
    RulesSnippetsActionsMixin,
    SchemaSearchMixin,
    TagsCollectionsMixin,
    VaultTrashMixin,
)
from .db_parts.shared import APP_DIR, get_app_directory


DB_FILE = os.path.join(APP_DIR, "clipboard_history_v6.db")


class ClipboardDB(
    SchemaSearchMixin,
    HistoryOpsMixin,
    RulesSnippetsActionsMixin,
    TagsCollectionsMixin,
    VaultTrashMixin,
):
    def __init__(self, db_file: Optional[str] = None, app_dir: Optional[str] = None):
        self.app_dir = app_dir or APP_DIR
        self.db_file = db_file or os.path.join(self.app_dir, "clipboard_history_v6.db")
        self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
        # v10.6: WAL 모드 활성화 (동시성 및 성능 향상)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.lock = threading.RLock()
        self.add_count = 0  # v10.0: cleanup 최적화를 위한 카운터
        self.cleanup_count = 0  # VACUUM 실행 주기 카운터
        self.create_tables()

