use tauri::Manager;

fn ensure_main_window(label: &str) -> Result<(), String> {
    if label == "main" {
        Ok(())
    } else {
        Err("Thoát Wiii chỉ khả dụng từ cửa sổ chính.".into())
    }
}

#[tauri::command]
pub fn quit_app(window: tauri::Window) -> Result<(), String> {
    ensure_main_window(window.label())?;
    // Match the tray's exit path so RunEvent::Exit drains owned runtimes.
    window.app_handle().exit(0);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::ensure_main_window;

    #[test]
    fn quit_authority_is_limited_to_the_main_window() {
        assert!(ensure_main_window("main").is_ok());
        for label in ["splashscreen", "main-preview", "", "other"] {
            assert!(ensure_main_window(label).is_err(), "{label}");
        }
    }
}
