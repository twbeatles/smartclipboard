//! Signed release-manifest verification for the native updater (G-3).
//!
//! Ports `legacy/python/smartclipboard_core/update_manifest.py`: strict
//! version ordering, canonical-payload Ed25519 verification, manifest
//! policy validation (https-only artifact, sha256/size bounds, expiry,
//! newer-than-current) and a capped HTTPS manifest download.

use std::collections::BTreeMap;
use std::io::Read;
use std::time::{Duration, SystemTime};

use base64::Engine;
use ed25519_dalek::{Signature, Verifier, VerifyingKey};

use crate::errors::{AppError, Result};

pub const MANIFEST_MAX_BYTES: usize = 256 * 1024;
pub const MANIFEST_TIMEOUT_SECS: u64 = 20;
pub const ARTIFACT_MAX_BYTES: u64 = 500 * 1024 * 1024;
pub const UPDATE_USER_AGENT: &str = "SmartClipboard-Updater";

/// Default manifest feed for native Windows builds. Overridable with the
/// `SMARTCLIPBOARD_UPDATE_MANIFEST_URL` environment variable (same contract
/// as the Python edition).
pub const DEFAULT_MANIFEST_URL: &str =
    "https://raw.githubusercontent.com/twbeatles/smartclipboard/main/updates/latest-native.json";

pub fn default_manifest_url() -> String {
    std::env::var("SMARTCLIPBOARD_UPDATE_MANIFEST_URL")
        .ok()
        .filter(|v| !v.trim().is_empty())
        .unwrap_or_else(|| DEFAULT_MANIFEST_URL.to_string())
}

fn app_version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ReleaseManifest {
    pub version: String,
    pub artifact_url: String,
    pub artifact_sha256: String,
    pub artifact_size: u64,
    pub expires_at: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum UpdateCheck {
    /// A verified, newer release is available.
    Available(ReleaseManifest),
    /// Feed verified (or unreachable) but nothing newer to install.
    NoUpdate,
}

/// Split "10.7" / "10.7.0" into numeric components; non-numeric parts stop
/// the parse, mirroring the Python implementation.
fn parse_version_core(version: &str) -> Vec<u64> {
    let mut parts = Vec::new();
    for chunk in version.split('.') {
        let mut digits = String::new();
        for ch in chunk.chars() {
            if ch.is_ascii_digit() {
                digits.push(ch);
            } else {
                break;
            }
        }
        if digits.is_empty() {
            break;
        }
        match digits.parse::<u64>() {
            Ok(n) => parts.push(n),
            Err(_) => break,
        }
    }
    parts
}

fn compare_version(left: &str, right: &str) -> std::cmp::Ordering {
    let mut l = parse_version_core(left);
    let mut r = parse_version_core(right);
    let width = l.len().max(r.len()).max(1);
    l.resize(width, 0);
    r.resize(width, 0);
    l.cmp(&r)
}

/// Strictly-newer check. Invalid version strings raise instead of comparing.
pub fn is_newer_version(current: &str, candidate: &str) -> Result<bool> {
    if parse_version_core(current).is_empty() || parse_version_core(candidate).is_empty() {
        return Err(AppError::Internal(format!(
            "Invalid version string: {:?} -> {:?}",
            current, candidate
        )));
    }
    Ok(compare_version(current, candidate) == std::cmp::Ordering::Less)
}

/// Canonical payload bytes: UTF-8 JSON, keys sorted, compact separators.
/// Must stay byte-identical with the Python signer or signatures break.
pub fn canonical_manifest_payload(
    payload: &BTreeMap<String, serde_json::Value>,
) -> Result<Vec<u8>> {
    let text = serde_json::to_string(payload).map_err(|e| {
        AppError::Internal(format!("Manifest payload is not JSON serializable: {}", e))
    })?;
    Ok(text.into_bytes())
}

fn public_key_from_b64(public_key_b64: &str) -> Result<VerifyingKey> {
    let raw = base64::engine::general_purpose::STANDARD
        .decode(public_key_b64.trim())
        .map_err(|e| AppError::Internal(format!("Update public key is not valid base64: {}", e)))?;
    if raw.len() != 32 {
        return Err(AppError::Internal(
            "Update public key must decode to 32 bytes".to_string(),
        ));
    }
    let mut bytes = [0u8; 32];
    bytes.copy_from_slice(&raw);
    VerifyingKey::from_bytes(&bytes)
        .map_err(|e| AppError::Internal(format!("Update public key is invalid: {}", e)))
}

fn parse_expiry(expires_at: &str) -> Result<SystemTime> {
    let text = expires_at.trim();
    // RFC 3339 with offset first (covers the trailing-Z form).
    if let Ok(dt) = chrono::DateTime::parse_from_rfc3339(text) {
        return Ok(SystemTime::from(dt));
    }
    // Naive `YYYY-MM-DDTHH:MM:SS` is assumed UTC, like the Python fallback.
    if let Ok(naive) = chrono::NaiveDateTime::parse_from_str(text, "%Y-%m-%dT%H:%M:%S") {
        return Ok(SystemTime::from(naive.and_utc()));
    }
    Err(AppError::Internal(format!(
        "Manifest expiry is not a valid timestamp: {:?}",
        expires_at
    )))
}

fn validate_payload_policy(
    payload: &BTreeMap<String, serde_json::Value>,
    current_version: &str,
    now: SystemTime,
) -> Result<ReleaseManifest> {
    let get_str = |key: &str| -> Result<String> {
        match payload.get(key).and_then(|v| v.as_str()) {
            Some(s) => Ok(s.to_string()),
            None => Err(AppError::Internal(format!(
                "Manifest payload is missing {:?}",
                key
            ))),
        }
    };
    let version = get_str("version")?;
    let artifact_url = get_str("artifact_url")?;
    // Wire key is `sha256` (Python signer + shipped feed contract); the
    // struct field keeps the explicit `artifact_` prefix.
    let artifact_sha256 = get_str("sha256")?;
    let expires_at = get_str("expires_at")?;
    let artifact_size = match payload.get("size") {
        Some(serde_json::Value::Number(n)) => n.as_u64().ok_or_else(|| {
            AppError::Internal("Manifest artifact size must be a non-negative integer".to_string())
        })?,
        _ => {
            return Err(AppError::Internal(
                "Manifest artifact size must be a non-negative integer".to_string(),
            ))
        }
    };

    if !artifact_url.to_lowercase().starts_with("https://") {
        return Err(AppError::Internal(
            "Manifest artifact URL must use https".to_string(),
        ));
    }
    if artifact_sha256.len() != 64 || !artifact_sha256.chars().all(|c| c.is_ascii_hexdigit()) {
        return Err(AppError::Internal(
            "Manifest artifact sha256 must be 64 hex characters".to_string(),
        ));
    }
    if artifact_size == 0 || artifact_size > ARTIFACT_MAX_BYTES {
        return Err(AppError::Internal(format!(
            "Manifest artifact size out of range: {}",
            artifact_size
        )));
    }
    let expiry = parse_expiry(&expires_at)?;
    if expiry <= now {
        return Err(AppError::Internal(format!(
            "Manifest expired at {:?}",
            expires_at
        )));
    }
    if !is_newer_version(current_version, &version)? {
        return Err(AppError::UpdateNotNewer(version));
    }
    Ok(ReleaseManifest {
        version,
        artifact_url,
        artifact_sha256: artifact_sha256.to_lowercase(),
        artifact_size,
        expires_at,
    })
}

/// Verify a raw manifest document (`{"payload": {...}, "signature": "..."}`).
/// Returns the validated manifest, or `UpdateCheck::NoUpdate` semantics via
/// `AppError::UpdateNotNewer` when the feed is valid but not newer.
pub fn verify_release_manifest(
    document: &serde_json::Value,
    public_key_b64: &str,
    current_version: &str,
    now: SystemTime,
) -> Result<ReleaseManifest> {
    let obj = document
        .as_object()
        .ok_or_else(|| AppError::Internal("Manifest document must be a JSON object".to_string()))?;
    let payload_value = obj
        .get("payload")
        .ok_or_else(|| AppError::Internal("Manifest payload must be a JSON object".to_string()))?;
    let payload_map = payload_value
        .as_object()
        .ok_or_else(|| AppError::Internal("Manifest payload must be a JSON object".to_string()))?;
    let signature_b64 = obj
        .get("signature")
        .and_then(|v| v.as_str())
        .ok_or_else(|| {
            AppError::Internal("Manifest signature must be a base64 string".to_string())
        })?;

    // Canonical bytes must cover exactly the payload object.
    let ordered: BTreeMap<String, serde_json::Value> = payload_map
        .iter()
        .map(|(k, v)| (k.clone(), v.clone()))
        .collect();
    let canonical = canonical_manifest_payload(&ordered)?;
    let signature_raw = base64::engine::general_purpose::STANDARD
        .decode(signature_b64.trim())
        .map_err(|e| {
            AppError::Internal(format!("Manifest signature is not valid base64: {}", e))
        })?;
    let signature = Signature::from_slice(&signature_raw)
        .map_err(|e| AppError::Internal(format!("Manifest signature has invalid length: {}", e)))?;
    let public_key = public_key_from_b64(public_key_b64)?;
    public_key
        .verify(&canonical, &signature)
        .map_err(|_| AppError::Internal("Manifest signature verification failed".to_string()))?;

    validate_payload_policy(&ordered, current_version, now)
}

/// Check a manifest URL end-to-end: download, verify, compare versions.
/// Network or policy failures surface as `Err`, except "valid but not
/// newer", which returns `Ok(UpdateCheck::NoUpdate)`.
pub fn check_for_updates(
    manifest_url: &str,
    public_key_b64: &str,
    current_version: Option<&str>,
) -> Result<UpdateCheck> {
    let current = current_version
        .map(str::to_string)
        .unwrap_or_else(app_version);
    let document = download_manifest(manifest_url)?;
    let now = SystemTime::now();
    match verify_release_manifest(&document, public_key_b64, &current, now) {
        Ok(manifest) => Ok(UpdateCheck::Available(manifest)),
        Err(AppError::UpdateNotNewer(_)) => Ok(UpdateCheck::NoUpdate),
        Err(e) => Err(e),
    }
}

/// HTTPS GET with no automatic redirects: up to 5 manual hops, each
/// re-validated as https (mirrors the Python `urlopen` final-URL check).
/// Shared by the manifest (`what = "Manifest"`) and artifact downloads.
fn is_https_url(url: &str) -> bool {
    url::Url::parse(url)
        .map(|parsed| parsed.scheme() == "https" && parsed.host_str().is_some())
        .unwrap_or(false)
}

pub fn fetch_https(url: &str, accept: &str, what: &str) -> Result<ureq::Response> {
    let https_err = || AppError::Internal(format!("{} URL must be an https URL", what));
    if !is_https_url(url) {
        return Err(https_err());
    }
    let agent = ureq::AgentBuilder::new()
        .timeout_connect(Duration::from_secs(10))
        .timeout_read(Duration::from_secs(MANIFEST_TIMEOUT_SECS))
        .redirects(0)
        .build();
    let mut current = url.to_string();
    for _ in 0..=5 {
        if !is_https_url(&current) {
            return Err(https_err());
        }
        let response = match agent
            .get(&current)
            .set("User-Agent", UPDATE_USER_AGENT)
            .set("Accept", accept)
            .call()
        {
            Ok(resp) => resp,
            Err(ureq::Error::Status(code, _)) => {
                return Err(AppError::Internal(format!(
                    "{} download failed with http status {}",
                    what, code
                )));
            }
            Err(e) => {
                return Err(AppError::Internal(format!(
                    "{} download failed: {}",
                    what, e
                )));
            }
        };
        let status = response.status();
        if (300..400).contains(&status) {
            let location = response.header("location").unwrap_or("").trim().to_string();
            if location.is_empty() {
                return Err(AppError::Internal(format!(
                    "{} redirect missing location",
                    what
                )));
            }
            let base = url::Url::parse(&current).map_err(|_| https_err())?;
            let joined = base
                .join(&location)
                .map_err(|_| AppError::Internal(format!("{} redirect missing location", what)))?;
            current = joined.to_string();
            continue;
        }
        if !(200..300).contains(&status) {
            return Err(AppError::Internal(format!(
                "{} download failed with http status {}",
                what, status
            )));
        }
        return Ok(response);
    }
    Err(AppError::Internal(format!(
        "{} redirect chain too long",
        what
    )))
}

/// Download and parse the manifest with size cap, timeout and
/// https-only (re)directs.
pub fn download_manifest(manifest_url: &str) -> Result<serde_json::Value> {
    let response = fetch_https(manifest_url, "application/json", "Manifest")?;
    let mut limited = response.into_reader().take(MANIFEST_MAX_BYTES as u64 + 1);
    let mut buf = Vec::new();
    limited
        .read_to_end(&mut buf)
        .map_err(|e| AppError::Internal(format!("Manifest download failed: {}", e)))?;
    if buf.len() > MANIFEST_MAX_BYTES {
        return Err(AppError::Internal(format!(
            "Manifest exceeds size limit of {} bytes",
            MANIFEST_MAX_BYTES
        )));
    }
    let document: serde_json::Value = serde_json::from_slice(&buf)
        .map_err(|e| AppError::Internal(format!("Manifest is not valid JSON: {}", e)))?;
    Ok(document)
}
