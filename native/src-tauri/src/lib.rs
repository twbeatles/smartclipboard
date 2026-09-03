pub mod action_palette;
pub mod app_state;
pub mod clipboard;
pub mod commands;
pub mod database;
pub mod errors;
pub mod import_export;
pub mod paste;
pub mod paths;
pub mod vault;

use std::path::PathBuf;
use std::sync::atomic::Ordering;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{AppHandle, Manager};

use app_state::AppState;
use database::Database;

fn resolve_db_path() -> PathBuf {
    if let Ok(override_path) = std::env::var("SMARTCLIPBOARD_DB_PATH") {
        return PathBuf::from(override_path);
    }

    // Default to test fixture if present in development
    let dev_fixture = PathBuf::from("../../tests/native_parity/fixtures/synthetic_test_v6.db");
    if dev_fixture.exists() {
        return dev_fixture;
    }

    // Or system legacy path
    if let Some(local_app_data) = std::env::var_os("LOCALAPPDATA") {
        let p = PathBuf::from(local_app_data)
            .join("SmartClipboard")
            .join("clipboard_history_v6.db");
        if p.exists() {
            return p;
        }
    }

    // Adjacent path
    PathBuf::from("clipboard_history_v6.db")
}

fn setup_tray(app: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    let show_i = MenuItem::with_id(app, "show", "보기", true, None::<&str>)?;
    let privacy_i = MenuItem::with_id(app, "privacy", "프라이버시 모드", true, None::<&str>)?;
    let pause_i = MenuItem::with_id(app, "pause", "모니터링 일시정지", true, None::<&str>)?;
    let settings_i = MenuItem::with_id(app, "settings", "설정", true, None::<&str>)?;
    let quit_i = MenuItem::with_id(app, "quit", "종료", true, None::<&str>)?;

    let menu = Menu::with_items(app, &[&show_i, &privacy_i, &pause_i, &settings_i, &quit_i])?;

    let _tray = TrayIconBuilder::new()
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(move |app, event| {
            match event.id.as_ref() {
                "show" => {
                    if let Some(window) = app.get_webview_window("main") {
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                }
                "privacy" => {
                    if let Some(state) = app.try_state::<AppState>() {
                        let curr = state.privacy_mode.fetch_xor(true, Ordering::SeqCst);
                        tracing::info!("Privacy mode toggled: {}", !curr);
                    }
                }
                "pause" => {
                    if let Some(state) = app.try_state::<AppState>() {
                        let curr = state.monitoring_paused.fetch_xor(true, Ordering::SeqCst);
                        tracing::info!("Monitoring paused toggled: {}", !curr);
                    }
                }
                "settings" => {
                    if let Some(window) = app.get_webview_window("main") {
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                }
                "quit" => {
                    app.exit(0);
                }
                _ => {}
            }
        })
        .build(app)?;

    Ok(())
}

pub fn run() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .init();

    tracing::info!("Starting SmartClipboard Pro Native (Rust + Tauri 2)");

    let db_path = resolve_db_path();
    tracing::info!("Connecting to SQLite database at: {:?}", db_path);

    let db = match Database::open_read_only(&db_path) {
        Ok(db) => db,
        Err(e) => {
            tracing::warn!(
                "Read-only open failed ({}), attempting read-write fallback (test synthetic)",
                e
            );
            Database::open_read_write(&db_path).expect("Failed to initialize database connection")
        }
    };

    let app_state = AppState::new(db);

    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            tracing::info!("Second instance launched - focusing main window");
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .manage(app_state)
        .setup(|app| {
            setup_tray(app.handle())?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::history_list,
            commands::history_detail,
            commands::history_search,
            commands::collections_list,
            commands::snippets_list,
            commands::settings_get_all,
            commands::trash_list,
            commands::vault_status,
            commands::hide_mini_window,
            commands::paste_last_command,
        ])
        .run(tauri::generate_context!())
        .expect("Error running SmartClipboard Pro Native application");
}
