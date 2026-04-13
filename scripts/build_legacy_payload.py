"""Build legacy marshal payload from restored source.

SmartClipboard ships `smartclipboard_app/legacy_main.py` as a loader that exec's
`legacy_main_payload.marshal`. To make code changes reflect in the EXE, we need
to recompile and re-marshal the restored legacy source.
"""

from __future__ import annotations

import argparse
import importlib
import marshal
import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from smartclipboard_app.legacy_payload import (
    DEFAULT_MANIFEST_FILENAME,
    load_payload_manifest,
    validate_payload_manifest,
    write_payload_manifest,
)


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
    sys.modules.pop("smartclipboard_app.legacy_main", None)
    module = importlib.import_module("smartclipboard_app.legacy_main")
    module = importlib.reload(module)
    if getattr(module, "LEGACY_IMPL_ACTIVE", None) != "payload":
        reason = getattr(module, "LEGACY_IMPL_FALLBACK_REASON", None) or "unknown payload fallback reason"
        raise RuntimeError(f"payload smoke import did not stay in payload mode: {reason}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build legacy_main_payload.marshal from legacy_main_src.py")
    parser.add_argument("--src", default="smartclipboard_app/legacy_main_src.py")
    parser.add_argument("--out", default="smartclipboard_app/legacy_main_payload.marshal")
    parser.add_argument(
        "--manifest-out",
        default="",
        help=f"Sidecar manifest output path (default: alongside payload as {DEFAULT_MANIFEST_FILENAME})",
    )
    parser.add_argument("--smoke-import", action="store_true", help="Import legacy_main in payload mode after build")
    parser.add_argument(
        "--smoke-import-only",
        action="store_true",
        help="Skip rebuilding and only validate/import the current payload in payload mode",
    )
    args = parser.parse_args(argv)

    src_path = Path(args.src)
    out_path = Path(args.out)
    manifest_path = Path(args.manifest_out) if args.manifest_out else out_path.with_name(DEFAULT_MANIFEST_FILENAME)

    if not src_path.exists():
        print(f"error: missing source: {src_path}", file=sys.stderr)
        return 2

    if not args.smoke_import_only:
        size = build_payload(src_path, out_path)
        manifest = write_payload_manifest(manifest_path=manifest_path, src_path=src_path, payload_path=out_path)
        print(f"built: {out_path} ({size} bytes)")
        print(f"manifest: {manifest_path} (python {manifest['python_minor']}, sha256 {manifest['source_sha256'][:12]}...)")
    else:
        if not out_path.exists():
            print(f"error: missing payload: {out_path}", file=sys.stderr)
            return 2
        if not manifest_path.exists():
            print(f"error: missing payload manifest: {manifest_path}", file=sys.stderr)
            return 2
        manifest = load_payload_manifest(manifest_path)
        ok, reason = validate_payload_manifest(manifest, src_path=src_path)
        if not ok:
            print(f"error: payload manifest validation failed: {reason}", file=sys.stderr)
            return 2
        print(f"validated: {out_path}")
        print(f"manifest: {manifest_path} (python {manifest['python_minor']}, sha256 {manifest['source_sha256'][:12]}...)")

    if args.smoke_import or args.smoke_import_only:
        smoke_import_payload()
        print("smoke-import: ok")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
