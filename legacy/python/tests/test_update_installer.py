from __future__ import annotations

import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from unittest import mock

from smartclipboard_core.update_installer import (
    UpdateApplyError,
    apply_staged_update,
    cleanup_update_backups,
    consume_update_result,
    prepare_staged_update,
    resolve_update_staging_root,
    sanitized_update_env,
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

    def test_stale_backup_is_overwritten_not_refused(self) -> None:
        # Regression: a backup left by a previous failed attempt must not
        # wedge later retries with "Update backup already exists".
        target = self.tmp_path / "SmartClipboard.exe"
        staged = self.tmp_path / "staged.exe"
        backup = self.tmp_path / "SmartClipboard.exe.bak"
        target.write_bytes(b"version 10.6")
        staged.write_bytes(b"version 10.7")
        backup.write_bytes(b"stale leftover")

        apply_staged_update(
            target=target,
            staged=staged,
            backup=backup,
            smoke_runner=lambda path: path.read_bytes() == b"version 10.7",
        )

        self.assertEqual(target.read_bytes(), b"version 10.7")
        self.assertEqual(backup.read_bytes(), b"version 10.6")
        self.assertFalse(staged.exists())

    def test_first_move_failure_leaves_install_intact(self) -> None:
        # Windows can rename a running exe but not overwrite it; the first
        # rename (install aside) must fail without touching the install.
        import smartclipboard_core.update_installer as installer

        target = self.tmp_path / "SmartClipboard.exe"
        staged = self.tmp_path / "staged.exe"
        backup = self.tmp_path / "SmartClipboard.exe.bak"
        target.write_bytes(b"version 10.6")
        staged.write_bytes(b"version 10.7")

        real_replace = installer.os.replace

        def fail_first_move(src: object, dst: object, *args: object, **kwargs: object) -> None:
            if Path(str(src)) == target.resolve():
                raise PermissionError("[WinError 5] Access is denied")
            return real_replace(src, dst, *args, **kwargs)  # type: ignore[arg-type]

        with mock.patch.object(installer.os, "replace", side_effect=fail_first_move):
            with self.assertRaises(UpdateApplyError):
                apply_staged_update(
                    target=target,
                    staged=staged,
                    backup=backup,
                    smoke_runner=lambda _path: True,
                )

        self.assertEqual(target.read_bytes(), b"version 10.6")
        self.assertTrue(staged.is_file())

    def test_second_move_failure_restores_backup(self) -> None:
        import smartclipboard_core.update_installer as installer

        target = self.tmp_path / "SmartClipboard.exe"
        staged = self.tmp_path / "staged.exe"
        backup = self.tmp_path / "SmartClipboard.exe.bak"
        target.write_bytes(b"version 10.6")
        staged.write_bytes(b"version 10.7")

        real_replace = installer.os.replace
        calls = {"count": 0}

        def fail_second_move(src: object, dst: object, *args: object, **kwargs: object) -> None:
            calls["count"] += 1
            if calls["count"] == 2:
                raise PermissionError("[WinError 5] Access is denied")
            return real_replace(src, dst, *args, **kwargs)  # type: ignore[arg-type]

        with mock.patch.object(installer.os, "replace", side_effect=fail_second_move):
            with self.assertRaises(UpdateApplyError):
                apply_staged_update(
                    target=target,
                    staged=staged,
                    backup=backup,
                    smoke_runner=lambda _path: True,
                )

        self.assertEqual(target.read_bytes(), b"version 10.6")

    def test_interrupted_replacement_recovers_from_backup(self) -> None:
        # Simulate a crash between the two renames: the old install sits at
        # the backup path, the target path is missing, staged is intact.
        target = self.tmp_path / "SmartClipboard.exe"
        staged = self.tmp_path / "staged.exe"
        backup = self.tmp_path / "SmartClipboard.exe.bak"
        backup.write_bytes(b"version 10.6")
        staged.write_bytes(b"version 10.7")
        self.assertFalse(target.exists())

        apply_staged_update(
            target=target,
            staged=staged,
            backup=backup,
            smoke_runner=lambda path: path.read_bytes() == b"version 10.7",
        )

        self.assertEqual(target.read_bytes(), b"version 10.7")
        self.assertEqual(backup.read_bytes(), b"version 10.6")

    def test_child_env_strips_bootloader_vars(self) -> None:
        env = sanitized_update_env(
            {
                "_MEIPASS": "C:\\temp\\onefile",
                "_MEI12345": "x",
                "_PYI_ARCHIVE_FILE": "y",
                "_PYI_PARENT_PROCESS_LEVEL": "1",
                "PATH": "keep",
                "SMARTCLIPBOARD_UPDATE_PUBLIC_KEY_B64": "keep2",
            }
        )
        self.assertNotIn("_MEIPASS", env)
        self.assertNotIn("_MEI12345", env)
        self.assertNotIn("_PYI_ARCHIVE_FILE", env)
        self.assertNotIn("_PYI_PARENT_PROCESS_LEVEL", env)
        self.assertEqual(env["PATH"], "keep")

    def test_helper_and_smoke_run_with_clean_env(self) -> None:
        import smartclipboard_core.update_installer as installer

        with mock.patch.object(
            installer.os, "environ", {"_MEIPASS": "stale", "PATH": "keep"}
        ):
            # Helper spawn inherits a sanitized env.
            staged = self.tmp_path / "staged.exe"
            staged.write_bytes(b"x")
            with (
                mock.patch.object(
                    installer.shutil, "copy2", return_value=None
                ),
                mock.patch.object(installer.subprocess, "Popen") as popen,
            ):
                installer.launch_update_helper(
                    target=self.tmp_path / "SmartClipboard.exe",
                    staged=staged,
                    backup=self.tmp_path / "SmartClipboard.exe.bak",
                    parent_pid=1234,
                    expected_sha256="0" * 64,
                    expected_size=1,
                    result_file=self.tmp_path / "result.json",
                )
            _, kwargs = popen.call_args
            helper_env = kwargs.get("env", {})
            self.assertNotIn("_MEIPASS", helper_env)
            self.assertEqual(helper_env.get("PATH"), "keep")

            # Post-update relaunch uses the same sanitized env.
            with mock.patch.object(installer.subprocess, "Popen") as relaunch_popen:
                installer.relaunch_sanitized(["SmartClipboard.exe"])
            _, relaunch_kwargs = relaunch_popen.call_args
            relaunch_env = relaunch_kwargs.get("env", {})
            self.assertNotIn("_MEIPASS", relaunch_env)
            self.assertEqual(relaunch_env.get("PATH"), "keep")

            # --smoke spawn inherits a sanitized env.
            target = self.tmp_path / "SmartClipboard.exe"
            target.write_bytes(b"v")
            staged2 = self.tmp_path / "staged2.exe"
            staged2.write_bytes(b"v")
            backup2 = self.tmp_path / "SmartClipboard.exe.bak"
            with mock.patch.object(
                installer.subprocess, "run"
            ) as run_mock:
                run_mock.return_value.returncode = 0
                installer.apply_staged_update(
                    target=target, staged=staged2, backup=backup2
                )
            _, run_kwargs = run_mock.call_args
            smoke_env = run_kwargs.get("env", {})
            self.assertNotIn("_MEIPASS", smoke_env)


if __name__ == "__main__":
    unittest.main()
