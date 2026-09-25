//! Native auto-update: signed-manifest check, staged download and
//! atomic apply with backup/rollback (G-3).
//!
//! Ports the Python `update_manifest` + `update_installer` contract,
//! including the Ed25519 canonical-payload signature, manifest policy,
//! same-directory backup, smoke check, backup rotation and the result
//! file handshake consumed at the next startup.

pub mod installer;
pub mod manifest;

pub use installer::{
    apply_staged_update, cleanup_old_backups, consume_update_result, default_public_key_b64,
    download_artifact_to_stage, launch_update_helper, parse_apply_update_args,
    resolve_update_staging_root, run_apply_update_cli, stage_artifact, write_update_result,
    write_update_result_to_path, ApplyRequest, ApplyUpdateArgs, SmokeCheck, StagedArtifact,
    UpdateApplyOutcome, APPLY_WAIT_TIMEOUT, ARTIFACT_CHUNK_BYTES, BACKUP_KEEP_COUNT, SMOKE_TIMEOUT,
    UPDATE_RESULT_FILENAME, UPDATE_STAGING_DIRNAME,
};
pub use manifest::{
    canonical_manifest_payload, check_for_updates, default_manifest_url, download_manifest,
    fetch_https, is_newer_version, verify_release_manifest, ReleaseManifest, UpdateCheck,
    ARTIFACT_MAX_BYTES, MANIFEST_MAX_BYTES, MANIFEST_TIMEOUT_SECS, UPDATE_USER_AGENT,
};

/// Embedded release-signing public key (fallback when the
/// `SMARTCLIPBOARD_UPDATE_PUBLIC_KEY_B64` environment variable is unset).
/// Public key material only; safe to ship in the binary.
pub const EMBEDDED_UPDATE_PUBLIC_KEY_B64: &str = "EV71tLaj1Qk4keGFCw3FKmVP7w96sUFDq7D0nJsNyC8=";

/// Resolve the verification key: environment override first, then the
/// embedded release key.
pub fn resolve_public_key_b64() -> Option<String> {
    default_public_key_b64().or_else(|| Some(EMBEDDED_UPDATE_PUBLIC_KEY_B64.to_string()))
}
