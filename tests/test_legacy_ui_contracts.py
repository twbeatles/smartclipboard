import pathlib
import re
import unittest


LEGACY_SRC = pathlib.Path("smartclipboard_app/legacy_main_src.py")


class LegacyUiContractsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = LEGACY_SRC.read_text(encoding="utf-8-sig")

    def _method_block(self, method_name: str) -> str:
        pattern = rf"^    def {re.escape(method_name)}\(self[^\n]*\):\n((?:        .*\n)*)"
        match = re.search(pattern, self.source, flags=re.MULTILINE)
        self.assertIsNotNone(match, f"missing method: {method_name}")
        return match.group(1)

    def test_show_toast_calls_are_not_bound_to_mainwindow(self):
        self.assertNotIn("self.show_toast(", self.source)
        self.assertIn("ToastNotification.show_toast(self,", self.source)

    def test_trash_dialog_supports_extended_selection(self):
        self.assertIn(
            "self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)",
            self.source,
        )

    def test_update_always_on_top_preserves_visibility(self):
        block = self._method_block("update_always_on_top")
        self.assertIn("was_visible = self.isVisible()", block)
        self.assertIn("if was_visible:", block)
        self.assertIn("self.show()", block)


if __name__ == "__main__":
    unittest.main(verbosity=2)
