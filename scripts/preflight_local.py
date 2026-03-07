"""Run local preflight checks for SmartClipboard.

This script standardizes the minimum verification sequence before packaging:
1) rebuild payload + smoke import
2) py_compile guard
3) unit tests
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_step(cmd: list[str]) -> int:
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    if result.returncode != 0:
        print(f"step failed with code {result.returncode}")
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

    helper_dir = REPO_ROOT / "smartclipboard_app" / "ui" / "mainwindow_parts"
    if helper_dir.exists():
        targets.extend(
            str(path.relative_to(REPO_ROOT)).replace("\\", "/")
            for path in sorted(helper_dir.glob("*.py"))
        )

    return targets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SmartClipboard local preflight checks")
    parser.add_argument(
        "--skip-payload-build",
        action="store_true",
        help="Skip rebuilding legacy payload before checks",
    )
    args = parser.parse_args(argv)

    python = sys.executable

    steps: list[list[str]] = []
    if not args.skip_payload_build:
        steps.append(
            [
                python,
                "scripts/build_legacy_payload.py",
                "--src",
                "smartclipboard_app/legacy_main_src.py",
                "--out",
                "smartclipboard_app/legacy_main_payload.marshal",
                "--smoke-import",
            ]
        )

    steps.append([python, "-m", "py_compile", *compile_targets()])
    steps.append([python, "-m", "unittest", "discover", "-s", "tests", "-v"])

    for step in steps:
        code = run_step(step)
        if code != 0:
            return code

    print("preflight: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
