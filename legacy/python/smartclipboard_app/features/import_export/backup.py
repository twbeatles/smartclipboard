"""Backup helpers for import/export flows."""

from __future__ import annotations

import datetime
import os
import shutil
import sqlite3
import tempfile

MINIMAL_RESTORE_COLUMNS = {
    "history": {"id", "content", "image_data", "type", "timestamp"},
    "settings": {"key", "value"},
}

FULL_RESTORE_COLUMNS = {
    "history": {"id", "content", "image_data", "type", "timestamp"},
    "settings": {"key", "value"},
    "snippets": {"id", "name", "content"},
    "copy_rules": {"id", "name", "pattern", "action"},
    "secure_vault": {"id", "encrypted_content", "label"},
    "clipboard_actions": {"id", "name", "pattern", "action_type"},
    "deleted_history": {"id", "content", "image_data", "type", "deleted_at", "expires_at"},
    "collections": {"id", "name"},
}


def create_pre_import_backup(db) -> str:
    app_dir = getattr(db, "app_dir", os.path.dirname(getattr(db, "db_file", "")))
    backup_dir = os.path.join(app_dir, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    candidate_time = datetime.datetime.now().replace(microsecond=0)
    while True:
        filename = f"pre_import_{candidate_time.strftime('%Y%m%d_%H%M%S')}.db"
        backup_path = os.path.join(backup_dir, filename)
        if not os.path.exists(backup_path):
            break
        candidate_time += datetime.timedelta(seconds=1)

    if not db.backup_db(target_path=backup_path, force=True):
        raise RuntimeError("pre-import backup creation failed")
    return backup_path


def create_pre_restore_backup(db) -> str:
    app_dir = getattr(db, "app_dir", os.path.dirname(getattr(db, "db_file", "")))
    backup_dir = os.path.join(app_dir, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    candidate_time = datetime.datetime.now().replace(microsecond=0)
    while True:
        filename = f"pre_restore_{candidate_time.strftime('%Y%m%d_%H%M%S')}.db"
        backup_path = os.path.join(backup_dir, filename)
        if not os.path.exists(backup_path):
            break
        candidate_time += datetime.timedelta(seconds=1)

    if not db.backup_db(target_path=backup_path, force=True):
        raise RuntimeError("pre-restore backup creation failed")
    return backup_path


def _validate_table_columns(cursor, required_columns: dict[str, set[str]]) -> str | None:
    for table_name, columns in required_columns.items():
        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        if cursor.fetchone() is None:
            return f"missing required table: {table_name}"
        cursor.execute(f"PRAGMA table_info({table_name})")
        actual_columns = {str(row[1]) for row in cursor.fetchall()}
        missing = sorted(columns - actual_columns)
        if missing:
            return f"missing required columns in {table_name}: {', '.join(missing)}"
    return None


def inspect_restore_database(path: str) -> tuple[bool, str | None, str]:
    """Validate a restore database and classify it as full, minimal, or invalid."""
    if not path or not os.path.exists(path):
        return False, "restore database file does not exist", "invalid"

    db_uri = f"file:{os.path.abspath(path)}?mode=ro"
    try:
        conn = sqlite3.connect(db_uri, uri=True)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            integrity = cursor.fetchone()
            if not integrity or str(integrity[0]).lower() != "ok":
                return False, f"sqlite integrity_check failed: {integrity[0] if integrity else 'no result'}", "invalid"

            minimal_error = _validate_table_columns(cursor, MINIMAL_RESTORE_COLUMNS)
            if minimal_error:
                return False, minimal_error, "invalid"

            full_error = _validate_table_columns(cursor, FULL_RESTORE_COLUMNS)
            if full_error:
                return True, full_error, "minimal"
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return False, f"sqlite validation failed: {exc}", "invalid"
    return True, None, "full"


def validate_restore_database(path: str, mode: str = "full") -> tuple[bool, str | None]:
    """Validate restore input in full or minimal mode.

    Full mode requires every SmartClipboard feature table. Minimal mode accepts
    legacy backups that only contain history and settings.
    """
    if mode not in {"full", "minimal"}:
        return False, f"unsupported restore validation mode: {mode}"

    is_valid, error, profile = inspect_restore_database(path)
    if not is_valid:
        return False, error
    if mode == "minimal":
        return True, None
    if profile != "full":
        return False, error or "restore database is missing full feature tables"
    return True, None


def _remove_sqlite_sidecars(db_path: str) -> None:
    for suffix in ("-wal", "-shm"):
        sidecar = f"{db_path}{suffix}"
        try:
            if os.path.exists(sidecar):
                os.remove(sidecar)
        except OSError:
            pass


def replace_database_from_backup(source_path: str, target_path: str) -> None:
    target_dir = os.path.dirname(os.path.abspath(target_path)) or "."
    os.makedirs(target_dir, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".restore-", suffix=".db", dir=target_dir)
    os.close(fd)
    try:
        shutil.copy2(source_path, temp_path)
        _remove_sqlite_sidecars(target_path)
        os.replace(temp_path, target_path)
        _remove_sqlite_sidecars(target_path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


__all__ = [
    "create_pre_import_backup",
    "create_pre_restore_backup",
    "inspect_restore_database",
    "replace_database_from_backup",
    "validate_restore_database",
]
