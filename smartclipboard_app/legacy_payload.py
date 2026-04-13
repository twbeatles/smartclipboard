"""Helpers for legacy marshal payload metadata and validation."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


PAYLOAD_MANIFEST_VERSION = 1
DEFAULT_PAYLOAD_FILENAME = "legacy_main_payload.marshal"
DEFAULT_MANIFEST_FILENAME = "legacy_main_payload.manifest.json"


def compute_source_sha256(src_path: Path) -> str:
    return hashlib.sha256(src_path.read_bytes()).hexdigest()


def build_payload_manifest(src_path: Path, payload_path: Path | None = None) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "manifest_version": PAYLOAD_MANIFEST_VERSION,
        "python_minor": f"{sys.version_info.major}.{sys.version_info.minor}",
        "python_implementation": sys.implementation.name,
        "source_name": src_path.name,
        "source_sha256": compute_source_sha256(src_path),
    }
    if payload_path is not None and payload_path.exists():
        manifest["payload_name"] = payload_path.name
        manifest["payload_size"] = payload_path.stat().st_size
    return manifest


def write_payload_manifest(
    manifest_path: Path,
    src_path: Path,
    payload_path: Path | None = None,
) -> dict[str, Any]:
    manifest = build_payload_manifest(src_path=src_path, payload_path=payload_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def load_payload_manifest(manifest_path: Path) -> dict[str, Any]:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def validate_payload_manifest(
    manifest: dict[str, Any],
    src_path: Path | None = None,
) -> tuple[bool, str | None]:
    if not isinstance(manifest, dict):
        return False, "payload manifest is not an object"
    if manifest.get("manifest_version") != PAYLOAD_MANIFEST_VERSION:
        return False, "payload manifest version mismatch"

    expected_minor = str(manifest.get("python_minor") or "").strip()
    runtime_minor = f"{sys.version_info.major}.{sys.version_info.minor}"
    if expected_minor != runtime_minor:
        return False, f"payload python minor mismatch: manifest={expected_minor or 'missing'}, runtime={runtime_minor}"

    expected_impl = str(manifest.get("python_implementation") or "").strip()
    runtime_impl = sys.implementation.name
    if expected_impl and expected_impl != runtime_impl:
        return False, f"payload python implementation mismatch: manifest={expected_impl}, runtime={runtime_impl}"

    expected_hash = str(manifest.get("source_sha256") or "").strip()
    if src_path is not None:
        if not src_path.exists():
            return False, f"legacy source file missing for validation: {src_path}"
        runtime_hash = compute_source_sha256(src_path)
        if not expected_hash:
            return False, "payload source hash missing from manifest"
        if expected_hash != runtime_hash:
            return False, "payload source hash mismatch"

    return True, None


__all__ = [
    "DEFAULT_MANIFEST_FILENAME",
    "DEFAULT_PAYLOAD_FILENAME",
    "PAYLOAD_MANIFEST_VERSION",
    "build_payload_manifest",
    "compute_source_sha256",
    "load_payload_manifest",
    "validate_payload_manifest",
    "write_payload_manifest",
]
