import pathlib
import unittest

from scripts.refactor_signal_snapshot import build_snapshot


class SignalSnapshotTests(unittest.TestCase):
    def test_mainwindow_signal_connections_snapshot(self):
        baseline_path = pathlib.Path("tests/baseline/mainwindow_signal_connects.txt")
        baseline = baseline_path.read_text(encoding="utf-8").splitlines()
        current = build_snapshot("smartclipboard_app/legacy_main.py")
        self.assertEqual(current, baseline)


if __name__ == "__main__":
    unittest.main(verbosity=2)

