"""Legacy main module loader.

The original source was packaged into the built executable as a marshalled
code object. This loader executes that payload to restore the full module
symbols while keeping the import path stable.
"""

from __future__ import annotations

import importlib
import logging
import marshal
import os
from pathlib import Path

logger = logging.getLogger(__name__)

LEGACY_IMPL_REQUESTED = os.environ.get("SMARTCLIPBOARD_LEGACY_IMPL", "payload").strip().lower() or "payload"
LEGACY_IMPL_ACTIVE = "unknown"
LEGACY_IMPL_FALLBACK_REASON: str | None = None


def _load_src_impl(reason: str | None = None) -> None:
    global LEGACY_IMPL_ACTIVE
    global LEGACY_IMPL_FALLBACK_REASON

    if reason:
        LEGACY_IMPL_FALLBACK_REASON = reason
        logger.warning("legacy_main payload load failed, falling back to src implementation: %s", reason)

    src_module = importlib.import_module(".legacy_main_src", __package__)
    exports = getattr(src_module, "__all__", None)
    if exports:
        for name in exports:
            globals()[name] = getattr(src_module, name)
    else:
        for name, value in src_module.__dict__.items():
            if name.startswith("_"):
                continue
            globals()[name] = value

    LEGACY_IMPL_ACTIVE = "src"


if LEGACY_IMPL_REQUESTED == "src":
    _load_src_impl()
else:
    try:
        payload_path = Path(__file__).with_name("legacy_main_payload.marshal")
        if not payload_path.exists():
            raise FileNotFoundError(f"Missing legacy payload: {payload_path}")

        code = marshal.loads(payload_path.read_bytes())
        exec(code, globals())
        LEGACY_IMPL_ACTIVE = "payload"
    except Exception as payload_exc:
        fallback_reason = f"{type(payload_exc).__name__}: {payload_exc}"
        try:
            _load_src_impl(reason=fallback_reason)
        except Exception as src_exc:
            raise RuntimeError("legacy_main payload failed and src fallback also failed") from src_exc
