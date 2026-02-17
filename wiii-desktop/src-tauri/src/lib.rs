mod commands;
mod tray;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_store::Builder::new().build())
        .plugin(tauri_plugin_http::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .invoke_handler(tauri::generate_handler![
            commands::health::check_server_reachable,
            commands::files::pick_document,
        ])
        .setup(|app| {
            // Create system tray
            tray::create_tray(app)?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Wiii desktop");
}
