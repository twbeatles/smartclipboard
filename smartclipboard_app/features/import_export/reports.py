"""Report helpers for import/export flows."""

from __future__ import annotations

from typing import Any


def new_export_report(fmt: str, path: str) -> dict[str, Any]:
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


def new_import_report(fmt: str, path: str) -> dict[str, Any]:
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


def append_warning(report: dict[str, Any], message: str) -> None:
    warnings = report.setdefault("warnings", [])
    if message not in warnings:
        warnings.append(message)


__all__ = ["new_export_report", "new_import_report", "append_warning"]
