//! Tauri boundary for the Neko local-computer authority.
//!
//! The renderer supplies project/environment intent. Docker executable,
//! image, container, volume, mounts, ports, quotas and credentials are owned
//! exclusively by `NekoComputerService`.

use crate::neko::computer::model::{
    BrowserNavigateRequest, ComputerCoworkerRequest, ComputerDoctor, ComputerEnsureRequest,
    ComputerEnvironment, ComputerHistoryDeleteRequest, ComputerHistoryPage, ComputerHistoryQuery,
    ComputerHistorySetEnabledRequest, ComputerHistoryStatus, ComputerLifecycleRequest,
    ComputerPackageRequest, ComputerProjectGrant, ComputerProjectGrantRequest,
    ComputerProjectRevokeRequest, ComputerRemoveRequest, ComputerReplayPage, ComputerResetRequest,
    CoworkerComputerStatus, DisplaySeat, SeatAcquireRequest, SeatReleaseRequest,
    SemanticActRequest, SemanticActResult, SemanticObserveRequest, SemanticSnapshot,
    SignalAccountRevokeRequest, SignalClaimRequest, SignalDeferRequest, SignalInboxConsultRequest,
    SignalInboxSummary, SignalItem, SignalResolveRequest, TerminalExecRequest, TerminalExecResult,
    WorkPlaneDescribeRequest, WorkPlaneDescriptor, WorkPlaneQueryRequest, WorkPlaneQueryResult,
    WorkPlaneTransactionRequest, WorkPlaneTransactionResult,
};
use crate::neko::computer::watcher::{AppEventPollRequest, WatcherBatch};
use crate::neko::computer::ComputerAvailability;
use tauri::State;

#[tauri::command]
pub async fn neko_computer_doctor(
    service: State<'_, ComputerAvailability>,
) -> Result<ComputerDoctor, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.doctor())
        .await
        .map_err(|error| format!("Neko computer doctor task failed: {error}"))
}

#[tauri::command]
pub async fn neko_computer_coworker_status(
    service: State<'_, ComputerAvailability>,
    request: ComputerCoworkerRequest,
) -> Result<CoworkerComputerStatus, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.coworker_status(request))
        .await
        .map_err(|error| format!("Neko coworker Computer status task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_computer_project_grant(
    service: State<'_, ComputerAvailability>,
    request: ComputerProjectGrantRequest,
) -> Result<ComputerProjectGrant, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.grant_project(request))
        .await
        .map_err(|error| format!("Neko coworker Project grant task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_computer_project_revoke(
    service: State<'_, ComputerAvailability>,
    request: ComputerProjectRevokeRequest,
) -> Result<(), String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.revoke_project(request))
        .await
        .map_err(|error| {
            format!("unknown_outcome: Neko coworker Project revoke task failed: {error}")
        })?
}

#[tauri::command]
pub async fn neko_computer_ensure(
    service: State<'_, ComputerAvailability>,
    request: ComputerEnsureRequest,
) -> Result<ComputerEnvironment, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.ensure(request))
        .await
        .map_err(|error| format!("unknown_outcome: Neko computer ensure task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_computer_package_install(
    service: State<'_, ComputerAvailability>,
    request: ComputerPackageRequest,
) -> Result<ComputerDoctor, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.install_package(request))
        .await
        .map_err(|error| format!("Neko computer package installation task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_computer_package_remove(
    service: State<'_, ComputerAvailability>,
    request: ComputerPackageRequest,
) -> Result<ComputerDoctor, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.remove_package(request))
        .await
        .map_err(|error| format!("Neko computer package task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_computer_remove(
    service: State<'_, ComputerAvailability>,
    request: ComputerRemoveRequest,
) -> Result<(), String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.remove(request))
        .await
        .map_err(|error| format!("unknown_outcome: Neko computer removal task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_computer_suspend(
    service: State<'_, ComputerAvailability>,
    request: ComputerLifecycleRequest,
) -> Result<ComputerEnvironment, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.suspend(request))
        .await
        .map_err(|error| format!("Neko computer suspend task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_computer_resume(
    service: State<'_, ComputerAvailability>,
    request: ComputerLifecycleRequest,
) -> Result<ComputerEnvironment, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.resume(request))
        .await
        .map_err(|error| format!("Neko computer resume task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_computer_reset(
    service: State<'_, ComputerAvailability>,
    request: ComputerResetRequest,
) -> Result<ComputerEnvironment, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.reset(request))
        .await
        .map_err(|error| format!("unknown_outcome: Neko computer reset task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_computer_seat_acquire(
    service: State<'_, ComputerAvailability>,
    request: SeatAcquireRequest,
) -> Result<DisplaySeat, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.acquire_seat(request))
        .await
        .map_err(|error| format!("Neko computer seat acquisition task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_computer_seat_release(
    service: State<'_, ComputerAvailability>,
    request: SeatReleaseRequest,
) -> Result<DisplaySeat, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.release_seat(request))
        .await
        .map_err(|error| format!("Neko computer seat release task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_computer_terminal_exec(
    service: State<'_, ComputerAvailability>,
    request: TerminalExecRequest,
) -> Result<TerminalExecResult, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.terminal_exec(request))
        .await
        .map_err(|error| format!("Neko computer terminal task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_computer_browser_navigate(
    service: State<'_, ComputerAvailability>,
    request: BrowserNavigateRequest,
) -> Result<(), String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.browser_navigate(request))
        .await
        .map_err(|error| format!("Neko computer browser task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_computer_events_read(
    service: State<'_, ComputerAvailability>,
    environment_id: String,
    after_seq: u64,
    limit: u32,
) -> Result<ComputerReplayPage, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.replay(&environment_id, after_seq, limit))
        .await
        .map_err(|error| format!("Neko computer event replay task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_computer_app_events_poll(
    service: State<'_, ComputerAvailability>,
    request: AppEventPollRequest,
) -> Result<WatcherBatch, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.app_events_poll(request))
        .await
        .map_err(|error| format!("Neko computer app-event poll task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_computer_semantic_observe(
    service: State<'_, ComputerAvailability>,
    request: SemanticObserveRequest,
) -> Result<SemanticSnapshot, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.semantic_observe(request))
        .await
        .map_err(|error| format!("Neko computer semantic observation task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_computer_history_status(
    service: State<'_, ComputerAvailability>,
) -> Result<ComputerHistoryStatus, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.history_status())
        .await
        .map_err(|error| format!("Computer History status task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_computer_history_set_enabled(
    service: State<'_, ComputerAvailability>,
    request: ComputerHistorySetEnabledRequest,
) -> Result<ComputerHistoryStatus, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.history_set_enabled(request))
        .await
        .map_err(|error| format!("Computer History setting task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_computer_history_query(
    service: State<'_, ComputerAvailability>,
    request: ComputerHistoryQuery,
) -> Result<ComputerHistoryPage, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.history_query(request))
        .await
        .map_err(|error| format!("Computer History query task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_computer_history_delete(
    service: State<'_, ComputerAvailability>,
    request: ComputerHistoryDeleteRequest,
) -> Result<u64, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.history_delete(request))
        .await
        .map_err(|error| format!("Computer History delete task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_signal_inbox_consult(
    service: State<'_, ComputerAvailability>,
    request: SignalInboxConsultRequest,
) -> Result<SignalInboxSummary, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.signal_inbox_consult(request))
        .await
        .map_err(|error| format!("Signal Inbox consultation task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_signal_inbox_claim(
    service: State<'_, ComputerAvailability>,
    request: SignalClaimRequest,
) -> Result<Vec<SignalItem>, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.signal_inbox_claim(request))
        .await
        .map_err(|error| format!("Signal Inbox claim task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_signal_inbox_defer(
    service: State<'_, ComputerAvailability>,
    request: SignalDeferRequest,
) -> Result<SignalItem, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.signal_inbox_defer(request))
        .await
        .map_err(|error| format!("unknown_outcome: Signal Inbox defer task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_signal_inbox_resolve(
    service: State<'_, ComputerAvailability>,
    request: SignalResolveRequest,
) -> Result<SignalItem, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.signal_inbox_resolve(request))
        .await
        .map_err(|error| format!("unknown_outcome: Signal Inbox resolve task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_signal_inbox_revoke_account(
    service: State<'_, ComputerAvailability>,
    request: SignalAccountRevokeRequest,
) -> Result<u64, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.signal_inbox_revoke_account(request))
        .await
        .map_err(|error| format!("Signal Inbox account revocation task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_computer_semantic_act(
    service: State<'_, ComputerAvailability>,
    request: SemanticActRequest,
) -> Result<SemanticActResult, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.semantic_act(request))
        .await
        .map_err(|error| {
            format!("unknown_outcome: Neko computer semantic action task failed: {error}")
        })?
}

#[tauri::command]
pub async fn neko_computer_work_plane_describe(
    service: State<'_, ComputerAvailability>,
    request: WorkPlaneDescribeRequest,
) -> Result<WorkPlaneDescriptor, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.work_plane_describe(request))
        .await
        .map_err(|error| format!("Work Plane description task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_computer_work_plane_query(
    service: State<'_, ComputerAvailability>,
    request: WorkPlaneQueryRequest,
) -> Result<WorkPlaneQueryResult, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.work_plane_query(request))
        .await
        .map_err(|error| format!("Work Plane query task failed: {error}"))?
}

#[tauri::command]
pub async fn neko_computer_work_plane_execute(
    service: State<'_, ComputerAvailability>,
    request: WorkPlaneTransactionRequest,
) -> Result<WorkPlaneTransactionResult, String> {
    let service = service.inner().as_ref().map_err(Clone::clone)?.clone();
    tauri::async_runtime::spawn_blocking(move || service.work_plane_execute(request))
        .await
        .map_err(|error| format!("unknown_outcome: Work Plane transaction task failed: {error}"))?
}
