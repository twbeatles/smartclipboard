//! Tauri commands for the signed auto-update flow (G-3).
//!
//! Mirrors the Python `UpdaterController` workflow: check the signed feed,
//! download + stage the artifact, then hand off to a detached helper copy
//! that applies the update after this process exits. The pending result is
//! consumed at the next startup.

use std::fs;
use std::path::PathBuf;

use serde::Serialize;
use tauri::AppHandle;

use crate::errors::{AppError, Result};
use crate::updater::{
    check_for_updates, consume_update_result, default_manifest_url, download_artifact_to_stage,
    launch_update_helper, resolve_public_key_b64, resolve_update_staging_root, UpdateCheck,
    UPDATE_RESULT_FILENAME,
};

fn current_version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

fn resolve_key() -> Result<String> {
    resolve_public_key_b64()
        .ok_or_else(|| AppError::Internal("No update signing key available".to_string()))
}

fn install_dir() -> Result<PathBuf> {
    let exe = std::env::current_exe()
        .map_err(|e| AppError::Internal(format!("Cannot locate current executable: {}", e)))?;
    exe.parent()
        .map(|p| p.to_path_buf())
        .ok_or_else(|| AppError::Internal("Current executable has no parent directory".to_string()))
}

fn dev_guard() -> Result<()> {
    if tauri::is_dev() {
        return Err(AppError::Internal(
            "Self-update is only available in release builds".to_string(),
        ));
    }
    Ok(())
}

#[derive(Debug, Clone, Serialize)]
pub struct UpdateCheckDto {
    pub status: String,
    pub current_version: String,
    pub version: Option<String>,
    pub artifact_url: Option<String>,
    pub artifact_size: Option<u64>,
    pub expires_at: Option<String>,
}

impl UpdateCheckDto {
    fn from_check(check: UpdateCheck, current_version: String) -> Self {
        match check {
            UpdateCheck::Available(manifest) => Self {
                status: "available".to_string(),
                current_version,
                version: Some(manifest.version),
                artifact_url: Some(manifest.artifact_url),
                artifact_size: Some(manifest.artifact_size),
                expires_at: Some(manifest.expires_at),
            },
            UpdateCheck::NoUpdate => Self {
                status: "no_update".to_string(),
                current_version,
                version: None,
                artifact_url: None,
                artifact_size: None,
                expires_at: None,
            },
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct UpdateDownloadDto {
    pub version: String,
    pub staged_path: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct UpdateApplyDto {
    pub status: String,
    pub version: String,
}

/// Check the signed release feed. Never touches the running binary.
#[tauri::command]
pub async fn update_check() -> Result<UpdateCheckDto> {
    let url = default_manifest_url();
    let key = resolve_key()?;
    let current = current_version();
    let check =
        tauri::async_runtime::spawn_blocking(move || check_for_updates(&url, &key, Some(&current)))
            .await
            .map_err(|e| AppError::Internal(format!("Update check task failed: {}", e)))??;
    Ok(UpdateCheckDto::from_check(check, current_version()))
}

/// Download and stage the verified artifact. Refused in dev builds.
#[tauri::command]
pub async fn update_download() -> Result<UpdateDownloadDto> {
    dev_guard()?;
    let url = default_manifest_url();
    let key = resolve_key()?;
    let current = current_version();
    let dir = install_dir()?;
    tauri::async_runtime::spawn_blocking(move || {
        let manifest = match check_for_updates(&url, &key, Some(&current))? {
            UpdateCheck::Available(manifest) => manifest,
            UpdateCheck::NoUpdate => {
                return Err(AppError::Internal(
                    "No verified update available".to_string(),
                ))
            }
        };
        let staging_root = resolve_update_staging_root(&dir);
        let staged = download_artifact_to_stage(&manifest, &staging_root)?;
        Ok(UpdateDownloadDto {
            version: manifest.version,
            staged_path: staged.path.to_string_lossy().into_owned(),
        })
    })
    .await
    .map_err(|e| AppError::Internal(format!("Update download task failed: {}", e)))?
}

/// Hand a staged artifact to the detached helper and quit via
/// `quit_for_update`. The helper re-validates, applies, smoke-checks and
/// records the result file for the next startup.
#[tauri::command]
pub async fn update_apply(staged_path: String) -> Result<UpdateApplyDto> {
    dev_guard()?;
    let url = default_manifest_url();
    let key = resolve_key()?;
    let current = current_version();
    let dir = install_dir()?;
    tauri::async_runtime::spawn_blocking(move || {
        let manifest = match check_for_updates(&url, &key, Some(&current))? {
            UpdateCheck::Available(manifest) => manifest,
            UpdateCheck::NoUpdate => {
                return Err(AppError::Internal(
                    "No verified update available".to_string(),
                ))
            }
        };
        let staged = PathBuf::from(&staged_path);
        if !staged.is_file() {
            return Err(AppError::Internal(
                "Staged update file is missing".to_string(),
            ));
        }
        let exe = std::env::current_exe()
            .map_err(|e| AppError::Internal(format!("Cannot locate current executable: {}", e)))?;
        let exe_name = exe
            .file_name()
            .and_then(|n| n.to_str())
            .ok_or_else(|| AppError::Internal("Invalid executable name".to_string()))?;
        // Same-directory .exe copy: satisfies the apply path policy, and the
        // helper re-verifies size + sha256 against the fresh manifest.
        let dest = dir.join(format!("SmartClipboard-Update-v{}.exe", manifest.version));
        fs::copy(&staged, &dest)
            .map_err(|e| AppError::Internal(format!("Cannot prepare staged update: {}", e)))?;
        let backup = dir.join(format!(
            "{}.v{}.{}.bak",
            exe_name,
            manifest.version,
            std::process::id()
        ));
        let staging_root = resolve_update_staging_root(&dir);
        fs::create_dir_all(&staging_root)
            .map_err(|e| AppError::Internal(format!("Cannot create staging dir: {}", e)))?;
        let helper = staging_root.join(format!("update-helper-{}.exe", std::process::id()));
        let result_file = staging_root.join(UPDATE_RESULT_FILENAME);
        let args = vec![
            "--apply-update".to_string(),
            "--update-target".to_string(),
            exe.to_string_lossy().into_owned(),
            "--update-staged".to_string(),
            dest.to_string_lossy().into_owned(),
            "--update-backup".to_string(),
            backup.to_string_lossy().into_owned(),
            "--update-parent-pid".to_string(),
            std::process::id().to_string(),
            "--update-expected-sha256".to_string(),
            manifest.artifact_sha256.clone(),
            "--update-expected-size".to_string(),
            manifest.artifact_size.to_string(),
            "--update-result-file".to_string(),
            result_file.to_string_lossy().into_owned(),
        ];
        launch_update_helper(&exe, &helper, &args)?;
        Ok(UpdateApplyDto {
            status: "helper_launched".to_string(),
            version: manifest.version,
        })
    })
    .await
    .map_err(|e| AppError::Internal(format!("Update apply task failed: {}", e)))?
}

/// Read and consume the helper's result file from the previous run.
#[tauri::command]
pub async fn update_pending_result() -> Result<Option<crate::updater::UpdateApplyOutcome>> {
    let dir = install_dir()?;
    tauri::async_runtime::spawn_blocking(move || {
        consume_update_result(&resolve_update_staging_root(&dir))
    })
    .await
    .map_err(|e| AppError::Internal(format!("Update result task failed: {}", e)))?
}

/// Exit so the launched update helper can replace the binary.
#[tauri::command]
pub async fn quit_for_update(app: AppHandle) -> Result<()> {
    app.exit(0);
    #[allow(unreachable_code)]
    Ok(())
}
