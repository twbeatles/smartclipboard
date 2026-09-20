//! Staged download, atomic apply with backup/rollback, and result-file
//! protocol for the native updater (G-3).
//!
//! Ports `legacy/python/smartclipboard_core/update_installer.py`: exact
//! size + sha256 staging verification, same-directory backup, smoke check,
//! cleanup of older backups (keep 2), atomic result recording and the
//! detached helper handshake used to replace a running executable.

use std::fs;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{Duration, Instant};

use sha2::{Digest, Sha256};

use crate::errors::{AppError, Result};
use crate::updater::manifest::{fetch_https, ReleaseManifest};

pub const ARTIFACT_CHUNK_BYTES: usize = 1024 * 1024;
pub const SMOKE_TIMEOUT: Duration = Duration::from_secs(60);
pub const UPDATE_RESULT_FILENAME: &str = "last-update-result.json";
pub const UPDATE_STAGING_DIRNAME: &str = ".updates";
pub const BACKUP_KEEP_COUNT: usize = 2;
/// How long the `--apply-update` helper waits for the parent process to
/// exit (via replace retries) before giving up.
pub const APPLY_WAIT_TIMEOUT: Duration = Duration::from_secs(60);

/// Handle for a downloaded artifact waiting in the staging directory.
#[derive(Debug, Clone)]
pub struct StagedArtifact {
    pub path: PathBuf,
    pub manifest: ReleaseManifest,
}

/// Final outcome of an apply attempt, mirrored to the result file.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct UpdateApplyOutcome {
    pub status: String,
    pub version: String,
    pub target: PathBuf,
    pub backup: Option<PathBuf>,
    pub message: String,
    pub rolled_back: bool,
}

/// Stream `reader` into the staging directory while enforcing the exact
/// expected byte count and sha256. Partial files are removed on failure.
pub fn stage_artifact<R: Read>(
    manifest: &ReleaseManifest,
    reader: R,
    staging_root: &Path,
) -> Result<StagedArtifact> {
    fs::create_dir_all(staging_root)
        .map_err(|e| AppError::Internal(format!("Cannot create staging dir: {}", e)))?;
    let staged_path = staging_root.join(format!(
        "SmartClipboard-Update-v{}.exe.download",
        manifest.version
    ));
    let _ = fs::remove_file(&staged_path);

    let mut reader = reader.take(manifest.artifact_size + 1);
    let mut file = fs::File::create(&staged_path)
        .map_err(|e| AppError::Internal(format!("Cannot stage artifact: {}", e)))?;
    let mut hasher = Sha256::new();
    let mut total: u64 = 0;
    let mut chunk = vec![0u8; ARTIFACT_CHUNK_BYTES];
    loop {
        let read = reader
            .read(&mut chunk)
            .map_err(|e| AppError::Internal(format!("Artifact download failed: {}", e)))?;
        if read == 0 {
            break;
        }
        total += read as u64;
        if total > manifest.artifact_size {
            drop(file);
            let _ = fs::remove_file(&staged_path);
            return Err(AppError::Internal(format!(
                "Artifact exceeds expected size of {} bytes",
                manifest.artifact_size
            )));
        }
        hasher.update(&chunk[..read]);
        file.write_all(&chunk[..read])
            .map_err(|e| AppError::Internal(format!("Cannot stage artifact: {}", e)))?;
    }
    if total != manifest.artifact_size {
        drop(file);
        let _ = fs::remove_file(&staged_path);
        return Err(AppError::Internal(format!(
            "Artifact size mismatch: got {} bytes, expected {} bytes",
            total, manifest.artifact_size
        )));
    }
    let digest = hex_encode(&hasher.finalize());
    if digest != manifest.artifact_sha256 {
        drop(file);
        let _ = fs::remove_file(&staged_path);
        return Err(AppError::Internal(
            "Artifact sha256 mismatch; refusing staged file".to_string(),
        ));
    }
    file.sync_all()
        .map_err(|e| AppError::Internal(format!("Cannot stage artifact: {}", e)))?;
    drop(file);
    Ok(StagedArtifact {
        path: staged_path,
        manifest: manifest.clone(),
    })
}

fn hex_encode(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        out.push(HEX[(b >> 4) as usize] as char);
        out.push(HEX[(b & 0xf) as usize] as char);
    }
    out
}

fn looks_like_exe(path: &Path) -> bool {
    path.extension()
        .and_then(|e| e.to_str())
        .map(|e| e.eq_ignore_ascii_case("exe"))
        .unwrap_or(false)
}

/// Default smoke check: run `target --smoke` with a timeout.
pub fn default_smoke_check(target: &Path) -> bool {
    let mut child = match Command::new(target).arg("--smoke").spawn() {
        Ok(child) => child,
        Err(_) => return false,
    };
    let start = std::time::Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(status)) => return status.success(),
            Ok(None) => {}
            Err(_) => return false,
        }
        if start.elapsed() > SMOKE_TIMEOUT {
            let _ = child.kill();
            let _ = child.wait();
            return false;
        }
        std::thread::sleep(Duration::from_millis(50));
    }
}

/// Smoke-check override for [`ApplyRequest`] (tests inject fakes here).
pub type SmokeCheck = Box<dyn Fn(&Path) -> bool + Send>;

#[allow(clippy::too_many_arguments)]
pub struct ApplyRequest {
    pub target: PathBuf,
    pub staged: PathBuf,
    pub backup: PathBuf,
    pub expected_sha256: String,
    pub expected_size: u64,
    pub version: String,
    /// Smoke check override (tests inject fakes here).
    pub smoke_check: Option<SmokeCheck>,
}

/// Atomically replace `target` with the staged file: validate paths and
/// hashes, back up, replace, smoke-check, roll back on any failure.
pub fn apply_staged_update(req: &ApplyRequest) -> Result<UpdateApplyOutcome> {
    let fail = |message: String, rolled_back: bool| UpdateApplyOutcome {
        status: "failed".to_string(),
        version: req.version.clone(),
        target: req.target.clone(),
        backup: None,
        message,
        rolled_back,
    };

    if !looks_like_exe(&req.target) || !looks_like_exe(&req.staged) {
        return Ok(fail(
            "Target and staged files must both be .exe files".to_string(),
            false,
        ));
    }
    if req.target == req.staged || req.target == req.backup || req.staged == req.backup {
        return Ok(fail(
            "Target, staged and backup paths must all differ".to_string(),
            false,
        ));
    }
    let target_parent = req.target.parent();
    if target_parent != req.staged.parent() || target_parent != req.backup.parent() {
        return Ok(fail(
            "Target, staged and backup must live in the same directory".to_string(),
            false,
        ));
    }
    if req.backup.exists() {
        return Ok(fail(
            "Backup path already exists; refusing to overwrite".to_string(),
            false,
        ));
    }

    let staged_meta = match fs::metadata(&req.staged) {
        Ok(m) => m,
        Err(_) => {
            return Ok(fail("Staged file is missing".to_string(), false));
        }
    };
    if staged_meta.len() != req.expected_size {
        return Ok(fail(
            "Staged file size does not match manifest".to_string(),
            false,
        ));
    }
    if !verify_file_sha256(&req.staged, &req.expected_sha256)? {
        return Ok(fail(
            "Staged file sha256 does not match manifest".to_string(),
            false,
        ));
    }

    if fs::copy(&req.target, &req.backup).is_err() {
        return Ok(fail(
            "Could not back up current executable".to_string(),
            false,
        ));
    }
    if fs::rename(&req.staged, &req.target).is_err() {
        let _ = fs::remove_file(&req.backup);
        return Ok(fail(
            "Could not replace target executable".to_string(),
            false,
        ));
    }

    let smoke_ok = match &req.smoke_check {
        Some(check) => check(&req.target),
        None => default_smoke_check(&req.target),
    };
    if !smoke_ok {
        // Roll back: restore the backup, remove the bad target.
        let _ = fs::remove_file(&req.target);
        let restored = fs::rename(&req.backup, &req.target).is_ok();
        return Ok(UpdateApplyOutcome {
            status: "failed".to_string(),
            version: req.version.clone(),
            target: req.target.clone(),
            backup: None,
            message: if restored {
                "Smoke check failed; previous version restored".to_string()
            } else {
                "Smoke check failed AND rollback failed; backup may remain".to_string()
            },
            rolled_back: restored,
        });
    }

    cleanup_old_backups(&req.target, BACKUP_KEEP_COUNT);
    Ok(UpdateApplyOutcome {
        status: "applied".to_string(),
        version: req.version.clone(),
        target: req.target.clone(),
        backup: Some(req.backup.clone()),
        message: String::new(),
        rolled_back: false,
    })
}

fn verify_file_sha256(path: &Path, expected_hex: &str) -> Result<bool> {
    let mut file = fs::File::open(path)
        .map_err(|e| AppError::Internal(format!("Cannot read file for hashing: {}", e)))?;
    let mut hasher = Sha256::new();
    let mut chunk = vec![0u8; ARTIFACT_CHUNK_BYTES];
    loop {
        let read = file
            .read(&mut chunk)
            .map_err(|e| AppError::Internal(format!("Cannot read file for hashing: {}", e)))?;
        if read == 0 {
            break;
        }
        hasher.update(&chunk[..read]);
    }
    Ok(hex_encode(&hasher.finalize()) == expected_hex.to_lowercase())
}

/// Keep the newest `keep` `<target>.v*.bak` files, delete the rest.
pub fn cleanup_old_backups(target: &Path, keep: usize) {
    let parent = match target.parent() {
        Some(p) => p,
        None => return,
    };
    let stem = match target.file_name().and_then(|n| n.to_str()) {
        Some(n) => n.to_string(),
        None => return,
    };
    let prefix = format!("{}.v", stem);
    let suffix = ".bak";
    let mut backups: Vec<(PathBuf, std::time::SystemTime)> = Vec::new();
    let entries = match fs::read_dir(parent) {
        Ok(e) => e,
        Err(_) => return,
    };
    for entry in entries.flatten() {
        let name = entry.file_name().to_string_lossy().into_owned();
        if name.starts_with(&prefix) && name.ends_with(suffix) {
            let modified = entry
                .metadata()
                .and_then(|m| m.modified())
                .unwrap_or(std::time::UNIX_EPOCH);
            backups.push((entry.path(), modified));
        }
    }
    backups.sort_by_key(|b| std::cmp::Reverse(b.1));
    for (path, _) in backups.into_iter().skip(keep) {
        let _ = fs::remove_file(path);
    }
}

/// Staging root for downloads, backups bookkeeping and the result file:
/// `<install_dir>/.updates` (mirrors the Python `resolve_update_staging_root`).
pub fn resolve_update_staging_root(install_dir: &Path) -> PathBuf {
    install_dir.join(UPDATE_STAGING_DIRNAME)
}

/// Download the verified manifest artifact over https-only (redirects
/// re-validated) and stage it with exact size + sha256 enforcement.
pub fn download_artifact_to_stage(
    manifest: &ReleaseManifest,
    staging_root: &Path,
) -> Result<StagedArtifact> {
    let response = fetch_https(
        &manifest.artifact_url,
        "application/octet-stream",
        "Artifact",
    )?;
    stage_artifact(manifest, response.into_reader(), staging_root)
}

/// Atomically record the apply outcome at an explicit result-file path.
pub fn write_update_result_to_path(
    result_file: &Path,
    outcome: &UpdateApplyOutcome,
) -> Result<PathBuf> {
    if let Some(parent) = result_file.parent() {
        fs::create_dir_all(parent)
            .map_err(|e| AppError::Internal(format!("Cannot create result dir: {}", e)))?;
    }
    let mut map = serde_json::Map::new();
    map.insert(
        "status".to_string(),
        serde_json::Value::String(outcome.status.clone()),
    );
    map.insert(
        "version".to_string(),
        serde_json::Value::String(outcome.version.clone()),
    );
    map.insert(
        "target".to_string(),
        serde_json::Value::String(outcome.target.to_string_lossy().into_owned()),
    );
    map.insert(
        "backup".to_string(),
        outcome
            .backup
            .as_ref()
            .map(|p| serde_json::Value::String(p.to_string_lossy().into_owned()))
            .unwrap_or(serde_json::Value::Null),
    );
    if !outcome.message.is_empty() {
        map.insert(
            "message".to_string(),
            serde_json::Value::String(outcome.message.clone()),
        );
    }
    map.insert(
        "rolled_back".to_string(),
        serde_json::Value::Bool(outcome.rolled_back),
    );
    let text = serde_json::Value::Object(map).to_string();
    let tmp = result_file.with_extension("json.tmp");
    fs::write(&tmp, text)
        .map_err(|e| AppError::Internal(format!("Cannot write update result: {}", e)))?;
    fs::rename(&tmp, result_file)
        .map_err(|e| AppError::Internal(format!("Cannot write update result: {}", e)))?;
    Ok(result_file.to_path_buf())
}

/// Atomically record the apply outcome next to the staging root.
pub fn write_update_result(staging_root: &Path, outcome: &UpdateApplyOutcome) -> Result<PathBuf> {
    fs::create_dir_all(staging_root)
        .map_err(|e| AppError::Internal(format!("Cannot create staging dir: {}", e)))?;
    write_update_result_to_path(&staging_root.join(UPDATE_RESULT_FILENAME), outcome)
}

/// Read and consume (delete) a pending result file. Returns `None` when
/// absent; foreign statuses raise instead of being silently dropped.
pub fn consume_update_result(staging_root: &Path) -> Result<Option<UpdateApplyOutcome>> {
    let path = staging_root.join(UPDATE_RESULT_FILENAME);
    if !path.exists() {
        return Ok(None);
    }
    let text = fs::read_to_string(&path)
        .map_err(|e| AppError::Internal(format!("Cannot read update result: {}", e)))?;
    let _ = fs::remove_file(&path);
    let doc: serde_json::Value = serde_json::from_str(&text)
        .map_err(|e| AppError::Internal(format!("Update result is not valid JSON: {}", e)))?;
    let status = doc
        .get("status")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    if status != "applied" && status != "failed" {
        return Err(AppError::Internal(format!(
            "Unknown update result status: {:?}",
            status
        )));
    }
    let str_field = |key: &str| -> String {
        doc.get(key)
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string()
    };
    Ok(Some(UpdateApplyOutcome {
        status,
        version: str_field("version"),
        target: PathBuf::from(str_field("target")),
        backup: doc
            .get("backup")
            .and_then(|v| v.as_str())
            .map(PathBuf::from),
        message: str_field("message"),
        rolled_back: doc
            .get("rolled_back")
            .and_then(|v| v.as_bool())
            .unwrap_or(false),
    }))
}

/// Copy the running executable to a helper path and spawn it detached with
/// the apply arguments, so the update can proceed after this process exits.
pub fn launch_update_helper(
    current_exe: &Path,
    helper_path: &Path,
    update_args: &[String],
) -> Result<()> {
    if helper_path.exists() {
        let _ = fs::remove_file(helper_path);
    }
    fs::copy(current_exe, helper_path)
        .map_err(|e| AppError::Internal(format!("Cannot stage update helper: {}", e)))?;
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        Command::new(helper_path)
            .args(update_args)
            .creation_flags(CREATE_NO_WINDOW)
            .spawn()
            .map_err(|e| AppError::Internal(format!("Cannot launch update helper: {}", e)))?;
    }
    #[cfg(not(windows))]
    {
        Command::new(helper_path)
            .args(update_args)
            .spawn()
            .map_err(|e| AppError::Internal(format!("Cannot launch update helper: {}", e)))?;
    }
    Ok(())
}

/// Standard key locations for the release-signing public key.
pub fn default_public_key_b64() -> Option<String> {
    std::env::var("SMARTCLIPBOARD_UPDATE_PUBLIC_KEY_B64")
        .ok()
        .filter(|v| !v.trim().is_empty())
}

/// Arguments for the detached `--apply-update` helper mode, mirroring the
/// flags the Python `launch_update_helper` spawns (single-dash `--update-*`
/// long names).
#[derive(Debug, Clone)]
pub struct ApplyUpdateArgs {
    pub target: PathBuf,
    pub staged: PathBuf,
    pub backup: PathBuf,
    pub parent_pid: u32,
    pub expected_sha256: String,
    pub expected_size: u64,
    pub result_file: PathBuf,
}

fn take_flag_value(argv: &[String], flag: &str) -> Result<String> {
    argv.windows(2)
        .find(|w| w[0] == flag)
        .map(|w| w[1].clone())
        .filter(|v| !v.is_empty())
        .ok_or_else(|| AppError::Internal(format!("Missing required flag {}", flag)))
}

/// Parse `--apply-update` helper arguments (program name already stripped).
pub fn parse_apply_update_args(argv: &[String]) -> Result<ApplyUpdateArgs> {
    let parent_pid: u32 = take_flag_value(argv, "--update-parent-pid")?
        .parse()
        .map_err(|_| AppError::Internal("Invalid --update-parent-pid".to_string()))?;
    let expected_size: u64 = take_flag_value(argv, "--update-expected-size")?
        .parse()
        .map_err(|_| AppError::Internal("Invalid --update-expected-size".to_string()))?;
    Ok(ApplyUpdateArgs {
        target: PathBuf::from(take_flag_value(argv, "--update-target")?),
        staged: PathBuf::from(take_flag_value(argv, "--update-staged")?),
        backup: PathBuf::from(take_flag_value(argv, "--update-backup")?),
        parent_pid,
        expected_sha256: take_flag_value(argv, "--update-expected-sha256")?,
        expected_size,
        result_file: PathBuf::from(take_flag_value(argv, "--update-result-file")?),
    })
}

fn failed_outcome(
    args: &ApplyUpdateArgs,
    message: String,
    rolled_back: bool,
) -> UpdateApplyOutcome {
    UpdateApplyOutcome {
        status: "failed".to_string(),
        version: String::new(),
        target: args.target.clone(),
        backup: if rolled_back {
            Some(args.backup.clone())
        } else {
            None
        },
        message,
        rolled_back,
    }
}

/// Helper entry point: wait for the parent to exit (observed as the target
/// becoming replaceable), apply with the default `--smoke` check, and
/// record the result file. Never touches the running UI process.
pub fn run_apply_update_cli(argv: &[String]) -> i32 {
    let args = match parse_apply_update_args(argv) {
        Ok(args) => args,
        Err(e) => {
            eprintln!("update helper: {}", e);
            return 2;
        }
    };
    if args.parent_pid == 0 {
        eprintln!("update helper: parent pid must be positive");
        return 2;
    }
    if args.backup.exists() {
        let outcome = failed_outcome(
            &args,
            "Backup path already exists; refusing to overwrite".to_string(),
            false,
        );
        let _ = write_update_result_to_path(&args.result_file, &outcome);
        eprintln!("update helper: {}", outcome.message);
        return 1;
    }
    let req = ApplyRequest {
        target: args.target.clone(),
        staged: args.staged.clone(),
        backup: args.backup.clone(),
        expected_sha256: args.expected_sha256.clone(),
        expected_size: args.expected_size,
        version: String::new(),
        smoke_check: None,
    };
    let deadline = Instant::now() + APPLY_WAIT_TIMEOUT;
    loop {
        match apply_staged_update(&req) {
            Ok(outcome) if outcome.status == "applied" => {
                let _ = write_update_result_to_path(&args.result_file, &outcome);
                return 0;
            }
            Ok(outcome)
                if outcome.message == "Could not replace target executable"
                    && Instant::now() < deadline =>
            {
                // Parent still alive (target locked): drop our partial
                // backup and retry until it exits or we time out.
                let _ = fs::remove_file(&args.backup);
                std::thread::sleep(Duration::from_millis(300));
                continue;
            }
            Ok(outcome) => {
                let _ = write_update_result_to_path(&args.result_file, &outcome);
                eprintln!("update helper: {}", outcome.message);
                return 1;
            }
            Err(e) => {
                let outcome = failed_outcome(&args, e.to_string(), false);
                let _ = write_update_result_to_path(&args.result_file, &outcome);
                eprintln!("update helper: {}", outcome.message);
                return 1;
            }
        }
    }
}
