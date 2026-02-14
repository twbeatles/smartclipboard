"""Extract MainWindow signal/slot connect snapshot for regression checks."""

from __future__ import annotations

import argparse
import pathlib


def build_snapshot(path: str | pathlib.Path) -> list[str]:
    path = pathlib.Path(path)
    lines = path.read_text(encoding="utf-8-sig").splitlines()

    class_start = None
    for idx, line in enumerate(lines, start=1):
        if line.startswith("class MainWindow("):
            class_start = idx
            break
    if class_start is None:
        return []

    class_end = len(lines)
    for idx in range(class_start, len(lines)):
        if idx > class_start and lines[idx - 1].startswith("if __name__ == "):
            class_end = idx - 1
            break

    snapshot = []
    for lineno in range(class_start, class_end + 1):
        line = lines[lineno - 1]
        if ".connect(" in line:
            snapshot.append(f"{lineno}:{line.strip()}")
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default="smartclipboard_app/legacy_main_src.py")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    snapshot = build_snapshot(args.target)
    output = pathlib.Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(snapshot) + ("\n" if snapshot else ""), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
