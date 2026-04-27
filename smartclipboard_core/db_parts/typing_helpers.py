from __future__ import annotations

import sqlite3
import threading
from typing import TYPE_CHECKING, Any


class DBRuntimeMixin:
    if TYPE_CHECKING:
        app_dir: str
        db_file: str
        conn: sqlite3.Connection
        lock: threading.RLock
        add_count: int
        cleanup_count: int

        def backup_db(self, target_path: str | None = None, force: bool = False) -> bool: ...
        def ensure_search_index(self) -> bool: ...
        def get_setting(self, key: Any, default: Any = None) -> Any: ...
        def _get_collection_by_name_locked(self, cursor: Any, normalized_name: str) -> Any: ...
        def _add_collection_locked(self, cursor: Any, normalized_name: str, icon: str, color: str) -> int | bool: ...
        @staticmethod
        def _normalize_collection_name(name: str) -> str: ...
        @staticmethod
        def _collection_exists(cursor: Any, collection_id: int) -> bool: ...
        def _set_item_metadata_locked(self, cursor: Any, item_id: int, **metadata: Any) -> bool: ...
        def _add_item_locked(
            self,
            cursor: Any,
            content: str,
            image_data: bytes | None,
            type_tag: str,
            timestamp: str | None = None,
        ) -> tuple[int | bool, bool]: ...
        @classmethod
        def _build_fts_match(cls, query: str) -> str: ...


__all__ = ["DBRuntimeMixin"]
