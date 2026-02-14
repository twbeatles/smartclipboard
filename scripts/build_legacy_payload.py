"""Build legacy marshal payload from restored source.

SmartClipboard ships `smartclipboard_app/legacy_main.py` as a loader that exec's
`legacy_main_payload.marshal`. To make code changes reflect in the EXE, we need
to recompile and re-marshal the restored legacy source.
"""

from __future__ import annotations

import argparse
import marshal
import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]


def build_payload(src_path: Path, out_path: Path) -> int:
    src_text = src_path.read_text(encoding="utf-8-sig")
    code = compile(src_text, filename=str(src_path).replace("\\", "/"), mode="exec", optimize=2)
    payload = marshal.dumps(code)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(payload)
    return len(payload)


def smoke_import_payload() -> None:
    # Ensure we execute the payload, not the restored source.
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    os.environ["SMARTCLIPBOARD_LEGACY_IMPL"] = "payload"
    __import__("smartclipboard_app.legacy_main")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build legacy_main_payload.marshal from legacy_main_src.py")
    parser.add_argument("--src", default="smartclipboard_app/legacy_main_src.py")
    parser.add_argument("--out", default="smartclipboard_app/legacy_main_payload.marshal")
    parser.add_argument("--smoke-import", action="store_true", help="Import legacy_main in payload mode after build")
    args = parser.parse_args(argv)

    src_path = Path(args.src)
    out_path = Path(args.out)

    if not src_path.exists():
        print(f"error: missing source: {src_path}", file=sys.stderr)
        return 2

    size = build_payload(src_path, out_path)
    print(f"built: {out_path} ({size} bytes)")

    if args.smoke_import:
        smoke_import_payload()
        print("smoke-import: ok")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
