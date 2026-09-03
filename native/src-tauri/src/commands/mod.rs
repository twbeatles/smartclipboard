use std::collections::HashMap;
use tauri::{AppHandle, Manager, State};

use crate::app_state::AppState;
use crate::database::{Collection, HistoryDetail, HistoryItem, SearchFilter, Snippet, TrashItem};
use crate::errors::{AppError, Result};

#[tauri::command]
pub async fn history_list(state: State<'_, AppState>, limit: Option<usize>) -> Result<Vec<HistoryItem>> {
    state.db.list_history(limit.unwrap_or(100))
}

#[tauri::command]
pub async fn history_detail(state: State<'_, AppState>, id: i64) -> Result<HistoryDetail> {
    state.db.get_history_detail(id)
}

#[tauri::command]
pub async fn history_search(state: State<'_, AppState>, filter: SearchFilter) -> Result<Vec<HistoryItem>> {
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
        mini_window.hide().map_err(|e| AppError::Internal(e.to_string()))?;
    }
    Ok(())
}

#[tauri::command]
pub async fn paste_last_command(state: State<'_, AppState>) -> Result<()> {
    let guard = crate::clipboard::internal_guard::InternalWriteGuard::new();
    crate::paste::paste_last(&state, &guard)
}
