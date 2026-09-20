"""Fail fast on release-workflow prerequisites.

Runs on every push (not only on tags) so the class of breakage that failed
the v10.8 Release is caught before a tag is pushed:

- PyInstaller window icon missing after a tree move (spec expects it next
  to ``smartclipboard.spec`` or at the repo root).
- GUI-subsystem smoke checks using ``&`` + ``$LASTEXITCODE`` (the call
  operator does not wait for windowed exes, so the exit code is stale).
- Version drift between Config, Cargo, package.json and tauri.conf.
- Stale hard-coded paths in the manual ``package-smoke`` workflow.

Standard library only: no Qt, no third-party packages.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional, Sequence

LEGACY_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = LEGACY_ROOT.parent.parent

SPEC_FILE = LEGACY_ROOT / "smartclipboard.spec"
MAIN_SCRIPT = LEGACY_ROOT / "클립모드 매니저.py"
ICON_CANDIDATES = (
    LEGACY_ROOT / "smartclipboard.ico",
    REPO_ROOT / "smartclipboard.ico",
)
PAYLOAD = LEGACY_ROOT / "smartclipboard_app" / "legacy_main_payload.marshal"
PAYLOAD_MANIFEST = (
    LEGACY_ROOT / "smartclipboard_app" / "legacy_main_payload.manifest.json"
)
CONFIG_FILE = LEGACY_ROOT / "smartclipboard_core" / "config.py"
CARGO_FILE = REPO_ROOT / "src-tauri" / "Cargo.toml"
PACKAGE_JSON = REPO_ROOT / "package.json"
TAURI_CONF = REPO_ROOT / "src-tauri" / "tauri.conf.json"
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"
PACKAGE_SMOKE_WORKFLOW = (
    REPO_ROOT / ".github" / "workflows" / "package-smoke.yml"
)


def short_version(version: str) -> str:
    """Normalize ``10.8.0`` to ``10.8`` so short tags compare equal."""
    return re.sub(r"(\.0)+$", "", version.strip())


def read_config_version(config_file: Path = CONFIG_FILE) -> str:
    match = re.search(
        r'VERSION\s*=\s*"([^"]+)"',
        config_file.read_text(encoding="utf-8"),
    )
    if match is None:
        raise ValueError(f"VERSION not found in {config_file}")
    return match.group(1)


def read_cargo_version(cargo_file: Path = CARGO_FILE) -> str:
    match = re.search(
        r'^version\s*=\s*"([^"]+)"',
        cargo_file.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if match is None:
        raise ValueError(f"version not found in {cargo_file}")
    return match.group(1)


def check_icon(candidates: Sequence[Path] = ICON_CANDIDATES) -> Optional[str]:
    if any(path.is_file() for path in candidates):
        return None
    searched = ", ".join(str(path) for path in candidates)
    return f"window icon not found; searched: {searched}"


def check_spec_references_icon(spec_file: Path = SPEC_FILE) -> Optional[str]:
    if not spec_file.is_file():
        return f"PyInstaller spec not found: {spec_file}"
    if "smartclipboard.ico" not in spec_file.read_text(encoding="utf-8"):
        return f"spec no longer references the window icon: {spec_file}"
    return None


def check_required_files(
    files: Sequence[Path] = (MAIN_SCRIPT, PAYLOAD, PAYLOAD_MANIFEST),
) -> Optional[str]:
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        return f"release input files missing: {', '.join(missing)}"
    return None


def check_versions(
    config_version: str,
    cargo_version: str,
    npm_version: str,
    tauri_version: str,
) -> Optional[str]:
    problems = []
    if short_version(config_version) != short_version(cargo_version):
        problems.append(
            f"Config.VERSION {config_version!r} != Cargo version {cargo_version!r}"
        )
    if short_version(config_version) != short_version(npm_version):
        problems.append(
            f"Config.VERSION {config_version!r} != package.json {npm_version!r}"
        )
    if tauri_version.strip() != cargo_version.strip():
        problems.append(
            f"tauri.conf.json {tauri_version!r} != Cargo version {cargo_version!r}"
        )
    if problems:
        return "version drift: " + "; ".join(problems)
    return None


def check_versions_from_tree() -> Optional[str]:
    try:
        config_version = read_config_version()
        cargo_version = read_cargo_version()
        npm_version = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))[
            "version"
        ]
        tauri_version = json.loads(TAURI_CONF.read_text(encoding="utf-8"))[
            "version"
        ]
    except (OSError, ValueError, KeyError) as exc:
        return f"cannot read version sources: {exc}"
    return check_versions(config_version, cargo_version, npm_version, tauri_version)


def check_release_workflow_smoke(
    workflow_file: Path = RELEASE_WORKFLOW,
) -> Optional[str]:
    """Windowed exes must be smoke-checked via Start-Process -Wait.

    ``& exe --smoke`` returns immediately for GUI-subsystem/windowed
    binaries, leaving ``$LASTEXITCODE`` unset or stale, which turns the
    ``if ($LASTEXITCODE -ne 0)`` guard into a false failure.
    """
    if not workflow_file.is_file():
        return f"workflow not found: {workflow_file}"
    problems = []
    for lineno, line in enumerate(
        workflow_file.read_text(encoding="utf-8").splitlines(), start=1
    ):
        stripped = line.strip()
        if stripped.startswith("&") and "--smoke" in stripped:
            problems.append(
                f"{workflow_file.name}:{lineno}: call-operator smoke check "
                "does not wait for windowed exes; use Start-Process -Wait"
            )
    text = workflow_file.read_text(encoding="utf-8")
    if "Start-Process" not in text:
        problems.append(
            f"{workflow_file.name}: no Start-Process smoke check found"
        )
    if problems:
        return "; ".join(problems)
    return None


def check_package_smoke_workdir(
    workflow_file: Path = PACKAGE_SMOKE_WORKFLOW,
) -> Optional[str]:
    if not workflow_file.is_file():
        return f"workflow not found: {workflow_file}"
    text = workflow_file.read_text(encoding="utf-8")
    if "working-directory: legacy/python" not in text:
        return (
            f"{workflow_file.name}: must run under legacy/python "
            "(requirements.txt / scripts / smartclipboard.spec moved there)"
        )
    return None


def collect_errors() -> list[str]:
    checks = [
        check_icon(),
        check_spec_references_icon(),
        check_required_files(),
        check_versions_from_tree(),
        check_release_workflow_smoke(),
        check_package_smoke_workdir(),
    ]
    return [error for error in checks if error is not None]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify release-workflow prerequisites."
    )
    parser.parse_args(argv)
    errors = collect_errors()
    if errors:
        print("release prerequisites: FAILED")
        for error in errors:
            print(f" - {error}")
        return 1
    print("release prerequisites: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
