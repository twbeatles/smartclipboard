from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.check_release_prereqs import (
    check_icon,
    check_spec_no_dunder_file,
    check_package_smoke_workdir,
    check_release_workflow_smoke,
    check_required_files,
    check_versions,
    collect_errors,
    short_version,
)


class ShortVersionTests(unittest.TestCase):
    def test_trailing_zero_groups_stripped(self) -> None:
        self.assertEqual(short_version("10.8.0"), "10.8")
        self.assertEqual(short_version("10.8"), "10.8")
        self.assertEqual(short_version(" 10.8.0 "), "10.8")

    def test_distinct_versions_stay_distinct(self) -> None:
        self.assertNotEqual(short_version("10.8"), short_version("10.9"))


class VersionConsistencyTests(unittest.TestCase):
    def test_short_tag_form_matches_full(self) -> None:
        self.assertIsNone(check_versions("10.8", "10.8.0", "10.8.0", "10.8.0"))

    def test_exact_match_passes(self) -> None:
        self.assertIsNone(check_versions("10.8", "10.8", "10.8", "10.8"))

    def test_config_cargo_drift_detected(self) -> None:
        error = check_versions("10.8", "10.9.0", "10.8.0", "10.9.0")
        self.assertIsNotNone(error)
        assert error is not None
        self.assertIn("Cargo", error)

    def test_tauri_must_match_cargo_exactly(self) -> None:
        error = check_versions("10.8", "10.8.0", "10.8.0", "10.8")
        self.assertIsNotNone(error)
        assert error is not None
        self.assertIn("tauri", error)


class IconCheckTests(unittest.TestCase):
    def test_missing_icon_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "smartclipboard.ico"
            error = check_icon((missing,))
            self.assertIsNotNone(error)
            assert error is not None
            self.assertIn(str(missing), error)

    def test_present_icon_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            icon = Path(tmp) / "smartclipboard.ico"
            icon.write_bytes(b"fake ico")
            self.assertIsNone(check_icon((icon,)))


class SpecGuardTests(unittest.TestCase):
    @staticmethod
    def _write(tmp: str, text: str) -> Path:
        path = Path(tmp) / "smartclipboard.spec"
        path.write_text(text, encoding="utf-8")
        return path

    def test_dunder_file_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec = self._write(tmp, 'SPEC_DIR = Path(__file__).parent\n')
            error = check_spec_no_dunder_file(spec)
            self.assertIsNotNone(error)

    def test_specpath_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec = self._write(
                tmp, 'SPEC_DIR = Path(globals().get("SPECPATH") or ".")\n'
            )
            self.assertIsNone(check_spec_no_dunder_file(spec))


class WorkflowGuardTests(unittest.TestCase):
    @staticmethod
    def _write(tmp: str, name: str, text: str) -> Path:
        path = Path(tmp) / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_call_operator_smoke_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow = self._write(tmp, "release.yml", "& $artifact --smoke\n")
            error = check_release_workflow_smoke(workflow)
            self.assertIsNotNone(error)

    def test_start_process_smoke_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow = self._write(
                tmp,
                "release.yml",
                '$smoke = Start-Process -FilePath $artifact -ArgumentList "--smoke"'
                " -NoNewWindow -Wait -PassThru\n",
            )
            self.assertIsNone(check_release_workflow_smoke(workflow))

    def test_package_smoke_requires_legacy_workdir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow = self._write(tmp, "package-smoke.yml", "run: pyinstaller\n")
            self.assertIsNotNone(check_package_smoke_workdir(workflow))
            workflow.write_text(
                "working-directory: legacy/python\n", encoding="utf-8"
            )
            self.assertIsNone(check_package_smoke_workdir(workflow))

    def test_required_files_detects_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            present = Path(tmp) / "a.txt"
            present.write_text("x", encoding="utf-8")
            missing = Path(tmp) / "b.txt"
            self.assertIsNone(check_required_files((present,)))
            self.assertIsNotNone(check_required_files((present, missing)))


class RepoTreeTests(unittest.TestCase):
    def test_repo_tree_passes_release_prereqs(self) -> None:
        self.assertEqual(collect_errors(), [])


if __name__ == "__main__":
    unittest.main()
