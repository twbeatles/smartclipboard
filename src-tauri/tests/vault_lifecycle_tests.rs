use std::fs;
use std::path::PathBuf;
use tempfile::NamedTempFile;

use smartclipboard_native_lib::database::Database;
use smartclipboard_native_lib::vault::VaultManager;

fn create_temp_db_copy() -> (NamedTempFile, Database) {
    let fixture_path = PathBuf::from("fixtures/synthetic_test_v6.db");
    assert!(fixture_path.exists());

    let temp = NamedTempFile::new().expect("create temp file");
    fs::copy(&fixture_path, temp.path()).expect("copy fixture db");

    let db = Database::open_read_write(temp.path()).expect("open read write");
    // The shared fixture ships vault keys; vault lifecycle tests need a blank vault.
    db.with_conn(|conn| {
        conn.execute("DELETE FROM secure_vault", [])?;
        conn.execute(
            "DELETE FROM settings WHERE key IN ('vault_salt', 'vault_verification')",
            [],
        )?;
        Ok(())
    })
    .expect("clear vault state");
    (temp, db)
}

#[test]
fn test_vault_setup_and_unlock() {
    let (_temp, db) = create_temp_db_copy();
    let manager = VaultManager::new();

    let password = "InitialMasterPassword123!@#";
    manager
        .set_master_password(password, &db)
        .expect("set password");
    assert!(
        manager.is_unlocked(),
        "Should be unlocked after setting password"
    );

    manager.lock();
    assert!(!manager.is_unlocked(), "Should be locked");

    // Wrong password
    let res_wrong = manager.unlock("WrongPass1234!", &db).expect("unlock call");
    assert!(!res_wrong, "Wrong password must fail unlock");
    assert!(!manager.is_unlocked());

    // Correct password
    let res_correct = manager.unlock(password, &db).expect("unlock call");
    assert!(res_correct, "Correct password must succeed");
    assert!(manager.is_unlocked());
}

#[test]
fn test_vault_add_and_get_secret() {
    let (_temp, db) = create_temp_db_copy();
    let manager = VaultManager::new();

    let password = "SecretMasterPassword123!@#";
    manager
        .set_master_password(password, &db)
        .expect("set password");

    let secret_val = "MySuperConfidentialApiKey123456789";
    let secret_id = manager
        .add_secret("OpenAI Key", secret_val, &db)
        .expect("add secret");

    let retrieved = manager.get_secret(secret_id, &db).expect("get secret");
    assert_eq!(
        retrieved, secret_val,
        "Decrypted secret must match original"
    );

    let secrets = manager.list_secrets(&db).expect("list secrets");
    assert!(secrets
        .iter()
        .any(|s| s.id == secret_id && s.label == "OpenAI Key"));

    // Delete secret
    manager
        .delete_secret(secret_id, &db)
        .expect("delete secret");
    assert!(
        manager.get_secret(secret_id, &db).is_err(),
        "Deleted secret should not exist"
    );
}

#[test]
fn test_vault_change_password_and_reencryption() {
    let (_temp, db) = create_temp_db_copy();
    let manager = VaultManager::new();

    let old_pwd = "OldMasterPassword123!@#";
    let new_pwd = "NewMasterPassword456!@#";

    manager
        .set_master_password(old_pwd, &db)
        .expect("set password");

    let secret_val = "SecretDataPreservedAcrossPasswordChange";
    let secret_id = manager
        .add_secret("Important Token", secret_val, &db)
        .expect("add secret");

    // Change master password
    manager
        .change_master_password(old_pwd, new_pwd, &db)
        .expect("change master password");

    // Lock and test with old password
    manager.lock();
    let old_unlock = manager.unlock(old_pwd, &db).expect("old unlock");
    assert!(!old_unlock, "Old password must no longer work");

    // Unlock with new password
    let new_unlock = manager.unlock(new_pwd, &db).expect("new unlock");
    assert!(new_unlock, "New password must unlock vault");

    // Verify previously stored secret decrypts successfully!
    let retrieved = manager.get_secret(secret_id, &db).expect("retrieve secret");
    assert_eq!(
        retrieved, secret_val,
        "Secret must be preserved and re-encrypted"
    );
}

#[test]
fn test_unlock_failure_resets_state() {
    let (_temp, db) = create_temp_db_copy();
    let manager = VaultManager::new();
    let password = "ResetStatePassword123!@#";
    manager
        .set_master_password(password, &db)
        .expect("set password");
    let secret_id = manager.add_secret("k", "v", &db).expect("add");
    assert!(manager.is_unlocked());

    let ok = manager
        .unlock("WrongPassword999!@#", &db)
        .expect("unlock call");
    assert!(!ok, "wrong password must fail");
    assert!(
        !manager.is_unlocked(),
        "failed unlock must clear unlocked state"
    );
    assert!(manager.get_secret(secret_id, &db).is_err());
}

#[test]
fn test_set_master_password_twice_rejected() {
    let (_temp, db) = create_temp_db_copy();
    let manager = VaultManager::new();
    manager
        .set_master_password("FirstPassword123!@#", &db)
        .expect("first set");
    let second = manager.set_master_password("SecondPassword456!@#", &db);
    assert!(
        second.is_err(),
        "re-initializing must be rejected to protect existing rows"
    );
    assert!(manager.unlock("FirstPassword123!@#", &db).expect("unlock"));
}

#[test]
fn test_change_password_rejects_short_new_password() {
    let (_temp, db) = create_temp_db_copy();
    let manager = VaultManager::new();
    let old_pwd = "OldPassword123!@#";
    manager
        .set_master_password(old_pwd, &db)
        .expect("set password");
    manager.add_secret("k", "v", &db).expect("add");

    let res = manager.change_master_password(old_pwd, "short", &db);
    assert!(res.is_err(), "short new password must be rejected");
    manager.lock();
    assert!(
        manager.unlock(old_pwd, &db).expect("unlock"),
        "old password must still work"
    );
}

#[test]
fn test_change_password_atomic_on_corrupt_row() {
    let (_temp, db) = create_temp_db_copy();
    let manager = VaultManager::new();
    let old_pwd = "AtomicOldPassword123!@#";
    let new_pwd = "AtomicNewPassword456!@#";
    manager
        .set_master_password(old_pwd, &db)
        .expect("set password");
    let good_id = manager
        .add_secret("good", "good-value", &db)
        .expect("add good");
    let bad_id = manager
        .add_secret("bad", "bad-value", &db)
        .expect("add bad");

    db.with_conn(|conn| {
        conn.execute(
            "UPDATE secure_vault SET encrypted_content = ? WHERE id = ?",
            rusqlite::params![b"not-a-fernet-token".to_vec(), bad_id],
        )?;
        Ok(())
    })
    .expect("corrupt row");

    let res = manager.change_master_password(old_pwd, new_pwd, &db);
    assert!(
        res.is_err(),
        "corrupt row must fail the whole change, not be skipped"
    );

    manager.lock();
    assert!(
        manager.unlock(old_pwd, &db).expect("unlock"),
        "old password must still work"
    );
    let val = manager.get_secret(good_id, &db).expect("good row readable");
    assert_eq!(val, "good-value");
}

#[test]
fn test_fernet_iv_randomness() {
    use smartclipboard_native_lib::vault::{derive_key, Fernet};
    let salt = [7u8; 16];
    let key = derive_key("RandomIvPassword123!@#", &salt).expect("derive");
    let fernet = Fernet::from_b64_key(&key).expect("fernet");

    let a = fernet.encrypt(b"same plaintext", None, None).expect("enc1");
    let b = fernet.encrypt(b"same plaintext", None, None).expect("enc2");
    assert_ne!(a, b, "IVs must differ per encryption");
    assert_eq!(fernet.decrypt(&a).expect("dec1"), b"same plaintext");
    assert_eq!(fernet.decrypt(&b).expect("dec2"), b"same plaintext");
}
