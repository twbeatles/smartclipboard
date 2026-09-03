use aes::cipher::block_padding::Pkcs7;
use aes::cipher::{BlockDecryptMut, BlockEncryptMut, KeyIvInit};
use base64::Engine;
use base64::engine::general_purpose::{URL_SAFE, URL_SAFE_NO_PAD};
use hmac::{Hmac, Mac};
use sha2::Sha256;
use zeroize::Zeroize;

use crate::errors::{AppError, Result};

type Aes128CbcEnc = cbc::Encryptor<aes::Aes128>;
type Aes128CbcDec = cbc::Decryptor<aes::Aes128>;
type HmacSha256 = Hmac<Sha256>;

pub const PBKDF2_ITERATIONS: u32 = 480_000;
pub const SALT_LEN: usize = 16;
pub const KEY_LEN: usize = 32;

/// Derive 32-byte Fernet key from master password and salt using PBKDF2-HMAC-SHA256 (480,000 iter)
pub fn derive_key(password: &str, salt: &[u8]) -> Result<String> {
    if salt.len() != SALT_LEN {
        return Err(AppError::Crypto(format!(
            "Salt must be {} bytes, got {}",
            SALT_LEN,
            salt.len()
        )));
    }

    let mut key_bytes = [0u8; KEY_LEN];
    pbkdf2::pbkdf2_hmac::<Sha256>(
        password.as_bytes(),
        salt,
        PBKDF2_ITERATIONS,
        &mut key_bytes,
    );

    let key_b64 = URL_SAFE.encode(key_bytes);
    key_bytes.zeroize();
    Ok(key_b64)
}

pub struct Fernet {
    signing_key: [u8; 16],
    encryption_key: [u8; 16],
}

impl Fernet {
    pub fn from_b64_key(key_b64: &str) -> Result<Self> {
        let decoded = URL_SAFE
            .decode(key_b64)
            .map_err(|e| AppError::Crypto(format!("Invalid base64 key: {}", e)))?;
        if decoded.len() != KEY_LEN {
            return Err(AppError::Crypto(format!(
                "Key must be 32 bytes, got {}",
                decoded.len()
            )));
        }

        let mut signing_key = [0u8; 16];
        let mut encryption_key = [0u8; 16];
        signing_key.copy_from_slice(&decoded[0..16]);
        encryption_key.copy_from_slice(&decoded[16..32]);

        Ok(Self {
            signing_key,
            encryption_key,
        })
    }

    /// Decrypt Fernet token into plaintext bytes
    pub fn decrypt(&self, token_b64: &str) -> Result<Vec<u8>> {
        let token = URL_SAFE
            .decode(token_b64)
            .or_else(|_| URL_SAFE_NO_PAD.decode(token_b64))
            .map_err(|e| AppError::Crypto(format!("Invalid base64 token: {}", e)))?;

        // Fernet token min length: 1 (version) + 8 (time) + 16 (iv) + 16 (min 1 block) + 32 (hmac) = 73 bytes
        if token.len() < 73 {
            return Err(AppError::Crypto("Token too short".into()));
        }

        // 1. Check version (0x80)
        if token[0] != 0x80 {
            return Err(AppError::Crypto("Unsupported Fernet version".into()));
        }

        let payload_len = token.len() - 32;
        let data_to_verify = &token[..payload_len];
        let expected_hmac = &token[payload_len..];

        // 2. Verify HMAC-SHA256
        let mut mac = HmacSha256::new_from_slice(&self.signing_key)
            .map_err(|e| AppError::Crypto(e.to_string()))?;
        mac.update(data_to_verify);
        mac.verify_slice(expected_hmac)
            .map_err(|_| AppError::Crypto("Fernet HMAC verification failed".into()))?;

        // 3. Extract IV and ciphertext
        let iv = &token[9..25];
        let ciphertext = &token[25..payload_len];

        if ciphertext.len() % 16 != 0 {
            return Err(AppError::Crypto("Invalid ciphertext block size".into()));
        }

        // 4. Decrypt AES-128-CBC with PKCS7
        let cipher = Aes128CbcDec::new((&self.encryption_key).into(), iv.into());
        let mut buf = ciphertext.to_vec();
        let decrypted = cipher
            .decrypt_padded_mut::<Pkcs7>(&mut buf)
            .map_err(|e| AppError::Crypto(format!("AES decryption failed: {:?}", e)))?;

        Ok(decrypted.to_vec())
    }

    /// Encrypt plaintext bytes into Fernet token
    pub fn encrypt(&self, plaintext: &[u8], timestamp: Option<u64>, iv_opt: Option<[u8; 16]>) -> Result<String> {
        let ts = timestamp.unwrap_or_else(|| {
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs()
        });

        let iv = iv_opt.unwrap_or_else(|| {
            let mut rand_iv = [0u8; 16];
            use sha2::Digest;
            let mut hasher = Sha256::new();
            hasher.update(ts.to_be_bytes());
            hasher.update(plaintext);
            let out = hasher.finalize();
            rand_iv.copy_from_slice(&out[0..16]);
            rand_iv
        });

        // AES-128-CBC encryption with PKCS7
        let cipher = Aes128CbcEnc::new((&self.encryption_key).into(), (&iv).into());
        let mut buf = vec![0u8; plaintext.len() + 16];
        let ct = cipher
            .encrypt_padded_b2b_mut::<Pkcs7>(plaintext, &mut buf)
            .map_err(|e| AppError::Crypto(format!("Encryption error: {:?}", e)))?;

        // Construct raw token: version(1) + timestamp(8) + iv(16) + ciphertext(N)
        let mut raw_token = Vec::with_capacity(1 + 8 + 16 + ct.len() + 32);
        raw_token.push(0x80);
        raw_token.extend_from_slice(&ts.to_be_bytes());
        raw_token.extend_from_slice(&iv);
        raw_token.extend_from_slice(ct);

        // Compute HMAC
        let mut mac = HmacSha256::new_from_slice(&self.signing_key)
            .map_err(|e| AppError::Crypto(e.to_string()))?;
        mac.update(&raw_token);
        let hmac_bytes = mac.finalize().into_bytes();
        raw_token.extend_from_slice(&hmac_bytes);

        Ok(URL_SAFE.encode(raw_token))
    }
}

impl Drop for Fernet {
    fn drop(&mut self) {
        self.signing_key.zeroize();
        self.encryption_key.zeroize();
    }
}
