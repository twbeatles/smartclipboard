# AGENTS.md — SmartClipboard Pro

## Repository layout

- `src/` — React 19 + TypeScript frontend (`App.tsx`, `MiniApp.tsx`)
- `src-tauri/` — Rust + Tauri 2 native backend (`src/`, `tests/`, `fixtures/`)
- `legacy/python/` — Python/PyQt6 classic edition (reference implementation, parity spec)
- `docs/` — `NATIVE_PARITY_MATRIX.md` (parity tracker, includes 2026-09-20 audit follow-up)
- `PROJECT_AUDIT.md` — 2026-09-20 functional audit + remediation record

`claude.md` still describes the Python tree at the repo root; the real
locations are under `legacy/python/`. The native edition is the active
development surface.

## Native backend conventions

- Single `Mutex<Connection>` in `database/connection.rs`; all DB access goes
  through `with_conn`. Never hold the guard across clipboard I/O.
- Manual `BEGIN IMMEDIATE`/`COMMIT` must always pair with `ROLLBACK` on error
  (see `vault/manager.rs`, `import_export/mod.rs` for the IIFE pattern).
- Every internal clipboard write must use the shared `AppState.write_guard`
  and mark **after** writing with the real sequence number.
- No `.unwrap()` on untrusted/stored data in Vault/DB paths — return `AppError`.
- `Fernet::encrypt` IVs come from the OS CSPRNG; deterministic IVs are a bug.
- Import paths: dual-format read (`items`/`history`), collection remap by name,
  FILE signature rebuild, pre-import backup attempt, single transaction.
- Files use CRLF line endings; run `rustfmt --edition 2021` on touched files.

## Native frontend conventions

- `App.tsx` owns state and orchestration; views live in `src/components/`
  (`HistoryList`, `Preview`, `AppMenu`, `PaletteDialog`, `TrashDialog`,
  `VaultDialog`), shared helpers in `src/lib/` (`tauri.ts`, `format.tsx`).
- Secondary features (trash, vault, theme, collections, import/export,
  update) stay behind the `⋯` menu; the main surface is search + list + preview.
- `invoke` argument keys are camelCase (`deletedId`, `itemId`) — Tauri maps
  them to the snake_case Rust parameters. Struct payloads (`filter`) keep
  their serde field names.
- Copy non-image rows through `history_copy` (shared write guard), never
  `navigator.clipboard.writeText`. The mini window pastes via `history_paste`.
- The list reloads on the `history_changed` event; closing the main window
  hides it to the tray, and the mini window hides on blur.
- Palette actions declare an `effect` (`replace` / `copy` / `view`); only
  `replace` writes back to the history row.

## Verification (needs network for first fetch)

```powershell
cargo test --manifest-path src-tauri/Cargo.toml
cargo clippy --manifest-path src-tauri/Cargo.toml
npm run build
```

`PROJECT_AUDIT.md` §3 lists what could not be verified in an offline sandbox.
