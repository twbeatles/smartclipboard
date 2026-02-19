import json
import os
import tempfile
import unittest
import zipfile

from smartclipboard_core.backup_zip import export_history_zip, import_history_zip
from smartclipboard_core.database import ClipboardDB


class BackupZipTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "clipboard_history_v6.db")
        self.db = ClipboardDB(db_file=self.db_path, app_dir=self.tmpdir.name)

    def tearDown(self):
        self.db.close()
        self.tmpdir.cleanup()

    def test_export_creates_manifest_and_import_roundtrip(self):
        # collection
        col_id = self.db.add_collection("Work", "📁", "#123456")

        # items
        t1 = self.db.add_item("hello", None, "TEXT")
        self.db.set_item_tags(t1, "a, b")
        self.db.set_note(t1, "note-1")
        self.db.toggle_bookmark(t1)
        self.db.move_to_collection(t1, col_id)
        self.db.set_expires_at(t1, "2099-01-01 00:00:00")

        # image
        img_id = self.db.add_item("[이미지 캡처됨]", b"\x89PNG\r\n\x1a\nfake", "IMAGE")
        self.db.toggle_pin(img_id)

        zip_path = os.path.join(self.tmpdir.name, "backup.zip")
        count = export_history_zip(self.db, zip_path)
        self.assertGreaterEqual(count, 2)

        with zipfile.ZipFile(zip_path, "r") as zf:
            self.assertIn("manifest.json", zf.namelist())
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            self.assertIn("history", manifest)

        # Import into a new DB
        other_dir = tempfile.TemporaryDirectory()
        try:
            other_db_path = os.path.join(other_dir.name, "clipboard_history_v6.db")
            other = ClipboardDB(db_file=other_db_path, app_dir=other_dir.name)
            try:
                imported = import_history_zip(other, zip_path, conflict="skip")
                self.assertGreaterEqual(imported, 2)

                # Ensure text item metadata survived.
                rows = other.search_items("hello", type_filter="전체")
                self.assertEqual(len(rows), 1)
                found_id = rows[0][0]
                self.assertEqual(other.get_item_tags(found_id).replace("，", ","), "a, b")
                self.assertEqual(other.get_note(found_id), "note-1")
            finally:
                other.close()
        finally:
            other_dir.cleanup()

    def test_import_rolls_back_entire_transaction_on_broken_image_ref(self):
        zip_path = os.path.join(self.tmpdir.name, "broken_backup.zip")
        manifest = {
            "collections": [],
            "history": [
                {"type": "TEXT", "content": "ok-1", "image_ref": None},
                {"type": "IMAGE", "content": "", "image_ref": "images/missing.png"},
            ],
        }
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False).encode("utf-8"))

        with self.assertRaises(KeyError):
            import_history_zip(self.db, zip_path, conflict="skip")

        with self.db.lock:
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM history")
            history_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM collections")
            collection_count = cursor.fetchone()[0]

        self.assertEqual(history_count, 0)
        self.assertEqual(collection_count, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
