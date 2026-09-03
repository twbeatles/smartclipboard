from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.apply_update import _wait_for_parent, main


class ApplyUpdateScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_wait_for_parent_rejects_non_positive_pid(self) -> None:
        with self.assertRaises(ValueError):
            _wait_for_parent(0)
        with self.assertRaises(ValueError):
            _wait_for_parent(-1)

    def test_apply_update_failure_writes_result_file(self) -> None:
        result_file = self.tmp_path / "result.json"
        exit_code = main(
            [
                "--target",
                str(self.tmp_path / "missing.exe"),
                "--staged",
                str(self.tmp_path / "staged.exe"),
                "--backup",
                str(self.tmp_path / "backup.bak"),
                "--parent-pid",
                "0",
                "--expected-sha256",
                "0" * 64,
                "--expected-size",
                "1",
                "--result-file",
                str(result_file),
            ]
        )

        self.assertEqual(exit_code, 1)
        self.assertTrue(result_file.exists())
        content = result_file.read_text(encoding="utf-8")
        self.assertIn('"status": "failed"', content)


if __name__ == "__main__":
    unittest.main()
