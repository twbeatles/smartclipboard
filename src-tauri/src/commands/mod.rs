pub mod updater;

use std::collections::HashMap;
use std::sync::atomic::Ordering;
use tauri::{AppHandle, Emitter, Manager, State};

use crate::action_palette::{execute_action, PaletteAction, BUILTIN_ACTIONS};
use crate::app_state::AppState;
use crate::database::{Collection, HistoryDetail, HistoryItem, SearchFilter, Snippet, TrashItem};
use crate::errors::{AppError, Result};
use crate::vault::manager::VaultItem;

// ---------- Reads (unchanged) ----------

#[tauri::command]
pub async fn history_list(
    state: State<'_, AppState>,
    limit: Option<usize>,
) -> Result<Vec<HistoryItem>> {
    state.db.list_history(limit.unwrap_or(100))
}

#[tauri::command]
pub async fn history_detail(state: State<'_, AppState>, id: i64) -> Result<HistoryDetail> {
    state.db.get_history_detail(id)
}

#[tauri::command]
pub async fn history_search(
    state: State<'_, AppState>,
    filter: SearchFilter,
) -> Result<Vec<HistoryItem>> {
    state.db.search_items(&filter)
}

#[tauri::command]
pub async fn collections_list(state: State<'_, AppState>) -> Result<Vec<Collection>> {
    state.db.get_collections()
}

#[tauri::command]
pub async fn snippets_list(state: State<'_, AppState>) -> Result<Vec<Snippet>> {
    state.db.get_snippets()
}

#[tauri::command]
pub async fn settings_get_all(state: State<'_, AppState>) -> Result<HashMap<String, String>> {
    state.db.get_settings()
}

#[tauri::command]
pub async fn trash_list(state: State<'_, AppState>) -> Result<Vec<TrashItem>> {
    state.db.get_trash()
}

#[tauri::command]
pub async fn vault_status(state: State<'_, AppState>) -> Result<bool> {
    state.db.vault_has_password()
}

#[tauri::command]
pub async fn hide_mini_window(app: AppHandle) -> Result<()> {
    if let Some(mini_window) = app.get_webview_window("mini") {
        mini_window
            .hide()
            .map_err(|e| AppError::Internal(e.to_string()))?;
    }
    Ok(())
}

#[tauri::command]
pub async fn paste_last_command(state: State<'_, AppState>) -> Result<()> {
    let guard = state.write_guard.clone();
    crate::paste::paste_last(&state, &guard)
}

// ---------- History writes ----------

#[tauri::command]
pub async fn history_toggle_pin(state: State<'_, AppState>, id: i64) -> Result<bool> {
    state.db.toggle_pin(id)
}

#[tauri::command]
pub async fn history_toggle_bookmark(state: State<'_, AppState>, id: i64) -> Result<bool> {
    state.db.toggle_bookmark(id)
}

#[tauri::command]
pub async fn history_set_note(state: State<'_, AppState>, id: i64, note: String) -> Result<()> {
    state.db.set_note(id, &note)
}

#[tauri::command]
pub async fn history_mark_used(state: State<'_, AppState>, id: i64) -> Result<()> {
    state.db.increment_use_count(id)
}

#[tauri::command]
pub async fn history_delete(state: State<'_, AppState>, id: i64) -> Result<()> {
    state.db.soft_delete(id)
}

#[tauri::command]
pub async fn history_restore(state: State<'_, AppState>, deleted_id: i64) -> Result<i64> {
    state.db.restore_item(deleted_id)
}

#[tauri::command]
pub async fn history_delete_permanent(state: State<'_, AppState>, deleted_id: i64) -> Result<()> {
    state.db.permanent_delete(deleted_id)
}

#[tauri::command]
pub async fn trash_purge_expired(state: State<'_, AppState>) -> Result<usize> {
    state.db.purge_expired_trash()
}

// ---------- Collections ----------

#[tauri::command]
pub async fn collection_add(
    state: State<'_, AppState>,
    name: String,
    icon: String,
    color: String,
) -> Result<i64> {
    state.db.add_collection(&name, &icon, &color)
}

#[tauri::command]
pub async fn collection_rename(
    state: State<'_, AppState>,
    id: i64,
    name: String,
    icon: String,
    color: String,
) -> Result<()> {
    state.db.update_collection(id, &name, &icon, &color)
}

#[tauri::command]
pub async fn collection_delete(state: State<'_, AppState>, id: i64) -> Result<()> {
    state.db.delete_collection(id)
}

// ---------- Snippets ----------

#[tauri::command]
pub async fn snippet_add(
    state: State<'_, AppState>,
    name: String,
    content: String,
    shortcut: Option<String>,
    category: String,
) -> Result<i64> {
    state
        .db
        .add_snippet(&name, &content, shortcut.as_deref(), &category)
}

#[tauri::command]
pub async fn snippet_update(
    state: State<'_, AppState>,
    id: i64,
    name: String,
    content: String,
    shortcut: Option<String>,
    category: String,
) -> Result<()> {
    state
        .db
        .update_snippet(id, &name, &content, shortcut.as_deref(), &category)
}

#[tauri::command]
pub async fn snippet_delete(state: State<'_, AppState>, id: i64) -> Result<()> {
    state.db.delete_snippet(id)
}

// ---------- Settings & capture flags ----------

#[tauri::command]
pub async fn settings_set(state: State<'_, AppState>, key: String, value: String) -> Result<()> {
    state.db.set_setting(&key, &value)
}

#[tauri::command]
pub async fn privacy_set(
    state: State<'_, AppState>,
    app: AppHandle,
    enabled: bool,
) -> Result<bool> {
    state.privacy_mode.store(enabled, Ordering::SeqCst);
    state
        .db
        .set_setting("privacy_mode", if enabled { "1" } else { "0" })?;
    let _ = app.emit("privacy_changed", enabled);
    Ok(enabled)
}

#[tauri::command]
pub async fn monitoring_set(
    state: State<'_, AppState>,
    app: AppHandle,
    enabled: bool,
) -> Result<bool> {
    state.monitoring_paused.store(!enabled, Ordering::SeqCst);
    state
        .db
        .set_setting("monitoring_paused", if enabled { "0" } else { "1" })?;
    let _ = app.emit("monitoring_changed", enabled);
    Ok(enabled)
}

// ---------- Action Palette ----------

#[tauri::command]
pub async fn palette_actions() -> Result<Vec<PaletteAction>> {
    Ok(BUILTIN_ACTIONS.to_vec())
}

/// Runs a palette action on a history item, writes the result back to the
/// same row (merge on duplicate) and to the clipboard. Never re-triggers the
/// automatic copy-rule pipeline.
#[tauri::command]
pub async fn palette_execute(
    state: State<'_, AppState>,
    item_id: i64,
    action_id: String,
) -> Result<String> {
    let detail = state.db.get_history_detail(item_id)?;
    let output = execute_action(&action_id, &detail.content)?;
    state
        .db
        .replace_text_item_or_merge(item_id, &output, &detail.r#type)?;
    if crate::clipboard::win32::write_clipboard_text(&output) {
        let seq = crate::clipboard::win32::get_sequence_number();
        state.write_guard.mark_internal(seq, &output);
        Ok(output)
    } else {
        Err(AppError::Internal(
            "Palette result could not be written to clipboard".into(),
        ))
    }
}

// ---------- Import / export ----------

#[tauri::command]
pub async fn export_json(state: State<'_, AppState>) -> Result<String> {
    crate::import_export::export_to_json(&state.db)
}

#[tauri::command]
pub async fn import_json(state: State<'_, AppState>, payload: String) -> Result<(usize, usize)> {
    crate::import_export::import_from_json(&payload, &state.db)
}

#[tauri::command]
pub async fn export_csv(state: State<'_, AppState>) -> Result<String> {
    crate::import_export::export_to_csv(&state.db)
}

#[tauri::command]
pub async fn import_csv(state: State<'_, AppState>, payload: String) -> Result<(usize, usize)> {
    crate::import_export::import_from_csv(&payload, &state.db)
}

#[tauri::command]
pub async fn export_markdown(state: State<'_, AppState>) -> Result<String> {
    crate::import_export::export_to_markdown(&state.db)
}

// ---------- Secure vault ----------

#[tauri::command]
pub async fn vault_setup(state: State<'_, AppState>, password: String) -> Result<()> {
    state.vault.set_master_password(&password, &state.db)
}

#[tauri::command]
pub async fn vault_unlock(state: State<'_, AppState>, password: String) -> Result<bool> {
    state.vault.unlock(&password, &state.db)
}

#[tauri::command]
pub async fn vault_lock(state: State<'_, AppState>) -> Result<()> {
    state.vault.lock();
    Ok(())
}

#[tauri::command]
pub async fn vault_add(state: State<'_, AppState>, label: String, secret: String) -> Result<i64> {
    state.vault.add_secret(&label, &secret, &state.db)
}

#[tauri::command]
pub async fn vault_list(state: State<'_, AppState>) -> Result<Vec<VaultItem>> {
    state.vault.list_secrets(&state.db)
}

/// Copies a secret to the clipboard with the shared internal guard and arms a
/// 30-second conditional clear: the clipboard is emptied only if it still
/// holds the revealed secret.
#[tauri::command]
pub async fn vault_reveal(state: State<'_, AppState>, id: i64) -> Result<()> {
    let secret = state.vault.get_secret(id, &state.db)?;
    if crate::clipboard::win32::write_clipboard_text(&secret) {
        let seq = crate::clipboard::win32::get_sequence_number();
        state.write_guard.mark_internal(seq, &secret);
        std::thread::spawn(move || {
            std::thread::sleep(std::time::Duration::from_secs(30));
            let current = crate::clipboard::win32::read_clipboard_text();
            if current.as_deref() == Some(secret.as_str()) {
                let _ = crate::clipboard::win32::write_clipboard_text("");
            }
        });
        Ok(())
    } else {
        Err(AppError::Internal(
            "Secret could not be written to clipboard".into(),
        ))
    }
}

#[tauri::command]
pub async fn vault_delete(state: State<'_, AppState>, id: i64) -> Result<()> {
    state.vault.delete_secret(id, &state.db)
}

#[tauri::command]
pub async fn vault_change_password(
    state: State<'_, AppState>,
    current_password: String,
    new_password: String,
) -> Result<()> {
    state
        .vault
        .change_master_password(&current_password, &new_password, &state.db)
}

// ---------- Page-title fetch (G-4) ----------

/// Manually (re)fetch the page title for a history row containing a URL.
/// Returns true when a fetch was queued; the result arrives asynchronously
/// via the `title_fetch_result` event.
#[tauri::command]
pub async fn history_fetch_title(
    state: State<'_, AppState>,
    app: AppHandle,
    id: i64,
) -> Result<bool> {
    let detail = state.db.get_history_detail(id)?;
    let url = match crate::clipboard::fetch_title::extract_first_url(&detail.content) {
        Some(u) => u,
        None => return Ok(false),
    };
    let fetcher = state.title_fetcher.clone();
    fetcher.fetch_async(&url, id, move |event| {
        #[derive(serde::Serialize, Clone)]
        struct TitleFetchEvent {
            item_ids: Vec<i64>,
            url: String,
            title: Option<String>,
            message: String,
        }
        let _ = app.emit(
            "title_fetch_result",
            TitleFetchEvent {
                item_ids: event.item_ids,
                url: event.url,
                title: event.title,
                message: event.message,
            },
        );
    });
    Ok(true)
}
