"""Backup helpers for import/export flows."""

from __future__ import annotations

import datetime
import os
import shutil
import sqlite3
import tempfile


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


def validate_restore_database(path: str) -> tuple[bool, str | None]:
    if not path or not os.path.exists(path):
        return False, "restore database file does not exist"

    db_uri = f"file:{os.path.abspath(path)}?mode=ro"
    try:
        conn = sqlite3.connect(db_uri, uri=True)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            integrity = cursor.fetchone()
            if not integrity or str(integrity[0]).lower() != "ok":
                return False, f"sqlite integrity_check failed: {integrity[0] if integrity else 'no result'}"

            required_columns = {
                "history": {"id", "content", "image_data", "type", "timestamp"},
                "settings": {"key", "value"},
            }
            for table_name, columns in required_columns.items():
                cursor.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,),
                )
                if cursor.fetchone() is None:
                    return False, f"missing required table: {table_name}"
                cursor.execute(f"PRAGMA table_info({table_name})")
                actual_columns = {str(row[1]) for row in cursor.fetchall()}
                missing = sorted(columns - actual_columns)
                if missing:
                    return False, f"missing required columns in {table_name}: {', '.join(missing)}"
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return False, f"sqlite validation failed: {exc}"
    return True, None


def replace_database_from_backup(source_path: str, target_path: str) -> None:
    target_dir = os.path.dirname(os.path.abspath(target_path)) or "."
    os.makedirs(target_dir, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".restore-", suffix=".db", dir=target_dir)
    os.close(fd)
    try:
        shutil.copy2(source_path, temp_path)
        os.replace(temp_path, target_path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


__all__ = [
    "create_pre_import_backup",
    "create_pre_restore_backup",
    "replace_database_from_backup",
    "validate_restore_database",
]
