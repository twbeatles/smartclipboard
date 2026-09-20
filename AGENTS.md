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

## Verification (needs network for first fetch)

```powershell
cargo test --manifest-path src-tauri/Cargo.toml
cargo clippy --manifest-path src-tauri/Cargo.toml
npm run build
```

`PROJECT_AUDIT.md` §3 lists what could not be verified in an offline sandbox.
