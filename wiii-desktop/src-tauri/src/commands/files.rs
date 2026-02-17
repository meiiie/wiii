/// Open a native file dialog to select a document (PDF) for upload.
/// Returns the selected file path, or None if cancelled.
///
/// Note: The dialog plugin can also be used from the frontend via
/// @tauri-apps/plugin-dialog directly. This command is a placeholder
/// for future Rust-side file processing if needed.
#[tauri::command]
pub async fn pick_document() -> Result<Option<String>, String> {
    Ok(None)
}
