from __future__ import annotations

import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from smartclipboard_core.update_installer import (
    UpdateApplyError,
    apply_staged_update,
    cleanup_update_backups,
    consume_update_result,
    prepare_staged_update,
    resolve_update_staging_root,
    update_result_path,
    write_update_result,
)
from smartclipboard_core.update_manifest import ReleaseManifest


def _sample_manifest(payload: bytes) -> ReleaseManifest:
    return ReleaseManifest(
        version="10.7",
        artifact_url="https://github.com/twbeatles/smartclipboard/releases/download/v10.7/SmartClipboard-v10.7.exe",
        artifact_sha256=hashlib.sha256(payload).hexdigest(),
        artifact_size=len(payload),
        expires_at=datetime.now(timezone.utc),
        signature="test_sig",
    )


class UpdateInstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_user_cancel_removes_staged_artifact(self) -> None:
        payload = b"new SmartClipboard binary data"
        staged = prepare_staged_update(
            _sample_manifest(payload),
            chunks=[payload],
            staging_root=self.tmp_path,
            approve=lambda _manifest, _path: False,
        )
        self.assertIsNone(staged)
        self.assertEqual(list(self.tmp_path.glob("*.exe")), [])

    def test_hash_mismatch_rejects_and_removes_staged_artifact(self) -> None:
        payload = b"new SmartClipboard binary data"
        with self.assertRaises(ValueError):
            prepare_staged_update(
                _sample_manifest(payload),
                chunks=[b"corrupted data payload"],
                staging_root=self.tmp_path,
                approve=lambda _manifest, _path: True,
            )
        self.assertEqual(list(self.tmp_path.glob("*.exe")), [])

    def test_successful_staged_replacement_keeps_backup(self) -> None:
        target = self.tmp_path / "SmartClipboard.exe"
        staged = self.tmp_path / "staged.exe"
        backup = self.tmp_path / "SmartClipboard.exe.bak"
        target.write_bytes(b"version 10.6")
        staged.write_bytes(b"version 10.7")

        apply_staged_update(
            target=target,
            staged=staged,
            backup=backup,
            smoke_runner=lambda path: path.read_bytes() == b"version 10.7",
        )

        self.assertEqual(target.read_bytes(), b"version 10.7")
        self.assertEqual(backup.read_bytes(), b"version 10.6")
        self.assertFalse(staged.exists())

    def test_smoke_failure_rolls_back_original(self) -> None:
        target = self.tmp_path / "SmartClipboard.exe"
        staged = self.tmp_path / "staged.exe"
        backup = self.tmp_path / "SmartClipboard.exe.bak"
        target.write_bytes(b"version 10.6")
        staged.write_bytes(b"bad executable payload")

        with self.assertRaises(UpdateApplyError):
            apply_staged_update(
                target=target,
                staged=staged,
                backup=backup,
                smoke_runner=lambda _path: False,
            )

        self.assertEqual(target.read_bytes(), b"version 10.6")

    def test_staging_stays_under_install_directory(self) -> None:
        install_dir = self.tmp_path / "install"
        root = resolve_update_staging_root(install_dir=install_dir)
        self.assertEqual(root, (install_dir / ".updates").resolve())

    def test_update_result_write_and_consume(self) -> None:
        result_file = update_result_path(self.tmp_path)
        write_update_result(result_file, {"status": "applied", "version": "10.7"})

        consumed = consume_update_result(result_file)
        self.assertIsNotNone(consumed)
        assert consumed is not None
        self.assertEqual(consumed.get("status"), "applied")
        self.assertEqual(consumed.get("version"), "10.7")

        # Second consume must return None
        self.assertIsNone(consume_update_result(result_file))

    def test_backup_cleanup_retention(self) -> None:
        target = self.tmp_path / "SmartClipboard.exe"
        target.write_bytes(b"current")
        for v in ("1.0", "2.0", "3.0"):
            backup = self.tmp_path / f"SmartClipboard.exe.v{v}.bak"
            backup.write_bytes(f"v{v}".encode())

        cleanup_update_backups(target, keep_count=1)
        remaining = list(self.tmp_path.glob("SmartClipboard.exe.v*.bak"))
        self.assertEqual(len(remaining), 1)


if __name__ == "__main__":
    unittest.main()
