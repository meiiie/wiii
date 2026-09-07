mod commands;
mod neko;
mod tray;

pub use neko::computer::gmail as gmail_signal_adapter;
pub use neko::computer::motor as realtime_motor;
pub use neko::computer::watcher as app_event_watcher;
use neko::computer::{AppEventPump, NekoComputerService};
use neko::coworker::CoworkerRecords;
use neko::runtime::NekoRuntime;
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        // Reject a second journal owner before setup. Bring the existing
        // Workbench to the foreground instead of surfacing a generic lease
        // error from a second process.
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.unminimize();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_store::Builder::new().build())
        .plugin(tauri_plugin_http::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .invoke_handler(tauri::generate_handler![
            commands::health::check_server_reachable,
            commands::files::pick_document,
            commands::files::neko_resolve_workspace,
            commands::files::neko_list_workspace_files,
            commands::files::neko_read_workspace_file,
            commands::files::neko_workspace_changes,
            commands::files::neko_workspace_diff,
            commands::splash::close_splash,
            commands::neko_agent::neko_control_provider_list,
            commands::neko_agent::neko_control_provider_profiles,
            commands::neko_agent::neko_control_provider_sessions,
            commands::neko_agent::neko_control_session_list,
            commands::neko_agent::neko_control_session_start,
            commands::neko_agent::neko_control_session_write,
            commands::neko_agent::neko_control_session_cancel,
            commands::neko_agent::neko_control_events_read,
            commands::neko_computer::neko_computer_doctor,
            commands::neko_computer::neko_computer_coworker_status,
            commands::neko_computer::neko_computer_project_grant,
            commands::neko_computer::neko_computer_project_revoke,
            commands::neko_computer::neko_computer_ensure,
            commands::neko_computer::neko_computer_package_install,
            commands::neko_computer::neko_computer_package_remove,
            commands::neko_computer::neko_computer_remove,
            commands::neko_computer::neko_computer_suspend,
            commands::neko_computer::neko_computer_resume,
            commands::neko_computer::neko_computer_reset,
            commands::neko_computer::neko_computer_seat_acquire,
            commands::neko_computer::neko_computer_seat_release,
            commands::neko_computer::neko_computer_terminal_exec,
            commands::neko_computer::neko_computer_browser_navigate,
            commands::neko_computer::neko_computer_events_read,
            commands::neko_computer::neko_computer_app_events_poll,
            commands::neko_computer::neko_computer_semantic_observe,
            commands::neko_computer::neko_computer_semantic_act,
            commands::neko_computer::neko_computer_history_status,
            commands::neko_computer::neko_computer_history_set_enabled,
            commands::neko_computer::neko_computer_history_query,
            commands::neko_computer::neko_computer_history_delete,
            commands::neko_computer::neko_signal_inbox_consult,
            commands::neko_computer::neko_signal_inbox_claim,
            commands::neko_computer::neko_signal_inbox_defer,
            commands::neko_computer::neko_signal_inbox_resolve,
            commands::neko_computer::neko_signal_inbox_revoke_account,
            commands::neko_computer::neko_computer_work_plane_describe,
            commands::neko_computer::neko_computer_work_plane_query,
            commands::neko_computer::neko_computer_work_plane_execute,
        ])
        .setup(|app| {
            neko::bundled_provider::initialize(app.path().resource_dir()?)?;
            let data_dir = app.path().app_local_data_dir()?;
            let runtime = NekoRuntime::open(&data_dir.join("neko-runtime-v1.sqlite3"))
                .map_err(std::io::Error::other)?;
            app.manage(runtime);
            let computer = NekoComputerService::open(&data_dir)
                .and_then(|computer| {
                    let pump = AppEventPump::start(computer.clone())?;
                    app.manage(pump);
                    Ok(computer)
                })
                .map_err(|error| format!("computer_unavailable: Computer chưa khả dụng. Dữ liệu đã được giữ nguyên; kiểm tra quyền truy cập hoặc khôi phục bản sao lưu rồi mở lại Wiii. Chi tiết: {error}"));
            app.manage(computer);
            let coworker_records = CoworkerRecords::open(
                &data_dir.join("neko-coworker-v1").join("records-v1.sqlite3"),
            )
            .map_err(std::io::Error::other)?;
            app.manage(coworker_records);
            // Create system tray
            tray::create_tray(app)?;
            Ok(())
        })
        .on_window_event(|window, event| {
            // Minimize to tray on close (main window only)
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                if window.label() == "main" {
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("error while running Wiii desktop")
        .run(|app, event| {
            // Phase 2A is in-process: a graceful app exit cancels every owned
            // child. Hard-crash recovery is classified from the journal.
            if let tauri::RunEvent::Exit = event {
                if let Some(pump) = app.try_state::<AppEventPump>() {
                    pump.shutdown();
                }
                app.state::<NekoRuntime>().kill_all(app);
            }
        });
}
