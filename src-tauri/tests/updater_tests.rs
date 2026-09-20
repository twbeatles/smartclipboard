//! G-3 regression tests: signed-manifest verification policy and the
//! staged-apply protocol. Fully hermetic (no network); the release-feed
//! test pins the shipped `updates/latest.json` signature.

use std::collections::BTreeMap;
use std::fs;
use std::io::Cursor;
use std::path::Path;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use ed25519_dalek::{Signer, SigningKey};
use smartclipboard_native_lib::errors::AppError;
use smartclipboard_native_lib::updater::{
    apply_staged_update, canonical_manifest_payload, cleanup_old_backups, consume_update_result,
    default_manifest_url, fetch_https, is_newer_version, parse_apply_update_args,
    resolve_update_staging_root, stage_artifact, verify_release_manifest, write_update_result,
    write_update_result_to_path, ApplyRequest, ReleaseManifest, UpdateApplyOutcome,
    ARTIFACT_MAX_BYTES, EMBEDDED_UPDATE_PUBLIC_KEY_B64,
};
use tempfile::TempDir;

const TEST_SEED: [u8; 32] = [
    0x9d, 0x61, 0xb1, 0x9d, 0xef, 0xfd, 0x5a, 0x60, 0xba, 0x84, 0x4a, 0xf4, 0x92, 0xec, 0x2c, 0xc4,
    0x44, 0x49, 0xc5, 0x69, 0x7b, 0x32, 0x69, 0x19, 0x70, 0x3b, 0x80, 0xbf, 0xd6, 0x2f, 0x0c, 0xdb,
];

fn test_keypair() -> (SigningKey, String) {
    let signing = SigningKey::from_bytes(&TEST_SEED);
    let verifying = signing.verifying_key();
    let public_b64 = base64_engine_encode(verifying.as_bytes());
    (signing, public_b64)
}

fn base64_engine_encode(bytes: &[u8]) -> String {
    // Standard-base64 without pulling base64 into test imports gymnastics:
    // reuse the crate under test through a signed roundtrip instead.
    // (Implemented manually to keep the test dependency surface minimal.)
    const ALPHABET: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::new();
    for chunk in bytes.chunks(3) {
        let mut n: u32 = 0;
        for (i, b) in chunk.iter().enumerate() {
            n |= (*b as u32) << (16 - 8 * i);
        }
        let pad = 3 - chunk.len();
        for i in 0..(4 - pad) {
            out.push(ALPHABET[((n >> (18 - 6 * i)) & 63) as usize] as char);
        }
        for _ in 0..pad {
            out.push('=');
        }
    }
    out
}

fn payload_fixture() -> BTreeMap<String, serde_json::Value> {
    let mut map = BTreeMap::new();
    map.insert(
        "artifact_url".to_string(),
        serde_json::Value::String("https://github.com/twbeatles/smartclipboard/releases/download/v10.8/SmartClipboard-v10.8.exe".to_string()),
    );
    map.insert(
        "expires_at".to_string(),
        serde_json::Value::String("2030-01-01T00:00:00Z".to_string()),
    );
    map.insert(
        "sha256".to_string(),
        serde_json::Value::String(
            "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08".to_string(),
        ),
    );
    map.insert(
        "size".to_string(),
        serde_json::Value::Number(serde_json::Number::from(41u64)),
    );
    map.insert(
        "version".to_string(),
        serde_json::Value::String("10.8".to_string()),
    );
    map
}

fn sign_doc(
    signing: &SigningKey,
    payload: BTreeMap<String, serde_json::Value>,
) -> serde_json::Value {
    let canonical = canonical_manifest_payload(&payload).expect("canonical");
    let signature = signing.sign(&canonical);
    let mut obj = serde_json::Map::new();
    obj.insert(
        "payload".to_string(),
        serde_json::Value::Object(
            payload
                .into_iter()
                .collect::<serde_json::Map<String, serde_json::Value>>(),
        ),
    );
    obj.insert(
        "signature".to_string(),
        serde_json::Value::String(base64_engine_encode(&signature.to_bytes())),
    );
    serde_json::Value::Object(obj)
}

fn fixed_now() -> SystemTime {
    // 2026-09-20T00:00:00Z, safely before the 2030 fixture expiry.
    UNIX_EPOCH + Duration::from_secs(1_758_931_200)
}

#[test]
fn test_version_ordering() {
    assert!(is_newer_version("10.7", "10.8").expect("cmp"));
    assert!(!is_newer_version("10.8", "10.7").expect("cmp"));
    assert!(!is_newer_version("10.7", "10.7").expect("cmp"));
    assert!(!is_newer_version("10.7", "10.7.0").expect("cmp"));
    assert!(is_newer_version("10.7", "10.7.1").expect("cmp"));
    assert!(is_newer_version("9.9.9", "10.0").expect("cmp"));
    assert!(is_newer_version("abc", "10.8").is_err());
    assert!(is_newer_version("10.7", "").is_err());
}

#[test]
fn test_canonical_payload_byte_layout() {
    // Byte-exact contract with the Python signer: sorted keys, compact
    // separators, unescaped UTF-8.
    let payload = payload_fixture();
    let canonical = canonical_manifest_payload(&payload).expect("canonical");
    let text = String::from_utf8(canonical).expect("utf8");
    assert_eq!(
        text,
        "{\"artifact_url\":\"https://github.com/twbeatles/smartclipboard/releases/download/v10.8/SmartClipboard-v10.8.exe\",\"expires_at\":\"2030-01-01T00:00:00Z\",\"sha256\":\"9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08\",\"size\":41,\"version\":\"10.8\"}"
    );
}

#[test]
fn test_verify_roundtrip_and_tamper_rejection() {
    let (signing, public_b64) = test_keypair();
    let doc = sign_doc(&signing, payload_fixture());
    let manifest = verify_release_manifest(&doc, &public_b64, "10.7", fixed_now()).expect("verify");
    assert_eq!(manifest.version, "10.8");
    assert_eq!(manifest.artifact_size, 41);

    // Any payload tampering breaks the signature, not the policy checks.
    let mut tampered = doc.clone();
    tampered["payload"]["size"] = serde_json::Value::Number(serde_json::Number::from(42u64));
    let err = verify_release_manifest(&tampered, &public_b64, "10.7", fixed_now())
        .expect_err("tamper must fail");
    assert!(
        err.to_string().contains("signature verification failed"),
        "unexpected error: {}",
        err
    );

    // Wrong key also fails at the signature, not later.
    let wrong_signing = SigningKey::from_bytes(&[8u8; 32]);
    let wrong_b64 = base64_engine_encode(wrong_signing.verifying_key().as_bytes());
    let err = verify_release_manifest(&doc, &wrong_b64, "10.7", fixed_now())
        .expect_err("wrong key must fail");
    assert!(err.to_string().contains("signature verification failed"));
}

#[test]
fn test_verify_policy_rejections() {
    let (signing, public_b64) = test_keypair();

    // Not newer than current.
    let doc = sign_doc(&signing, payload_fixture());
    match verify_release_manifest(&doc, &public_b64, "10.8", fixed_now()) {
        Err(AppError::UpdateNotNewer(v)) => assert_eq!(v, "10.8"),
        other => panic!("expected UpdateNotNewer, got {:?}", other),
    }

    // Expired feed.
    let mut expired_payload = payload_fixture();
    expired_payload.insert(
        "expires_at".to_string(),
        serde_json::Value::String("2020-01-01T00:00:00Z".to_string()),
    );
    let err = verify_release_manifest(
        &sign_doc(&signing, expired_payload),
        &public_b64,
        "10.7",
        fixed_now(),
    )
    .expect_err("expired must fail");
    assert!(err.to_string().contains("expired"), "got: {}", err);

    // Non-https artifact URL.
    let mut http_payload = payload_fixture();
    http_payload.insert(
        "artifact_url".to_string(),
        serde_json::Value::String("http://evil.example/x.exe".to_string()),
    );
    let err = verify_release_manifest(
        &sign_doc(&signing, http_payload),
        &public_b64,
        "10.7",
        fixed_now(),
    )
    .expect_err("http url must fail");
    assert!(err.to_string().contains("https"), "got: {}", err);

    // Malformed sha256.
    let mut bad_sha = payload_fixture();
    bad_sha.insert(
        "sha256".to_string(),
        serde_json::Value::String("xyz".to_string()),
    );
    let err = verify_release_manifest(
        &sign_doc(&signing, bad_sha),
        &public_b64,
        "10.7",
        fixed_now(),
    )
    .expect_err("bad sha256 must fail");
    assert!(err.to_string().contains("sha256"), "got: {}", err);

    // Zero size.
    let mut zero_size = payload_fixture();
    zero_size.insert(
        "size".to_string(),
        serde_json::Value::Number(serde_json::Number::from(0u64)),
    );
    let err = verify_release_manifest(
        &sign_doc(&signing, zero_size),
        &public_b64,
        "10.7",
        fixed_now(),
    )
    .expect_err("zero size must fail");
    assert!(err.to_string().contains("size"), "got: {}", err);

    // Oversized artifact.
    let mut huge_size = payload_fixture();
    huge_size.insert(
        "size".to_string(),
        serde_json::Value::Number(serde_json::Number::from(ARTIFACT_MAX_BYTES + 1)),
    );
    let err = verify_release_manifest(
        &sign_doc(&signing, huge_size),
        &public_b64,
        "10.7",
        fixed_now(),
    )
    .expect_err("oversize must fail");
    assert!(err.to_string().contains("size"), "got: {}", err);
}

#[test]
fn test_shipped_release_feed_verifies() {
    // Pins the real updates/latest.json signature. If the feed has aged
    // past expiry the signature itself must still verify; only the expiry
    // verdict is allowed to change.
    let text = fs::read_to_string("../updates/latest.json").expect("read shipped manifest");
    let doc: serde_json::Value = serde_json::from_str(&text).expect("parse manifest");
    match verify_release_manifest(
        &doc,
        EMBEDDED_UPDATE_PUBLIC_KEY_B64,
        "10.0",
        SystemTime::now(),
    ) {
        Ok(manifest) => assert!(!manifest.version.is_empty()),
        Err(AppError::Internal(msg)) if msg.contains("expired") => {}
        Err(e) => panic!("shipped manifest must verify: {}", e),
    }
}

#[test]
fn test_shipped_native_feed_verifies_when_present() {
    // Published by the release workflow; absent on a fresh checkout.
    let path = "../updates/latest-native.json";
    if !Path::new(path).exists() {
        return;
    }
    let text = fs::read_to_string(path).expect("read native manifest");
    let doc: serde_json::Value = serde_json::from_str(&text).expect("parse manifest");
    match verify_release_manifest(
        &doc,
        EMBEDDED_UPDATE_PUBLIC_KEY_B64,
        "10.0",
        SystemTime::now(),
    ) {
        Ok(manifest) => assert!(!manifest.version.is_empty()),
        Err(AppError::Internal(msg)) if msg.contains("expired") => {}
        Err(e) => panic!("shipped native manifest must verify: {}", e),
    }
}

#[test]
fn test_default_manifest_url_override() {
    // Default points at the native feed; env override wins.
    let saved = std::env::var("SMARTCLIPBOARD_UPDATE_MANIFEST_URL").ok();
    std::env::remove_var("SMARTCLIPBOARD_UPDATE_MANIFEST_URL");
    assert!(default_manifest_url().ends_with("updates/latest-native.json"));
    std::env::set_var(
        "SMARTCLIPBOARD_UPDATE_MANIFEST_URL",
        "https://example.com/custom.json",
    );
    assert_eq!(default_manifest_url(), "https://example.com/custom.json");
    std::env::remove_var("SMARTCLIPBOARD_UPDATE_MANIFEST_URL");
    if let Some(value) = saved {
        std::env::set_var("SMARTCLIPBOARD_UPDATE_MANIFEST_URL", value);
    }
}

fn manifest_for_bytes(body: &[u8]) -> ReleaseManifest {
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    hasher.update(body);
    let digest = hasher.finalize();
    let mut hex = String::new();
    for b in digest {
        hex.push_str(&format!("{:02x}", b));
    }
    ReleaseManifest {
        version: "10.8".to_string(),
        artifact_url: "https://github.com/twbeatles/smartclipboard/releases/download/v10.8/x.exe"
            .to_string(),
        artifact_sha256: hex,
        artifact_size: body.len() as u64,
        expires_at: "2030-01-01T00:00:00Z".to_string(),
    }
}

#[test]
fn test_stage_artifact_exact_and_mismatch() {
    let dir = TempDir::new().expect("tempdir");
    let body = b"fake-installer-bytes-0123456789";
    let manifest = manifest_for_bytes(body);

    let staged =
        stage_artifact(&manifest, Cursor::new(body.to_vec()), dir.path()).expect("stage exact");
    assert!(staged.path.exists());
    assert_eq!(fs::read(&staged.path).expect("read"), body);

    // Declared size larger than the stream: mismatch, staged file removed.
    let mut big_manifest = manifest.clone();
    big_manifest.artifact_size += 1;
    assert!(stage_artifact(&big_manifest, Cursor::new(body.to_vec()), dir.path()).is_err());

    // Corrupt byte: sha mismatch, staged file removed.
    let mut corrupt = body.to_vec();
    corrupt[0] ^= 0xff;
    assert!(stage_artifact(&manifest, Cursor::new(corrupt), dir.path()).is_err());

    // Oversized stream aborts even when the hash would match a prefix.
    let mut oversize = manifest.clone();
    oversize.artifact_size = 4;
    assert!(stage_artifact(&oversize, Cursor::new(body.to_vec()), dir.path()).is_err());
}

fn write_exe(dir: &std::path::Path, name: &str, content: &[u8]) -> std::path::PathBuf {
    let path = dir.join(name);
    fs::write(&path, content).expect("write exe");
    path
}

#[test]
fn test_apply_success_and_rollback() {
    let dir = TempDir::new().expect("tempdir");
    let target = write_exe(dir.path(), "App.exe", b"v10.7-binary");
    let staged = write_exe(dir.path(), "App-Staged.exe", b"v10.8-binary");
    let backup = dir.path().join("App.exe.v10.8.bak");
    let staged_manifest = manifest_for_bytes(b"v10.8-binary");

    let req = ApplyRequest {
        target: target.clone(),
        staged: staged.clone(),
        backup: backup.clone(),
        expected_sha256: staged_manifest.artifact_sha256.clone(),
        expected_size: staged_manifest.artifact_size,
        version: "10.8".to_string(),
        smoke_check: Some(Box::new(|_| true)),
    };
    let outcome = apply_staged_update(&req).expect("apply");
    assert_eq!(outcome.status, "applied");
    assert!(!outcome.rolled_back);
    assert_eq!(fs::read(&target).expect("read"), b"v10.8-binary");
    assert_eq!(fs::read(&backup).expect("read"), b"v10.7-binary");
    assert!(!staged.exists());

    // Failing smoke check restores the previous binary.
    let target2 = write_exe(dir.path(), "Tool.exe", b"old-tool");
    let staged2 = write_exe(dir.path(), "Tool-Staged.exe", b"new-tool");
    let backup2 = dir.path().join("Tool.exe.v10.8.bak");
    let manifest2 = manifest_for_bytes(b"new-tool");
    let req2 = ApplyRequest {
        target: target2.clone(),
        staged: staged2,
        backup: backup2.clone(),
        expected_sha256: manifest2.artifact_sha256,
        expected_size: manifest2.artifact_size,
        version: "10.8".to_string(),
        smoke_check: Some(Box::new(|_| false)),
    };
    let outcome2 = apply_staged_update(&req2).expect("apply fails");
    assert_eq!(outcome2.status, "failed");
    assert!(outcome2.rolled_back);
    assert_eq!(fs::read(&target2).expect("read"), b"old-tool");
    assert!(!backup2.exists());
}

#[test]
fn test_apply_refuses_unsafe_layouts() {
    let dir = TempDir::new().expect("tempdir");
    let target = write_exe(dir.path(), "App.exe", b"old");
    let staged = write_exe(dir.path(), "App-Staged.exe", b"new");
    let manifest = manifest_for_bytes(b"new");
    let base = ApplyRequest {
        target: target.clone(),
        staged: staged.clone(),
        backup: dir.path().join("App.exe.v9.bak"),
        expected_sha256: manifest.artifact_sha256.clone(),
        expected_size: manifest.artifact_size,
        version: "9.0".to_string(),
        smoke_check: Some(Box::new(|_| true)),
    };

    // Non-exe target.
    let txt = write_exe(dir.path(), "notes.txt", b"old");
    let mut bad = ApplyRequest {
        target: txt,
        staged: staged.clone(),
        backup: dir.path().join("notes.txt.v9.bak"),
        expected_sha256: manifest.artifact_sha256.clone(),
        expected_size: manifest.artifact_size,
        version: "9.0".to_string(),
        smoke_check: Some(Box::new(|_| true)),
    };
    assert_eq!(apply_staged_update(&bad).expect("refuse").status, "failed");

    // Identical paths.
    bad = ApplyRequest {
        target: target.clone(),
        staged: target.clone(),
        backup: dir.path().join("App.exe.v9.bak"),
        expected_sha256: manifest.artifact_sha256.clone(),
        expected_size: manifest.artifact_size,
        version: "9.0".to_string(),
        smoke_check: Some(Box::new(|_| true)),
    };
    assert_eq!(apply_staged_update(&bad).expect("refuse").status, "failed");

    // Pre-existing backup is never overwritten.
    fs::write(dir.path().join("App.exe.v9.bak"), b"someone").expect("write");
    assert_eq!(apply_staged_update(&base).expect("refuse").status, "failed");
    assert_eq!(
        fs::read(target).expect("read"),
        b"old",
        "target untouched on refusal"
    );
}

#[test]
fn test_result_write_consume_roundtrip() {
    let dir = TempDir::new().expect("tempdir");
    assert_eq!(consume_update_result(dir.path()).expect("consume"), None);

    let outcome = UpdateApplyOutcome {
        status: "applied".to_string(),
        version: "10.8".to_string(),
        target: dir.path().join("App.exe"),
        backup: Some(dir.path().join("App.exe.v10.8.bak")),
        message: String::new(),
        rolled_back: false,
    };
    write_update_result(dir.path(), &outcome).expect("write");
    let back = consume_update_result(dir.path())
        .expect("consume")
        .expect("present");
    assert_eq!(back, outcome);
    assert_eq!(consume_update_result(dir.path()).expect("consume"), None);

    fs::write(
        dir.path().join("last-update-result.json"),
        "{\"status\": \"mystery\"}",
    )
    .expect("write");
    assert!(consume_update_result(dir.path()).is_err());
}

#[test]
fn test_staging_root_resolution() {
    assert_eq!(
        resolve_update_staging_root(Path::new("C:/Program Files/App")),
        Path::new("C:/Program Files/App/.updates")
    );
}

#[test]
fn test_result_path_writer_roundtrip() {
    let dir = TempDir::new().expect("tempdir");
    let outcome = UpdateApplyOutcome {
        status: "applied".to_string(),
        version: "10.8".to_string(),
        target: dir.path().join("App.exe"),
        backup: None,
        message: String::new(),
        rolled_back: false,
    };
    let custom = dir.path().join("sub").join("result.json");
    let written = write_update_result_to_path(&custom, &outcome).expect("write");
    assert_eq!(written, custom);
    let doc: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(&custom).expect("read")).expect("json");
    assert_eq!(doc["status"], "applied");
    assert_eq!(doc["version"], "10.8");
    assert_eq!(doc["rolled_back"], false);
}

fn apply_cli_argv() -> Vec<String> {
    [
        "--update-target",
        "C:/App/SmartClipboard.exe",
        "--update-staged",
        "C:/App/SmartClipboard-Update-v10.8.exe",
        "--update-backup",
        "C:/App/SmartClipboard.exe.v10.8.1.bak",
        "--update-parent-pid",
        "1234",
        "--update-expected-sha256",
        "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
        "--update-expected-size",
        "41",
        "--update-result-file",
        "C:/App/.updates/last-update-result.json",
    ]
    .iter()
    .map(|s| s.to_string())
    .collect()
}

#[test]
fn test_parse_apply_update_args() {
    let args = parse_apply_update_args(&apply_cli_argv()).expect("parse");
    assert_eq!(args.target, Path::new("C:/App/SmartClipboard.exe"));
    assert_eq!(args.parent_pid, 1234);
    assert_eq!(args.expected_size, 41);
    assert_eq!(
        args.result_file,
        Path::new("C:/App/.updates/last-update-result.json")
    );

    assert!(parse_apply_update_args(&[]).is_err());

    let mut bad_pid = apply_cli_argv();
    let pos = bad_pid
        .iter()
        .position(|a| a == "--update-parent-pid")
        .expect("flag");
    bad_pid[pos + 1] = "not-a-pid".to_string();
    assert!(parse_apply_update_args(&bad_pid).is_err());

    let truncated = apply_cli_argv();
    let truncated = &truncated[..truncated.len() - 2];
    assert!(parse_apply_update_args(truncated).is_err());
}

#[test]
fn test_fetch_https_rejects_plain_http_without_network() {
    // Policy rejection happens before any socket I/O: hermetic.
    let err = fetch_https(
        "http://example.com/x.exe",
        "application/octet-stream",
        "Artifact",
    )
    .expect_err("http must be rejected");
    assert!(err.to_string().contains("https"), "got: {}", err);
}

#[test]
fn test_cleanup_old_backups_keeps_two() {
    let dir = TempDir::new().expect("tempdir");
    let target = write_exe(dir.path(), "App.exe", b"x");
    assert_eq!(target.file_name().unwrap(), "App.exe");
    for name in [
        "App.exe.v10.5.bak",
        "App.exe.v10.6.bak",
        "App.exe.v10.7.bak",
        "App.exe.v10.8.bak",
    ] {
        fs::write(dir.path().join(name), b"old").expect("write");
        std::thread::sleep(Duration::from_millis(30));
    }
    cleanup_old_backups(&target, 2);
    let remaining: Vec<String> = fs::read_dir(dir.path())
        .expect("read")
        .flatten()
        .map(|e| e.file_name().to_string_lossy().into_owned())
        .filter(|n| n.ends_with(".bak"))
        .collect();
    assert_eq!(remaining.len(), 2, "keeps newest two: {:?}", remaining);
    assert!(remaining.contains(&"App.exe.v10.8.bak".to_string()));
}
