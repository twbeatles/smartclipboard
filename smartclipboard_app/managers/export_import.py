"""Export/import manager implementation."""

from __future__ import annotations

import base64
import binascii
import csv
import datetime
import json
import logging
import os

from smartclipboard_core.file_paths import (
    describe_file_paths,
    file_content_from_paths,
    file_paths_from_content,
    normalize_local_file_paths,
)

logger = logging.getLogger(__name__)

DEFAULT_TYPE_ICONS = {
    "TEXT": "[T]",
    "LINK": "[L]",
    "IMAGE": "[I]",
    "CODE": "[C]",
    "COLOR": "[K]",
    "FILE": "[F]",
}


class ExportImportManager:
    """Import/export clipboard data in JSON/CSV/Markdown formats."""

    def __init__(self, db, version="10.6", type_icons=None, logger_=None):
        self.db = db
        self.version = version
        self.type_icons = type_icons or DEFAULT_TYPE_ICONS
        self.logger = logger_ or logger

    @staticmethod
    def _parse_timestamp(timestamp):
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
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed

    @classmethod
    def _normalize_timestamp(cls, timestamp, fallback: str | None = None) -> str:
        parsed = cls._parse_timestamp(timestamp)
        if parsed is None:
            return fallback or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return parsed.strftime("%Y-%m-%d %H:%M:%S")

    @classmethod
    def _matches_date_filter(cls, timestamp, date_from) -> bool:
        if not date_from:
            return True
        parsed = cls._parse_timestamp(timestamp)
        return parsed.date() >= date_from if parsed is not None else False

    @staticmethod
    def _resolve_file_paths(payload: dict) -> list[str]:
        raw_paths = payload.get("file_paths")
        if isinstance(raw_paths, list):
            return normalize_local_file_paths(raw_paths)

        single_path = payload.get("file_path")
        if single_path:
            return normalize_local_file_paths([single_path])

        return file_paths_from_content(payload.get("content", ""))

    def _get_filtered_items(self, filter_type="all", date_from=None):
        items = self.db.get_items("", "전체")
        filtered = []
        for item in items:
            _pid, _content, ptype, timestamp, *_rest = item
            if filter_type != "all" and filter_type != ptype:
                continue
            if not self._matches_date_filter(timestamp, date_from):
                continue
            filtered.append(item)
        return filtered

    def export_json(self, path, filter_type="all", date_from=None, include_metadata=False):
        try:
            items = self._get_filtered_items(filter_type, date_from=date_from)
            export_data = {
                "app": "SmartClipboard Pro",
                "version": self.version,
                "exported_at": datetime.datetime.now().isoformat(),
                "migration_mode": bool(include_metadata),
                "items": [],
            }
            if include_metadata:
                export_data["collections"] = []
                if hasattr(self.db, "get_collections"):
                    try:
                        for cid, cname, cicon, ccolor, _created_at in self.db.get_collections():
                            export_data["collections"].append(
                                {
                                    "legacy_id": int(cid),
                                    "name": cname,
                                    "icon": cicon,
                                    "color": ccolor,
                                }
                            )
                    except Exception as exc:
                        self.logger.debug("Collection export skipped: %s", exc)
            for item in items:
                pid, content, ptype, timestamp, pinned, use_count, pin_order = item

                payload = {
                    "content": content,
                    "type": ptype,
                    "timestamp": timestamp,
                    "pinned": bool(pinned),
                    "use_count": use_count,
                    "pin_order": pin_order,
                }
                if ptype == "IMAGE":
                    try:
                        with self.db.lock:
                            cursor = self.db.conn.cursor()
                            cursor.execute("SELECT image_data FROM history WHERE id = ?", (pid,))
                            image_row = cursor.fetchone()
                        image_data = image_row[0] if image_row else None
                        if not image_data:
                            self.logger.debug("Image export skipped for id=%s: missing blob", pid)
                            continue
                        payload["image_data_b64"] = base64.b64encode(image_data).decode("ascii")
                    except Exception as exc:
                        self.logger.debug("Image export skipped for id=%s: %s", pid, exc)
                        continue
                elif ptype == "FILE":
                    file_paths = file_paths_from_content(content)
                    if file_paths:
                        payload["file_paths"] = file_paths
                        payload["file_path"] = file_paths[0]
                if include_metadata:
                    try:
                        with self.db.lock:
                            cursor = self.db.conn.cursor()
                            cursor.execute(
                                "SELECT tags, note, bookmark, collection_id, pinned, pin_order, use_count, timestamp "
                                "FROM history WHERE id = ?",
                                (pid,),
                            )
                            meta = cursor.fetchone()
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
                    except Exception as exc:
                        self.logger.debug("Export metadata fetch skipped for id=%s: %s", pid, exc)
                export_data["items"].append(payload)

            with open(path, "w", encoding="utf-8") as fh:
                json.dump(export_data, fh, ensure_ascii=False, indent=2)
            return len(export_data["items"])
        except Exception as exc:
            self.logger.error("JSON Export Error: %s", exc)
            return -1

    def export_csv(self, path, filter_type="all", date_from=None):
        try:
            items = self._get_filtered_items(filter_type, date_from=date_from)
            with open(path, "w", encoding="utf-8-sig", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(["내용", "유형", "시간", "고정", "사용횟수"])
                count = 0
                for item in items:
                    _, content, ptype, timestamp, pinned, use_count, _pin_order = item
                    if ptype == "IMAGE":
                        export_content = content or "[이미지 항목 - 바이너리 제외]"
                    elif ptype == "FILE":
                        file_paths = file_paths_from_content(content)
                        export_content = "\n".join(file_paths) if file_paths else (content or "[파일 항목]")
                    else:
                        export_content = content or ""
                    if not export_content:
                        continue
                    writer.writerow([export_content, ptype, timestamp, "예" if pinned else "아니오", use_count])
                    count += 1
            return count
        except Exception as exc:
            self.logger.error("CSV Export Error: %s", exc)
            return -1

    def export_markdown(self, path, filter_type="all", date_from=None):
        try:
            items = self._get_filtered_items(filter_type, date_from=date_from)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("# SmartClipboard Pro 히스토리\n\n")
                fh.write(f"내보낸 날짜: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                fh.write("---\n\n")

                count = 0
                for item in items:
                    _, content, ptype, timestamp, pinned, _use_count, _pin_order = item

                    pin_mark = "[PIN] " if pinned else ""
                    type_icon = self.type_icons.get(ptype, "[T]")
                    fh.write(f"### {pin_mark}{type_icon} {timestamp}\n\n")
                    if ptype == "IMAGE":
                        placeholder = content or "[이미지 항목]"
                        fh.write(f"{placeholder}\n\n")
                        fh.write("> 이미지 바이너리 데이터는 Markdown 내보내기에서 제외됩니다.\n\n")
                    elif ptype == "FILE":
                        file_paths = file_paths_from_content(content)
                        lines = file_paths or [content or "[파일 항목]"]
                        fh.write("```text\n")
                        fh.write("\n".join(lines))
                        fh.write("\n```\n\n")
                    elif ptype == "CODE":
                        fh.write(f"```\n{content}\n```\n\n")
                    elif ptype == "LINK":
                        fh.write(f"[{content}]({content})\n\n")
                    else:
                        fh.write(f"{content}\n\n")
                    fh.write("---\n\n")
                    count += 1
            return count
        except Exception as exc:
            self.logger.error("Markdown Export Error: %s", exc)
            return -1

    def import_json(self, path):
        valid_types = {"TEXT", "LINK", "IMAGE", "CODE", "COLOR", "FILE"}
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)

            collection_id_map = {}
            collections_payload = data.get("collections", [])
            if collections_payload and hasattr(self.db, "add_collection"):
                for entry in collections_payload:
                    legacy_id = entry.get("legacy_id")
                    name = (entry.get("name") or "").strip()
                    if not name:
                        continue
                    try:
                        existing = None
                        if hasattr(self.db, "get_collection_by_name"):
                            existing = self.db.get_collection_by_name(name)
                        if existing:
                            new_id = existing[0]
                        else:
                            icon = entry.get("icon") or "📁"
                            color = entry.get("color") or "#6366f1"
                            new_id = self.db.add_collection(name, icon, color)
                        if isinstance(new_id, int) and not isinstance(new_id, bool) and legacy_id is not None:
                            collection_id_map[int(legacy_id)] = new_id
                    except Exception as exc:
                        self.logger.debug("Collection import skipped for %s: %s", name, exc)

            imported = 0
            for item in data.get("items", []):
                content = item.get("content", "")
                ptype = item.get("type", "TEXT")
                if ptype not in valid_types:
                    ptype = "TEXT"
                image_data = None
                if ptype == "IMAGE":
                    image_data_b64 = item.get("image_data_b64")
                    if not image_data_b64:
                        continue
                    try:
                        image_data = base64.b64decode(image_data_b64, validate=True)
                    except (ValueError, TypeError, binascii.Error) as exc:
                        self.logger.debug("Image import skipped for content=%r: %s", content, exc)
                        continue
                    content = content or "[이미지 캡처]"
                elif ptype == "FILE":
                    file_paths = self._resolve_file_paths(item)
                    if not file_paths:
                        self.logger.debug("File import skipped for payload without valid local paths")
                        continue
                    content = file_content_from_paths(file_paths)
                elif not content:
                    continue
                item_id = self.db.add_item(content, image_data, ptype)
                if not item_id:
                    continue
                imported += 1

                metadata = {}
                for key in ("tags", "note", "bookmark", "collection_id", "pinned", "pin_order", "use_count", "timestamp"):
                    if key in item:
                        metadata[key] = item.get(key)
                if "collection_id" in metadata:
                    metadata["collection_id"] = None
                    legacy_collection_id = item.get("collection_id")
                    lookup_key = legacy_collection_id
                    if legacy_collection_id is not None and not isinstance(legacy_collection_id, bool):
                        try:
                            lookup_key = int(str(legacy_collection_id))
                        except (TypeError, ValueError):
                            lookup_key = None
                    if collections_payload and lookup_key in collection_id_map:
                        metadata["collection_id"] = collection_id_map[lookup_key]
                if "timestamp" in metadata:
                    metadata["timestamp"] = self._normalize_timestamp(metadata.get("timestamp"))
                if metadata and hasattr(self.db, "set_item_metadata"):
                    self.db.set_item_metadata(item_id, **metadata)
            return imported
        except Exception as exc:
            self.logger.error("JSON Import Error: %s", exc)
            return -1

    def import_csv(self, path):
        valid_types = {"TEXT", "LINK", "IMAGE", "CODE", "COLOR", "FILE"}
        try:
            imported = 0
            with open(path, "r", encoding="utf-8-sig") as fh:
                reader = csv.reader(fh)
                next(reader)
                for row in reader:
                    if len(row) < 2:
                        continue
                    content, ptype = row[0], row[1]
                    if ptype not in valid_types:
                        ptype = "TEXT"
                    if ptype == "IMAGE":
                        continue
                    if ptype == "FILE":
                        file_paths = file_paths_from_content(content)
                        if not file_paths:
                            continue
                        content = file_content_from_paths(file_paths)
                    if content:
                        self.db.add_item(content, None, ptype)
                        imported += 1
            return imported
        except Exception as exc:
            self.logger.error("CSV Import Error: %s", exc)
            return -1


__all__ = ["ExportImportManager", "DEFAULT_TYPE_ICONS"]
