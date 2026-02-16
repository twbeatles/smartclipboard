import os
import tempfile
import unittest

from smartclipboard_core.database import ClipboardDB


class V11DatabaseFeatureTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "clipboard_history_v6.db")
        self.db = ClipboardDB(db_file=self.db_path, app_dir=self.tmpdir.name)

    def tearDown(self):
        self.db.close()
        self.tmpdir.cleanup()

    def test_file_item_roundtrip(self):
        item_id = self.db.add_file_item([r"C:\a.txt", r"C:\b.txt"])
        self.assertTrue(item_id)
        paths = self.db.get_file_paths(item_id)
        self.assertEqual(paths, [r"C:\a.txt", r"C:\b.txt"])

        rows = self.db.search_items("a.txt", type_filter="전체")
        self.assertIn(item_id, [r[0] for r in rows])

    def test_update_item_content_in_place(self):
        item_id = self.db.add_item("old", None, "TEXT")
        self.assertTrue(self.db.update_item_content(item_id, "new", type_tag="TEXT"))
        rows = self.db.search_items("new", type_filter="전체")
        self.assertEqual([r[0] for r in rows], [item_id])

    def test_expiry_map_and_bulk_updates(self):
        a = self.db.add_item("a", None, "TEXT")
        b = self.db.add_item("b", None, "TEXT")
        self.db.set_expires_at(a, "2099-01-01 00:00:00")
        m = self.db.get_expires_at_map([a, b])
        self.assertIn(a, m)
        self.assertNotIn(b, m)

        self.assertEqual(self.db.set_bookmarks([a, b], 1), 2)
        bm = {row[0] for row in self.db.get_bookmarked_items()}
        self.assertEqual(bm, {a, b})

        col = self.db.add_collection("C")
        self.assertTrue(col)
        self.assertEqual(self.db.set_collection_many([a, b], col), 2)
        by_col = {row[0] for row in self.db.get_items_by_collection(col)}
        self.assertEqual(by_col, {a, b})

    def test_runtime_indexes_are_idempotent(self):
        self.assertTrue(self.db.ensure_runtime_indexes())
        self.assertTrue(self.db.ensure_runtime_indexes())

        with self.db.lock:
            cursor = self.db.conn.cursor()
            cursor.execute("PRAGMA index_list('history')")
            names = {row[1] for row in cursor.fetchall()}

        self.assertIn("idx_history_sort", names)
        self.assertIn("idx_history_collection_sort", names)
        self.assertIn("idx_history_content_unpinned", names)
        self.assertIn("idx_history_file_path_unpinned", names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
