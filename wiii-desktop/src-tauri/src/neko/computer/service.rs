use super::app_event_inbox::AppEventInboxAdapter;
use super::history::ComputerHistory;
use super::journal::{ComputerJournal, CoworkerProjectActivation, RequestDecision};
use super::model::{
    BrowserNavigateRequest, ComputerCoworkerRequest, ComputerDoctor, ComputerEnsureRequest,
    ComputerEnvironment, ComputerHistoryDeleteRequest, ComputerHistoryPage, ComputerHistoryQuery,
    ComputerHistorySetEnabledRequest, ComputerHistoryStatus, ComputerLifecycleRequest,
    ComputerPackageRequest, ComputerProjectGrant, ComputerProjectGrantRequest,
    ComputerProjectRevokeRequest, ComputerRemoveRequest, ComputerReplayPage, ComputerResetRequest,
    ComputerResourcePreset, ComputerState, CoworkerComputerStatus, DisplaySeat, SeatAcquireRequest,
    SeatReleaseRequest, SeatState, SemanticActRequest, SemanticActResult, SemanticActionOutcome,
    SemanticObserveRequest, SemanticSnapshot, SignalAccountRevokeRequest, SignalClaimRequest,
    SignalDeferRequest, SignalInboxConsultRequest, SignalInboxSummary, SignalItem,
    SignalResolveRequest, TerminalExecRequest, TerminalExecResult, WorkPlaneDescribeRequest,
    WorkPlaneDescriptor, WorkPlaneQueryRequest, WorkPlaneQueryResult, WorkPlaneTransactionRequest,
    WorkPlaneTransactionResult, WorkTransactionOutcome,
};
use super::provider::{ComputerProvider, LocalDockerComputerProvider, ProviderEnvironment};
use super::signal_inbox::SignalInbox;
use super::watcher::{AppEventPollRequest, WatcherBatch};
use super::work_plane::{
    validate_describe, validate_descriptor, validate_query, validate_query_result,
    validate_transaction, validate_transaction_result, WorkPlaneAdapter,
};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, MutexGuard};

#[derive(Clone)]
pub struct NekoComputerService {
    history: ComputerHistory,
    signal_inbox: SignalInbox,
    journal: ComputerJournal,
    provider: Arc<dyn ComputerProvider>,
    work_plane: Arc<dyn WorkPlaneAdapter>,
    operations: Arc<Mutex<()>>,
}

impl NekoComputerService {
    pub fn open(data_root: &Path) -> Result<Self, String> {
        let root = data_root.join("neko-computer-v1");
        std::fs::create_dir_all(&root)
            .map_err(|error| format!("create Neko computer state directory failed: {error}"))?;
        let journal = ComputerJournal::open(&root.join("computer-v1.sqlite3"))?;
        let history = ComputerHistory::open(&root)?;
        let signal_inbox = SignalInbox::open(&root)?;
        journal.adopt_legacy_coworker("wiii-coworker-neko")?;
        let provider = Arc::new(LocalDockerComputerProvider::new(root.join("provider")));
        Ok(Self {
            history,
            signal_inbox,
            journal,
            provider: provider.clone(),
            work_plane: provider,
            operations: Arc::new(Mutex::new(())),
        })
    }

    pub fn doctor(&self) -> ComputerDoctor {
        self.provider.doctor()
    }

    pub fn coworker_status(
        &self,
        request: ComputerCoworkerRequest,
    ) -> Result<CoworkerComputerStatus, String> {
        let binding = self.journal.coworker_binding(&request.coworker_id)?;
        let grants = self.journal.project_grants(&request.coworker_id)?;
        let Some(binding) = binding else {
            return Ok(CoworkerComputerStatus {
                coworker_id: request.coworker_id,
                environment_id: None,
                active_project_id: None,
                active_project_path: None,
                environment: None,
                grants,
            });
        };
        let environment = match binding.active_project_id.as_deref() {
            Some(_) => Some(self.require_live_environment(&binding.environment_id)?),
            None => None,
        };
        Ok(CoworkerComputerStatus {
            coworker_id: binding.coworker_id,
            environment_id: Some(binding.environment_id),
            active_project_id: binding.active_project_id,
            active_project_path: binding.active_project_path,
            environment,
            grants,
        })
    }

    pub fn grant_project(
        &self,
        request: ComputerProjectGrantRequest,
    ) -> Result<ComputerProjectGrant, String> {
        let _guard = self.operation_guard();
        let canonical = canonical_project(&request.project_path)?;
        let path = canonical.to_string_lossy().to_string();
        let target = project_operation_target(&request.coworker_id, &request.project_id);
        match self
            .journal
            .begin_request(&request.request_id, "computer/project/grant", &target)?
        {
            RequestDecision::Replay(value) => {
                return serde_json::from_value(value)
                    .map_err(|error| format!("decode project grant replay failed: {error}"));
            }
            RequestDecision::RecordedError(code) => return Err(code),
            RequestDecision::UnknownOutcome => {
                return Err("unknown_outcome: project grant needs inspection".to_string())
            }
            RequestDecision::Execute => {}
        }
        let name = requested_project_name(&request.project_name, &canonical);
        let grant =
            self.journal
                .grant_project(&request.coworker_id, &request.project_id, &name, &path)?;
        self.journal.complete_request(
            &request.request_id,
            &serde_json::to_value(&grant)
                .map_err(|error| format!("encode project grant failed: {error}"))?,
        )?;
        Ok(grant)
    }

    pub fn revoke_project(&self, request: ComputerProjectRevokeRequest) -> Result<(), String> {
        let _guard = self.operation_guard();
        let target = project_operation_target(&request.coworker_id, &request.project_id);
        match self
            .journal
            .begin_request(&request.request_id, "computer/project/revoke", &target)?
        {
            RequestDecision::Replay(_) => return Ok(()),
            RequestDecision::RecordedError(code) => return Err(code),
            RequestDecision::UnknownOutcome => {
                return Err("unknown_outcome: project revocation needs inspection".to_string())
            }
            RequestDecision::Execute => {}
        }
        let active_environment = self
            .journal
            .coworker_binding(&request.coworker_id)?
            .filter(|binding| {
                binding.active_project_id.as_deref() == Some(request.project_id.as_str())
            })
            .map(|binding| binding.environment_id);
        if let Some(environment_id) = active_environment.as_deref() {
            self.journal.mark_side_effect_started(&request.request_id)?;
            if let Err(error) = self.provider.detach(environment_id) {
                return Err(self.uncertain(&request.request_id, environment_id, error));
            }
        }
        if let Err(error) = self
            .journal
            .revoke_project(&request.coworker_id, &request.project_id)
        {
            return match active_environment.as_deref() {
                Some(environment_id) => {
                    Err(self.uncertain(&request.request_id, environment_id, error))
                }
                None => Err(error),
            };
        }
        self.journal.complete_request(
            &request.request_id,
            &json!({ "revoked": true, "projectId": request.project_id }),
        )?;
        Ok(())
    }

    pub fn ensure(&self, request: ComputerEnsureRequest) -> Result<ComputerEnvironment, String> {
        let _guard = self.operation_guard();
        let canonical = canonical_project(&request.project_path)?;
        let project_path = canonical.to_string_lossy().to_string();
        if !self
            .journal
            .has_project_grant(&request.coworker_id, &request.project_id)?
        {
            return Err(
                "project_access_denied: grant this Project to Neko before opening it".to_string(),
            );
        }
        let environment_id =
            if let Some(binding) = self.journal.coworker_binding(&request.coworker_id)? {
                binding.environment_id
            } else if let Some(legacy) = self
                .journal
                .environment_by_project_path(&canonical.to_string_lossy())?
            {
                legacy
            } else {
                coworker_environment_id(&request.coworker_id)
            };
        match self
            .journal
            .begin_request(&request.request_id, "computer/ensure", &environment_id)?
        {
            RequestDecision::Replay(_) => return self.require_live_environment(&environment_id),
            RequestDecision::RecordedError(code) => return Err(code),
            RequestDecision::UnknownOutcome => return Err(unknown_outcome(&environment_id)),
            RequestDecision::Execute => {}
        }

        let project_name = requested_project_name(&request.project_name, &canonical);
        let doctor = self.provider.doctor();
        let resources = if let Some(existing) = self.journal.environment(&environment_id)? {
            existing.resources
        } else {
            match request.resource_preset {
                ComputerResourcePreset::Auto => doctor.recommended_preset.resources(),
                preset => preset.resources(),
            }
        };
        if let Err(error) = self
            .journal
            .activate_coworker_project(CoworkerProjectActivation {
                coworker_id: &request.coworker_id,
                environment_id: &environment_id,
                project_id: &request.project_id,
                project_name: &project_name,
                project_path: &project_path,
                state: ComputerState::Preparing,
                resources: &resources,
                event_type: "computer.preparing",
            })
        {
            let _ = self
                .journal
                .fail_request(&request.request_id, "journal_rejected");
            return Err(error);
        }

        if !doctor.supported {
            let _ = self
                .journal
                .fail_request(&request.request_id, "provider_unavailable");
            let _ = self.journal.set_environment_state(
                &environment_id,
                ComputerState::Error,
                "computer.provider_unavailable",
            );
            return Err(doctor.detail);
        }

        self.journal.mark_side_effect_started(&request.request_id)?;
        let provider = match self
            .provider
            .ensure(&environment_id, &canonical, &resources)
        {
            Ok(provider) => provider,
            Err(error) => return Err(self.uncertain(&request.request_id, &environment_id, error)),
        };
        if let Err(error) = self.journal.upsert_environment(
            &environment_id,
            &project_name,
            &project_path,
            provider.state.clone(),
            &resources,
            "computer.ready",
        ) {
            return Err(self.uncertain(&request.request_id, &environment_id, error));
        }
        if let Err(error) = self.journal.complete_request(
            &request.request_id,
            &json!({ "environmentId": environment_id }),
        ) {
            return Err(self.uncertain(&request.request_id, &environment_id, error));
        }
        let mut environment = self.require_environment(&environment_id)?;
        apply_provider_environment(&mut environment, provider);
        Ok(environment)
    }

    pub fn remove_package(
        &self,
        request: ComputerPackageRequest,
    ) -> Result<ComputerDoctor, String> {
        let _guard = self.operation_guard();
        if !self
            .provider
            .doctor()
            .packages
            .iter()
            .any(|package| package.package_id == request.package_id)
        {
            return Err(format!("computer_package_unknown: {}", request.package_id));
        }
        let target = format!("computer-package:{}", request.package_id);
        match self
            .journal
            .begin_request(&request.request_id, "computer/package/remove", &target)?
        {
            RequestDecision::Replay(_) => return Ok(self.provider.doctor()),
            RequestDecision::RecordedError(code) => return Err(code),
            RequestDecision::UnknownOutcome => {
                return Err("unknown_outcome: Computer package removal needs inspection".to_string())
            }
            RequestDecision::Execute => {}
        }
        let environment = self
            .journal
            .coworker_binding(&request.coworker_id)?
            .map(|binding| self.require_environment(&binding.environment_id))
            .transpose()?;
        if environment
            .as_ref()
            .is_some_and(|value| value.seat.state != SeatState::Available)
        {
            self.journal
                .fail_request(&request.request_id, "computer_package_in_use")?;
            return Err(
                "computer_package_in_use: return display control before removing the package"
                    .to_string(),
            );
        }
        self.journal.mark_side_effect_started(&request.request_id)?;
        if let Some(environment) = &environment {
            if let Err(error) = self.provider.detach(&environment.environment_id) {
                return Err(self.uncertain(
                    &request.request_id,
                    &environment.environment_id,
                    error,
                ));
            }
            if let Err(error) = self.journal.set_environment_state(
                &environment.environment_id,
                ComputerState::Suspended,
                "computer.package_detached",
            ) {
                return Err(self.uncertain(
                    &request.request_id,
                    &environment.environment_id,
                    error,
                ));
            }
        }
        if let Err(error) = self.provider.remove_package(&request.package_id) {
            let doctor = self.provider.doctor();
            if doctor.runtime_ready && !doctor.package_ready {
                self.journal
                    .complete_request(&request.request_id, &json!({ "packageReady": false }))?;
                return Ok(doctor);
            }
            let code = if error.starts_with("computer_package_in_use:") {
                "computer_package_in_use"
            } else {
                "computer_package_remove_failed"
            };
            self.journal.fail_request(&request.request_id, code)?;
            return Err(error);
        }
        self.journal
            .complete_request(&request.request_id, &json!({ "packageReady": false }))?;
        Ok(self.provider.doctor())
    }

    pub fn install_package(
        &self,
        request: ComputerPackageRequest,
    ) -> Result<ComputerDoctor, String> {
        let _guard = self.operation_guard();
        let target = format!("computer-package:{}", request.package_id);
        match self.journal.begin_request(
            &request.request_id,
            "computer/package/install",
            &target,
        )? {
            RequestDecision::Replay(_) => return Ok(self.provider.doctor()),
            RequestDecision::RecordedError(code) => return Err(code),
            RequestDecision::UnknownOutcome => {
                let doctor = self.provider.doctor();
                if doctor.package_ready {
                    self.journal
                        .complete_request(&request.request_id, &json!({ "packageReady": true }))?;
                    return Ok(doctor);
                }
                return Err(
                    "unknown_outcome: Computer package installation needs inspection".to_string(),
                );
            }
            RequestDecision::Execute => {}
        }
        self.journal.mark_side_effect_started(&request.request_id)?;
        if let Err(error) = self.provider.install_package(&request.package_id) {
            let doctor = self.provider.doctor();
            if doctor.package_ready {
                self.journal
                    .complete_request(&request.request_id, &json!({ "packageReady": true }))?;
                return Ok(doctor);
            }
            self.journal
                .fail_request(&request.request_id, "computer_package_install_failed")?;
            return Err(error);
        }
        self.journal
            .complete_request(&request.request_id, &json!({ "packageReady": true }))?;
        Ok(self.provider.doctor())
    }

    pub fn remove(&self, request: ComputerRemoveRequest) -> Result<(), String> {
        let _guard = self.operation_guard();
        match self.journal.begin_request(
            &request.request_id,
            "computer/remove",
            &request.environment_id,
        )? {
            RequestDecision::Replay(_) => return Ok(()),
            RequestDecision::RecordedError(code) => return Err(code),
            RequestDecision::UnknownOutcome => {
                return Err(unknown_outcome(&request.environment_id))
            }
            RequestDecision::Execute => {}
        }
        let environment = match self.require_environment(&request.environment_id) {
            Ok(environment) => environment,
            Err(error) => {
                self.journal
                    .fail_request(&request.request_id, "computer_environment_missing")?;
                return Err(error);
            }
        };
        let expected = if self
            .journal
            .coworker_binding_for_environment(&request.environment_id)?
            .is_some()
        {
            "REMOVE NEKO".to_string()
        } else {
            format!("REMOVE {}", environment.project_name)
        };
        if request.confirmation != expected {
            self.journal
                .fail_request(&request.request_id, "confirmation_rejected")?;
            return Err(format!(
                "Computer removal confirmation must equal {expected}"
            ));
        }
        self.journal.mark_side_effect_started(&request.request_id)?;
        if let Err(error) = self.provider.destroy(&request.environment_id) {
            return Err(self.uncertain(&request.request_id, &request.environment_id, error));
        }
        if let Err(error) = self.journal.delete_environment(&request.environment_id) {
            return Err(self.uncertain(&request.request_id, &request.environment_id, error));
        }
        let _ = self.history.delete(&request.environment_id);
        self.journal
            .complete_request(&request.request_id, &json!({ "removed": true }))?;
        Ok(())
    }

    pub fn suspend(
        &self,
        request: ComputerLifecycleRequest,
    ) -> Result<ComputerEnvironment, String> {
        let _guard = self.operation_guard();
        let environment = self.require_environment(&request.environment_id)?;
        match self.journal.begin_request(
            &request.request_id,
            "computer/suspend",
            &request.environment_id,
        )? {
            RequestDecision::Replay(_) => return self.require_environment(&request.environment_id),
            RequestDecision::RecordedError(code) => return Err(code),
            RequestDecision::UnknownOutcome => {
                return Err(unknown_outcome(&request.environment_id))
            }
            RequestDecision::Execute => {}
        }
        self.journal.mark_side_effect_started(&request.request_id)?;
        if let Err(error) = self.provider.suspend(&request.environment_id) {
            return Err(self.uncertain(&request.request_id, &request.environment_id, error));
        }
        if let Err(error) = self.journal.set_environment_state(
            &request.environment_id,
            ComputerState::Suspended,
            "computer.suspended",
        ) {
            return Err(self.uncertain(&request.request_id, &request.environment_id, error));
        }
        if let Err(error) =
            self.complete_environment_request(&request.request_id, &request.environment_id)
        {
            return Err(self.uncertain(&request.request_id, &request.environment_id, error));
        }
        let mut result = environment;
        result.state = ComputerState::Suspended;
        result.attach_url = None;
        Ok(result)
    }

    pub fn resume(&self, request: ComputerLifecycleRequest) -> Result<ComputerEnvironment, String> {
        let _guard = self.operation_guard();
        let environment = self.require_granted_environment(&request.environment_id)?;
        match self.journal.begin_request(
            &request.request_id,
            "computer/resume",
            &request.environment_id,
        )? {
            RequestDecision::Replay(_) => {
                return self.require_live_environment(&request.environment_id)
            }
            RequestDecision::RecordedError(code) => return Err(code),
            RequestDecision::UnknownOutcome => {
                return Err(unknown_outcome(&request.environment_id))
            }
            RequestDecision::Execute => {}
        }
        self.journal.mark_side_effect_started(&request.request_id)?;
        let provider = match self.provider.resume(
            &request.environment_id,
            Path::new(&environment.project_path),
            &environment.resources,
        ) {
            Ok(provider) => provider,
            Err(error) => {
                return Err(self.uncertain(&request.request_id, &request.environment_id, error))
            }
        };
        if let Err(error) = self.journal.set_environment_state(
            &request.environment_id,
            ComputerState::Ready,
            "computer.ready",
        ) {
            return Err(self.uncertain(&request.request_id, &request.environment_id, error));
        }
        if let Err(error) =
            self.complete_environment_request(&request.request_id, &request.environment_id)
        {
            return Err(self.uncertain(&request.request_id, &request.environment_id, error));
        }
        let mut result = self.require_environment(&request.environment_id)?;
        apply_provider_environment(&mut result, provider);
        Ok(result)
    }

    pub fn reset(&self, request: ComputerResetRequest) -> Result<ComputerEnvironment, String> {
        let _guard = self.operation_guard();
        let environment = self.require_granted_environment(&request.environment_id)?;
        let expected = if self
            .journal
            .coworker_binding_for_environment(&request.environment_id)?
            .is_some()
        {
            "RESET NEKO".to_string()
        } else {
            format!("RESET {}", environment.project_name)
        };
        if request.confirmation != expected {
            return Err(format!(
                "Type {expected:?} to reset only computer-owned state"
            ));
        }
        match self.journal.begin_request(
            &request.request_id,
            "computer/reset",
            &request.environment_id,
        )? {
            RequestDecision::Replay(_) => {
                return self.require_live_environment(&request.environment_id)
            }
            RequestDecision::RecordedError(code) => return Err(code),
            RequestDecision::UnknownOutcome => {
                return Err(unknown_outcome(&request.environment_id))
            }
            RequestDecision::Execute => {}
        }
        self.journal.set_environment_state(
            &request.environment_id,
            ComputerState::Preparing,
            "computer.reset_started",
        )?;
        self.journal.mark_side_effect_started(&request.request_id)?;
        let provider = match self.provider.reset(
            &request.environment_id,
            Path::new(&environment.project_path),
            &environment.resources,
        ) {
            Ok(provider) => provider,
            Err(error) => {
                return Err(self.uncertain(&request.request_id, &request.environment_id, error))
            }
        };
        if let Err(error) = self.journal.set_environment_state(
            &request.environment_id,
            ComputerState::Ready,
            "computer.reset_completed",
        ) {
            return Err(self.uncertain(&request.request_id, &request.environment_id, error));
        }
        if let Err(error) =
            self.complete_environment_request(&request.request_id, &request.environment_id)
        {
            return Err(self.uncertain(&request.request_id, &request.environment_id, error));
        }
        let mut result = self.require_environment(&request.environment_id)?;
        apply_provider_environment(&mut result, provider);
        Ok(result)
    }

    pub fn acquire_seat(&self, request: SeatAcquireRequest) -> Result<DisplaySeat, String> {
        let _guard = self.operation_guard();
        self.require_environment(&request.environment_id)?;
        match self.journal.begin_request(
            &request.request_id,
            "computer/seat/acquire",
            &request.environment_id,
        )? {
            RequestDecision::Replay(value) => {
                return serde_json::from_value(value)
                    .map_err(|error| format!("decode display lease replay failed: {error}"));
            }
            RequestDecision::RecordedError(code) => return Err(code),
            RequestDecision::UnknownOutcome => {
                return Err(unknown_outcome(&request.environment_id))
            }
            RequestDecision::Execute => {}
        }
        self.journal.mark_side_effect_started(&request.request_id)?;
        if request.user_controlled {
            let _ = self.provider.resume_realtime(&request.environment_id);
        }
        let seat = match self.journal.acquire_seat(
            &request.environment_id,
            &request.owner_id,
            request.user_controlled,
        ) {
            Ok(seat) => seat,
            Err(error) => {
                return Err(self.record_local_rejection(
                    &request.request_id,
                    "seat_acquire_rejected",
                    error,
                ));
            }
        };
        if let Err(error) = self.journal.complete_request(
            &request.request_id,
            &serde_json::to_value(&seat)
                .map_err(|error| format!("encode display lease failed: {error}"))?,
        ) {
            return Err(self.uncertain(&request.request_id, &request.environment_id, error));
        }
        Ok(seat)
    }

    pub fn release_seat(&self, request: SeatReleaseRequest) -> Result<DisplaySeat, String> {
        let _guard = self.operation_guard();
        self.require_environment(&request.environment_id)?;
        match self.journal.begin_request(
            &request.request_id,
            "computer/seat/release",
            &request.environment_id,
        )? {
            RequestDecision::Replay(value) => {
                return serde_json::from_value(value)
                    .map_err(|error| format!("decode display release replay failed: {error}"));
            }
            RequestDecision::RecordedError(code) => return Err(code),
            RequestDecision::UnknownOutcome => {
                return Err(unknown_outcome(&request.environment_id))
            }
            RequestDecision::Execute => {}
        }
        self.journal.mark_side_effect_started(&request.request_id)?;
        let _ = self.provider.resume_realtime(&request.environment_id);
        let seat = match self
            .journal
            .release_seat(&request.environment_id, &request.lease_id)
        {
            Ok(seat) => seat,
            Err(error) => {
                return Err(self.record_local_rejection(
                    &request.request_id,
                    "seat_release_rejected",
                    error,
                ));
            }
        };
        if let Err(error) = self.journal.complete_request(
            &request.request_id,
            &serde_json::to_value(&seat)
                .map_err(|error| format!("encode display release failed: {error}"))?,
        ) {
            return Err(self.uncertain(&request.request_id, &request.environment_id, error));
        }
        Ok(seat)
    }

    pub fn terminal_exec(
        &self,
        request: TerminalExecRequest,
    ) -> Result<TerminalExecResult, String> {
        let _guard = self.operation_guard();
        let environment = self.require_environment(&request.environment_id)?;
        if environment.state != ComputerState::Ready {
            return Err("Computer must be running before Terminal can execute".to_string());
        }
        match self.journal.begin_request(
            &request.request_id,
            "computer/terminal/exec",
            &request.environment_id,
        )? {
            RequestDecision::Replay(value) => {
                return Ok(TerminalExecResult {
                    environment_id: request.environment_id,
                    exit_code: value
                        .get("exitCode")
                        .and_then(Value::as_i64)
                        .map(|value| value as i32),
                    stdout: String::new(),
                    stderr:
                        "Command already executed; terminal output is intentionally not persisted."
                            .to_string(),
                    truncated: value
                        .get("truncated")
                        .and_then(Value::as_bool)
                        .unwrap_or(false),
                    replayed_without_output: true,
                });
            }
            RequestDecision::RecordedError(code) => return Err(code),
            RequestDecision::UnknownOutcome => {
                return Err(unknown_outcome(&request.environment_id))
            }
            RequestDecision::Execute => {}
        }
        self.journal.mark_side_effect_started(&request.request_id)?;
        let provider = match self
            .provider
            .terminal_exec(&request.environment_id, &request.command)
        {
            Ok(result) => result,
            Err(error) => {
                return Err(self.uncertain(&request.request_id, &request.environment_id, error))
            }
        };
        if let Err(error) = self.journal.append_event(
            &request.environment_id,
            "terminal.completed",
            json!({
                "exitCode": provider.exit_code,
                "truncated": provider.truncated,
                "outputPersisted": false
            }),
        ) {
            return Err(self.uncertain(&request.request_id, &request.environment_id, error));
        }
        if let Err(error) = self.journal.complete_request(
            &request.request_id,
            &json!({ "exitCode": provider.exit_code, "truncated": provider.truncated }),
        ) {
            return Err(self.uncertain(&request.request_id, &request.environment_id, error));
        }
        Ok(TerminalExecResult {
            environment_id: request.environment_id,
            exit_code: provider.exit_code,
            stdout: provider.stdout,
            stderr: provider.stderr,
            truncated: provider.truncated,
            replayed_without_output: false,
        })
    }

    pub fn browser_navigate(&self, request: BrowserNavigateRequest) -> Result<(), String> {
        let _guard = self.operation_guard();
        let environment = self.require_environment(&request.environment_id)?;
        if environment.state != ComputerState::Ready {
            return Err("Computer must be running before Browser can navigate".to_string());
        }
        match self.journal.begin_request(
            &request.request_id,
            "computer/browser/navigate",
            &request.environment_id,
        )? {
            RequestDecision::Replay(_) => return Ok(()),
            RequestDecision::RecordedError(code) => return Err(code),
            RequestDecision::UnknownOutcome => {
                return Err(unknown_outcome(&request.environment_id))
            }
            RequestDecision::Execute => {}
        }
        self.journal.mark_side_effect_started(&request.request_id)?;
        if let Err(error) = self
            .provider
            .browser_navigate(&request.environment_id, &request.url)
        {
            return Err(self.uncertain(&request.request_id, &request.environment_id, error));
        }
        if let Err(error) = self.journal.append_event(
            &request.environment_id,
            "browser.navigated",
            json!({ "scheme": request.url.split(':').next().unwrap_or("https") }),
        ) {
            return Err(self.uncertain(&request.request_id, &request.environment_id, error));
        }
        self.complete_environment_request(&request.request_id, &request.environment_id)
            .map_err(|error| self.uncertain(&request.request_id, &request.environment_id, error))
    }

    pub fn semantic_observe(
        &self,
        request: SemanticObserveRequest,
    ) -> Result<SemanticSnapshot, String> {
        if !(1..=1000).contains(&request.max_nodes) {
            return Err("Computer semantic maxNodes must be between 1 and 1000".to_string());
        }
        if request
            .scope_ref
            .as_ref()
            .is_some_and(|value| value.is_empty() || value.len() > 256)
        {
            return Err("Computer semantic scopeRef is invalid".to_string());
        }
        if request
            .visual_ref
            .as_ref()
            .is_some_and(|value| value.is_empty() || value.len() > 256)
        {
            return Err("Computer semantic visualRef is invalid".to_string());
        }
        if request
            .continuation
            .as_ref()
            .is_some_and(|value| value.is_empty() || value.len() > 4096)
        {
            return Err("Computer semantic continuation is invalid".to_string());
        }
        if request
            .since_state_version
            .as_ref()
            .is_some_and(|value| !value.starts_with("sha256:") || value.len() > 96)
        {
            return Err("Computer semantic sinceStateVersion is invalid".to_string());
        }
        if request.known_node_versions.len() > 2000
            || request.known_node_versions.iter().any(|entry| {
                entry.node_ref.is_empty()
                    || entry.node_ref.len() > 256
                    || !entry.version.starts_with("sha256:")
                    || entry.version.len() > 96
            })
        {
            return Err("Computer semantic knownNodeVersions is invalid".to_string());
        }
        let environment = self.require_live_environment(&request.environment_id)?;
        if environment.state != ComputerState::Ready {
            return Err("Computer must be running before it can be observed".to_string());
        }
        self.provider.semantic_observe(&request)
    }

    pub fn app_events_poll(&self, request: AppEventPollRequest) -> Result<WatcherBatch, String> {
        let environment = self.require_live_environment(&request.environment_id)?;
        if environment.state != ComputerState::Ready {
            return Err("Computer must be running before app events can be read".to_string());
        }
        self.provider.app_events_poll(
            &request.environment_id,
            request.after_cursor.as_deref(),
            request.limit,
            request.wait_ms,
            None,
        )
    }

    pub(crate) fn sync_active_app_events(
        &self,
        wait_ms: u32,
        stopped: Option<&AtomicBool>,
    ) -> Result<bool, String> {
        let environment_ids = self.journal.active_environment_ids()?;
        if environment_ids.is_empty() {
            return Ok(false);
        }
        let adapter = AppEventInboxAdapter::new(self.signal_inbox.clone());
        let environment_count = u32::try_from(environment_ids.len()).unwrap_or(u32::MAX);
        let per_environment_wait = wait_ms / environment_count;
        let wait_remainder = wait_ms % environment_count;
        let mut active = false;
        for (environment_index, environment_id) in environment_ids.into_iter().enumerate() {
            if stopped.is_some_and(|flag| flag.load(Ordering::Acquire)) {
                break;
            }
            let environment = self.require_live_environment(&environment_id)?;
            if environment.state != ComputerState::Ready {
                continue;
            }
            active = true;
            let mut cursor = adapter.cursor(&environment_id)?;
            for page_index in 0..4 {
                let environment_wait = per_environment_wait
                    + u32::from(
                        page_index == 0
                            && u32::try_from(environment_index).unwrap_or(u32::MAX)
                                < wait_remainder,
                    );
                let batch = self.provider.app_events_poll(
                    &environment_id,
                    cursor.as_deref(),
                    512,
                    if page_index == 0 { environment_wait } else { 0 },
                    stopped,
                )?;
                let page_length = batch.events.len();
                cursor = Some(batch.cursor.clone());
                adapter.materialize(&environment_id, batch)?;
                if page_length < 512 {
                    break;
                }
            }
        }
        Ok(active)
    }

    pub fn semantic_act(&self, request: SemanticActRequest) -> Result<SemanticActResult, String> {
        validate_semantic_action(&request)?;
        let _guard = self.operation_guard();
        let environment = self.require_live_environment(&request.environment_id)?;
        if environment.state != ComputerState::Ready {
            return Err("Computer must be running before a semantic action".to_string());
        }
        if environment.seat.state != SeatState::AgentControlled
            || environment.seat.lease_id.as_deref() != Some(request.lease_id.as_str())
        {
            return Err(
                "Computer semantic actions require the current agent-controlled display lease"
                    .to_string(),
            );
        }
        match self.journal.begin_request(
            &request.request_id,
            "computer/semantic/act",
            &request.environment_id,
        )? {
            RequestDecision::Replay(value) => {
                return serde_json::from_value(value)
                    .map_err(|error| format!("decode semantic action replay failed: {error}"));
            }
            RequestDecision::RecordedError(code) => return Err(code),
            RequestDecision::UnknownOutcome => {
                return Err(unknown_outcome(&request.environment_id))
            }
            RequestDecision::Execute => {}
        }

        self.journal.mark_side_effect_started(&request.request_id)?;
        let result = match self.provider.semantic_act(&request) {
            Ok(result) => result,
            Err(error) => {
                return Err(self.uncertain(&request.request_id, &request.environment_id, error))
            }
        };
        let event_type = if result.outcome == SemanticActionOutcome::Completed {
            "semantic.action_completed"
        } else {
            "semantic.action_rejected"
        };
        if let Err(error) = self.journal.append_event(
            &request.environment_id,
            event_type,
            json!({
                "action": result.action.as_str(),
                "targetRef": result.target_ref,
                "beforeStateVersion": result.before_state_version,
                "afterStateVersion": result.after_state_version,
                "verified": result.verified,
                "code": result.code,
                "contentPersisted": false
            }),
        ) {
            return Err(self.uncertain(&request.request_id, &request.environment_id, error));
        }
        let replay_result = replayable_semantic_result(&result);
        let replay = serde_json::to_value(&replay_result)
            .map_err(|error| format!("encode semantic action result failed: {error}"))?;
        if let Err(error) = self.journal.complete_request(&request.request_id, &replay) {
            return Err(self.uncertain(&request.request_id, &request.environment_id, error));
        }
        let _ = self.history.append_action(&result);
        Ok(result)
    }

    pub fn work_plane_describe(
        &self,
        request: WorkPlaneDescribeRequest,
    ) -> Result<WorkPlaneDescriptor, String> {
        validate_describe(&request)?;
        self.require_work_plane_scope(&request.environment_id, &request.project_id)?;
        let descriptor = self.work_plane.describe(&request)?;
        validate_descriptor(&descriptor)?;
        Ok(descriptor)
    }

    pub fn work_plane_query(
        &self,
        request: WorkPlaneQueryRequest,
    ) -> Result<WorkPlaneQueryResult, String> {
        validate_query(&request)?;
        self.require_work_plane_scope(&request.environment_id, &request.project_id)?;
        let result = self.work_plane.query(&request)?;
        validate_query_result(&result)?;
        Ok(result)
    }

    pub fn work_plane_execute(
        &self,
        request: WorkPlaneTransactionRequest,
    ) -> Result<WorkPlaneTransactionResult, String> {
        validate_transaction(&request)?;
        let environment =
            self.require_work_plane_authority(&request.environment_id, &request.project_id)?;
        let mut encoded = serde_json::to_value(&request)
            .map_err(|error| format!("encode Work Plane identity failed: {error}"))?;
        encoded.sort_all_objects();
        let target = format!(
            "sha256:{:x}",
            Sha256::digest(encoded.to_string().as_bytes())
        );
        if let Some(decision) = self.journal.existing_request_decision(
            &request.request_id,
            "computer/work-plane/execute",
            &target,
        )? {
            return match decision {
                RequestDecision::Replay(value) => serde_json::from_value(value)
                    .map_err(|error| format!("decode Work Plane replay failed: {error}")),
                RequestDecision::RecordedError(code) => Err(code),
                RequestDecision::UnknownOutcome => Err(unknown_outcome(&request.environment_id)),
                RequestDecision::Execute => {
                    Err("Computer request journal returned an invalid existing state".to_string())
                }
            };
        }
        if environment.state != ComputerState::Ready {
            return Err("Computer must be running before Work Plane can be used".to_string());
        }
        match self.journal.begin_request(
            &request.request_id,
            "computer/work-plane/execute",
            &target,
        )? {
            RequestDecision::Replay(value) => {
                return serde_json::from_value(value)
                    .map_err(|error| format!("decode Work Plane replay failed: {error}"));
            }
            RequestDecision::RecordedError(code) => return Err(code),
            RequestDecision::UnknownOutcome => {
                return Err(unknown_outcome(&request.environment_id));
            }
            RequestDecision::Execute => {}
        }
        self.journal.mark_side_effect_started(&request.request_id)?;
        let result = match self.work_plane.execute(&request) {
            Ok(result) => result,
            Err(error) => {
                return Err(self.uncertain(&request.request_id, &request.environment_id, error));
            }
        };
        validate_transaction_result(&result)
            .map_err(|error| self.uncertain(&request.request_id, &request.environment_id, error))?;
        if result.capability_id != request.capability_id
            || result.target_ref != request.target_ref
            || !result.before_revision.starts_with("sha256:")
            || !result.after_revision.starts_with("sha256:")
            || (result.outcome == WorkTransactionOutcome::Completed
                && (result.before_revision != request.if_revision || result.changes.is_empty()))
        {
            return Err(self.uncertain(
                &request.request_id,
                &request.environment_id,
                "Work Plane provider returned mismatched transaction evidence".to_string(),
            ));
        }
        let event_type = if result.outcome == WorkTransactionOutcome::Completed {
            "work_plane.transaction_completed"
        } else {
            "work_plane.transaction_rejected"
        };
        if let Err(error) = self.journal.append_event(
            &request.environment_id,
            event_type,
            json!({
                "capabilityId": result.capability_id,
                "targetRef": result.target_ref,
                "beforeRevision": result.before_revision,
                "afterRevision": result.after_revision,
                "outcome": result.outcome,
                "evidence": result.evidence,
                "contentPersisted": false
            }),
        ) {
            return Err(self.uncertain(&request.request_id, &request.environment_id, error));
        }
        let replay = serde_json::to_value(&result)
            .map_err(|error| format!("encode Work Plane replay failed: {error}"))?;
        if let Err(error) = self.journal.complete_request(&request.request_id, &replay) {
            return Err(self.uncertain(&request.request_id, &request.environment_id, error));
        }
        Ok(result)
    }

    pub fn history_status(&self) -> Result<ComputerHistoryStatus, String> {
        self.history.status()
    }

    pub fn history_set_enabled(
        &self,
        request: ComputerHistorySetEnabledRequest,
    ) -> Result<ComputerHistoryStatus, String> {
        let _guard = self.operation_guard();
        self.history.set_enabled(request.enabled)
    }

    pub fn history_query(
        &self,
        request: ComputerHistoryQuery,
    ) -> Result<ComputerHistoryPage, String> {
        validate_history_environment(&request.environment_id)?;
        if !(1..=200).contains(&request.limit) {
            return Err("Computer History limit must be between 1 and 200".to_string());
        }
        self.history
            .query(&request.environment_id, request.before_seq, request.limit)
    }

    pub fn history_delete(&self, request: ComputerHistoryDeleteRequest) -> Result<u64, String> {
        validate_history_environment(&request.environment_id)?;
        let _guard = self.operation_guard();
        self.history.delete(&request.environment_id)
    }

    pub fn signal_inbox_consult(
        &self,
        request: SignalInboxConsultRequest,
    ) -> Result<SignalInboxSummary, String> {
        self.signal_inbox.consult(request)
    }

    pub fn signal_inbox_claim(
        &self,
        request: SignalClaimRequest,
    ) -> Result<Vec<SignalItem>, String> {
        self.signal_inbox.claim(request)
    }

    pub fn signal_inbox_defer(&self, request: SignalDeferRequest) -> Result<SignalItem, String> {
        self.signal_inbox.defer(request)
    }

    pub fn signal_inbox_resolve(
        &self,
        request: SignalResolveRequest,
    ) -> Result<SignalItem, String> {
        self.signal_inbox.resolve(request)
    }

    pub fn signal_inbox_revoke_account(
        &self,
        request: SignalAccountRevokeRequest,
    ) -> Result<u64, String> {
        self.signal_inbox.revoke_account(request)
    }

    pub fn replay(
        &self,
        environment_id: &str,
        after_seq: u64,
        limit: u32,
    ) -> Result<ComputerReplayPage, String> {
        self.journal.replay(environment_id, after_seq, limit)
    }

    fn require_environment(&self, environment_id: &str) -> Result<ComputerEnvironment, String> {
        let mut environment = self
            .journal
            .environment(environment_id)?
            .ok_or_else(|| "Computer environment does not exist".to_string())?;
        if let Some(binding) = self
            .journal
            .coworker_binding_for_environment(environment_id)?
        {
            environment.project_id = binding.active_project_id;
            if let (Some(project_name), Some(project_path)) =
                (binding.active_project_name, binding.active_project_path)
            {
                environment.project_name = project_name;
                environment.project_path = project_path;
            }
        }
        Ok(environment)
    }

    fn require_work_plane_scope(
        &self,
        environment_id: &str,
        project_id: &str,
    ) -> Result<ComputerEnvironment, String> {
        let environment = self.require_work_plane_authority(environment_id, project_id)?;
        if environment.state != ComputerState::Ready {
            return Err("Computer must be running before Work Plane can be used".to_string());
        }
        Ok(environment)
    }

    fn require_work_plane_authority(
        &self,
        environment_id: &str,
        project_id: &str,
    ) -> Result<ComputerEnvironment, String> {
        let environment = self.require_granted_environment(environment_id)?;
        if environment.project_id.as_deref() != Some(project_id) {
            return Err(
                "project_access_denied: Work Plane is bound to the active Project".to_string(),
            );
        }
        Ok(environment)
    }

    fn require_granted_environment(
        &self,
        environment_id: &str,
    ) -> Result<ComputerEnvironment, String> {
        let environment = self.require_environment(environment_id)?;
        let denied =
            || "project_access_denied: Computer requires an active Project grant".to_string();
        let binding = self
            .journal
            .coworker_binding_for_environment(environment_id)?
            .ok_or_else(denied)?;
        let project_id = binding.active_project_id.as_deref().ok_or_else(denied)?;
        if !self
            .journal
            .project_grants(&binding.coworker_id)?
            .iter()
            .any(|grant| {
                grant.project_id.as_deref() == Some(project_id)
                    && grant.project_path == environment.project_path
            })
            || binding.active_project_path.as_deref() != Some(environment.project_path.as_str())
        {
            return Err(denied());
        }
        Ok(environment)
    }

    fn require_live_environment(
        &self,
        environment_id: &str,
    ) -> Result<ComputerEnvironment, String> {
        let mut environment = self.require_environment(environment_id)?;
        if let Some(provider) = self
            .provider
            .resolve(environment_id, Path::new(&environment.project_path))?
        {
            apply_provider_environment(&mut environment, provider);
        }
        Ok(environment)
    }

    fn complete_environment_request(
        &self,
        request_id: &str,
        environment_id: &str,
    ) -> Result<(), String> {
        self.journal
            .complete_request(request_id, &json!({ "environmentId": environment_id }))
    }

    fn uncertain(&self, request_id: &str, environment_id: &str, detail: String) -> String {
        let _ = self
            .journal
            .mark_unknown_outcome(request_id, environment_id);
        format!("unknown_outcome: {detail}")
    }

    fn record_local_rejection(&self, request_id: &str, code: &str, detail: String) -> String {
        match self.journal.fail_request(request_id, code) {
            Ok(()) => detail,
            Err(error) => format!("computer_request_journal_failed: {error}; {detail}"),
        }
    }

    fn operation_guard(&self) -> MutexGuard<'_, ()> {
        self.operations
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
    }
}

fn apply_provider_environment(
    environment: &mut ComputerEnvironment,
    provider: ProviderEnvironment,
) {
    environment.state = provider.state;
    environment.attach_url = provider.attach_url;
    environment.active_pack_version = provider.active_pack_version;
    environment.pack_update_available = provider.pack_update_available;
}

fn validate_history_environment(environment_id: &str) -> Result<(), String> {
    if environment_id.is_empty() || environment_id.len() > 200 {
        Err("Computer History environmentId is invalid".to_string())
    } else {
        Ok(())
    }
}

fn canonical_project(value: &str) -> Result<PathBuf, String> {
    let path = Path::new(value)
        .canonicalize()
        .map_err(|error| format!("resolve computer project failed: {error}"))?;
    if !path.is_dir() {
        return Err("Computer project must be a directory".to_string());
    }
    Ok(path)
}

fn coworker_environment_id(coworker_id: &str) -> String {
    let digest = Sha256::digest(coworker_id.as_bytes());
    format!("computer-coworker-{}", hex_prefix(&digest, 12))
}

fn project_operation_target(coworker_id: &str, project_id: &str) -> String {
    let digest = Sha256::digest(project_id.as_bytes());
    format!("{coworker_id}:project:{}", hex_prefix(&digest, 12))
}

fn hex_prefix(bytes: &[u8], count: usize) -> String {
    bytes
        .iter()
        .take(count / 2)
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

fn project_name(path: &Path) -> String {
    path.file_name()
        .and_then(|value| value.to_str())
        .filter(|value| !value.trim().is_empty())
        .unwrap_or("Project")
        .to_string()
}

fn requested_project_name(value: &str, path: &Path) -> String {
    let value = value.trim();
    if value.is_empty() {
        project_name(path)
    } else {
        value.chars().take(160).collect()
    }
}

fn unknown_outcome(environment_id: &str) -> String {
    format!("unknown_outcome: computer operation for {environment_id} cannot be replayed safely")
}

fn supported_semantic_key(key: &str) -> bool {
    if matches!(
        key,
        "Alt"
            | "Control"
            | "Shift"
            | "Meta"
            | "ArrowLeft"
            | "ArrowUp"
            | "ArrowRight"
            | "ArrowDown"
            | "Enter"
            | "Escape"
            | "Tab"
            | "Space"
            | "Backspace"
            | "Delete"
            | "Home"
            | "End"
            | "PageUp"
            | "PageDown"
    ) {
        return true;
    }
    let mut characters = key.chars();
    matches!((characters.next(), characters.next()), (Some(value), None) if !value.is_control())
}

fn validate_semantic_action(request: &SemanticActRequest) -> Result<(), String> {
    if request.state_version.len() != 71 || !request.state_version.starts_with("sha256:") {
        return Err("Computer semantic action requires a sha256 stateVersion".to_string());
    }
    if request.target_ref.is_empty() || request.target_ref.len() > 100 {
        return Err("Computer semantic targetRef must contain 1 to 100 bytes".to_string());
    }
    if request.expected_role.is_empty() || request.expected_role.len() > 100 {
        return Err("Computer semantic expectedRole must contain 1 to 100 bytes".to_string());
    }
    if request.expected_name.len() > 512 {
        return Err("Computer semantic expectedName must be at most 512 bytes".to_string());
    }
    if request.lease_id.is_empty() || request.lease_id.len() > 200 {
        return Err("Computer semantic action requires a valid display lease".to_string());
    }
    match &request.action {
        super::model::SemanticActionKind::SetText => {
            let text = request
                .text
                .as_ref()
                .ok_or_else(|| "Computer semantic set_text requires text".to_string())?;
            if text.len() > 8192 {
                return Err("Computer semantic text must be at most 8192 bytes".to_string());
            }
            if request.key.is_some() {
                return Err("Computer semantic key is only valid for press_key".to_string());
            }
            if !request.input_sequence.is_empty() {
                return Err(
                    "Computer semantic inputSequence is only valid for input_sequence".to_string(),
                );
            }
        }
        super::model::SemanticActionKind::PressKey => {
            let key = request
                .key
                .as_deref()
                .ok_or_else(|| "Computer semantic press_key requires key".to_string())?;
            if !supported_semantic_key(key) {
                return Err("Computer semantic key is not allowlisted".to_string());
            }
            if request.text.is_some() {
                return Err("Computer semantic text is only valid for set_text".to_string());
            }
            if !request.input_sequence.is_empty() {
                return Err(
                    "Computer semantic inputSequence is only valid for input_sequence".to_string(),
                );
            }
        }
        super::model::SemanticActionKind::InputSequence => {
            if request.text.is_some() || request.key.is_some() {
                return Err(
                    "Computer semantic input_sequence accepts only inputSequence".to_string(),
                );
            }
            if request.input_sequence.is_empty() || request.input_sequence.len() > 64 {
                return Err(
                    "Computer semantic inputSequence must contain 1 to 64 steps".to_string()
                );
            }
            let mut total_ms = 0_u32;
            for step in &request.input_sequence {
                if step.keys.is_empty() || step.keys.len() > 3 {
                    return Err("Computer semantic input step must contain 1 to 3 keys".to_string());
                }
                if step.keys.iter().any(|key| !supported_semantic_key(key)) {
                    return Err(
                        "Computer semantic input step contains a non-allowlisted key".to_string(),
                    );
                }
                let mut unique = step.keys.clone();
                unique.sort();
                unique.dedup();
                if unique.len() != step.keys.len() {
                    return Err("Computer semantic input step keys must be unique".to_string());
                }
                if !(16..=2_000).contains(&step.hold_ms) || step.wait_ms > 1_000 {
                    return Err(
                        "Computer semantic input timing is outside the bounded range".to_string(),
                    );
                }
                total_ms = total_ms
                    .saturating_add(step.hold_ms)
                    .saturating_add(step.wait_ms);
            }
            if total_ms > 8_000 {
                return Err(
                    "Computer semantic inputSequence must finish within 8000 ms".to_string()
                );
            }
        }
        _ if request.text.is_some() => {
            return Err("Computer semantic text is only valid for set_text".to_string())
        }
        _ if request.key.is_some() => {
            return Err("Computer semantic key is only valid for press_key".to_string())
        }
        _ if !request.input_sequence.is_empty() => {
            return Err(
                "Computer semantic inputSequence is only valid for input_sequence".to_string(),
            )
        }
        _ => {}
    }
    if request.realtime_mode.is_some() {
        if request.expected_role != "canvas"
            || !matches!(
                &request.action,
                super::model::SemanticActionKind::Focus
                    | super::model::SemanticActionKind::PressKey
                    | super::model::SemanticActionKind::InputSequence
            )
        {
            return Err(
                "Computer realtime mode requires a focused canvas keyboard action".to_string(),
            );
        }
        if matches!(
            &request.realtime_mode,
            Some(super::model::SemanticRealtimeMode::Stepped)
        ) && !request.return_observation
        {
            return Err("Computer stepped realtime mode requires returnObservation".to_string());
        }
    }
    Ok(())
}

fn replayable_semantic_result(result: &SemanticActResult) -> SemanticActResult {
    let mut replay = result.clone();
    replay.visual_patch = None;
    replay.observation = None;
    replay
}

#[cfg(test)]
mod tests {
    use super::super::model::{WorkChange, WorkTransactionOutcome};
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};

    struct FakeWorkPlane {
        calls: AtomicUsize,
    }

    struct LostResponseWorkPlane {
        side_effects: AtomicUsize,
    }

    impl FakeWorkPlane {
        fn new() -> Self {
            Self {
                calls: AtomicUsize::new(0),
            }
        }
    }

    impl WorkPlaneAdapter for FakeWorkPlane {
        fn describe(
            &self,
            _request: &WorkPlaneDescribeRequest,
        ) -> Result<WorkPlaneDescriptor, String> {
            unreachable!()
        }

        fn query(&self, _request: &WorkPlaneQueryRequest) -> Result<WorkPlaneQueryResult, String> {
            unreachable!()
        }

        fn execute(
            &self,
            request: &WorkPlaneTransactionRequest,
        ) -> Result<WorkPlaneTransactionResult, String> {
            self.calls.fetch_add(1, Ordering::SeqCst);
            let after = format!("sha256:{}", "b".repeat(64));
            Ok(WorkPlaneTransactionResult {
                protocol_version: super::super::work_plane::WORK_PLANE_PROTOCOL.to_string(),
                outcome: WorkTransactionOutcome::Completed,
                code: None,
                detail: "Verified source mutation".to_string(),
                capability_id: request.capability_id.clone(),
                target_ref: request.target_ref.clone(),
                before_revision: request.if_revision.clone(),
                after_revision: after.clone(),
                changes: vec![WorkChange {
                    resource_ref: request.target_ref.clone(),
                    kind: "updated".to_string(),
                    before_revision: Some(request.if_revision.clone()),
                    after_revision: Some(after),
                }],
                evidence: vec!["source_readback".to_string()],
                reversible: true,
                recovery: None,
            })
        }
    }

    impl WorkPlaneAdapter for LostResponseWorkPlane {
        fn describe(
            &self,
            _request: &WorkPlaneDescribeRequest,
        ) -> Result<WorkPlaneDescriptor, String> {
            unreachable!()
        }

        fn query(&self, _request: &WorkPlaneQueryRequest) -> Result<WorkPlaneQueryResult, String> {
            unreachable!()
        }

        fn execute(
            &self,
            _request: &WorkPlaneTransactionRequest,
        ) -> Result<WorkPlaneTransactionResult, String> {
            self.side_effects.fetch_add(1, Ordering::SeqCst);
            Err("simulated_response_lost_after_effect".to_string())
        }
    }

    fn service_with_environment() -> NekoComputerService {
        let journal = ComputerJournal::in_memory();
        journal
            .upsert_environment(
                "computer-abc",
                "Wiii",
                "C:/wiii",
                ComputerState::Ready,
                &super::super::model::ComputerResources::default(),
                "computer.ready",
            )
            .unwrap();
        let provider = Arc::new(LocalDockerComputerProvider::new(std::env::temp_dir()));
        NekoComputerService {
            history: ComputerHistory::in_memory(),
            signal_inbox: SignalInbox::in_memory(),
            journal,
            provider: provider.clone(),
            work_plane: provider,
            operations: Arc::new(Mutex::new(())),
        }
    }

    fn service_with_fake_work_plane() -> (NekoComputerService, Arc<FakeWorkPlane>) {
        let journal = ComputerJournal::in_memory();
        journal
            .grant_project("wiii-coworker-neko", "project-wiii", "Wiii", "C:/wiii")
            .unwrap();
        journal
            .activate_coworker_project(CoworkerProjectActivation {
                coworker_id: "wiii-coworker-neko",
                environment_id: "computer-abc",
                project_id: "project-wiii",
                project_name: "Wiii",
                project_path: "C:/wiii",
                state: ComputerState::Ready,
                resources: &super::super::model::ComputerResources::default(),
                event_type: "computer.ready",
            })
            .unwrap();
        let provider = Arc::new(LocalDockerComputerProvider::new(std::env::temp_dir()));
        let work_plane = Arc::new(FakeWorkPlane::new());
        (
            NekoComputerService {
                history: ComputerHistory::in_memory(),
                signal_inbox: SignalInbox::in_memory(),
                journal,
                provider,
                work_plane: work_plane.clone(),
                operations: Arc::new(Mutex::new(())),
            },
            work_plane,
        )
    }

    fn service_with_work_plane(work_plane: Arc<dyn WorkPlaneAdapter>) -> NekoComputerService {
        let journal = ComputerJournal::in_memory();
        journal
            .grant_project("wiii-coworker-neko", "project-wiii", "Wiii", "C:/wiii")
            .unwrap();
        journal
            .activate_coworker_project(CoworkerProjectActivation {
                coworker_id: "wiii-coworker-neko",
                environment_id: "computer-abc",
                project_id: "project-wiii",
                project_name: "Wiii",
                project_path: "C:/wiii",
                state: ComputerState::Ready,
                resources: &super::super::model::ComputerResources::default(),
                event_type: "computer.ready",
            })
            .unwrap();
        NekoComputerService {
            history: ComputerHistory::in_memory(),
            signal_inbox: SignalInbox::in_memory(),
            journal,
            provider: Arc::new(LocalDockerComputerProvider::new(std::env::temp_dir())),
            work_plane,
            operations: Arc::new(Mutex::new(())),
        }
    }

    #[test]
    fn work_plane_replays_completed_transactions_without_a_display_lease() {
        let (service, adapter) = service_with_fake_work_plane();
        let request = WorkPlaneTransactionRequest {
            request_id: "operation-work-1".to_string(),
            environment_id: "computer-abc".to_string(),
            project_id: "project-wiii".to_string(),
            capability_id: "project.file.patch_text".to_string(),
            capability_version: "1".to_string(),
            target_ref: "work:file:YWxwaGE".to_string(),
            if_revision: format!("sha256:{}", "a".repeat(64)),
            input: json!({ "expectedText": "old", "replacement": "new" }),
        };

        let first = service.work_plane_execute(request.clone()).unwrap();
        let replay = service.work_plane_execute(request).unwrap();

        assert_eq!(first, replay);
        assert_eq!(first.outcome, WorkTransactionOutcome::Completed);
        assert_eq!(adapter.calls.load(Ordering::SeqCst), 1);
        assert_eq!(
            service
                .require_environment("computer-abc")
                .unwrap()
                .seat
                .state,
            SeatState::Available
        );
    }

    #[test]
    fn work_plane_lost_response_is_unknown_and_never_reexecutes_the_effect() {
        let adapter = Arc::new(LostResponseWorkPlane {
            side_effects: AtomicUsize::new(0),
        });
        let service = service_with_work_plane(adapter.clone());
        let request = WorkPlaneTransactionRequest {
            request_id: "operation-work-lost-response".to_string(),
            environment_id: "computer-abc".to_string(),
            project_id: "project-wiii".to_string(),
            capability_id: "project.file.patch_text".to_string(),
            capability_version: "1".to_string(),
            target_ref: "work:file:YWxwaGE".to_string(),
            if_revision: format!("sha256:{}", "a".repeat(64)),
            input: json!({ "expectedText": "old", "replacement": "new" }),
        };

        let first = service.work_plane_execute(request.clone()).unwrap_err();
        let replay = service.work_plane_execute(request).unwrap_err();

        assert!(first.starts_with("unknown_outcome:"));
        assert!(replay.starts_with("unknown_outcome:"));
        assert_eq!(adapter.side_effects.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn work_plane_rejects_reused_ids_for_different_transactions() {
        let (service, adapter) = service_with_fake_work_plane();
        let request = WorkPlaneTransactionRequest {
            request_id: "operation-work-conflict".to_string(),
            environment_id: "computer-abc".to_string(),
            project_id: "project-wiii".to_string(),
            capability_id: "project.file.patch_text".to_string(),
            capability_version: "1".to_string(),
            target_ref: "work:file:YWxwaGE".to_string(),
            if_revision: format!("sha256:{}", "a".repeat(64)),
            input: json!({ "expectedText": "old", "replacement": "new" }),
        };
        service.work_plane_execute(request.clone()).unwrap();
        let mut reordered = request.clone();
        reordered.input =
            serde_json::from_str(r#"{"replacement":"new","expectedText":"old"}"#).unwrap();
        service.work_plane_execute(reordered).unwrap();
        for field in 0..5 {
            let mut conflicting = request.clone();
            match field {
                0 => conflicting.capability_id = "project.file.replace_text".to_string(),
                1 => conflicting.capability_version = "2".to_string(),
                2 => conflicting.target_ref = "work:file:YmV0YQ".to_string(),
                3 => conflicting.if_revision = format!("sha256:{}", "b".repeat(64)),
                _ => conflicting.input = json!({ "expectedText": "old", "replacement": "other" }),
            }
            assert!(service.work_plane_execute(conflicting).is_err());
        }
        assert_eq!(adapter.calls.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn revoked_project_cannot_be_resumed_or_reset() {
        let (service, _) = service_with_fake_work_plane();
        service
            .journal
            .revoke_project("wiii-coworker-neko", "project-wiii")
            .unwrap();
        let resume = service
            .resume(ComputerLifecycleRequest {
                request_id: "revoked-resume".to_string(),
                environment_id: "computer-abc".to_string(),
            })
            .unwrap_err();
        let reset = service
            .reset(ComputerResetRequest {
                request_id: "revoked-reset".to_string(),
                environment_id: "computer-abc".to_string(),
                confirmation: "RESET NEKO".to_string(),
            })
            .unwrap_err();
        assert!(resume.starts_with("project_access_denied:"));
        assert!(reset.starts_with("project_access_denied:"));
        for (id, method) in [
            ("revoked-resume", "computer/resume"),
            ("revoked-reset", "computer/reset"),
        ] {
            assert!(service
                .journal
                .existing_request_decision(id, method, "computer-abc")
                .unwrap()
                .is_none());
        }
    }

    #[test]
    fn corrupt_optional_computer_key_is_preserved_for_recovery() {
        let root =
            std::env::temp_dir().join(format!("wiii-computer-key-test-{}", uuid::Uuid::new_v4()));
        let state = root.join("neko-computer-v1");
        std::fs::create_dir_all(&state).unwrap();
        let key = state.join("computer-history-v1.key");
        std::fs::write(&key, b"incomplete-key").unwrap();
        let availability: super::super::ComputerAvailability = NekoComputerService::open(&root);
        assert!(availability.is_err());
        assert_eq!(std::fs::read(key).unwrap(), b"incomplete-key");
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn changed_project_grant_does_not_authorize_the_old_mount() {
        let (service, _) = service_with_fake_work_plane();
        service
            .journal
            .grant_project("wiii-coworker-neko", "project-wiii", "Other", "C:/other")
            .unwrap();
        assert!(service
            .require_granted_environment("computer-abc")
            .unwrap_err()
            .starts_with("project_access_denied:"));
    }

    #[test]
    fn environment_identity_is_stable_and_coworker_scoped() {
        let first = coworker_environment_id("wiii-coworker-neko");
        let second = coworker_environment_id("wiii-coworker-neko");
        let other = coworker_environment_id("wiii-coworker-other");
        assert_eq!(first, second);
        assert_ne!(first, other);
        assert!(first.starts_with("computer-coworker-"));
    }

    #[test]
    fn semantic_action_validation_rejects_stale_or_oversized_selectors() {
        let valid = SemanticActRequest {
            request_id: "request-1".to_string(),
            environment_id: "computer-1".to_string(),
            lease_id: "lease-1".to_string(),
            state_version: format!("sha256:{}", "a".repeat(64)),
            target_ref: "ui-0001".to_string(),
            expected_role: "push button".to_string(),
            expected_name: "Open".to_string(),
            action: super::super::model::SemanticActionKind::Invoke,
            text: None,
            key: None,
            input_sequence: Vec::new(),
            return_observation: false,
            realtime_mode: None,
        };
        assert!(validate_semantic_action(&valid).is_ok());
        assert!(validate_semantic_action(&SemanticActRequest {
            action: super::super::model::SemanticActionKind::PressKey,
            key: Some("n".to_string()),
            ..valid.clone()
        })
        .is_ok());
        assert!(validate_semantic_action(&SemanticActRequest {
            action: super::super::model::SemanticActionKind::PressKey,
            key: Some("\n".to_string()),
            ..valid.clone()
        })
        .is_err());
        assert!(validate_semantic_action(&SemanticActRequest {
            state_version: "stale".to_string(),
            ..valid.clone()
        })
        .is_err());
        assert!(validate_semantic_action(&SemanticActRequest {
            action: super::super::model::SemanticActionKind::InputSequence,
            input_sequence: vec![super::super::model::SemanticInputStep {
                keys: vec!["Shift".to_string(), "ArrowUp".to_string()],
                hold_ms: 250,
                wait_ms: 20,
            }],
            ..valid.clone()
        })
        .is_ok());
        assert!(validate_semantic_action(&SemanticActRequest {
            action: super::super::model::SemanticActionKind::InputSequence,
            input_sequence: vec![super::super::model::SemanticInputStep {
                keys: vec!["ArrowUp".to_string()],
                hold_ms: 8_001,
                wait_ms: 0,
            }],
            ..valid.clone()
        })
        .is_err());
        assert!(validate_semantic_action(&SemanticActRequest {
            target_ref: "web-canvas".to_string(),
            expected_role: "canvas".to_string(),
            action: super::super::model::SemanticActionKind::Focus,
            return_observation: true,
            realtime_mode: Some(super::super::model::SemanticRealtimeMode::Stepped),
            ..valid.clone()
        })
        .is_ok());
        assert!(validate_semantic_action(&SemanticActRequest {
            target_ref: "web-canvas".to_string(),
            expected_role: "canvas".to_string(),
            action: super::super::model::SemanticActionKind::Focus,
            realtime_mode: Some(super::super::model::SemanticRealtimeMode::Stepped),
            ..valid.clone()
        })
        .is_err());
        assert!(validate_semantic_action(&SemanticActRequest {
            action: super::super::model::SemanticActionKind::SetText,
            text: None,
            key: None,
            ..valid
        })
        .is_err());
    }

    #[test]
    fn semantic_action_replay_drops_transient_visual_data() {
        let result = SemanticActResult {
            environment_id: "computer-1".to_string(),
            outcome: SemanticActionOutcome::Completed,
            code: None,
            detail: "Input delivered".to_string(),
            action: super::super::model::SemanticActionKind::InputSequence,
            target_ref: "web-canvas".to_string(),
            before_state_version: format!("sha256:{}", "a".repeat(64)),
            after_state_version: format!("sha256:{}", "b".repeat(64)),
            verified: true,
            effect: Some("input_delivered".to_string()),
            route: Some("browser_target_input_sequence".to_string()),
            evidence: vec!["post_action_visual".to_string()],
            escalation: None,
            visual_patch: Some(super::super::model::SemanticVisualPatch {
                node_ref: "web-canvas".to_string(),
                mime_type: "image/png".to_string(),
                width: 640,
                height: 400,
                sha256: format!("sha256:{}", "c".repeat(64)),
                data: "image bytes".to_string(),
            }),
            clock: Some(super::super::model::SemanticClockResult {
                mode: super::super::model::SemanticRealtimeMode::Stepped,
                active_ms: 240,
                watchdog_ms: 30_000,
                deadline_ms: Some(1_000),
            }),
            observation: Some(SemanticSnapshot {
                protocol_version: "neko-computer.semantic.v1".to_string(),
                environment_id: "computer-1".to_string(),
                state_version: format!("sha256:{}", "d".repeat(64)),
                captured_at: "2026-09-01T00:00:00Z".to_string(),
                platform: "linux_atspi".to_string(),
                screen: super::super::model::SemanticScreen {
                    width: 1440,
                    height: 900,
                },
                active_window_ref: None,
                frame: None,
                nodes: Vec::new(),
                truncated: false,
                scope_ref: Some("app:browser".to_string()),
                projection: super::super::model::SemanticProjection::Full,
                next_continuation: None,
                delta_from_state_version: None,
                removed_refs: Vec::new(),
                visual_patch: None,
            }),
        };

        let replay = replayable_semantic_result(&result);
        assert!(replay.visual_patch.is_none());
        assert!(replay.observation.is_none());
        assert!(result.visual_patch.is_some());
        assert!(result.observation.is_some());
        assert_eq!(replay.effect.as_deref(), Some("input_delivered"));
        assert_eq!(
            replay.clock.as_ref().map(|clock| clock.active_ms),
            Some(240)
        );
    }

    #[test]
    fn rejected_seat_mutations_are_recorded_instead_of_left_unknown() {
        let service = service_with_environment();
        service
            .acquire_seat(SeatAcquireRequest {
                request_id: "request-acquire-one".to_string(),
                environment_id: "computer-abc".to_string(),
                owner_id: "agent-session:one".to_string(),
                user_controlled: false,
            })
            .unwrap();

        let rejected = SeatAcquireRequest {
            request_id: "request-acquire-two".to_string(),
            environment_id: "computer-abc".to_string(),
            owner_id: "agent-session:two".to_string(),
            user_controlled: false,
        };
        assert!(service
            .acquire_seat(rejected.clone())
            .unwrap_err()
            .contains("already controlled by another owner"));
        assert_eq!(
            service
                .journal
                .begin_request(
                    &rejected.request_id,
                    "computer/seat/acquire",
                    &rejected.environment_id,
                )
                .unwrap(),
            RequestDecision::RecordedError("seat_acquire_rejected".to_string()),
        );

        let release = SeatReleaseRequest {
            request_id: "request-release-stale".to_string(),
            environment_id: "computer-abc".to_string(),
            lease_id: "lease-stale".to_string(),
        };
        assert!(service.release_seat(release.clone()).is_err());
        assert_eq!(
            service
                .journal
                .begin_request(
                    &release.request_id,
                    "computer/seat/release",
                    &release.environment_id,
                )
                .unwrap(),
            RequestDecision::RecordedError("seat_release_rejected".to_string()),
        );
    }
}
