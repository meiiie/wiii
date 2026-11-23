use crate::neko::local_models::{self, LocalModelStatus, SaveLocalModelRequest, SavedLocalModel};
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Manager, State, Window};

#[derive(Clone, Default)]
pub struct LocalModelSetupState(Arc<Mutex<()>>);

fn ensure_main_window(label: &str) -> Result<(), String> {
    if label == "main" {
        Ok(())
    } else {
        Err("Chỉ thiết lập mô hình trong cửa sổ Wiii chính.".into())
    }
}

#[tauri::command]
pub async fn local_model_status(
    window: Window,
    app: AppHandle,
) -> Result<LocalModelStatus, String> {
    ensure_main_window(window.label())?;
    let home = local_models::home_from_environment(|| app.path().home_dir().ok())?;
    tauri::async_runtime::spawn_blocking(move || local_models::status(&home))
        .await
        .map_err(|_| "Chưa kiểm tra được cấu hình mô hình. Hãy thử lại.".to_string())?
}

#[tauri::command]
pub async fn local_model_save(
    window: Window,
    app: AppHandle,
    state: State<'_, LocalModelSetupState>,
    request: SaveLocalModelRequest,
) -> Result<SavedLocalModel, String> {
    ensure_main_window(window.label())?;
    // These explicit Core overrides would otherwise defeat a UI save on the
    // next launch. Do not change the user's process environment or misreport
    // which credential/profile will be used.
    if [
        "NEKO_API_KEY",
        "NEKO_PROFILE",
        "NEKO_PROVIDER",
        "NEKO_BASE_URL",
        "NEKO_MODEL",
    ]
    .iter()
    .any(|name| std::env::var(name).is_ok_and(|value| !value.trim().is_empty()))
    {
        return Err("Môi trường đang đặt mô hình hoặc khóa API ưu tiên. Wiii chưa thể thay cấu hình đó an toàn.".into());
    }
    let home = local_models::home_from_environment(|| app.path().home_dir().ok())?;
    let state = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let _guard = state
            .0
            .lock()
            .map_err(|_| "Chưa lưu được mô hình. Hãy thử lại.".to_string())?;
        local_models::save(&home, request)
    })
    .await
    .map_err(|_| "Chưa lưu được mô hình. Hãy thử lại.".to_string())?
}

#[cfg(test)]
mod tests {
    #[test]
    fn model_configuration_authority_is_main_only() {
        assert!(super::ensure_main_window("main").is_ok());
        for label in ["splashscreen", "main-preview", "browser", ""] {
            assert!(super::ensure_main_window(label).is_err());
        }
    }
}
