"""Legacy main module loader.

The original source was packaged into the built executable as a marshalled
code object. This loader executes that payload to restore the full module
symbols while keeping the import path stable.
"""

from __future__ import annotations

import os
import marshal
from pathlib import Path

_impl = os.environ.get("SMARTCLIPBOARD_LEGACY_IMPL", "payload").strip().lower()

if _impl == "src":
    # Optional developer mode: load the restored legacy source for inspection
    # and refactor safety checks.
    from .legacy_main_src import *  # noqa: F401,F403
else:
    _payload_path = Path(__file__).with_name("legacy_main_payload.marshal")
    if not _payload_path.exists():
        raise FileNotFoundError(f"Missing legacy payload: {_payload_path}")

    _code = marshal.loads(_payload_path.read_bytes())
    exec(_code, globals())
