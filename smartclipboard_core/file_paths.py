from __future__ import annotations

import os
from collections.abc import Iterable
from urllib.parse import unquote, urlparse


def normalize_local_file_path(raw_path: str | None) -> str:
    value = str(raw_path or "").strip()
    if not value:
        return ""

    drive, _tail = os.path.splitdrive(value)
    has_windows_drive = bool(drive) and drive.endswith(":")

    parsed = urlparse(value)
    if parsed.scheme and not has_windows_drive:
        if parsed.scheme.lower() != "file":
            return ""
        if parsed.netloc:
            value = f"//{parsed.netloc}{unquote(parsed.path or '')}"
        else:
            value = unquote(parsed.path or "")
        if os.name == "nt" and value.startswith("/") and len(value) > 2 and value[2] == ":":
            value = value[1:]

    normalized = os.path.normpath(os.path.abspath(value))
    return normalized if normalized else ""


def normalize_local_file_paths(paths: Iterable[str | None]) -> list[str]:
    normalized_paths: list[str] = []
    seen: set[str] = set()
    for raw_path in paths:
        normalized = normalize_local_file_path(raw_path)
        if not normalized:
            continue
        dedupe_key = os.path.normcase(normalized)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized_paths.append(normalized)
    return normalized_paths


def file_paths_from_content(content: str | None) -> list[str]:
    if not content:
        return []
    return normalize_local_file_paths(str(content).splitlines())


def file_content_from_paths(paths: Iterable[str | None]) -> str:
    return "\n".join(normalize_local_file_paths(paths))


def file_duplicate_signature(paths: Iterable[str | None]) -> tuple[str, ...]:
    normalized_paths = normalize_local_file_paths(paths)
    return tuple(sorted(os.path.normcase(path) for path in normalized_paths))


def describe_file_paths(paths: Iterable[str | None]) -> str:
    normalized_paths = normalize_local_file_paths(paths)
    if not normalized_paths:
        return "[파일 항목]"

    first_path = normalized_paths[0].rstrip("\\/")
    first_label = os.path.basename(first_path) or first_path or normalized_paths[0]
    if len(normalized_paths) == 1:
        return first_label
    return f"{first_label} 외 {len(normalized_paths) - 1}개"


__all__ = [
    "describe_file_paths",
    "file_content_from_paths",
    "file_duplicate_signature",
    "file_paths_from_content",
    "normalize_local_file_path",
    "normalize_local_file_paths",
]
