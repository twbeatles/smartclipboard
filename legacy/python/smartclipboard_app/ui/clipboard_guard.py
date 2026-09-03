"""Helpers for clipboard writes initiated by the application itself."""

from __future__ import annotations

import os

from PyQt6.QtCore import QMimeData, QUrl

from smartclipboard_core.file_paths import (
    file_paths_from_content,
    normalize_local_file_paths,
    partition_existing_file_paths,
)


def mark_internal_copy(parent: object | None) -> None:
    if parent is None or not hasattr(parent, "is_internal_copy"):
        return
    try:
        setattr(parent, "is_internal_copy", True)
    except Exception:
        pass


def extract_local_file_paths(mime_data) -> list[str]:
    if mime_data is None or not hasattr(mime_data, "hasUrls") or not mime_data.hasUrls():
        return []

    raw_paths: list[str] = []
    for url in mime_data.urls():
        try:
            if url.isLocalFile():
                raw_paths.append(url.toLocalFile())
            elif str(url.scheme()).lower() == "file":
                raw_paths.append(url.toString())
        except Exception:
            continue
    return normalize_local_file_paths(raw_paths)


def restore_file_clipboard(
    parent: object | None,
    clipboard,
    file_paths,
    qmime_data_cls=QMimeData,
    qurl_cls=QUrl,
    os_module=os,
) -> dict[str, object]:
    normalized_paths = normalize_local_file_paths(file_paths)
    available_paths, missing_paths = partition_existing_file_paths(normalized_paths, os_module=os_module)

    if clipboard is None or not hasattr(clipboard, "setMimeData") or not available_paths:
        return {
            "applied": False,
            "available_paths": available_paths,
            "missing_paths": missing_paths,
        }

    mime_data = qmime_data_cls()
    mime_data.setUrls([qurl_cls.fromLocalFile(path) for path in available_paths])
    mark_internal_copy(parent)
    clipboard.setMimeData(mime_data)
    return {
        "applied": True,
        "available_paths": available_paths,
        "missing_paths": missing_paths,
    }


__all__ = [
    "extract_local_file_paths",
    "file_paths_from_content",
    "mark_internal_copy",
    "normalize_local_file_paths",
    "restore_file_clipboard",
]
