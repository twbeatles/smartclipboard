"""Shared services for import/export manager helpers."""

from __future__ import annotations

import datetime
import os

from smartclipboard_core.file_paths import normalize_import_file_path

from .reports import append_warning


def parse_timestamp(timestamp):
    if not timestamp:
        return None

    if isinstance(timestamp, datetime.datetime):
        parsed = timestamp
    else:
        raw_value = str(timestamp).strip()
        if not raw_value:
            return None

        try:
            parsed = datetime.datetime.strptime(raw_value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            iso_value = raw_value[:-1] + "+00:00" if raw_value.endswith("Z") else raw_value
            try:
                parsed = datetime.datetime.fromisoformat(iso_value)
            except ValueError:
                try:
                    parsed = datetime.datetime.combine(
                        datetime.date.fromisoformat(raw_value),
                        datetime.time(),
                    )
                except ValueError:
                    return None

    if parsed.tzinfo is not None:
        parsed = parsed.replace(tzinfo=None)
    return parsed


def normalize_timestamp(timestamp, fallback: str | None = None) -> str:
    parsed = parse_timestamp(timestamp)
    if parsed is None:
        return fallback or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def matches_date_filter(timestamp, date_from) -> bool:
    if not date_from:
        return True
    parsed = parse_timestamp(timestamp)
    return parsed.date() >= date_from if parsed is not None else False


def resolve_file_paths(payload: dict, report: dict | None = None) -> list[str]:
    raw_paths = payload.get("file_paths")
    if isinstance(raw_paths, list):
        candidates = raw_paths
    else:
        single_path = payload.get("file_path")
        if single_path:
            candidates = [single_path]
        else:
            candidates = str(payload.get("content", "") or "").splitlines()

    normalized_paths: list[str] = []
    seen: set[str] = set()
    rejected_count = 0
    for raw_path in candidates:
        normalized = normalize_import_file_path(raw_path)
        if not normalized:
            rejected_count += 1
            continue
        dedupe_key = os.path.normcase(normalized)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized_paths.append(normalized)

    if rejected_count and report is not None:
        append_warning(report, "상대 경로 또는 로컬 file:// URL이 아닌 FILE 경로를 건너뛰었습니다.")
    return normalized_paths


def get_filtered_items(db, filter_type="all", date_from=None):
    items = db.get_items("", "전체")
    filtered = []
    for item in items:
        _pid, _content, ptype, timestamp, *_rest = item
        if filter_type != "all" and filter_type != ptype:
            continue
        if not matches_date_filter(timestamp, date_from):
            continue
        filtered.append(item)
    return filtered


def get_item_image_blob(db, item_id: int):
    with db.lock:
        cursor = db.conn.cursor()
        cursor.execute("SELECT image_data FROM history WHERE id = ?", (item_id,))
        row = cursor.fetchone()
    return row[0] if row else None


def get_item_metadata(db, item_id: int):
    with db.lock:
        cursor = db.conn.cursor()
        cursor.execute(
            "SELECT tags, note, bookmark, collection_id, pinned, pin_order, use_count, timestamp, url_title "
            "FROM history WHERE id = ?",
            (item_id,),
        )
        return cursor.fetchone()


__all__ = [
    "get_filtered_items",
    "get_item_image_blob",
    "get_item_metadata",
    "matches_date_filter",
    "normalize_timestamp",
    "parse_timestamp",
    "resolve_file_paths",
]
