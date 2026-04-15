"""CSV import/export helpers."""

from __future__ import annotations

from smartclipboard_core.file_paths import file_content_from_paths, file_paths_from_content

from .reports import append_warning


def export_csv_rows(writer, items, report: dict, logger):
    writer.writerow(["내용", "유형", "시간", "고정", "사용횟수"])
    for item in items:
        _pid, content, item_type, timestamp, pinned, use_count, _pin_order = item
        if item_type == "IMAGE":
            export_content = content or "[이미지 항목 - 바이너리 제외]"
            append_warning(report, "CSV export는 이미지 바이너리를 제외하고 placeholder만 저장합니다.")
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


def import_csv_row_locked(db, cursor, row: list[str], report: dict, valid_item_types: set[str], normalize_timestamp):
    if len(row) < 2:
        report["skipped"] += 1
        return

    content, item_type = row[0], row[1]
    if item_type not in valid_item_types:
        item_type = "TEXT"

    if item_type == "IMAGE":
        report["skipped"] += 1
        append_warning(report, "CSV import는 IMAGE 바이너리를 복원하지 않아 이미지 행을 건너뜁니다.")
        return

    if item_type == "FILE":
        file_paths = file_paths_from_content(content)
        if not file_paths:
            report["skipped"] += 1
            append_warning(report, "CSV의 FILE 행 중 유효한 경로가 없는 항목을 건너뛰었습니다.")
            return
        content = file_content_from_paths(file_paths)

    if not content:
        report["skipped"] += 1
        return

    timestamp = row[2] if len(row) > 2 else None
    normalized_timestamp = normalize_timestamp(timestamp)
    item_id, _updated_existing = db._add_item_locked(cursor, content, None, item_type, timestamp=normalized_timestamp)
    if not item_id:
        report["skipped"] += 1
        return
    report["imported"] += 1


__all__ = ["export_csv_rows", "import_csv_row_locked"]
