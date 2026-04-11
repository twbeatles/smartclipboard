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


def partition_existing_file_paths(
    paths: Iterable[str | None],
    os_module=os,
) -> tuple[list[str], list[str]]:
    normalized_paths = normalize_local_file_paths(paths)
    available_paths = [path for path in normalized_paths if os_module.path.exists(path)]
    missing_paths = [path for path in normalized_paths if not os_module.path.exists(path)]
    return available_paths, missing_paths


def describe_file_paths_with_status(paths: Iterable[str | None], os_module=os) -> str:
    normalized_paths = normalize_local_file_paths(paths)
    base_label = describe_file_paths(normalized_paths)
    if not normalized_paths:
        return base_label

    available_paths, missing_paths = partition_existing_file_paths(normalized_paths, os_module=os_module)
    if not missing_paths:
        return base_label
    if available_paths:
        return f"[누락 {len(missing_paths)}] {base_label}"
    return f"[모두 누락] {base_label}"


def build_file_paths_tooltip(paths: Iterable[str | None], os_module=os) -> str:
    normalized_paths = normalize_local_file_paths(paths)
    if not normalized_paths:
        return "[파일 항목]"

    available_paths, missing_paths = partition_existing_file_paths(normalized_paths, os_module=os_module)
    lines: list[str] = []
    if missing_paths:
        if available_paths:
            lines.append(f"⚠️ 일부 경로를 찾을 수 없습니다. 사용 가능 {len(available_paths)}개, 누락 {len(missing_paths)}개")
        else:
            lines.append(f"⚠️ 저장된 경로를 모두 찾을 수 없습니다. 총 {len(missing_paths)}개 누락")
        lines.append("")

    lines.extend(normalized_paths[:20])
    if len(normalized_paths) > 20:
        lines.append(f"... 외 {len(normalized_paths) - 20}개")
    return "\n".join(lines)


def build_file_paths_detail_text(paths: Iterable[str | None], os_module=os) -> str:
    normalized_paths = normalize_local_file_paths(paths)
    if not normalized_paths:
        return "[파일 항목]"

    available_paths, missing_paths = partition_existing_file_paths(normalized_paths, os_module=os_module)
    lines: list[str] = []
    if missing_paths:
        if available_paths:
            lines.append(f"⚠️ 일부 파일/폴더를 찾을 수 없습니다. 사용 가능 {len(available_paths)}개, 누락 {len(missing_paths)}개")
        else:
            lines.append(f"⚠️ 저장된 파일/폴더 경로를 모두 찾을 수 없습니다. 총 {len(missing_paths)}개 누락")
        lines.append("")

    lines.extend(normalized_paths)
    return "\n".join(lines)


__all__ = [
    "build_file_paths_detail_text",
    "build_file_paths_tooltip",
    "describe_file_paths",
    "describe_file_paths_with_status",
    "file_content_from_paths",
    "file_duplicate_signature",
    "file_paths_from_content",
    "normalize_local_file_path",
    "normalize_local_file_paths",
    "partition_existing_file_paths",
]
