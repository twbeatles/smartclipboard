import inspect
import json
import pathlib
import unittest

from scripts.refactor_symbol_inventory import build_inventory
from smartclipboard_core.database import ClipboardDB


class PublicSurfaceTests(unittest.TestCase):
    def test_clipboarddb_public_methods_match_baseline(self):
        baseline_path = pathlib.Path("tests/baseline/clipboarddb_public_methods.txt")
        baseline = [line.strip() for line in baseline_path.read_text(encoding="utf-8").splitlines() if line.strip()]

        current = sorted(
            {
                name
                for name, fn in inspect.getmembers(ClipboardDB, inspect.isfunction)
                if not name.startswith("_")
            }
        )
        self.assertEqual(current, baseline)

    def test_mainwindow_signatures_match_symbol_inventory_baseline(self):
        baseline_inventory_path = pathlib.Path("tests/baseline/symbol_inventory_v10_6.json")
        baseline_inventory = json.loads(baseline_inventory_path.read_text(encoding="utf-8"))
        current_inventory = build_inventory("smartclipboard_app/legacy_main_src.py")

        def _methods(inv: dict) -> dict[str, dict]:
            classes = {c["name"]: c for c in inv["classes"]}
            main_window = classes.get("MainWindow")
            self.assertIsNotNone(main_window, "MainWindow missing in inventory")
            return {m["name"]: m["signature"] for m in main_window["methods"]}

        self.assertEqual(_methods(current_inventory), _methods(baseline_inventory))


if __name__ == "__main__":
    unittest.main(verbosity=2)
