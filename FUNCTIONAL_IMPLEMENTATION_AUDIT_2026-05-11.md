# SmartClipboard Functional Implementation Audit (2026-05-11)

## Scope

This document replaces the removed root `FUNCTIONAL_IMPLEMENTATION_REVIEW.md` as the current implementation audit note. It reflects the 2026-05-11 functional hardening pass and the follow-up documentation/spec/.gitignore consistency check.

## Implemented Hardening

- Clipboard privacy now cancels any pending debounce timer when privacy mode is enabled, and `process_clipboard_impl()` re-checks privacy before reading clipboard data.
- Text clipboard capture has a 1MB UTF-8 byte limit. Oversized text is skipped and reported through status/toast; the existing 5MB image limit remains unchanged.
- `deleted_history.url_title` is part of schema creation/migration and is preserved through soft delete, unpinned bulk delete, restore, duplicate restore merge, and JSON migration import/export.
- Clipboard action writeback merges into an existing matching history row instead of leaving a duplicate. Metadata merge follows the restore merge policy for tags, note, bookmark, collection, pin, use count, and URL title.
- Restore validation is split into `full` and `minimal` modes. UI restore requires full validation by default and only accepts legacy/minimal DBs after an explicit feature-data-loss warning.
- Restore replacement removes target SQLite `-wal` and `-shm` sidecars before and after atomic replace.
- Startup global hotkey registration failures are surfaced through visible UI channels where available.
- Settings save now checks `set_setting()` return values and read-back results; the dialog remains open on failed persistence.

## Validation And CI

- Local preflight supports `--with-pyright` and retains existing `--skip-payload-build` and `--strict-optional-deps` behavior.
- Normal GitHub Actions CI runs `python scripts/preflight_local.py --skip-payload-build --strict-optional-deps --with-pyright` across the Windows Python matrix.
- PyInstaller build and frozen executable startup smoke are intentionally separated into the manual `.github/workflows/package-smoke.yml` workflow.

## Packaging / Spec Consistency

- `smartclipboard.spec` still includes `smartclipboard_app/legacy_main_payload.marshal` and `smartclipboard_app/legacy_main_payload.manifest.json`.
- The 2026-05-11 runtime changes are covered by the existing `collect_submodules` rules for `smartclipboard_core`, `smartclipboard_core.automation`, `smartclipboard_app.features`, and `smartclipboard_app.ui.mainwindow_parts`.
- No additional PyInstaller hidden import or data file is required for this hardening pass.

## Ignore Policy

- `.gitignore` continues to exclude build outputs, frozen executables, Python caches, local test temp files, user DBs, logs, and backups.
- SQLite rollback journal, WAL, and SHM sidecars are ignored for `.db`, `.sqlite`, and `.sqlite3` database names.

## Documentation Sync

- `README.md`, `claude.md`, `.gemini/GEMINI.md`, `gemini.md`, `PROJECT_ANALYSIS.md`, both legacy README files, and `smartclipboard.spec` were checked against the current implementation and CI behavior.
- References to the removed root `FUNCTIONAL_IMPLEMENTATION_REVIEW.md` were replaced with this 2026-05-11 audit document or the root README/guide baseline.
