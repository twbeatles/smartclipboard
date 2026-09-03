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
    (temp, db)
}

#[test]
fn test_vault_setup_and_unlock() {
    let (_temp, db) = create_temp_db_copy();
    let manager = VaultManager::new();

    let password = "InitialMasterPassword123!@#";
    manager.set_master_password(password, &db).expect("set password");
    assert!(manager.is_unlocked(), "Should be unlocked after setting password");

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
    manager.set_master_password(password, &db).expect("set password");

    let secret_val = "MySuperConfidentialApiKey123456789";
    let secret_id = manager.add_secret("OpenAI Key", secret_val, &db).expect("add secret");

    let retrieved = manager.get_secret(secret_id, &db).expect("get secret");
    assert_eq!(retrieved, secret_val, "Decrypted secret must match original");

    let secrets = manager.list_secrets(&db).expect("list secrets");
    assert!(secrets.iter().any(|s| s.id == secret_id && s.label == "OpenAI Key"));

    // Delete secret
    manager.delete_secret(secret_id, &db).expect("delete secret");
    assert!(manager.get_secret(secret_id, &db).is_err(), "Deleted secret should not exist");
}

#[test]
fn test_vault_change_password_and_reencryption() {
    let (_temp, db) = create_temp_db_copy();
    let manager = VaultManager::new();

    let old_pwd = "OldMasterPassword123!@#";
    let new_pwd = "NewMasterPassword456!@#";

    manager.set_master_password(old_pwd, &db).expect("set password");

    let secret_val = "SecretDataPreservedAcrossPasswordChange";
    let secret_id = manager.add_secret("Important Token", secret_val, &db).expect("add secret");

    // Change master password
    manager.change_master_password(old_pwd, new_pwd, &db).expect("change master password");

    // Lock and test with old password
    manager.lock();
    let old_unlock = manager.unlock(old_pwd, &db).expect("old unlock");
    assert!(!old_unlock, "Old password must no longer work");

    // Unlock with new password
    let new_unlock = manager.unlock(new_pwd, &db).expect("new unlock");
    assert!(new_unlock, "New password must unlock vault");

    // Verify previously stored secret decrypts successfully!
    let retrieved = manager.get_secret(secret_id, &db).expect("retrieve secret");
    assert_eq!(retrieved, secret_val, "Secret must be preserved and re-encrypted");
}
