use std::path::PathBuf;

/// Resolves application data directory following the migration plan priority:
/// 1. --data-dir command-line argument override
/// 2. %LOCALAPPDATA%\SmartClipboard
/// 3. Portable adjacent directory
pub fn resolve_app_data_dir() -> PathBuf {
    // 1. Command-line --data-dir override
    let mut args = std::env::args();
    while let Some(arg) = args.next() {
        if arg == "--data-dir" {
            if let Some(val) = args.next() {
                let p = PathBuf::from(val);
                let _ = std::fs::create_dir_all(&p);
                return p;
            }
        }
    }

    // 2. %LOCALAPPDATA%\SmartClipboard
    if let Some(local_app_data) = std::env::var_os("LOCALAPPDATA") {
        let p = PathBuf::from(local_app_data).join("SmartClipboard");
        let _ = std::fs::create_dir_all(&p);
        return p;
    }

    // 3. Fallback to current directory
    PathBuf::from(".")
}

pub fn resolve_db_path() -> PathBuf {
    if let Ok(override_path) = std::env::var("SMARTCLIPBOARD_DB_PATH") {
        return PathBuf::from(override_path);
    }
    let data_dir = resolve_app_data_dir();
    data_dir.join("clipboard_history_v6.db")
}
