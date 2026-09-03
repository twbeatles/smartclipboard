import pathlib
import unittest

from scripts.refactor_signal_snapshot import build_snapshot, discover_helper_paths


class SignalSnapshotTests(unittest.TestCase):
    def test_mainwindow_signal_connections_snapshot(self):
        baseline_path = pathlib.Path("tests/baseline/mainwindow_signal_connects.txt")
        baseline = baseline_path.read_text(encoding="utf-8").splitlines()
        helper_paths = discover_helper_paths()
        current = build_snapshot("smartclipboard_app/legacy_main_src.py", helper_paths=[*helper_paths])
        self.assertEqual(current, baseline)


if __name__ == "__main__":
    unittest.main(verbosity=2)

