"""Export/import manager implementation."""

from __future__ import annotations

import csv
import json
import logging
from typing import Any

from . import services
from .backup import create_pre_import_backup
from .csv_codec import export_csv_rows, import_csv_row_locked
from .json_codec import build_json_export_payload, import_collections_locked, import_json_item_locked
from .markdown_codec import export_markdown_document
from .reports import append_warning, new_export_report, new_import_report

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
        self.last_import_report: dict[str, Any] = new_import_report("none", "")
        self.last_export_report: dict[str, Any] = new_export_report("none", "")

    @staticmethod
    def _parse_timestamp(timestamp):
        return services.parse_timestamp(timestamp)

    @classmethod
    def _normalize_timestamp(cls, timestamp, fallback: str | None = None) -> str:
        return services.normalize_timestamp(timestamp, fallback)

    @classmethod
    def _matches_date_filter(cls, timestamp, date_from) -> bool:
        return services.matches_date_filter(timestamp, date_from)

    @staticmethod
    def _resolve_file_paths(payload: dict, report: dict[str, Any] | None = None) -> list[str]:
        return services.resolve_file_paths(payload, report=report)

    def _get_filtered_items(self, filter_type="all", date_from=None):
        return services.get_filtered_items(self.db, filter_type, date_from)

    def _get_item_image_blob(self, item_id: int):
        return services.get_item_image_blob(self.db, item_id)

    def _get_item_metadata(self, item_id: int):
        return services.get_item_metadata(self.db, item_id)

    def export_json(self, path, filter_type="all", date_from=None, include_metadata=False):
        report = new_export_report("json", path)
        report["filter_type"] = filter_type
        report["date_from"] = str(date_from) if date_from else None
        report["include_metadata"] = bool(include_metadata)
        self.last_export_report = report

        try:
            items = self._get_filtered_items(filter_type, date_from=date_from)
            export_data = build_json_export_payload(
                self.db,
                items,
                include_metadata,
                self.version,
                report,
                self._get_item_image_blob,
                self._get_item_metadata,
            )
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(export_data, fh, ensure_ascii=False, indent=2)
            report["success"] = True
            return report["exported"]
        except Exception as exc:
            report["error"] = str(exc)
            self.logger.error("JSON Export Error: %s", exc)
            return -1

    def export_csv(self, path, filter_type="all", date_from=None):
        report = new_export_report("csv", path)
        report["filter_type"] = filter_type
        report["date_from"] = str(date_from) if date_from else None
        self.last_export_report = report

        try:
            items = self._get_filtered_items(filter_type, date_from=date_from)
            with open(path, "w", encoding="utf-8-sig", newline="") as fh:
                writer = csv.writer(fh)
                export_csv_rows(writer, items, report, self.logger)
            report["success"] = True
            return report["exported"]
        except Exception as exc:
            report["error"] = str(exc)
            self.logger.error("CSV Export Error: %s", exc)
            return -1

    def export_markdown(self, path, filter_type="all", date_from=None):
        report = new_export_report("markdown", path)
        report["filter_type"] = filter_type
        report["date_from"] = str(date_from) if date_from else None
        self.last_export_report = report

        try:
            items = self._get_filtered_items(filter_type, date_from=date_from)
            with open(path, "w", encoding="utf-8") as fh:
                export_markdown_document(fh, items, self.type_icons, report)
            report["success"] = True
            return report["exported"]
        except Exception as exc:
            report["error"] = str(exc)
            self.logger.error("Markdown Export Error: %s", exc)
            return -1

    def import_json(self, path):
        report = new_import_report("json", path)
        self.last_import_report = report

        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                raise ValueError("JSON import payload must be an object")
            items_payload = data.get("items")
            if not isinstance(items_payload, list):
                raise ValueError("JSON import payload must contain an items list")

            report["backup_path"] = create_pre_import_backup(self.db)
            collections_payload = data.get("collections", [])
            collections_payload_present = bool(collections_payload)

            with self.db.lock:
                cursor = self.db.conn.cursor()
                cursor.execute("BEGIN")
                try:
                    collection_id_map = import_collections_locked(self.db, cursor, collections_payload, report)
                    for item in items_payload:
                        if not isinstance(item, dict):
                            report["skipped"] += 1
                            append_warning(report, "일부 item payload가 잘못된 형식이라 건너뛰었습니다.")
                            continue
                        import_json_item_locked(
                            self.db,
                            cursor,
                            item,
                            collection_id_map,
                            collections_payload_present,
                            report,
                            VALID_ITEM_TYPES,
                            self._normalize_timestamp,
                            self._resolve_file_paths,
                        )
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
        report = new_import_report("csv", path)
        self.last_import_report = report

        try:
            report["backup_path"] = create_pre_import_backup(self.db)
            with open(path, "r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.reader(fh)
                next(reader, None)

                with self.db.lock:
                    cursor = self.db.conn.cursor()
                    cursor.execute("BEGIN")
                    try:
                        for row in reader:
                            import_csv_row_locked(
                                self.db,
                                cursor,
                                row,
                                report,
                                VALID_ITEM_TYPES,
                                self._normalize_timestamp,
                            )
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
