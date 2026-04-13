"""Run local preflight checks for SmartClipboard.

This script standardizes the minimum verification sequence before packaging:
1) rebuild payload + smoke import
2) py_compile guard
3) unit tests
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OPTIONAL_DEPENDENCIES = [
    ("cryptography", "cryptography"),
    ("requests", "requests"),
    ("bs4", "beautifulsoup4"),
    ("qrcode", "qrcode"),
    ("PIL", "pillow"),
]


def run_step(label: str, cmd: list[str]) -> int:
    print(f">>> {label}")
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    if result.returncode != 0:
        print(f"step '{label}' failed with code {result.returncode}")
    return result.returncode


def compile_targets() -> list[str]:
    targets = [
        "클립모드 매니저.py",
        "smartclipboard_app/bootstrap.py",
        "smartclipboard_app/legacy_main.py",
        "smartclipboard_app/legacy_main_src.py",
        "smartclipboard_core/database.py",
        "smartclipboard_core/actions.py",
        "smartclipboard_core/worker.py",
    ]

    ui_dir = REPO_ROOT / "smartclipboard_app" / "ui"
    if ui_dir.exists():
        targets.extend(
            str(path.relative_to(REPO_ROOT)).replace("\\", "/")
            for path in sorted(ui_dir.glob("*.py"))
        )

    helper_dir = REPO_ROOT / "smartclipboard_app" / "ui" / "mainwindow_parts"
    if helper_dir.exists():
        targets.extend(
            str(path.relative_to(REPO_ROOT)).replace("\\", "/")
            for path in sorted(helper_dir.glob("*.py"))
        )

    db_parts_dir = REPO_ROOT / "smartclipboard_core" / "db_parts"
    if db_parts_dir.exists():
        targets.extend(
            str(path.relative_to(REPO_ROOT)).replace("\\", "/")
            for path in sorted(db_parts_dir.glob("*.py"))
        )

    return targets


def check_optional_dependencies(strict: bool) -> int:
    print(">>> optional dependency check")
    missing: list[tuple[str, str]] = []
    for module_name, package_name in OPTIONAL_DEPENDENCIES:
        if importlib.util.find_spec(module_name) is None:
            missing.append((module_name, package_name))

    if not missing:
        print("all optional dependencies available")
        return 0

    print("missing optional dependencies detected:")
    for module_name, package_name in missing:
        print(f" - module '{module_name}' (install via: pip install {package_name})")
    print("note: local feature coverage or tests may be reduced when these are missing")
    if strict:
        print("strict optional dependency mode enabled; failing preflight")
        return 1
    print("continuing because strict optional dependency mode is off")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SmartClipboard local preflight checks")
    parser.add_argument(
        "--skip-payload-build",
        action="store_true",
        help="Skip rebuilding legacy payload before checks",
    )
    parser.add_argument(
        "--strict-optional-deps",
        action="store_true",
        help="Fail when optional runtime dependencies are missing",
    )
    args = parser.parse_args(argv)

    python = sys.executable

    optional_dep_code = check_optional_dependencies(strict=args.strict_optional_deps)
    if optional_dep_code != 0:
        return optional_dep_code

    print(f">>> runtime python")
    print(f"python: {sys.version.split()[0]}")
    print(f"executable: {sys.executable}")

    steps: list[tuple[str, list[str]]] = []
    if not args.skip_payload_build:
        steps.append(
            (
                "payload build",
                [
                    python,
                    "scripts/build_legacy_payload.py",
                    "--src",
                    "smartclipboard_app/legacy_main_src.py",
                    "--out",
                    "smartclipboard_app/legacy_main_payload.marshal",
                ],
            )
        )

    steps.append(
        (
            "payload smoke import",
            [
                python,
                "scripts/build_legacy_payload.py",
                "--src",
                "smartclipboard_app/legacy_main_src.py",
                "--out",
                "smartclipboard_app/legacy_main_payload.marshal",
                "--smoke-import-only",
            ],
        )
    )
    steps.append(("py_compile", [python, "-m", "py_compile", *compile_targets()]))
    steps.append(("unittest", [python, "-m", "unittest", "discover", "-s", "tests", "-v"]))

    for label, step in steps:
        code = run_step(label, step)
        if code != 0:
            return code

    print("preflight: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
