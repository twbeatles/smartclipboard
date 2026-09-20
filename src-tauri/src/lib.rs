pub mod action_palette;
pub mod app_state;
pub mod clipboard;
pub mod commands;
pub mod database;
pub mod errors;
pub mod import_export;
pub mod paste;
pub mod paths;
pub mod updater;
pub mod vault;

use std::path::PathBuf;
use std::sync::atomic::Ordering;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{AppHandle, Emitter, Manager};

use app_state::AppState;
use database::Database;

fn resolve_db_path() -> PathBuf {
    // Single source of truth lives in paths::resolve_db_path.
    crate::paths::resolve_db_path()
}

/// Global shortcuts: Alt+V toggles the mini window, Ctrl+Shift+Z pastes
/// the most recent item. Registration happens in setup so failures can be
/// reported to the UI instead of crashing startup.
fn global_shortcuts_plugin<R: tauri::Runtime>() -> tauri::plugin::TauriPlugin<R> {
    use tauri_plugin_global_shortcut::{Shortcut, ShortcutState};

    let mini: Shortcut = "Alt+V".parse().expect("static shortcut Alt+V must parse");
    let paste: Shortcut = "Ctrl+Shift+Z"
        .parse()
        .expect("static shortcut Ctrl+Shift+Z must parse");
    let (mini_id, paste_id) = (mini.id(), paste.id());

    // Shortcuts are registered in setup (user-visible errors); the handler
    // below serves any shortcut registered afterwards.
    tauri_plugin_global_shortcut::Builder::new()
        .with_handler(move |app, _shortcut, event| {
            if event.state != ShortcutState::Pressed {
                return;
            }
            if event.id == mini_id {
                if let Some(window) = app.get_webview_window("mini") {
                    match window.is_visible() {
                        Ok(true) => {
                            let _ = window.hide();
                        }
                        _ => {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                }
            } else if event.id == paste_id {
                if let Some(state) = app.try_state::<AppState>() {
                    let guard = state.write_guard.clone();
                    if let Err(e) = crate::paste::paste_last(&state, &guard) {
                        tracing::warn!("Global-shortcut paste-last failed: {:?}", e);
                    }
                }
            }
        })
        .build()
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
        .on_menu_event(move |app, event| match event.id.as_ref() {
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
                    let _ = app.emit("privacy_changed", !curr);
                }
            }
            "pause" => {
                if let Some(state) = app.try_state::<AppState>() {
                    let curr = state.monitoring_paused.fetch_xor(true, Ordering::SeqCst);
                    tracing::info!("Monitoring paused toggled: {}", !curr);
                    let _ = app.emit("monitoring_changed", curr);
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
        })
        .build(app)?;

    Ok(())
}

/// Minimal smoke check for the updater: no GUI, no DB, exit fast.
/// Mirrors the Python `--smoke` contract (version + signing key present).
fn run_smoke_check() -> i32 {
    let version = env!("CARGO_PKG_VERSION");
    if version.is_empty() {
        eprintln!("smoke: missing version");
        return 1;
    }
    if crate::updater::resolve_public_key_b64().is_none() {
        eprintln!("smoke: missing update signing key");
        return 1;
    }
    println!("smartclipboard-native {} smoke ok", version);
    0
}

pub fn run() {
    // Helper modes must exit before Tauri (and single-instance) boots.
    let argv: Vec<String> = std::env::args().collect();
    if argv.iter().any(|a| a == "--smoke") {
        std::process::exit(run_smoke_check());
    }
    if argv.iter().any(|a| a == "--apply-update") {
        let rest: Vec<String> = argv
            .into_iter()
            .skip(1)
            .filter(|a| a != "--apply-update")
            .collect();
        std::process::exit(crate::updater::run_apply_update_cli(&rest));
    }
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .init();

    tracing::info!("Starting SmartClipboard Pro Native (Rust + Tauri 2)");

    let db_path = resolve_db_path();
    tracing::info!("Connecting to SQLite database at: {:?}", db_path);

    let db = Database::open_read_write(&db_path)
        .or_else(|_| Database::open_read_only(&db_path))
        .expect("Failed to initialize database connection");

    let app_state = AppState::new(db);
    // Restore persisted capture flags (tray/commands may have changed them).
    if app_state
        .db
        .get_setting("privacy_mode")
        .ok()
        .flatten()
        .as_deref()
        == Some("1")
    {
        app_state.privacy_mode.store(true, Ordering::SeqCst);
    }
    if app_state
        .db
        .get_setting("monitoring_paused")
        .ok()
        .flatten()
        .as_deref()
        == Some("1")
    {
        app_state.monitoring_paused.store(true, Ordering::SeqCst);
    }
    match app_state.db.purge_expired_trash() {
        Ok(0) => {}
        Ok(n) => tracing::info!("Purged {} expired trash rows", n),
        Err(e) => tracing::warn!("Failed to purge expired trash: {:?}", e),
    }

    tauri::Builder::default()
        .plugin(global_shortcuts_plugin())
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            tracing::info!("Second instance launched - focusing main window");
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .manage(app_state.clone())
        .setup(move |app| {
            setup_tray(app.handle())?;

            // Global shortcuts: report registration failures to the UI.
            {
                use tauri_plugin_global_shortcut::GlobalShortcutExt;
                for shortcut in ["Alt+V", "Ctrl+Shift+Z"] {
                    if let Err(e) = app.global_shortcut().register(shortcut) {
                        tracing::error!("Global shortcut {} registration failed: {}", shortcut, e);
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.emit(
                                "hotkey_error",
                                format!("전역 단축키 {} 등록 실패: {}", shortcut, e),
                            );
                        }
                    }
                }
            }

            // Initialize and start background clipboard listener
            // (the pipeline shares AppState's guard with every internal write).
            let write_guard = app_state.write_guard.clone();
            let pipeline = std::sync::Arc::new(crate::clipboard::ClipboardPipeline::new(
                std::sync::Arc::new(app_state),
                write_guard,
            ));

            let handle = app.handle().clone();
            let pipeline_clone = pipeline.clone();
            let _listener = crate::clipboard::win32::start_clipboard_listener(move || {
                pipeline_clone.process_event(Some(&handle));
            });
            Box::leak(Box::new(_listener));

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
            commands::history_toggle_pin,
            commands::history_toggle_bookmark,
            commands::history_set_note,
            commands::history_mark_used,
            commands::history_delete,
            commands::history_restore,
            commands::history_delete_permanent,
            commands::trash_purge_expired,
            commands::collection_add,
            commands::collection_rename,
            commands::collection_delete,
            commands::snippet_add,
            commands::snippet_update,
            commands::snippet_delete,
            commands::settings_set,
            commands::privacy_set,
            commands::monitoring_set,
            commands::palette_actions,
            commands::palette_execute,
            commands::export_json,
            commands::import_json,
            commands::export_csv,
            commands::import_csv,
            commands::export_markdown,
            commands::vault_setup,
            commands::vault_unlock,
            commands::vault_lock,
            commands::vault_add,
            commands::vault_list,
            commands::vault_reveal,
            commands::vault_delete,
            commands::vault_change_password,
            commands::history_fetch_title,
            commands::updater::update_check,
            commands::updater::update_download,
            commands::updater::update_apply,
            commands::updater::update_pending_result,
            commands::updater::quit_for_update,
        ])
        .run(tauri::generate_context!())
        .expect("Error running SmartClipboard Pro Native application");
}
