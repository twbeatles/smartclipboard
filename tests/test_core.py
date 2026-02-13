import datetime
import os
import tempfile
import unittest

from PyQt6.QtCore import QCoreApplication

from smartclipboard_core.actions import ClipboardActionManager, extract_first_url
from smartclipboard_core.database import ClipboardDB


class FakeActionDB:
    def __init__(self, actions):
        self._actions = actions
        self.updated_titles = []

    def get_clipboard_actions(self):
        return self._actions

    def update_url_title(self, item_id, title):
        self.updated_titles.append((item_id, title))
        return True


class CoreActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_extract_first_url(self):
        text = "prefix https://example.com/path?q=1 suffix"
        self.assertEqual(extract_first_url(text), "https://example.com/path?q=1")

    def test_fetch_title_uses_extracted_url(self):
        db = FakeActionDB([(1, "fetch", r"https?://", "fetch_title", "{}", 1, 0)])
        manager = ClipboardActionManager(db)
        captured = {}

        def fake_fetch(url, item_id, action_name):
            captured["url"] = url
            captured["item_id"] = item_id
            captured["action_name"] = action_name

        manager.fetch_url_title_async = fake_fetch
        results = manager.process("링크: https://example.com/a?b=1 내용", item_id=7)

        self.assertEqual(results, [])
        self.assertEqual(captured["url"], "https://example.com/a?b=1")
        self.assertEqual(captured["item_id"], 7)

    def test_fetch_title_without_url_returns_notify(self):
        db = FakeActionDB([(1, "fetch", r".*", "fetch_title", "{}", 1, 0)])
        manager = ClipboardActionManager(db)
        results = manager.process("url 없음", item_id=11)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][1]["type"], "notify")
        self.assertIn("URL", results[0][1]["message"])


class CoreDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "clipboard_history_v6.db")
        self.db = ClipboardDB(db_file=self.db_path, app_dir=self.tmpdir.name)

    def tearDown(self):
        self.db.close()
        self.tmpdir.cleanup()

    def test_cleanup_respects_max_history_and_keeps_pinned(self):
        self.db.set_setting("max_history", 10)

        pinned_ids = []
        for i in range(2):
            item_id = self.db.add_item(f"pinned-{i}", None, "TEXT")
            pinned_ids.append(item_id)
            self.db.toggle_pin(item_id)

        for i in range(30):
            self.db.add_item(f"normal-{i}", None, "TEXT")

        self.db.cleanup()

        with self.db.lock:
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM history WHERE pinned = 0")
            unpinned_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM history WHERE pinned = 1")
            pinned_count = cursor.fetchone()[0]

        self.assertLessEqual(unpinned_count, 10)
        self.assertEqual(pinned_count, 2)

    def test_backup_db_creates_target_file(self):
        target_file = os.path.join(self.tmpdir.name, "manual_backup.db")
        ok = self.db.backup_db(target_path=target_file, force=True)

        self.assertTrue(ok)
        self.assertTrue(os.path.exists(target_file))

    def test_update_pin_orders_success(self):
        ids = []
        for i in range(3):
            item_id = self.db.add_item(f"pin-order-{i}", None, "TEXT")
            self.db.toggle_pin(item_id)
            ids.append(item_id)

        expected_order = [ids[2], ids[0], ids[1]]
        self.assertTrue(self.db.update_pin_orders(expected_order))

        pinned_items = self.db.get_items("", "📌 고정")
        self.assertEqual([row[0] for row in pinned_items], expected_order)

    def test_update_pin_orders_rollback_on_invalid_item(self):
        pinned_ids = []
        for i in range(2):
            item_id = self.db.add_item(f"rollback-pin-{i}", None, "TEXT")
            self.db.toggle_pin(item_id)
            pinned_ids.append(item_id)

        invalid_unpinned_id = self.db.add_item("rollback-normal", None, "TEXT")

        with self.db.lock:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT id, pin_order FROM history WHERE id IN (?, ?) ORDER BY id",
                (pinned_ids[0], pinned_ids[1]),
            )
            before = dict(cursor.fetchall())

        ok = self.db.update_pin_orders([pinned_ids[1], invalid_unpinned_id, pinned_ids[0]])
        self.assertFalse(ok)

        with self.db.lock:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT id, pin_order FROM history WHERE id IN (?, ?) ORDER BY id",
                (pinned_ids[0], pinned_ids[1]),
            )
            after = dict(cursor.fetchall())
        self.assertEqual(before, after)

    def test_get_items_by_tag_exact_match(self):
        only_a_id = self.db.add_item("tag-only-a", None, "TEXT")
        only_data_id = self.db.add_item("tag-only-data", None, "TEXT")
        both_id = self.db.add_item("tag-both", None, "TEXT")

        self.db.set_item_tags(only_a_id, "a")
        self.db.set_item_tags(only_data_id, "data")
        self.db.set_item_tags(both_id, "a, data")

        a_ids = {row[0] for row in self.db.get_items_by_tag("a")}
        data_ids = {row[0] for row in self.db.get_items_by_tag("data")}
        at_ids = {row[0] for row in self.db.get_items_by_tag("at")}

        self.assertEqual(a_ids, {only_a_id, both_id})
        self.assertEqual(data_ids, {only_data_id, both_id})
        self.assertEqual(at_ids, set())

    def test_get_items_keeps_pinned_first_with_custom_pin_order(self):
        normal_first = self.db.add_item("normal-first", None, "TEXT")
        pinned_a = self.db.add_item("pinned-a", None, "TEXT")
        pinned_b = self.db.add_item("pinned-b", None, "TEXT")
        pinned_c = self.db.add_item("pinned-c", None, "TEXT")
        normal_last = self.db.add_item("normal-last", None, "TEXT")

        self.db.toggle_pin(pinned_a)
        self.db.toggle_pin(pinned_b)
        self.db.toggle_pin(pinned_c)

        expected_pinned_order = [pinned_c, pinned_a, pinned_b]
        self.assertTrue(self.db.update_pin_orders(expected_pinned_order))

        items = self.db.get_items("", "전체")
        self.assertEqual([row[0] for row in items[:3]], expected_pinned_order)
        self.assertTrue(all(row[4] == 1 for row in items[:3]))
        self.assertTrue(all(row[4] == 0 for row in items[3:]))
        self.assertIn(normal_first, [row[0] for row in items[3:]])
        self.assertIn(normal_last, [row[0] for row in items[3:]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
