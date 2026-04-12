"""Export/import manager implementation."""

from __future__ import annotations

import base64
import binascii
import csv
import datetime
import json
import logging
import os
from typing import Any

from smartclipboard_core.file_paths import (
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

VALID_ITEM_TYPES = {"TEXT", "LINK", "IMAGE", "CODE", "COLOR", "FILE"}


class ExportImportManager:
    """Import/export clipboard data in JSON/CSV/Markdown formats."""

    def __init__(self, db, version="10.6", type_icons=None, logger_=None):
        self.db = db
        self.version = version
        self.type_icons = type_icons or DEFAULT_TYPE_ICONS
        self.logger = logger_ or logger
        self.last_import_report: dict[str, Any] = self._new_import_report("none", "")
        self.last_export_report: dict[str, Any] = self._new_export_report("none", "")

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
            parsed = parsed.replace(tzinfo=None)
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

    @staticmethod
    def _new_export_report(fmt: str, path: str) -> dict[str, Any]:
        return {
            "success": False,
            "format": fmt,
            "path": path,
            "filter_type": "all",
            "date_from": None,
            "include_metadata": False,
            "exported": 0,
            "skipped": 0,
            "warnings": [],
            "error": None,
        }

    @staticmethod
    def _new_import_report(fmt: str, path: str) -> dict[str, Any]:
        return {
            "success": False,
            "format": fmt,
            "path": path,
            "imported": 0,
            "skipped": 0,
            "warnings": [],
            "error": None,
            "backup_path": None,
            "collection_summary": {
                "created": 0,
                "reused": 0,
                "remapped": 0,
                "cleared": 0,
            },
        }

    @staticmethod
    def _append_warning(report: dict[str, Any], message: str) -> None:
        warnings = report.setdefault("warnings", [])
        if message not in warnings:
            warnings.append(message)

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

    def _get_item_image_blob(self, item_id: int):
        with self.db.lock:
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT image_data FROM history WHERE id = ?", (item_id,))
            row = cursor.fetchone()
        return row[0] if row else None

    def _get_item_metadata(self, item_id: int):
        with self.db.lock:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT tags, note, bookmark, collection_id, pinned, pin_order, use_count, timestamp "
                "FROM history WHERE id = ?",
                (item_id,),
            )
            return cursor.fetchone()

    def _create_pre_import_backup(self) -> str:
        app_dir = getattr(self.db, "app_dir", os.path.dirname(getattr(self.db, "db_file", "")))
        backup_dir = os.path.join(app_dir, "backups")
        os.makedirs(backup_dir, exist_ok=True)

        candidate_time = datetime.datetime.now().replace(microsecond=0)
        while True:
            filename = f"pre_import_{candidate_time.strftime('%Y%m%d_%H%M%S')}.db"
            backup_path = os.path.join(backup_dir, filename)
            if not os.path.exists(backup_path):
                break
            candidate_time += datetime.timedelta(seconds=1)

        if not self.db.backup_db(target_path=backup_path, force=True):
            raise RuntimeError("pre-import backup creation failed")
        return backup_path

    @staticmethod
    def _normalize_collection_lookup_key(value) -> int | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None

    def _import_collections_locked(self, cursor, payload, report: dict[str, Any]) -> dict[int, int]:
        collection_id_map: dict[int, int] = {}
        if not isinstance(payload, list):
            return collection_id_map

        for entry in payload:
            if not isinstance(entry, dict):
                report["skipped"] += 1
                self._append_warning(report, "일부 collection 항목이 잘못된 형식이라 건너뛰었습니다.")
                continue

            legacy_id = self._normalize_collection_lookup_key(entry.get("legacy_id"))
            name = self.db._normalize_collection_name(entry.get("name", ""))
            if not name:
                report["skipped"] += 1
                self._append_warning(report, "이름이 비어 있는 collection 항목을 건너뛰었습니다.")
                continue

            existing = self.db._get_collection_by_name_locked(cursor, name)
            if existing:
                if legacy_id is not None:
                    collection_id_map[legacy_id] = int(existing[0])
                report["collection_summary"]["reused"] += 1
                continue

            icon = entry.get("icon") or "📁"
            color = entry.get("color") or "#6366f1"
            new_id = self.db._add_collection_locked(cursor, name, icon, color)
            if isinstance(new_id, int) and legacy_id is not None:
                collection_id_map[legacy_id] = new_id
            if isinstance(new_id, int):
                report["collection_summary"]["created"] += 1

        return collection_id_map

    def _build_item_metadata(
        self,
        payload: dict[str, Any],
        collection_id_map: dict[int, int],
        collections_payload_present: bool,
        report: dict[str, Any],
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        for key in ("tags", "note", "bookmark", "collection_id", "pinned", "pin_order", "use_count"):
            if key in payload:
                metadata[key] = payload.get(key)

        if "collection_id" in payload:
            remapped_collection_id = None
            lookup_key = self._normalize_collection_lookup_key(payload.get("collection_id"))
            if collections_payload_present and lookup_key in collection_id_map:
                remapped_collection_id = collection_id_map[lookup_key]
                report["collection_summary"]["remapped"] += 1
            else:
                report["collection_summary"]["cleared"] += 1
                if lookup_key is not None:
                    self._append_warning(report, "일부 항목의 collection 연결을 찾지 못해 해제했습니다.")
            metadata["collection_id"] = remapped_collection_id

        return metadata

    def _import_json_item_locked(
        self,
        cursor,
        payload: dict[str, Any],
        collection_id_map: dict[int, int],
        collections_payload_present: bool,
        report: dict[str, Any],
    ) -> None:
        content = payload.get("content", "")
        item_type = payload.get("type", "TEXT")
        if item_type not in VALID_ITEM_TYPES:
            item_type = "TEXT"

        image_data = None
        if item_type == "IMAGE":
            image_data_b64 = payload.get("image_data_b64")
            if not image_data_b64:
                report["skipped"] += 1
                self._append_warning(report, "이미지 바이너리가 없는 IMAGE 항목을 건너뛰었습니다.")
                return
            try:
                image_data = base64.b64decode(image_data_b64, validate=True)
            except (ValueError, TypeError, binascii.Error) as exc:
                report["skipped"] += 1
                self.logger.debug("Image import skipped for content=%r: %s", content, exc)
                self._append_warning(report, "손상된 image_data_b64 항목을 건너뛰었습니다.")
                return
            content = content or "[이미지 캡처]"
        elif item_type == "FILE":
            file_paths = self._resolve_file_paths(payload)
            if not file_paths:
                report["skipped"] += 1
                self._append_warning(report, "유효한 로컬 경로가 없는 FILE 항목을 건너뛰었습니다.")
                return
            content = file_content_from_paths(file_paths)
        elif not content:
            report["skipped"] += 1
            return

        timestamp = self._normalize_timestamp(payload.get("timestamp"))
        item_id, _updated_existing = self.db._add_item_locked(cursor, content, image_data, item_type, timestamp=timestamp)
        if not item_id:
            report["skipped"] += 1
            return

        metadata = self._build_item_metadata(payload, collection_id_map, collections_payload_present, report)
        if metadata:
            self.db._set_item_metadata_locked(cursor, item_id, **metadata)
        report["imported"] += 1

    def _import_csv_row_locked(self, cursor, row: list[str], report: dict[str, Any]) -> None:
        if len(row) < 2:
            report["skipped"] += 1
            return

        content, item_type = row[0], row[1]
        if item_type not in VALID_ITEM_TYPES:
            item_type = "TEXT"

        if item_type == "IMAGE":
            report["skipped"] += 1
            self._append_warning(report, "CSV import는 IMAGE 바이너리를 복원하지 않아 이미지 행을 건너뜁니다.")
            return

        if item_type == "FILE":
            file_paths = file_paths_from_content(content)
            if not file_paths:
                report["skipped"] += 1
                self._append_warning(report, "CSV의 FILE 행 중 유효한 경로가 없는 항목을 건너뛰었습니다.")
                return
            content = file_content_from_paths(file_paths)

        if not content:
            report["skipped"] += 1
            return

        timestamp = row[2] if len(row) > 2 else None
        normalized_timestamp = self._normalize_timestamp(timestamp)
        item_id, _updated_existing = self.db._add_item_locked(cursor, content, None, item_type, timestamp=normalized_timestamp)
        if not item_id:
            report["skipped"] += 1
            return
        report["imported"] += 1

    def export_json(self, path, filter_type="all", date_from=None, include_metadata=False):
        report = self._new_export_report("json", path)
        report["filter_type"] = filter_type
        report["date_from"] = str(date_from) if date_from else None
        report["include_metadata"] = bool(include_metadata)
        self.last_export_report = report

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
                        self._append_warning(report, "컬렉션 메타데이터를 일부 내보내지 못했습니다.")

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
                    image_data = self._get_item_image_blob(pid)
                    if not image_data:
                        report["skipped"] += 1
                        self.logger.debug("Image export skipped for id=%s: missing blob", pid)
                        self._append_warning(report, "이미지 바이너리가 없는 IMAGE 항목을 건너뛰었습니다.")
                        continue
                    payload["image_data_b64"] = base64.b64encode(image_data).decode("ascii")
                elif item_type == "FILE":
                    file_paths = file_paths_from_content(content)
                    if file_paths:
                        payload["file_paths"] = file_paths
                        payload["file_path"] = file_paths[0]

                if include_metadata:
                    meta = self._get_item_metadata(pid)
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

            with open(path, "w", encoding="utf-8") as fh:
                json.dump(export_data, fh, ensure_ascii=False, indent=2)
            report["success"] = True
            return report["exported"]
        except Exception as exc:
            report["error"] = str(exc)
            self.logger.error("JSON Export Error: %s", exc)
            return -1

    def export_csv(self, path, filter_type="all", date_from=None):
        report = self._new_export_report("csv", path)
        report["filter_type"] = filter_type
        report["date_from"] = str(date_from) if date_from else None
        self.last_export_report = report

        try:
            items = self._get_filtered_items(filter_type, date_from=date_from)
            with open(path, "w", encoding="utf-8-sig", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(["내용", "유형", "시간", "고정", "사용횟수"])
                for item in items:
                    _pid, content, item_type, timestamp, pinned, use_count, _pin_order = item
                    if item_type == "IMAGE":
                        export_content = content or "[이미지 항목 - 바이너리 제외]"
                        self._append_warning(report, "CSV export는 이미지 바이너리를 제외하고 placeholder만 저장합니다.")
                    elif item_type == "FILE":
                        file_paths = file_paths_from_content(content)
                        export_content = "\n".join(file_paths) if file_paths else (content or "[파일 항목]")
                    else:
                        export_content = content or ""
                    if not export_content:
                        report["skipped"] += 1
                        continue
                    writer.writerow([export_content, item_type, timestamp, "예" if pinned else "아니오", use_count])
                    report["exported"] += 1
            report["success"] = True
            return report["exported"]
        except Exception as exc:
            report["error"] = str(exc)
            self.logger.error("CSV Export Error: %s", exc)
            return -1

    def export_markdown(self, path, filter_type="all", date_from=None):
        report = self._new_export_report("markdown", path)
        report["filter_type"] = filter_type
        report["date_from"] = str(date_from) if date_from else None
        self.last_export_report = report

        try:
            items = self._get_filtered_items(filter_type, date_from=date_from)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("# SmartClipboard Pro 히스토리\n\n")
                fh.write(f"내보낸 날짜: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                fh.write("---\n\n")

                for item in items:
                    _pid, content, item_type, timestamp, pinned, _use_count, _pin_order = item

                    pin_mark = "[PIN] " if pinned else ""
                    type_icon = self.type_icons.get(item_type, "[T]")
                    fh.write(f"### {pin_mark}{type_icon} {timestamp}\n\n")
                    if item_type == "IMAGE":
                        placeholder = content or "[이미지 항목]"
                        fh.write(f"{placeholder}\n\n")
                        fh.write("> 이미지 바이너리 데이터는 Markdown 내보내기에서 제외됩니다.\n\n")
                        self._append_warning(report, "Markdown export는 이미지 바이너리를 제외합니다.")
                    elif item_type == "FILE":
                        file_paths = file_paths_from_content(content)
                        lines = file_paths or [content or "[파일 항목]"]
                        fh.write("```text\n")
                        fh.write("\n".join(lines))
                        fh.write("\n```\n\n")
                    elif item_type == "CODE":
                        fh.write(f"```\n{content}\n```\n\n")
                    elif item_type == "LINK":
                        fh.write(f"[{content}]({content})\n\n")
                    else:
                        fh.write(f"{content}\n\n")
                    fh.write("---\n\n")
                    report["exported"] += 1
            report["success"] = True
            return report["exported"]
        except Exception as exc:
            report["error"] = str(exc)
            self.logger.error("Markdown Export Error: %s", exc)
            return -1

    def import_json(self, path):
        report = self._new_import_report("json", path)
        self.last_import_report = report

        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                raise ValueError("JSON import payload must be an object")

            report["backup_path"] = self._create_pre_import_backup()
            collections_payload = data.get("collections", [])
            collections_payload_present = bool(collections_payload)

            with self.db.lock:
                cursor = self.db.conn.cursor()
                cursor.execute("BEGIN")
                try:
                    collection_id_map = self._import_collections_locked(cursor, collections_payload, report)
                    for item in data.get("items", []):
                        if not isinstance(item, dict):
                            report["skipped"] += 1
                            self._append_warning(report, "일부 item payload가 잘못된 형식이라 건너뛰었습니다.")
                            continue
                        self._import_json_item_locked(cursor, item, collection_id_map, collections_payload_present, report)
                    self.db.conn.commit()
                except Exception:
                    self.db.conn.rollback()
                    raise

            report["success"] = True
            return report["imported"]
        except Exception as exc:
            report["error"] = str(exc)
            self.logger.error("JSON Import Error: %s", exc)
            return -1

    def import_csv(self, path):
        report = self._new_import_report("csv", path)
        self.last_import_report = report

        try:
            report["backup_path"] = self._create_pre_import_backup()
            with open(path, "r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.reader(fh)
                next(reader, None)

                with self.db.lock:
                    cursor = self.db.conn.cursor()
                    cursor.execute("BEGIN")
                    try:
                        for row in reader:
                            self._import_csv_row_locked(cursor, row, report)
                        self.db.conn.commit()
                    except Exception:
                        self.db.conn.rollback()
                        raise

            report["success"] = True
            return report["imported"]
        except Exception as exc:
            report["error"] = str(exc)
            self.logger.error("CSV Import Error: %s", exc)
            return -1


__all__ = ["ExportImportManager", "DEFAULT_TYPE_ICONS"]
