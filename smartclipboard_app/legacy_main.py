"""Legacy main module loader.

The original source was packaged into the built executable as a marshalled
code object. This loader executes that payload to restore the full module
symbols while keeping the import path stable.
"""

from __future__ import annotations

import marshal
from pathlib import Path

_payload_path = Path(__file__).with_name("legacy_main_payload.marshal")
if not _payload_path.exists():
    raise FileNotFoundError(f"Missing legacy payload: {_payload_path}")

_code = marshal.loads(_payload_path.read_bytes())
exec(_code, globals())
