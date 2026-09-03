use base64::Engine;
use base64::engine::general_purpose::URL_SAFE;
use serde::Deserialize;
use std::fs::File;
use std::io::BufReader;
use std::path::PathBuf;

use smartclipboard_native_lib::vault::{derive_key, Fernet};

#[derive(Deserialize)]
#[allow(dead_code)]
struct KdfParams {
    iterations: u32,
    key_length: usize,
    salt_b64: String,
}

#[derive(Deserialize)]
struct SampleItem {
    id: String,
    plaintext: String,
    ciphertext: String,
}

#[derive(Deserialize)]
struct NegativeCases {
    wrong_password: String,
    corrupted_token: String,
}

#[derive(Deserialize)]
struct GoldenVectors {
    kdf_params: KdfParams,
    master_password: String,
    derived_key_b64: String,
    verification_plaintext: String,
    verification_token: String,
    samples: Vec<SampleItem>,
    negative_cases: NegativeCases,
}

fn load_vectors() -> GoldenVectors {
    let path = PathBuf::from("../../tests/native_parity/fixtures/vault_golden_vectors.json");
    let file = File::open(&path).unwrap_or_else(|_| panic!("Failed to open golden vectors file: {:?}", path));
    let reader = BufReader::new(file);
    serde_json::from_reader(reader).expect("Failed to parse golden vectors JSON")
}

#[test]
fn test_pbkdf2_key_derivation_parity() {
    let vectors = load_vectors();
    let salt = URL_SAFE
        .decode(&vectors.kdf_params.salt_b64)
        .or_else(|_| base64::engine::general_purpose::STANDARD.decode(&vectors.kdf_params.salt_b64))
        .expect("Failed to decode salt");

    let derived_key = derive_key(&vectors.master_password, &salt).expect("derive_key failed");
    assert_eq!(
        derived_key, vectors.derived_key_b64,
        "Rust derived PBKDF2 key must match Python derived key exactly!"
    );
}

#[test]
fn test_python_encrypted_verification_token_decrypt_in_rust() {
    let vectors = load_vectors();
    let fernet = Fernet::from_b64_key(&vectors.derived_key_b64).expect("Valid Fernet key");

    let decrypted = fernet.decrypt(&vectors.verification_token).expect("Decryption failed");
    let decrypted_str = String::from_utf8(decrypted).expect("Valid UTF-8");
    assert_eq!(decrypted_str, vectors.verification_plaintext);
}

#[test]
fn test_python_encrypted_samples_decrypt_in_rust() {
    let vectors = load_vectors();
    let fernet = Fernet::from_b64_key(&vectors.derived_key_b64).expect("Valid Fernet key");

    for sample in vectors.samples {
        let decrypted = fernet.decrypt(&sample.ciphertext).unwrap_or_else(|e| {
            panic!("Failed to decrypt sample {}: {:?}", sample.id, e);
        });
        let decrypted_str = String::from_utf8(decrypted).unwrap();
        assert_eq!(
            decrypted_str, sample.plaintext,
            "Decrypted plaintext mismatch for sample: {}",
            sample.id
        );
    }
}

#[test]
fn test_rust_encrypt_decrypt_roundtrip() {
    let vectors = load_vectors();
    let fernet = Fernet::from_b64_key(&vectors.derived_key_b64).expect("Valid Fernet key");

    let message = "Roundtrip encryption test from Rust Native 2026!";
    let token = fernet.encrypt(message.as_bytes(), None, None).expect("Encryption failed");

    let decrypted = fernet.decrypt(&token).expect("Decryption failed");
    assert_eq!(String::from_utf8(decrypted).unwrap(), message);
}

#[test]
fn test_negative_cases() {
    let vectors = load_vectors();
    let salt = base64::engine::general_purpose::STANDARD
        .decode(&vectors.kdf_params.salt_b64)
        .expect("decode salt");

    let wrong_key = derive_key(&vectors.negative_cases.wrong_password, &salt).expect("derive key");
    let wrong_fernet = Fernet::from_b64_key(&wrong_key).expect("Fernet key");

    // Decrypting with wrong key must fail HMAC check
    let res = wrong_fernet.decrypt(&vectors.verification_token);
    assert!(res.is_err(), "Decryption with wrong password must fail!");

    // Decrypting corrupted token must fail
    let good_fernet = Fernet::from_b64_key(&vectors.derived_key_b64).expect("Fernet key");
    let res2 = good_fernet.decrypt(&vectors.negative_cases.corrupted_token);
    assert!(res2.is_err(), "Decryption of corrupted token must fail!");
}
