use base64::Engine;
use base64::engine::general_purpose::STANDARD as BASE64;
use rusqlite::params;
use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use super::fernet::{derive_key, Fernet, SALT_LEN};
use crate::database::Database;
use crate::errors::{AppError, Result};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VaultItem {
    pub id: i64,
    pub label: String,
    pub created_at: String,
}

pub struct VaultManager {
    is_unlocked: AtomicBool,
    fernet: Mutex<Option<Fernet>>,
    last_activity: Mutex<Instant>,
    lock_timeout: Duration,
}

impl Default for VaultManager {
    fn default() -> Self {
        Self::new()
    }
}

impl VaultManager {
    pub fn new() -> Self {
        Self {
            is_unlocked: AtomicBool::new(false),
            fernet: Mutex::new(None),
            last_activity: Mutex::new(Instant::now()),
            lock_timeout: Duration::from_secs(300), // 5 minutes default
        }
    }

    pub fn is_unlocked(&self) -> bool {
        if self.is_unlocked.load(Ordering::SeqCst) {
            if let Ok(last) = self.last_activity.lock() {
                if last.elapsed() > self.lock_timeout {
                    self.lock();
                    return false;
                }
            }
            return true;
        }
        false
    }

    pub fn lock(&self) {
        self.is_unlocked.store(false, Ordering::SeqCst);
        if let Ok(mut lock) = self.fernet.lock() {
            *lock = None;
        }
    }

    fn touch(&self) {
        if let Ok(mut lock) = self.last_activity.lock() {
            *lock = Instant::now();
        }
    }

    /// Sets master password for the first time
    pub fn set_master_password(&self, password: &str, db: &Database) -> Result<()> {
        if password.len() < 8 {
            return Err(AppError::Crypto("Password must be at least 8 characters".into()));
        }

        let mut salt = [0u8; SALT_LEN];
        getrandom::getrandom(&mut salt)
            .map_err(|e| AppError::Crypto(format!("Failed to generate random salt: {}", e)))?;

        let key_b64 = derive_key(password, &salt)?;
        let fernet = Fernet::from_b64_key(&key_b64)?;
        let verification = fernet.encrypt(b"VAULT_VERIFIED", None, None)?;

        let salt_b64 = BASE64.encode(salt);

        db.with_conn(|conn| {
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('vault_salt', ?)",
                params![salt_b64],
            )?;
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('vault_verification', ?)",
                params![verification],
            )?;
            Ok(())
        })?;

        if let Ok(mut lock) = self.fernet.lock() {
            *lock = Some(fernet);
        }
        self.is_unlocked.store(true, Ordering::SeqCst);
        self.touch();
        Ok(())
    }

    /// Unlock vault with master password
    pub fn unlock(&self, password: &str, db: &Database) -> Result<bool> {
        let (salt_b64, verification) = db.with_conn(|conn| {
            let mut stmt = conn.prepare("SELECT key, value FROM settings WHERE key IN ('vault_salt', 'vault_verification')")?;
            let mut salt = None;
            let mut verif = None;
            let rows = stmt.query_map([], |row| {
                Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
            })?;
            for r in rows {
                let (k, v) = r?;
                if k == "vault_salt" {
                    salt = Some(v);
                } else if k == "vault_verification" {
                    verif = Some(v);
                }
            }
            Ok((salt, verif))
        })?;

        let (salt_b64, verification) = match (salt_b64, verification) {
            (Some(s), Some(v)) => (s, v),
            _ => return Err(AppError::Crypto("Vault has not been initialized with a password".into())),
        };

        let salt = BASE64
            .decode(&salt_b64)
            .map_err(|e| AppError::Crypto(format!("Invalid salt encoding: {}", e)))?;

        let key_b64 = derive_key(password, &salt)?;
        let fernet = Fernet::from_b64_key(&key_b64)?;

        match fernet.decrypt(&verification) {
            Ok(bytes) if bytes == b"VAULT_VERIFIED" => {
                if let Ok(mut lock) = self.fernet.lock() {
                    *lock = Some(fernet);
                }
                self.is_unlocked.store(true, Ordering::SeqCst);
                self.touch();
                Ok(true)
            }
            _ => Ok(false),
        }
    }

    /// Atomically changes master password and re-encrypts all rows in secure_vault
    pub fn change_master_password(
        &self,
        current_pwd: &str,
        new_pwd: &str,
        db: &Database,
    ) -> Result<()> {
        if !self.unlock(current_pwd, db)? {
            return Err(AppError::Crypto("Current password verification failed".into()));
        }

        let old_fernet = {
            let lock = self.fernet.lock().unwrap();
            match lock.as_ref() {
                Some(_) => Fernet::from_b64_key(&derive_key(
                    current_pwd,
                    &BASE64.decode(
                        &db.get_setting("vault_salt")?.ok_or_else(|| AppError::Crypto("No salt".into()))?,
                    ).unwrap(),
                )?)?,
                None => return Err(AppError::Crypto("Vault is locked".into())),
            }
        };

        // 1. Decrypt all existing items
        let existing_items: Vec<(i64, Vec<u8>)> = db.with_conn(|conn| {
            let mut stmt = conn.prepare("SELECT id, encrypted_content FROM secure_vault ORDER BY id ASC")?;
            let rows = stmt.query_map([], |row| {
                Ok((row.get::<_, i64>(0)?, row.get::<_, Vec<u8>>(1)?))
            })?;
            let mut list = Vec::new();
            for r in rows {
                list.push(r?);
            }
            Ok(list)
        })?;

        let mut reencrypted_items = Vec::new();
        for (id, cipher_bytes) in &existing_items {
            let token_str = String::from_utf8_lossy(cipher_bytes);
            if let Ok(decrypted_plain) = old_fernet.decrypt(&token_str) {
                reencrypted_items.push((*id, decrypted_plain));
            } else {
                tracing::warn!("Skipping corrupted/dummy vault row id={}", id);
            }
        }

        // 2. Generate new salt and key
        let mut new_salt = [0u8; SALT_LEN];
        getrandom::getrandom(&mut new_salt)
            .map_err(|e| AppError::Crypto(format!("Failed to generate random salt: {}", e)))?;

        let new_key_b64 = derive_key(new_pwd, &new_salt)?;
        let new_fernet = Fernet::from_b64_key(&new_key_b64)?;
        let new_verification = new_fernet.encrypt(b"VAULT_VERIFIED", None, None)?;
        let new_salt_b64 = BASE64.encode(new_salt);

        // 3. Atomically update database in a transaction
        db.with_conn(|conn| {
            conn.execute("BEGIN TRANSACTION", [])?;

            for (id, plain_bytes) in reencrypted_items {
                let new_token = new_fernet.encrypt(&plain_bytes, None, None)?;
                conn.execute(
                    "UPDATE secure_vault SET encrypted_content = ? WHERE id = ?",
                    params![new_token.into_bytes(), id],
                )?;
            }

            conn.execute(
                "UPDATE settings SET value = ? WHERE key = 'vault_salt'",
                params![new_salt_b64],
            )?;
            conn.execute(
                "UPDATE settings SET value = ? WHERE key = 'vault_verification'",
                params![new_verification],
            )?;

            conn.execute("COMMIT", [])?;
            Ok(())
        })?;

        if let Ok(mut lock) = self.fernet.lock() {
            *lock = Some(new_fernet);
        }
        self.touch();
        Ok(())
    }

    pub fn add_secret(&self, label: &str, secret_text: &str, db: &Database) -> Result<i64> {
        self.touch();
        let lock = self.fernet.lock().unwrap();
        let fernet = lock.as_ref().ok_or_else(|| AppError::Crypto("Vault is locked".into()))?;

        let token = fernet.encrypt(secret_text.as_bytes(), None, None)?;
        let token_bytes = token.into_bytes();

        db.with_conn(|conn| {
            conn.execute(
                "INSERT INTO secure_vault (label, encrypted_content, created_at) \
                 VALUES (?, ?, datetime('now', 'localtime'))",
                params![label, token_bytes],
            )?;
            Ok(conn.last_insert_rowid())
        })
    }

    pub fn get_secret(&self, item_id: i64, db: &Database) -> Result<String> {
        self.touch();
        let lock = self.fernet.lock().unwrap();
        let fernet = lock.as_ref().ok_or_else(|| AppError::Crypto("Vault is locked".into()))?;

        let cipher_bytes: Vec<u8> = db.with_conn(|conn| {
            conn.query_row(
                "SELECT encrypted_content FROM secure_vault WHERE id = ?",
                params![item_id],
                |r| r.get(0),
            )
            .map_err(AppError::from)
        })?;

        let token_str = String::from_utf8_lossy(&cipher_bytes);
        let decrypted = fernet.decrypt(&token_str)?;
        String::from_utf8(decrypted).map_err(|e| AppError::Crypto(e.to_string()))
    }

    pub fn list_secrets(&self, db: &Database) -> Result<Vec<VaultItem>> {
        self.touch();
        db.with_conn(|conn| {
            let mut stmt = conn.prepare("SELECT id, label, created_at FROM secure_vault ORDER BY id DESC")?;
            let rows = stmt.query_map([], |row| {
                Ok(VaultItem {
                    id: row.get(0)?,
                    label: row.get::<_, Option<String>>(1)?.unwrap_or_default(),
                    created_at: row.get::<_, Option<String>>(2)?.unwrap_or_default(),
                })
            })?;
            let mut items = Vec::new();
            for r in rows {
                items.push(r?);
            }
            Ok(items)
        })
    }

    pub fn delete_secret(&self, item_id: i64, db: &Database) -> Result<()> {
        self.touch();
        db.with_conn(|conn| {
            conn.execute("DELETE FROM secure_vault WHERE id = ?", params![item_id])?;
            Ok(())
        })
    }
}
