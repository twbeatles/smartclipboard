"""Extract MainWindow signal/slot connect snapshot for regression checks."""

from __future__ import annotations

import argparse
import pathlib


def _normalize_connect_line(line: str) -> str:
    return " ".join(line.strip().split())


def _find_mainwindow_bounds(lines: list[str]) -> tuple[int, int] | None:
    class_start = 0
    for idx, line in enumerate(lines, start=1):
        if line.startswith("class MainWindow("):
            class_start = idx
            break
    if class_start == 0:
        return None

    class_end = len(lines)
    for idx in range(class_start, len(lines)):
        if idx > class_start and lines[idx - 1].startswith("if __name__ == "):
            class_end = idx - 1
            break
    return class_start, class_end


def _collect_connect_lines(lines: list[str], start: int = 1, end: int | None = None) -> list[str]:
    scan_end = len(lines) if end is None else end
    snapshot: list[str] = []
    for lineno in range(start, scan_end + 1):
        line = lines[lineno - 1]
        if ".connect(" in line:
            snapshot.append(_normalize_connect_line(line))
    return snapshot


def _discover_helper_paths(target: pathlib.Path) -> list[pathlib.Path]:
    helper_dir = target.parent / "ui" / "mainwindow_parts"
    if not helper_dir.exists():
        return []
    return sorted(p for p in helper_dir.glob("*.py") if p.name != "__init__.py")


def build_snapshot(
    path: str | pathlib.Path,
    helper_paths: list[str | pathlib.Path] | None = None,
) -> list[str]:
    target = pathlib.Path(path)
    target_lines = target.read_text(encoding="utf-8-sig").splitlines()

    bounds = _find_mainwindow_bounds(target_lines)
    if bounds is None:
        return []

    class_start, class_end = bounds
    snapshot = _collect_connect_lines(target_lines, start=class_start, end=class_end)

    helpers = _discover_helper_paths(target) if helper_paths is None else [pathlib.Path(p) for p in helper_paths]
    target_resolved = target.resolve()
    for helper_path in helpers:
        if helper_path.resolve() == target_resolved:
            continue
        helper_lines = helper_path.read_text(encoding="utf-8-sig").splitlines()
        snapshot.extend(_collect_connect_lines(helper_lines))

    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default="smartclipboard_app/legacy_main_src.py")
    parser.add_argument(
        "--helper-path",
        action="append",
        default=None,
        help="Additional helper module path to include (repeatable). If omitted, auto-discovers mainwindow_parts/*.py.",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    snapshot = build_snapshot(args.target, helper_paths=args.helper_path)
    output = pathlib.Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(snapshot) + ("\n" if snapshot else ""), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
