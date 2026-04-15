"""Markdown export helpers."""

from __future__ import annotations

import datetime

from smartclipboard_core.file_paths import file_paths_from_content

from .reports import append_warning


def export_markdown_document(fh, items, type_icons, report: dict):
    fh.write("# SmartClipboard Pro 히스토리\n\n")
    fh.write(f"내보낸 날짜: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    fh.write("---\n\n")

    for item in items:
        _pid, content, item_type, timestamp, pinned, _use_count, _pin_order = item
        pin_mark = "[PIN] " if pinned else ""
        type_icon = type_icons.get(item_type, "[T]")
        fh.write(f"### {pin_mark}{type_icon} {timestamp}\n\n")
        if item_type == "IMAGE":
            placeholder = content or "[이미지 항목]"
            fh.write(f"{placeholder}\n\n")
            fh.write("> 이미지 바이너리 데이터는 Markdown 내보내기에서 제외됩니다.\n\n")
            append_warning(report, "Markdown export는 이미지 바이너리를 제외합니다.")
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


__all__ = ["export_markdown_document"]
