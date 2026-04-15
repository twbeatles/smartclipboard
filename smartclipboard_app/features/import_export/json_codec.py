"""JSON import/export helpers."""

from __future__ import annotations

import base64
import binascii
import datetime
from typing import Any

from smartclipboard_core.file_paths import file_content_from_paths

from .reports import append_warning


def import_collections_locked(db, cursor, payload, report: dict[str, Any]) -> dict[int, int]:
    collection_id_map: dict[int, int] = {}
    if not isinstance(payload, list):
        return collection_id_map

    for entry in payload:
        if not isinstance(entry, dict):
            report["skipped"] += 1
            append_warning(report, "일부 collection 항목이 잘못된 형식이라 건너뛰었습니다.")
            continue

        legacy_id = normalize_collection_lookup_key(entry.get("legacy_id"))
        name = db._normalize_collection_name(entry.get("name", ""))
        if not name:
            report["skipped"] += 1
            append_warning(report, "이름이 비어 있는 collection 항목을 건너뛰었습니다.")
            continue

        existing = db._get_collection_by_name_locked(cursor, name)
        if existing:
            if legacy_id is not None:
                collection_id_map[legacy_id] = int(existing[0])
            report["collection_summary"]["reused"] += 1
            continue

        icon = entry.get("icon") or "📁"
        color = entry.get("color") or "#6366f1"
        new_id = db._add_collection_locked(cursor, name, icon, color)
        if isinstance(new_id, int) and legacy_id is not None:
            collection_id_map[legacy_id] = new_id
        if isinstance(new_id, int):
            report["collection_summary"]["created"] += 1

    return collection_id_map


def normalize_collection_lookup_key(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def build_item_metadata(payload: dict[str, Any], collection_id_map: dict[int, int], collections_payload_present: bool, report: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ("tags", "note", "bookmark", "collection_id", "pinned", "pin_order", "use_count"):
        if key in payload:
            metadata[key] = payload.get(key)

    if "collection_id" in payload:
        remapped_collection_id = None
        lookup_key = normalize_collection_lookup_key(payload.get("collection_id"))
        if collections_payload_present and lookup_key in collection_id_map:
            remapped_collection_id = collection_id_map[lookup_key]
            report["collection_summary"]["remapped"] += 1
        else:
            report["collection_summary"]["cleared"] += 1
            if lookup_key is not None:
                append_warning(report, "일부 항목의 collection 연결을 찾지 못해 해제했습니다.")
        metadata["collection_id"] = remapped_collection_id

    return metadata


def import_json_item_locked(
    db,
    cursor,
    payload: dict[str, Any],
    collection_id_map: dict[int, int],
    collections_payload_present: bool,
    report: dict[str, Any],
    valid_item_types: set[str],
    normalize_timestamp,
    resolve_file_paths,
) -> None:
    content = payload.get("content", "")
    item_type = payload.get("type", "TEXT")
    if item_type not in valid_item_types:
        item_type = "TEXT"

    image_data = None
    if item_type == "IMAGE":
        image_data_b64 = payload.get("image_data_b64")
        if not image_data_b64:
            report["skipped"] += 1
            append_warning(report, "이미지 바이너리가 없는 IMAGE 항목을 건너뛰었습니다.")
            return
        try:
            image_data = base64.b64decode(image_data_b64, validate=True)
        except (ValueError, TypeError, binascii.Error):
            report["skipped"] += 1
            append_warning(report, "손상된 image_data_b64 항목을 건너뛰었습니다.")
            return
        content = content or "[이미지 캡처]"
    elif item_type == "FILE":
        file_paths = resolve_file_paths(payload)
        if not file_paths:
            report["skipped"] += 1
            append_warning(report, "유효한 로컬 경로가 없는 FILE 항목을 건너뛰었습니다.")
            return
        content = file_content_from_paths(file_paths)
    elif not content:
        report["skipped"] += 1
        return

    timestamp = normalize_timestamp(payload.get("timestamp"))
    item_id, _updated_existing = db._add_item_locked(cursor, content, image_data, item_type, timestamp=timestamp)
    if not item_id:
        report["skipped"] += 1
        return

    metadata = build_item_metadata(payload, collection_id_map, collections_payload_present, report)
    if metadata:
        db._set_item_metadata_locked(cursor, item_id, **metadata)
    report["imported"] += 1


def build_json_export_payload(
    db,
    items,
    include_metadata: bool,
    version: str,
    report: dict[str, Any],
    get_item_image_blob,
    get_item_metadata,
) -> dict[str, Any]:
    from smartclipboard_core.file_paths import file_paths_from_content

    export_data = {
        "app": "SmartClipboard Pro",
        "version": version,
        "exported_at": datetime.datetime.now().isoformat(),
        "migration_mode": bool(include_metadata),
        "items": [],
    }
    if include_metadata:
        export_data["collections"] = []
        if hasattr(db, "get_collections"):
            try:
                for cid, cname, cicon, ccolor, _created_at in db.get_collections():
                    export_data["collections"].append(
                        {
                            "legacy_id": int(cid),
                            "name": cname,
                            "icon": cicon,
                            "color": ccolor,
                        }
                    )
            except Exception:
                append_warning(report, "컬렉션 메타데이터를 일부 내보내지 못했습니다.")

    for item in items:
        pid, content, item_type, timestamp, pinned, use_count, pin_order = item
        payload = {
            "content": content,
            "type": item_type,
            "timestamp": timestamp,
            "pinned": bool(pinned),
            "use_count": use_count,
            "pin_order": pin_order,
        }
        if item_type == "IMAGE":
            image_data = get_item_image_blob(pid)
            if not image_data:
                report["skipped"] += 1
                append_warning(report, "이미지 바이너리가 없는 IMAGE 항목을 건너뛰었습니다.")
                continue
            payload["image_data_b64"] = base64.b64encode(image_data).decode("ascii")
        elif item_type == "FILE":
            file_paths = file_paths_from_content(content)
            if file_paths:
                payload["file_paths"] = file_paths
                payload["file_path"] = file_paths[0]

        if include_metadata:
            meta = get_item_metadata(pid)
            if meta:
                payload.update(
                    {
                        "tags": meta[0] or "",
                        "note": meta[1] or "",
                        "bookmark": int(meta[2] or 0),
                        "collection_id": meta[3],
                        "pinned": bool(meta[4] or 0),
                        "pin_order": int(meta[5] or 0),
                        "use_count": int(meta[6] or 0),
                        "timestamp": meta[7] or timestamp,
                    }
                )
        export_data["items"].append(payload)
        report["exported"] += 1

    return export_data


__all__ = [
    "build_json_export_payload",
    "import_collections_locked",
    "import_json_item_locked",
    "normalize_collection_lookup_key",
]
