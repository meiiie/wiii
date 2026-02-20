use tauri::Manager;

/// Close the splash screen and show the main application window.
/// Called from splashscreen.html after startup sequence completes.
#[tauri::command]
pub fn close_splash(window: tauri::Window) {
    // Close splash screen
    if let Some(splash) = window.get_webview_window("splashscreen") {
        let _ = splash.close();
    }

    // Show and focus main window
    if let Some(main) = window.get_webview_window("main") {
        let _ = main.set_skip_taskbar(false);
        let _ = main.show();
        let _ = main.set_focus();
    }
}
