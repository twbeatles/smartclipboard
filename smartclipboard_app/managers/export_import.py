"""Export/import manager implementation."""

from __future__ import annotations

import csv
import datetime
import json
import logging

logger = logging.getLogger(__name__)

DEFAULT_TYPE_ICONS = {
    "TEXT": "[T]",
    "LINK": "[L]",
    "IMAGE": "[I]",
    "CODE": "[C]",
    "COLOR": "[K]",
}


class ExportImportManager:
    """Import/export clipboard data in JSON/CSV/Markdown formats."""

    def __init__(self, db, version="10.6", type_icons=None, logger_=None):
        self.db = db
        self.version = version
        self.type_icons = type_icons or DEFAULT_TYPE_ICONS
        self.logger = logger_ or logger

    def export_json(self, path, filter_type="all", date_from=None, include_metadata=False):
        try:
            items = self.db.get_items("", "전체")
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
                if filter_type != "all" and filter_type != ptype:
                    continue
                if ptype == "IMAGE":
                    continue
                if date_from and timestamp:
                    try:
                        item_date = datetime.datetime.strptime(timestamp.split()[0], "%Y-%m-%d").date()
                        if item_date < date_from:
                            continue
                    except (ValueError, IndexError):
                        pass

                payload = {
                    "content": content,
                    "type": ptype,
                    "timestamp": timestamp,
                    "pinned": bool(pinned),
                    "use_count": use_count,
                    "pin_order": pin_order,
                }
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

    def export_csv(self, path, filter_type="all"):
        try:
            items = self.db.get_items("", "전체")
            with open(path, "w", encoding="utf-8-sig", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(["내용", "유형", "시간", "고정", "사용횟수"])
                count = 0
                for item in items:
                    _, content, ptype, timestamp, pinned, use_count, _pin_order = item
                    if filter_type != "all" and filter_type != ptype:
                        continue
                    if ptype == "IMAGE":
                        continue
                    writer.writerow([content, ptype, timestamp, "예" if pinned else "아니오", use_count])
                    count += 1
            return count
        except Exception as exc:
            self.logger.error("CSV Export Error: %s", exc)
            return -1

    def export_markdown(self, path, filter_type="all"):
        try:
            items = self.db.get_items("", "전체")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("# SmartClipboard Pro 히스토리\n\n")
                fh.write(f"내보낸 날짜: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                fh.write("---\n\n")

                count = 0
                for item in items:
                    _, content, ptype, timestamp, pinned, _use_count, _pin_order = item
                    if filter_type != "all" and filter_type != ptype:
                        continue
                    if ptype == "IMAGE":
                        continue

                    pin_mark = "[PIN] " if pinned else ""
                    type_icon = self.type_icons.get(ptype, "[T]")
                    fh.write(f"### {pin_mark}{type_icon} {timestamp}\n\n")
                    if ptype == "CODE":
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
        valid_types = {"TEXT", "LINK", "IMAGE", "CODE", "COLOR"}
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
                    icon = entry.get("icon") or "?뱛"
                    color = entry.get("color") or "#6366f1"
                    try:
                        new_id = self.db.add_collection(name, icon, color)
                        if new_id and legacy_id is not None:
                            collection_id_map[int(legacy_id)] = int(new_id)
                    except Exception as exc:
                        self.logger.debug("Collection import skipped for %s: %s", name, exc)

            imported = 0
            for item in data.get("items", []):
                content = item.get("content", "")
                ptype = item.get("type", "TEXT")
                if ptype not in valid_types:
                    ptype = "TEXT"
                if not content:
                    continue
                item_id = self.db.add_item(content, None, ptype)
                if not item_id:
                    continue
                imported += 1

                metadata = {}
                for key in ("tags", "note", "bookmark", "collection_id", "pinned", "pin_order", "use_count", "timestamp"):
                    if key in item:
                        metadata[key] = item.get(key)
                if collection_id_map and "collection_id" in metadata:
                    legacy_collection_id = metadata.get("collection_id")
                    try:
                        lookup_key = int(legacy_collection_id)
                    except (TypeError, ValueError):
                        lookup_key = legacy_collection_id
                    if lookup_key in collection_id_map:
                        metadata["collection_id"] = collection_id_map[lookup_key]
                if metadata and hasattr(self.db, "set_item_metadata"):
                    self.db.set_item_metadata(item_id, **metadata)
            return imported
        except Exception as exc:
            self.logger.error("JSON Import Error: %s", exc)
            return -1

    def import_csv(self, path):
        valid_types = {"TEXT", "LINK", "IMAGE", "CODE", "COLOR"}
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
                    if content:
                        self.db.add_item(content, None, ptype)
                        imported += 1
            return imported
        except Exception as exc:
            self.logger.error("CSV Import Error: %s", exc)
            return -1


__all__ = ["ExportImportManager", "DEFAULT_TYPE_ICONS"]
