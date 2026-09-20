from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from smartclipboard_app.bootstrap import run
from smartclipboard_core.config import Config


class BootstrapSmokeTests(unittest.TestCase):
    def test_smoke_returns_zero(self) -> None:
        self.assertEqual(run(["SmartClipboard", "--smoke"]), 0)

    def test_smoke_writes_marker_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "smoke.txt"
            code = run(
                ["SmartClipboard", "--smoke", "--smoke-file", str(marker)]
            )
            self.assertEqual(code, 0)
            self.assertEqual(
                marker.read_text(encoding="utf-8").strip(),
                f"ok {Config.VERSION}",
            )


if __name__ == "__main__":
    unittest.main()
