"""Backup helpers for import/export flows."""

from __future__ import annotations

import datetime
import os


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


__all__ = ["create_pre_import_backup"]
