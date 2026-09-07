use super::model::{
    ComputerDoctor, ComputerPackManifest, ComputerPackageState, ComputerPackageStatus,
    ComputerResourcePreset, ComputerResources, ComputerState, ComputerStorageSummary,
    SemanticActRequest, SemanticActResult, SemanticObserveRequest, SemanticSnapshot,
    WorkPlaneDescribeRequest, WorkPlaneDescriptor, WorkPlaneQueryRequest, WorkPlaneQueryResult,
    WorkPlaneTransactionRequest, WorkPlaneTransactionResult,
};
use super::watcher::WatcherBatch;
use super::work_plane::WorkPlaneAdapter;
use serde::Serialize;
use serde_json::Value;
use std::ffi::{OsStr, OsString};
use std::fs;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, ExitStatus, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread;
use std::time::{Duration, Instant};

const IMAGE_REF: &str = "wiii/web-computer:semantic-v40";
const OBSOLETE_IMAGE_REFS: [&str; 38] = [
    "wiii/web-computer:semantic-v39",
    "wiii/web-computer:semantic-v38",
    "wiii/web-computer:semantic-v37",
    "wiii/web-computer:semantic-v36",
    "wiii/web-computer:semantic-v35",
    "wiii/web-computer:semantic-v34",
    "wiii/web-computer:semantic-v33",
    "wiii/web-computer:semantic-v32",
    "wiii/web-computer:semantic-v31",
    "wiii/web-computer:semantic-v30",
    "wiii/web-computer:semantic-v29",
    "wiii/web-computer:semantic-v28",
    "wiii/web-computer:semantic-v27",
    "wiii/web-computer:semantic-v26",
    "wiii/web-computer:semantic-v25",
    "wiii/web-computer:semantic-v24",
    "wiii/web-computer:semantic-v23",
    "wiii/web-computer:semantic-v22",
    "wiii/web-computer:semantic-v21",
    "wiii/web-computer:semantic-v20",
    "wiii/web-computer:semantic-v19",
    "wiii/web-computer:semantic-v17",
    "wiii/web-computer:semantic-v16",
    "wiii/web-computer:semantic-v15",
    "wiii/web-computer:semantic-v14",
    "wiii/web-computer:semantic-v13",
    "wiii/web-computer:semantic-v12",
    "wiii/web-computer:semantic-v11",
    "wiii/web-computer:semantic-v10",
    "wiii/web-computer:semantic-v9",
    "wiii/web-computer:semantic-v8",
    "wiii/web-computer:semantic-v7",
    "wiii/web-computer:semantic-v6",
    "wiii/web-computer:semantic-v5",
    "wiii/web-computer:semantic-v4",
    "wiii/web-computer:semantic-v3",
    "wiii/web-computer:semantic-v2",
    "wiii/local-computer:pilot-v1",
];
const OWNER_LABEL: &str = "neko-computer-v1";
const PACK_ID: &str = "web-computer-semantic-v40";
const PACK_SCHEMA_VERSION: &str = "wiii-computer-pack.v2";
const PACK_VERSION: &str = "semantic-v40";
const PACK_CHANNEL: &str = "preview";
const PROFILE_SCHEMA_VERSION: u32 = 1;
pub(crate) const CORE_PACKAGE_ID: &str = "web-computer-core";
const MAX_CONTROL_OUTPUT: usize = 256 * 1024;
const MAX_TERMINAL_OUTPUT: usize = 512 * 1024;
const MAX_SEMANTIC_OUTPUT: usize = 2 * 1024 * 1024;
const MAX_WORK_PLANE_OUTPUT: usize = 1024 * 1024;
const CONTROL_TIMEOUT: Duration = Duration::from_secs(45);
const BUILD_TIMEOUT: Duration = Duration::from_secs(15 * 60);
const TERMINAL_TIMEOUT: Duration = Duration::from_secs(90);
const SEMANTIC_TIMEOUT: Duration = Duration::from_secs(20);
const WORK_PLANE_TIMEOUT: Duration = Duration::from_secs(90);

#[derive(Clone, Debug)]
pub(crate) struct LocalDockerComputerProvider {
    docker: Option<PathBuf>,
    state_root: PathBuf,
}

#[derive(Clone, Debug)]
pub(crate) struct ProviderEnvironment {
    pub state: ComputerState,
    pub attach_url: Option<String>,
    pub active_pack_version: Option<String>,
    pub pack_update_available: bool,
}

#[derive(Clone, Debug)]
struct ContainerVerification {
    compatible: bool,
    active_pack_version: Option<String>,
}

#[derive(Clone, Debug)]
pub(crate) struct ProviderTerminalResult {
    pub exit_code: Option<i32>,
    pub stdout: String,
    pub stderr: String,
    pub truncated: bool,
}

pub(crate) trait ComputerProvider: Send + Sync {
    fn doctor(&self) -> ComputerDoctor;
    fn ensure(
        &self,
        environment_id: &str,
        project_path: &Path,
        resources: &ComputerResources,
    ) -> Result<ProviderEnvironment, String>;
    fn resolve(
        &self,
        environment_id: &str,
        project_path: &Path,
    ) -> Result<Option<ProviderEnvironment>, String>;
    fn suspend(&self, environment_id: &str) -> Result<(), String>;
    fn resume(
        &self,
        environment_id: &str,
        project_path: &Path,
        resources: &ComputerResources,
    ) -> Result<ProviderEnvironment, String>;
    fn reset(
        &self,
        environment_id: &str,
        project_path: &Path,
        resources: &ComputerResources,
    ) -> Result<ProviderEnvironment, String>;
    fn destroy(&self, environment_id: &str) -> Result<(), String>;
    fn detach(&self, environment_id: &str) -> Result<(), String>;
    fn install_package(&self, package_id: &str) -> Result<(), String>;
    fn remove_package(&self, package_id: &str) -> Result<(), String>;
    fn semantic_observe(
        &self,
        request: &SemanticObserveRequest,
    ) -> Result<SemanticSnapshot, String>;
    fn semantic_act(&self, request: &SemanticActRequest) -> Result<SemanticActResult, String>;
    fn app_events_poll(
        &self,
        environment_id: &str,
        after_cursor: Option<&str>,
        limit: u32,
        wait_ms: u32,
        stopped: Option<&AtomicBool>,
    ) -> Result<WatcherBatch, String>;
    fn resume_realtime(&self, environment_id: &str) -> Result<(), String>;
    fn terminal_exec(
        &self,
        environment_id: &str,
        command: &str,
    ) -> Result<ProviderTerminalResult, String>;
    fn browser_navigate(&self, environment_id: &str, url: &str) -> Result<(), String>;
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct ProviderAppEventsRequest<'a> {
    environment_id: &'a str,
    after_cursor: Option<&'a str>,
    limit: u32,
    wait_ms: u32,
}

#[derive(Debug)]
struct BoundedOutput {
    status: ExitStatus,
    stdout: Vec<u8>,
    stderr: Vec<u8>,
    truncated: bool,
}

impl BoundedOutput {
    fn success(&self) -> bool {
        self.status.success()
    }

    fn stdout_text(&self) -> String {
        String::from_utf8_lossy(&self.stdout).trim().to_string()
    }

    fn stderr_text(&self) -> String {
        String::from_utf8_lossy(&self.stderr).trim().to_string()
    }
}

impl LocalDockerComputerProvider {
    pub(crate) fn new(state_root: PathBuf) -> Self {
        Self {
            docker: resolve_docker_cli(),
            state_root,
        }
    }

    pub(crate) fn doctor(&self) -> ComputerDoctor {
        let Some(docker) = &self.docker else {
            return ComputerDoctor {
                supported: false,
                runtime_ready: false,
                package_ready: false,
                docker_cli: false,
                daemon_ready: false,
                image_ready: false,
                provider_kind: "local_docker".to_string(),
                isolation_class: "shared_container".to_string(),
                available_cpus: None,
                available_memory_bytes: None,
                recommended_preset: ComputerResourcePreset::Balanced,
                packages: Self::package_catalog(false, None),
                storage: Self::storage_summary(),
                detail: "Docker CLI was not found in the installed application paths".to_string(),
            };
        };

        let cli_ready = run_bounded(
            docker,
            [OsString::from("--version")],
            None,
            CONTROL_TIMEOUT,
            MAX_CONTROL_OUTPUT,
        )
        .map(|output| output.success())
        .unwrap_or(false);
        let daemon = run_bounded(
            docker,
            [
                OsString::from("info"),
                OsString::from("--format"),
                OsString::from("{{json .}}"),
            ],
            None,
            CONTROL_TIMEOUT,
            MAX_CONTROL_OUTPUT,
        );
        let daemon_ready = daemon
            .as_ref()
            .map(|value| value.success())
            .unwrap_or(false);
        let daemon_facts = daemon
            .as_ref()
            .ok()
            .filter(|value| value.success())
            .and_then(|value| serde_json::from_str::<Value>(&value.stdout_text()).ok());
        let available_cpus = daemon_facts
            .as_ref()
            .and_then(|value| value.get("NCPU"))
            .and_then(Value::as_u64)
            .and_then(|value| u32::try_from(value).ok());
        let available_memory_bytes = daemon_facts
            .as_ref()
            .and_then(|value| value.get("MemTotal"))
            .and_then(Value::as_u64);
        let recommended_preset =
            ComputerResourcePreset::recommend(available_cpus, available_memory_bytes);
        let image_ready = daemon_ready && self.image_exists().unwrap_or(false);
        let installed_bytes = image_ready.then(|| self.image_size_bytes()).flatten();
        let detail = if daemon_ready {
            if image_ready {
                "Docker is ready and the Wiii computer image is available".to_string()
            } else {
                "Docker is ready; the Wiii computer image will be prepared on first use".to_string()
            }
        } else {
            daemon
                .ok()
                .map(|value| value.stderr_text())
                .filter(|value| !value.is_empty())
                .unwrap_or_else(|| {
                    "Docker Desktop is installed but its Linux engine is not running".to_string()
                })
        };

        ComputerDoctor {
            supported: cli_ready && daemon_ready,
            runtime_ready: cli_ready && daemon_ready,
            package_ready: image_ready,
            docker_cli: cli_ready,
            daemon_ready,
            image_ready,
            provider_kind: "local_docker".to_string(),
            isolation_class: "shared_container".to_string(),
            available_cpus,
            available_memory_bytes,
            recommended_preset,
            packages: Self::package_catalog(image_ready, installed_bytes),
            storage: Self::storage_summary(),
            detail,
        }
    }

    fn package_catalog(
        installed: bool,
        installed_bytes: Option<u64>,
    ) -> Vec<ComputerPackageStatus> {
        vec![ComputerPackageStatus {
            package_id: CORE_PACKAGE_ID.to_string(),
            display_name: "Web Computer Core".to_string(),
            description:
                "Desktop Linux, Browser, Terminal, Files và lớp thao tác ngữ nghĩa cho Wiii"
                    .to_string(),
            state: if installed {
                ComputerPackageState::Installed
            } else {
                ComputerPackageState::NotInstalled
            },
            manifest: ComputerPackManifest {
                schema_version: PACK_SCHEMA_VERSION.to_string(),
                version: PACK_VERSION.to_string(),
                channel: PACK_CHANNEL.to_string(),
                ai_frame_version: "wiii-ai-frame.v1".to_string(),
                profile_schema_version: PROFILE_SCHEMA_VERSION,
                upgrade_policy: "replace_shell_preserve_profile".to_string(),
                rollback_policy: "automatic_shell_restore".to_string(),
            },
            installed_bytes,
            shared_across_projects: true,
            preserves_profile_on_remove: true,
            capabilities: vec![
                "computer".to_string(),
                "browser".to_string(),
                "terminal".to_string(),
                "files".to_string(),
            ],
        }]
    }

    fn storage_summary() -> ComputerStorageSummary {
        ComputerStorageSummary {
            package_store_kind: "runtime_managed_local".to_string(),
            profile_store_kind: "durable_local".to_string(),
            project_store_kind: "host_source".to_string(),
            location_selectable: false,
        }
    }

    pub(crate) fn ensure(
        &self,
        environment_id: &str,
        project_path: &Path,
        resources: &ComputerResources,
    ) -> Result<ProviderEnvironment, String> {
        self.require_daemon()?;
        self.ensure_image()?;
        let canonical = canonical_project(project_path)?;
        let names = ProviderNames::new(environment_id);
        let secret = self.ensure_display_secret(environment_id)?;

        let mut ready_verified = false;
        if self.container_exists(&names.container)? {
            let verification =
                self.verify_container(&names.container, environment_id, &canonical)?;
            if verification.compatible {
                let state = self.container_state(&names.container)?;
                if state != "running" {
                    self.docker_checked(["start", &names.container], CONTROL_TIMEOUT)?;
                }
            } else {
                self.replace_container_shell(
                    environment_id,
                    &names,
                    &canonical,
                    &secret,
                    resources,
                )?;
                ready_verified = true;
            }
        } else {
            self.create_container(environment_id, &names, &canonical, &secret, resources)?;
        }

        if !ready_verified {
            self.wait_until_ready(&names.container)?;
        }
        Ok(ProviderEnvironment {
            state: ComputerState::Ready,
            attach_url: Some(self.attach_url(&names.container, &secret)?),
            active_pack_version: Some(PACK_VERSION.to_string()),
            pack_update_available: false,
        })
    }

    fn replace_container_shell(
        &self,
        environment_id: &str,
        names: &ProviderNames,
        project_path: &Path,
        secret_path: &Path,
        resources: &ComputerResources,
    ) -> Result<(), String> {
        if self.container_exists(&names.rollback_container)? {
            return Err(
                "computer_pack_recovery_required: a previous shell rollback is still present"
                    .to_string(),
            );
        }

        let previous_state = self.container_state(&names.container)?;
        if previous_state == "running" {
            self.docker_checked(["stop", "--time", "10", &names.container], CONTROL_TIMEOUT)?;
        }
        self.docker_checked(
            ["rename", &names.container, &names.rollback_container],
            CONTROL_TIMEOUT,
        )?;

        let replacement = self
            .create_container(environment_id, names, project_path, secret_path, resources)
            .and_then(|_| self.wait_until_ready(&names.container));
        if replacement.is_ok() {
            self.docker_checked(
                ["rm", "--force", &names.rollback_container],
                CONTROL_TIMEOUT,
            )?;
            return Ok(());
        }

        let replacement_error = replacement.expect_err("replacement failed");
        if self.container_exists(&names.container)? {
            let _ = self.docker_checked(["rm", "--force", &names.container], CONTROL_TIMEOUT);
        }
        let restored = self
            .docker_checked(
                ["rename", &names.rollback_container, &names.container],
                CONTROL_TIMEOUT,
            )
            .and_then(|_| {
                if previous_state == "running" {
                    self.docker_checked(["start", &names.container], CONTROL_TIMEOUT)?;
                }
                Ok(())
            });
        match restored {
            Ok(()) => Err(format!(
                "computer_pack_upgrade_rolled_back: {replacement_error}"
            )),
            Err(restore_error) => Err(format!(
                "unknown_outcome: Computer pack replacement failed ({replacement_error}) and the previous shell could not be restored ({restore_error})"
            )),
        }
    }

    pub(crate) fn resolve(
        &self,
        environment_id: &str,
        project_path: &Path,
    ) -> Result<Option<ProviderEnvironment>, String> {
        if self.docker.is_none() || !self.doctor().daemon_ready {
            return Ok(None);
        }
        let names = ProviderNames::new(environment_id);
        if !self.container_exists(&names.container)? {
            return Ok(None);
        }
        let canonical = canonical_project(project_path)?;
        let verification = self.verify_container(&names.container, environment_id, &canonical)?;
        if !verification.compatible {
            return Ok(Some(ProviderEnvironment {
                state: ComputerState::Suspended,
                attach_url: None,
                active_pack_version: verification.active_pack_version,
                pack_update_available: true,
            }));
        }
        let state = match self.container_state(&names.container)?.as_str() {
            "running" => ComputerState::Ready,
            "created" | "exited" | "paused" => ComputerState::Suspended,
            _ => ComputerState::Error,
        };
        let secret = self.ensure_display_secret(environment_id)?;
        let attach_url = if state == ComputerState::Ready {
            Some(self.attach_url(&names.container, &secret)?)
        } else {
            None
        };
        Ok(Some(ProviderEnvironment {
            state,
            attach_url,
            active_pack_version: verification.active_pack_version,
            pack_update_available: false,
        }))
    }

    pub(crate) fn suspend(&self, environment_id: &str) -> Result<(), String> {
        self.require_daemon()?;
        let names = ProviderNames::new(environment_id);
        self.docker_checked(["stop", "--time", "10", &names.container], CONTROL_TIMEOUT)?;
        Ok(())
    }

    pub(crate) fn resume(
        &self,
        environment_id: &str,
        project_path: &Path,
        resources: &ComputerResources,
    ) -> Result<ProviderEnvironment, String> {
        self.ensure(environment_id, project_path, resources)
    }

    pub(crate) fn reset(
        &self,
        environment_id: &str,
        project_path: &Path,
        resources: &ComputerResources,
    ) -> Result<ProviderEnvironment, String> {
        self.destroy(environment_id)?;
        self.ensure(environment_id, project_path, resources)
    }

    pub(crate) fn destroy(&self, environment_id: &str) -> Result<(), String> {
        self.require_daemon()?;
        let names = ProviderNames::new(environment_id);
        if self.container_exists(&names.container)? {
            self.docker_checked(["rm", "--force", &names.container], CONTROL_TIMEOUT)?;
        }
        if self.volume_exists(&names.volume)? {
            self.docker_checked(["volume", "rm", &names.volume], CONTROL_TIMEOUT)?;
        }
        let secret_path = self.secret_path(environment_id);
        if secret_path.exists() {
            fs::remove_file(&secret_path).map_err(|error| {
                format!("remove Wiii computer display credential failed: {error}")
            })?;
        }
        Ok(())
    }

    pub(crate) fn detach(&self, environment_id: &str) -> Result<(), String> {
        self.require_daemon()?;
        let names = ProviderNames::new(environment_id);
        if self.container_exists(&names.container)? {
            self.docker_checked(["rm", "--force", &names.container], CONTROL_TIMEOUT)?;
        }
        Ok(())
    }

    pub(crate) fn install_package(&self, package_id: &str) -> Result<(), String> {
        Self::require_core_package(package_id)?;
        self.require_daemon()?;
        self.ensure_image()
    }

    pub(crate) fn remove_package(&self, package_id: &str) -> Result<(), String> {
        Self::require_core_package(package_id)?;
        self.require_daemon()?;
        let users = self.docker_checked(
            [
                "ps",
                "--all",
                "--quiet",
                "--filter",
                &format!("label=dev.wiii.owner={OWNER_LABEL}"),
            ],
            CONTROL_TIMEOUT,
        )?;
        if !users.stdout_text().is_empty() {
            return Err(
                "computer_package_in_use: remove Project Computers before removing the package"
                    .to_string(),
            );
        }
        if self.image_exists()? {
            self.docker_checked(["image", "rm", IMAGE_REF], CONTROL_TIMEOUT)?;
        }
        for image_ref in OBSOLETE_IMAGE_REFS {
            if self.image_exists_ref(image_ref)? {
                self.docker_checked(["image", "rm", image_ref], CONTROL_TIMEOUT)?;
            }
        }
        Ok(())
    }

    fn require_core_package(package_id: &str) -> Result<(), String> {
        if package_id == CORE_PACKAGE_ID {
            Ok(())
        } else {
            Err(format!("computer_package_unknown: {package_id}"))
        }
    }

    pub(crate) fn semantic_observe(
        &self,
        request: &SemanticObserveRequest,
    ) -> Result<SemanticSnapshot, String> {
        let envelope = self.semantic_bridge_request(
            &request.environment_id,
            "observe",
            request,
            "Computer semantic observation",
            None,
        )?;
        if envelope.get("status").and_then(Value::as_str) != Some("ok") {
            return Err("Computer semantic bridge rejected observation".to_string());
        }
        serde_json::from_value(
            envelope
                .get("snapshot")
                .cloned()
                .ok_or_else(|| "Computer semantic observation returned no snapshot".to_string())?,
        )
        .map_err(|error| format!("decode Computer semantic snapshot failed: {error}"))
    }

    pub(crate) fn semantic_act(
        &self,
        request: &SemanticActRequest,
    ) -> Result<SemanticActResult, String> {
        let envelope = self.semantic_bridge_request(
            &request.environment_id,
            "act",
            request,
            "Computer semantic action",
            None,
        )?;
        if envelope.get("status").and_then(Value::as_str) != Some("ok") {
            return Err("Computer semantic bridge did not complete the action".to_string());
        }
        serde_json::from_value(
            envelope
                .get("result")
                .cloned()
                .ok_or_else(|| "Computer semantic action returned no result".to_string())?,
        )
        .map_err(|error| format!("decode Computer semantic action result failed: {error}"))
    }

    pub(crate) fn app_events_poll(
        &self,
        environment_id: &str,
        after_cursor: Option<&str>,
        limit: u32,
        wait_ms: u32,
        stopped: Option<&AtomicBool>,
    ) -> Result<WatcherBatch, String> {
        if !(1..=512).contains(&limit) {
            return Err("Computer app-event limit must be between 1 and 512".to_string());
        }
        if let Some(cursor) = after_cursor {
            if cursor.is_empty()
                || cursor.len() > 80
                || !cursor.bytes().all(|byte| {
                    byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b':' | b'-')
                })
            {
                return Err("Computer app-event cursor is invalid".to_string());
            }
        }
        if wait_ms > 15_000 {
            return Err("Computer app-event wait must not exceed 15000 ms".to_string());
        }
        let request = ProviderAppEventsRequest {
            environment_id,
            after_cursor,
            limit,
            wait_ms,
        };
        let envelope = self.semantic_bridge_request(
            environment_id,
            "events",
            &request,
            "Computer app-event poll",
            stopped,
        )?;
        if envelope.get("status").and_then(Value::as_str) != Some("ok") {
            return Err("Computer app-event bridge rejected the poll".to_string());
        }
        serde_json::from_value(
            envelope
                .get("batch")
                .cloned()
                .ok_or_else(|| "Computer app-event poll returned no batch".to_string())?,
        )
        .map_err(|error| format!("decode Computer app-event batch failed: {error}"))
    }

    fn semantic_bridge_request<T: Serialize>(
        &self,
        environment_id: &str,
        route: &str,
        request: &T,
        operation: &str,
        stopped: Option<&AtomicBool>,
    ) -> Result<Value, String> {
        let docker = self.require_daemon()?;
        let names = ProviderNames::new(environment_id);
        let input = serde_json::to_vec(request)
            .map_err(|error| format!("encode {operation} failed: {error}"))?;
        let output = run_bounded_with_input_cancellable(
            docker,
            [
                OsString::from("exec"),
                OsString::from("--interactive"),
                OsString::from(&names.container),
                OsString::from("curl"),
                OsString::from("--fail"),
                OsString::from("--silent"),
                OsString::from("--show-error"),
                OsString::from("--max-time"),
                OsString::from(SEMANTIC_TIMEOUT.as_secs().to_string()),
                OsString::from("--header"),
                OsString::from("Content-Type: application/json"),
                OsString::from("--data-binary"),
                OsString::from("@-"),
                OsString::from(format!("http://127.0.0.1:9234/{route}")),
            ],
            None,
            SEMANTIC_TIMEOUT,
            MAX_SEMANTIC_OUTPUT,
            &input,
            stopped,
        )?;
        if !output.success() {
            return Err(nonempty_error(&format!("{operation} failed"), &output));
        }
        serde_json::from_slice(&output.stdout)
            .map_err(|error| format!("decode {operation} failed: {error}"))
    }

    fn work_plane_bridge<T: Serialize>(
        &self,
        environment_id: &str,
        operation: &str,
        request: &T,
    ) -> Result<Value, String> {
        let docker = self.require_daemon()?;
        let names = ProviderNames::new(environment_id);
        let input = serde_json::to_vec(request)
            .map_err(|error| format!("encode Work Plane request failed: {error}"))?;
        let output = run_bounded_with_input(
            docker,
            [
                OsString::from("exec"),
                OsString::from("--interactive"),
                OsString::from(&names.container),
                OsString::from("python3"),
                OsString::from("/usr/local/lib/wiii-computer/work_plane_bridge.py"),
                OsString::from(operation),
            ],
            None,
            WORK_PLANE_TIMEOUT,
            MAX_WORK_PLANE_OUTPUT,
            &input,
        )?;
        if !output.success() {
            return Err(nonempty_error("Work Plane provider failed", &output));
        }
        let envelope: Value = serde_json::from_slice(&output.stdout)
            .map_err(|error| format!("decode Work Plane response failed: {error}"))?;
        if envelope.get("status").and_then(Value::as_str) != Some("ok") {
            return Err("Work Plane provider rejected the request".to_string());
        }
        Ok(envelope)
    }

    pub(crate) fn resume_realtime(&self, environment_id: &str) -> Result<(), String> {
        let docker = self.require_daemon()?;
        let names = ProviderNames::new(environment_id);
        if !self.container_exists(&names.container)? {
            return Ok(());
        }
        let output = run_bounded(
            docker,
            [
                OsString::from("exec"),
                OsString::from(&names.container),
                OsString::from("python3"),
                OsString::from("/usr/local/lib/wiii-computer/semantic_bridge.py"),
                OsString::from("clock-resume"),
            ],
            None,
            SEMANTIC_TIMEOUT,
            MAX_CONTROL_OUTPUT,
        )?;
        if !output.success() {
            return Err(nonempty_error("Computer realtime resume failed", &output));
        }
        Ok(())
    }

    pub(crate) fn terminal_exec(
        &self,
        environment_id: &str,
        command: &str,
    ) -> Result<ProviderTerminalResult, String> {
        if command.trim().is_empty() || command.len() > 16 * 1024 {
            return Err("Computer terminal command must contain 1 to 16384 bytes".to_string());
        }
        let docker = self.require_daemon()?;
        let names = ProviderNames::new(environment_id);
        let output = run_bounded(
            docker,
            [
                OsString::from("exec"),
                OsString::from("--workdir"),
                OsString::from("/workspace/project"),
                OsString::from(&names.container),
                OsString::from("/bin/sh"),
                OsString::from("-lc"),
                OsString::from(command),
            ],
            None,
            TERMINAL_TIMEOUT,
            MAX_TERMINAL_OUTPUT,
        )?;
        Ok(ProviderTerminalResult {
            exit_code: output.status.code(),
            stdout: output.stdout_text(),
            stderr: output.stderr_text(),
            truncated: output.truncated,
        })
    }

    pub(crate) fn browser_navigate(&self, environment_id: &str, url: &str) -> Result<(), String> {
        validate_browser_url(url)?;
        let names = ProviderNames::new(environment_id);
        self.docker_checked_owned(
            vec![
                OsString::from("exec"),
                OsString::from("--env"),
                OsString::from("DISPLAY=:1"),
                OsString::from(&names.container),
                OsString::from("wiii-browser"),
                OsString::from(url),
            ],
            CONTROL_TIMEOUT,
        )?;
        Ok(())
    }

    fn require_daemon(&self) -> Result<&Path, String> {
        let docker = self
            .docker
            .as_deref()
            .ok_or_else(|| "Docker CLI is not installed".to_string())?;
        let output = run_bounded(
            docker,
            [
                OsString::from("info"),
                OsString::from("--format"),
                OsString::from("{{.ServerVersion}}"),
            ],
            None,
            CONTROL_TIMEOUT,
            MAX_CONTROL_OUTPUT,
        )?;
        if !output.success() {
            return Err(nonempty_error(
                "Docker Desktop Linux engine is not running",
                &output,
            ));
        }
        Ok(docker)
    }

    fn ensure_image(&self) -> Result<(), String> {
        if self.image_exists()? {
            return Ok(());
        }
        let context = self.materialize_build_context()?;
        self.docker_checked_owned(
            vec![
                OsString::from("build"),
                OsString::from("--pull=false"),
                OsString::from("--tag"),
                OsString::from(IMAGE_REF),
                OsString::from("--file"),
                context.join("Dockerfile").into_os_string(),
                context.into_os_string(),
            ],
            BUILD_TIMEOUT,
        )?;
        Ok(())
    }

    fn materialize_build_context(&self) -> Result<PathBuf, String> {
        let context = self.state_root.join("image-semantic-v40");
        fs::create_dir_all(&context)
            .map_err(|error| format!("create Wiii computer image context failed: {error}"))?;
        write_if_changed(
            &context.join("Dockerfile"),
            include_bytes!("image/Dockerfile"),
        )?;
        write_if_changed(
            &context.join("entrypoint.sh"),
            include_bytes!("image/entrypoint.sh"),
        )?;
        write_if_changed(
            &context.join("wiii-browser"),
            include_bytes!("image/wiii-browser"),
        )?;
        write_if_changed(
            &context.join("wiii.html"),
            include_bytes!("image/wiii.html"),
        )?;
        write_if_changed(
            &context.join("semantic_bridge.py"),
            include_bytes!("image/semantic_bridge.py"),
        )?;
        write_if_changed(
            &context.join("work_plane_bridge.py"),
            include_bytes!("image/work_plane_bridge.py"),
        )?;
        write_if_changed(
            &context.join("project_paths.py"),
            include_bytes!("image/project_paths.py"),
        )?;
        write_if_changed(
            &context.join("panel.conf"),
            include_bytes!("image/panel.conf"),
        )?;
        write_if_changed(
            &context.join("wallpaper.svg"),
            include_bytes!("image/wallpaper.svg"),
        )?;
        write_if_changed(
            &context.join("desktop-items-0.conf"),
            include_bytes!("image/desktop-items-0.conf"),
        )?;
        write_if_changed(
            &context.join("chrome-managed-policies.json"),
            include_bytes!("image/chrome-managed-policies.json"),
        )?;
        let desktop = context.join("desktop");
        fs::create_dir_all(&desktop)
            .map_err(|error| format!("create Wiii computer desktop context failed: {error}"))?;
        write_if_changed(
            &desktop.join("browser.desktop"),
            include_bytes!("image/desktop/browser.desktop"),
        )?;
        write_if_changed(
            &desktop.join("files.desktop"),
            include_bytes!("image/desktop/files.desktop"),
        )?;
        write_if_changed(
            &desktop.join("terminal.desktop"),
            include_bytes!("image/desktop/terminal.desktop"),
        )?;
        Ok(context)
    }

    fn image_exists(&self) -> Result<bool, String> {
        self.image_exists_ref(IMAGE_REF)
    }

    fn image_exists_ref(&self, image_ref: &str) -> Result<bool, String> {
        let Some(docker) = &self.docker else {
            return Ok(false);
        };
        let output = run_bounded(
            docker,
            [
                OsString::from("image"),
                OsString::from("inspect"),
                OsString::from(image_ref),
            ],
            None,
            CONTROL_TIMEOUT,
            MAX_CONTROL_OUTPUT,
        )?;
        Ok(output.success())
    }

    fn image_size_bytes(&self) -> Option<u64> {
        let docker = self.docker.as_ref()?;
        run_bounded(
            docker,
            [
                OsString::from("image"),
                OsString::from("inspect"),
                OsString::from("--format"),
                OsString::from("{{.Size}}"),
                OsString::from(IMAGE_REF),
            ],
            None,
            CONTROL_TIMEOUT,
            MAX_CONTROL_OUTPUT,
        )
        .ok()
        .filter(|output| output.success())
        .and_then(|output| output.stdout_text().parse::<u64>().ok())
    }

    fn create_container(
        &self,
        environment_id: &str,
        names: &ProviderNames,
        project_path: &Path,
        secret_path: &Path,
        resources: &ComputerResources,
    ) -> Result<(), String> {
        self.create_container_with_manifest(
            environment_id,
            names,
            project_path,
            secret_path,
            resources,
            PACK_ID,
            PACK_CHANNEL,
            PROFILE_SCHEMA_VERSION,
        )
    }

    #[allow(clippy::too_many_arguments)]
    fn create_container_with_manifest(
        &self,
        environment_id: &str,
        names: &ProviderNames,
        project_path: &Path,
        secret_path: &Path,
        resources: &ComputerResources,
        pack_id: &str,
        pack_channel: &str,
        profile_schema_version: u32,
    ) -> Result<(), String> {
        let project = docker_mount_source(project_path)?;
        let secret = docker_mount_source(secret_path)?;
        let time_zone = host_time_zone();
        if project.contains(',') || secret.contains(',') {
            return Err(
                "Docker mount paths containing commas are not supported by this pilot".to_string(),
            );
        }
        let args = vec![
            OsString::from("run"),
            OsString::from("--detach"),
            OsString::from("--name"),
            OsString::from(&names.container),
            OsString::from("--label"),
            OsString::from(format!("dev.wiii.environment={environment_id}")),
            OsString::from("--label"),
            OsString::from(format!("dev.wiii.owner={OWNER_LABEL}")),
            OsString::from("--label"),
            OsString::from(format!("dev.wiii.pack={pack_id}")),
            OsString::from("--label"),
            OsString::from(format!("dev.wiii.pack.channel={pack_channel}")),
            OsString::from("--label"),
            OsString::from(format!("dev.wiii.profile-schema={profile_schema_version}")),
            OsString::from("--label"),
            OsString::from(format!("dev.wiii.timezone={time_zone}")),
            OsString::from("--env"),
            OsString::from(format!("TZ={time_zone}")),
            OsString::from("--restart"),
            OsString::from("unless-stopped"),
            OsString::from("--cpus"),
            OsString::from(&resources.cpus),
            OsString::from("--memory"),
            OsString::from(resources.memory_bytes.to_string()),
            OsString::from("--pids-limit"),
            OsString::from(resources.pids_limit.to_string()),
            OsString::from("--shm-size"),
            OsString::from(resources.shared_memory_bytes.to_string()),
            OsString::from("--cap-drop"),
            OsString::from("ALL"),
            OsString::from("--security-opt"),
            OsString::from("no-new-privileges:true"),
            OsString::from("--read-only"),
            OsString::from("--tmpfs"),
            OsString::from(format!(
                "/tmp:rw,nosuid,nodev,size={}",
                resources.temporary_storage_bytes
            )),
            OsString::from("--mount"),
            OsString::from(format!(
                "type=bind,source={project},target=/workspace/project"
            )),
            OsString::from("--mount"),
            OsString::from(format!(
                "type=volume,source={},target=/home/neko",
                names.volume
            )),
            OsString::from("--mount"),
            OsString::from(format!(
                "type=bind,source={secret},target=/run/secrets/wiii-vnc-password,readonly"
            )),
            OsString::from("--publish"),
            OsString::from("127.0.0.1::6080/tcp"),
            OsString::from(IMAGE_REF),
        ];
        self.docker_checked_owned(args, CONTROL_TIMEOUT)?;
        Ok(())
    }

    fn verify_container(
        &self,
        container: &str,
        environment_id: &str,
        project_path: &Path,
    ) -> Result<ContainerVerification, String> {
        let output = self.docker_output_owned(
            vec![OsString::from("inspect"), OsString::from(container)],
            CONTROL_TIMEOUT,
        )?;
        if !output.success() {
            return Err(nonempty_error("inspect Wiii computer failed", &output));
        }
        let values: Vec<Value> = serde_json::from_slice(&output.stdout)
            .map_err(|error| format!("decode Docker inspect response failed: {error}"))?;
        let value = values
            .first()
            .ok_or_else(|| "Docker inspect returned no computer".to_string())?;
        let owner = value
            .pointer("/Config/Labels/dev.wiii.owner")
            .and_then(Value::as_str);
        let environment = value
            .pointer("/Config/Labels/dev.wiii.environment")
            .and_then(Value::as_str);
        if owner != Some(OWNER_LABEL) || environment != Some(environment_id) {
            return Err(
                "Docker container identity does not belong to this Wiii computer".to_string(),
            );
        }
        let expected = normalize_path(project_path);
        let expected_time_zone = host_time_zone();
        let mount_ok = value
            .get("Mounts")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
            .any(|mount| {
                mount.get("Destination").and_then(Value::as_str) == Some("/workspace/project")
                    && mount
                        .get("Source")
                        .and_then(Value::as_str)
                        .map(|source| normalize_path(Path::new(source)) == expected)
                        .unwrap_or(false)
            });
        let active_pack = value
            .pointer("/Config/Labels/dev.wiii.pack")
            .and_then(Value::as_str);
        Ok(ContainerVerification {
            compatible: mount_ok
                && container_time_zone_matches(value, &expected_time_zone)
                && active_pack == Some(PACK_ID)
                && value
                    .pointer("/Config/Labels/dev.wiii.pack.channel")
                    .and_then(Value::as_str)
                    == Some(PACK_CHANNEL)
                && value
                    .pointer("/Config/Labels/dev.wiii.profile-schema")
                    .and_then(Value::as_str)
                    .and_then(|value| value.parse::<u32>().ok())
                    == Some(PROFILE_SCHEMA_VERSION),
            active_pack_version: pack_version_from_id(active_pack),
        })
    }

    fn container_exists(&self, container: &str) -> Result<bool, String> {
        let output = self.docker_output_owned(
            vec![
                OsString::from("container"),
                OsString::from("inspect"),
                OsString::from(container),
            ],
            CONTROL_TIMEOUT,
        )?;
        Ok(output.success())
    }

    fn volume_exists(&self, volume: &str) -> Result<bool, String> {
        let output = self.docker_output_owned(
            vec![
                OsString::from("volume"),
                OsString::from("inspect"),
                OsString::from(volume),
            ],
            CONTROL_TIMEOUT,
        )?;
        Ok(output.success())
    }

    fn container_state(&self, container: &str) -> Result<String, String> {
        let output = self.docker_checked_owned(
            vec![
                OsString::from("inspect"),
                OsString::from("--format"),
                OsString::from("{{.State.Status}}"),
                OsString::from(container),
            ],
            CONTROL_TIMEOUT,
        )?;
        Ok(output.stdout_text())
    }

    fn wait_until_ready(&self, container: &str) -> Result<(), String> {
        let deadline = Instant::now() + Duration::from_secs(60);
        loop {
            let output = self.docker_output_owned(
                vec![
                    OsString::from("inspect"),
                    OsString::from("--format"),
                    OsString::from("{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}"),
                    OsString::from(container),
                ],
                CONTROL_TIMEOUT,
            )?;
            let status = output.stdout_text();
            if output.success() && (status == "healthy" || status == "running") {
                return Ok(());
            }
            if status == "unhealthy" || status == "exited" || status == "dead" {
                return Err(format!("Wiii computer failed to become ready: {status}"));
            }
            if Instant::now() >= deadline {
                return Err("Wiii computer readiness timed out".to_string());
            }
            thread::sleep(Duration::from_millis(500));
        }
    }

    fn attach_url(&self, container: &str, secret_path: &Path) -> Result<String, String> {
        let output = self.docker_checked_owned(
            vec![
                OsString::from("port"),
                OsString::from(container),
                OsString::from("6080/tcp"),
            ],
            CONTROL_TIMEOUT,
        )?;
        let stdout = output.stdout_text();
        let address = stdout
            .lines()
            .find(|line| line.starts_with("127.0.0.1:"))
            .ok_or_else(|| "Wiii computer has no loopback display gateway".to_string())?;
        let port = address
            .rsplit(':')
            .next()
            .and_then(|value| value.parse::<u16>().ok())
            .filter(|port| *port > 0)
            .ok_or_else(|| "Wiii computer display gateway returned an invalid port".to_string())?;
        let password = fs::read_to_string(secret_path)
            .map_err(|error| format!("read Wiii computer display credential failed: {error}"))?;
        Ok(format!(
            "http://127.0.0.1:{port}/wiii.html#password={}",
            password.trim()
        ))
    }

    fn ensure_display_secret(&self, environment_id: &str) -> Result<PathBuf, String> {
        let path = self.secret_path(environment_id);
        if path.exists() {
            return Ok(path);
        }
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)
                .map_err(|error| format!("create computer secret directory failed: {error}"))?;
        }
        fs::write(&path, uuid::Uuid::new_v4().simple().to_string())
            .map_err(|error| format!("write computer display credential failed: {error}"))?;
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            fs::set_permissions(&path, fs::Permissions::from_mode(0o600))
                .map_err(|error| format!("protect computer display credential failed: {error}"))?;
        }
        Ok(path)
    }

    fn secret_path(&self, environment_id: &str) -> PathBuf {
        self.state_root
            .join("secrets")
            .join(format!("{environment_id}.vnc"))
    }

    fn docker_output_owned(
        &self,
        args: Vec<OsString>,
        timeout: Duration,
    ) -> Result<BoundedOutput, String> {
        run_bounded(
            self.docker
                .as_deref()
                .ok_or_else(|| "Docker CLI is not installed".to_string())?,
            args,
            None,
            timeout,
            MAX_CONTROL_OUTPUT,
        )
    }

    fn docker_checked<const N: usize>(
        &self,
        args: [&str; N],
        timeout: Duration,
    ) -> Result<BoundedOutput, String> {
        self.docker_checked_owned(args.into_iter().map(OsString::from).collect(), timeout)
    }

    fn docker_checked_owned(
        &self,
        args: Vec<OsString>,
        timeout: Duration,
    ) -> Result<BoundedOutput, String> {
        let output = self.docker_output_owned(args, timeout)?;
        if !output.success() {
            return Err(nonempty_error("Docker operation failed", &output));
        }
        Ok(output)
    }
}

impl ComputerProvider for LocalDockerComputerProvider {
    fn doctor(&self) -> ComputerDoctor {
        LocalDockerComputerProvider::doctor(self)
    }

    fn ensure(
        &self,
        environment_id: &str,
        project_path: &Path,
        resources: &ComputerResources,
    ) -> Result<ProviderEnvironment, String> {
        LocalDockerComputerProvider::ensure(self, environment_id, project_path, resources)
    }

    fn resolve(
        &self,
        environment_id: &str,
        project_path: &Path,
    ) -> Result<Option<ProviderEnvironment>, String> {
        LocalDockerComputerProvider::resolve(self, environment_id, project_path)
    }

    fn suspend(&self, environment_id: &str) -> Result<(), String> {
        LocalDockerComputerProvider::suspend(self, environment_id)
    }

    fn resume(
        &self,
        environment_id: &str,
        project_path: &Path,
        resources: &ComputerResources,
    ) -> Result<ProviderEnvironment, String> {
        LocalDockerComputerProvider::resume(self, environment_id, project_path, resources)
    }

    fn reset(
        &self,
        environment_id: &str,
        project_path: &Path,
        resources: &ComputerResources,
    ) -> Result<ProviderEnvironment, String> {
        LocalDockerComputerProvider::reset(self, environment_id, project_path, resources)
    }

    fn destroy(&self, environment_id: &str) -> Result<(), String> {
        LocalDockerComputerProvider::destroy(self, environment_id)
    }

    fn detach(&self, environment_id: &str) -> Result<(), String> {
        LocalDockerComputerProvider::detach(self, environment_id)
    }

    fn install_package(&self, package_id: &str) -> Result<(), String> {
        LocalDockerComputerProvider::install_package(self, package_id)
    }

    fn remove_package(&self, package_id: &str) -> Result<(), String> {
        LocalDockerComputerProvider::remove_package(self, package_id)
    }

    fn semantic_observe(
        &self,
        request: &SemanticObserveRequest,
    ) -> Result<SemanticSnapshot, String> {
        LocalDockerComputerProvider::semantic_observe(self, request)
    }

    fn semantic_act(&self, request: &SemanticActRequest) -> Result<SemanticActResult, String> {
        LocalDockerComputerProvider::semantic_act(self, request)
    }

    fn app_events_poll(
        &self,
        environment_id: &str,
        after_cursor: Option<&str>,
        limit: u32,
        wait_ms: u32,
        stopped: Option<&AtomicBool>,
    ) -> Result<WatcherBatch, String> {
        LocalDockerComputerProvider::app_events_poll(
            self,
            environment_id,
            after_cursor,
            limit,
            wait_ms,
            stopped,
        )
    }

    fn resume_realtime(&self, environment_id: &str) -> Result<(), String> {
        LocalDockerComputerProvider::resume_realtime(self, environment_id)
    }

    fn terminal_exec(
        &self,
        environment_id: &str,
        command: &str,
    ) -> Result<ProviderTerminalResult, String> {
        LocalDockerComputerProvider::terminal_exec(self, environment_id, command)
    }

    fn browser_navigate(&self, environment_id: &str, url: &str) -> Result<(), String> {
        LocalDockerComputerProvider::browser_navigate(self, environment_id, url)
    }
}

impl WorkPlaneAdapter for LocalDockerComputerProvider {
    fn describe(&self, request: &WorkPlaneDescribeRequest) -> Result<WorkPlaneDescriptor, String> {
        let envelope = self.work_plane_bridge(&request.environment_id, "describe", request)?;
        serde_json::from_value(
            envelope
                .get("descriptor")
                .cloned()
                .ok_or_else(|| "Work Plane provider returned no descriptor".to_string())?,
        )
        .map_err(|error| format!("decode Work Plane descriptor failed: {error}"))
    }

    fn query(&self, request: &WorkPlaneQueryRequest) -> Result<WorkPlaneQueryResult, String> {
        let envelope = self.work_plane_bridge(&request.environment_id, "query", request)?;
        serde_json::from_value(
            envelope
                .get("result")
                .cloned()
                .ok_or_else(|| "Work Plane provider returned no query result".to_string())?,
        )
        .map_err(|error| format!("decode Work Plane query result failed: {error}"))
    }

    fn execute(
        &self,
        request: &WorkPlaneTransactionRequest,
    ) -> Result<WorkPlaneTransactionResult, String> {
        let envelope = self.work_plane_bridge(&request.environment_id, "execute", request)?;
        serde_json::from_value(
            envelope
                .get("result")
                .cloned()
                .ok_or_else(|| "Work Plane provider returned no transaction result".to_string())?,
        )
        .map_err(|error| format!("decode Work Plane transaction result failed: {error}"))
    }
}

#[derive(Debug)]
struct ProviderNames {
    container: String,
    rollback_container: String,
    volume: String,
}

impl ProviderNames {
    fn new(environment_id: &str) -> Self {
        let suffix = environment_id
            .strip_prefix("computer-")
            .unwrap_or(environment_id);
        Self {
            container: format!("wiii-computer-{suffix}"),
            rollback_container: format!("wiii-computer-{suffix}-rollback"),
            volume: format!("wiii-computer-home-{suffix}"),
        }
    }
}

fn canonical_project(path: &Path) -> Result<PathBuf, String> {
    let canonical = path
        .canonicalize()
        .map_err(|error| format!("resolve selected project failed: {error}"))?;
    if !canonical.is_dir() {
        return Err("Selected computer project is not a directory".to_string());
    }
    Ok(canonical)
}

fn normalize_path(path: &Path) -> String {
    let value = external_tool_path(&path.to_string_lossy()).replace('\\', "/");
    if cfg!(windows) {
        value.to_ascii_lowercase()
    } else {
        value
    }
}

fn pack_version_from_id(pack: Option<&str>) -> Option<String> {
    pack.and_then(|value| value.strip_prefix("web-computer-"))
        .filter(|value| !value.is_empty())
        .map(str::to_string)
}

fn docker_mount_source(path: &Path) -> Result<String, String> {
    let raw = path
        .to_str()
        .ok_or_else(|| "Computer mount path is not valid Unicode".to_string())?;
    Ok(external_tool_path(raw).replace('\\', "/"))
}

fn external_tool_path(value: &str) -> String {
    if cfg!(windows) {
        if let Some(rest) = value.strip_prefix(r"\\?\UNC\") {
            return format!(r"\\{rest}");
        }
        if let Some(rest) = value.strip_prefix(r"\\?\") {
            return rest.to_string();
        }
    }
    value.to_string()
}

fn host_time_zone() -> String {
    iana_time_zone::get_timezone().unwrap_or_else(|_| "Etc/UTC".to_string())
}

fn container_time_zone_matches(value: &Value, expected: &str) -> bool {
    let label_matches = value
        .pointer("/Config/Labels/dev.wiii.timezone")
        .and_then(Value::as_str)
        == Some(expected);
    let environment_matches = value
        .pointer("/Config/Env")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .any(|entry| entry == format!("TZ={expected}"));
    label_matches && environment_matches
}

fn validate_browser_url(value: &str) -> Result<(), String> {
    if value.is_empty() || value.len() > 4096 {
        return Err("Computer browser URL must contain 1 to 4096 bytes".to_string());
    }
    let lower = value.to_ascii_lowercase();
    if !lower.starts_with("http://") && !lower.starts_with("https://") {
        return Err("Computer browser only accepts http and https URLs".to_string());
    }
    if value.chars().any(char::is_control) {
        return Err("Computer browser URL contains control characters".to_string());
    }
    Ok(())
}

fn write_if_changed(path: &Path, content: &[u8]) -> Result<(), String> {
    if fs::read(path)
        .map(|current| current == content)
        .unwrap_or(false)
    {
        return Ok(());
    }
    fs::write(path, content)
        .map_err(|error| format!("write Wiii computer image file failed: {error}"))
}

fn resolve_docker_cli() -> Option<PathBuf> {
    let executable = if cfg!(windows) {
        "docker.exe"
    } else {
        "docker"
    };
    let mut candidates = Vec::new();
    if cfg!(windows) {
        if let Some(program_files) = std::env::var_os("ProgramFiles") {
            candidates.push(
                PathBuf::from(program_files)
                    .join("Docker")
                    .join("Docker")
                    .join("resources")
                    .join("bin")
                    .join(executable),
            );
        }
    }
    if let Some(path) = std::env::var_os("PATH") {
        candidates.extend(std::env::split_paths(&path).map(|directory| directory.join(executable)));
    }
    candidates
        .into_iter()
        .find(|candidate| candidate.is_file())
        .and_then(|candidate| candidate.canonicalize().ok())
}

fn run_bounded<I, S>(
    program: &Path,
    args: I,
    cwd: Option<&Path>,
    timeout: Duration,
    max_output: usize,
) -> Result<BoundedOutput, String>
where
    I: IntoIterator<Item = S>,
    S: AsRef<OsStr>,
{
    run_bounded_internal(program, args, cwd, timeout, max_output, None, None)
}

fn run_bounded_with_input<I, S>(
    program: &Path,
    args: I,
    cwd: Option<&Path>,
    timeout: Duration,
    max_output: usize,
    input: &[u8],
) -> Result<BoundedOutput, String>
where
    I: IntoIterator<Item = S>,
    S: AsRef<OsStr>,
{
    run_bounded_internal(program, args, cwd, timeout, max_output, Some(input), None)
}

fn run_bounded_with_input_cancellable<I, S>(
    program: &Path,
    args: I,
    cwd: Option<&Path>,
    timeout: Duration,
    max_output: usize,
    input: &[u8],
    stopped: Option<&AtomicBool>,
) -> Result<BoundedOutput, String>
where
    I: IntoIterator<Item = S>,
    S: AsRef<OsStr>,
{
    run_bounded_internal(
        program,
        args,
        cwd,
        timeout,
        max_output,
        Some(input),
        stopped,
    )
}

fn run_bounded_internal<I, S>(
    program: &Path,
    args: I,
    cwd: Option<&Path>,
    timeout: Duration,
    max_output: usize,
    input: Option<&[u8]>,
    stopped: Option<&AtomicBool>,
) -> Result<BoundedOutput, String>
where
    I: IntoIterator<Item = S>,
    S: AsRef<OsStr>,
{
    let mut command = Command::new(program);
    command
        .args(args)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    if input.is_some() {
        command.stdin(Stdio::piped());
    }
    if let Some(cwd) = cwd {
        command.current_dir(cwd);
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
    let mut child = command
        .spawn()
        .map_err(|error| format!("start Docker CLI failed: {error}"))?;
    if let Some(input) = input {
        let mut stdin = child
            .stdin
            .take()
            .ok_or_else(|| "open Docker stdin failed".to_string())?;
        stdin
            .write_all(input)
            .map_err(|error| format!("write Docker stdin failed: {error}"))?;
    }
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "capture Docker stdout failed".to_string())?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| "capture Docker stderr failed".to_string())?;
    let stdout_reader = thread::spawn(move || read_bounded_stream(stdout, max_output));
    let stderr_reader = thread::spawn(move || read_bounded_stream(stderr, max_output));
    let deadline = Instant::now() + timeout;
    let status = loop {
        if stopped.is_some_and(|flag| flag.load(Ordering::Acquire)) {
            let _ = child.kill();
            let _ = child.wait();
            break Err("Docker operation cancelled".to_string());
        }
        match child.try_wait() {
            Ok(Some(status)) => break Ok(status),
            Ok(None) if Instant::now() < deadline => thread::sleep(Duration::from_millis(50)),
            Ok(None) => {
                let _ = child.kill();
                let _ = child.wait();
                break Err("Docker operation timed out and was terminated".to_string());
            }
            Err(error) => {
                let _ = child.kill();
                let _ = child.wait();
                break Err(format!("observe Docker operation failed: {error}"));
            }
        }
    };
    let (stdout, stdout_truncated) = stdout_reader
        .join()
        .map_err(|_| "Docker stdout reader failed".to_string())??;
    let (stderr, stderr_truncated) = stderr_reader
        .join()
        .map_err(|_| "Docker stderr reader failed".to_string())??;
    let status = status?;
    Ok(BoundedOutput {
        status,
        stdout,
        stderr,
        truncated: stdout_truncated || stderr_truncated,
    })
}

fn read_bounded_stream<R: Read>(mut stream: R, max: usize) -> Result<(Vec<u8>, bool), String> {
    let mut kept = Vec::new();
    let mut buffer = [0u8; 8192];
    let mut truncated = false;
    loop {
        let read = stream
            .read(&mut buffer)
            .map_err(|error| format!("read Docker output failed: {error}"))?;
        if read == 0 {
            break;
        }
        let available = max.saturating_sub(kept.len());
        let take = available.min(read);
        kept.extend_from_slice(&buffer[..take]);
        truncated |= take < read;
    }
    Ok((kept, truncated))
}

fn nonempty_error(prefix: &str, output: &BoundedOutput) -> String {
    let detail = output.stderr_text();
    if detail.is_empty() {
        format!("{prefix} (exit {:?})", output.status.code())
    } else {
        format!("{prefix}: {detail}")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn provider_names_are_stable_and_scoped() {
        let names = ProviderNames::new("computer-abc123");
        assert_eq!(names.container, "wiii-computer-abc123");
        assert_eq!(names.rollback_container, "wiii-computer-abc123-rollback");
        assert_eq!(names.volume, "wiii-computer-home-abc123");
    }

    #[test]
    fn core_package_catalog_is_truthful_about_sharing_and_profile_retention() {
        let packages = LocalDockerComputerProvider::package_catalog(true, Some(42));
        let core = packages.first().expect("core package");

        assert_eq!(core.package_id, CORE_PACKAGE_ID);
        assert_eq!(core.state, ComputerPackageState::Installed);
        assert_eq!(core.installed_bytes, Some(42));
        assert_eq!(core.manifest.schema_version, PACK_SCHEMA_VERSION);
        assert_eq!(core.manifest.version, PACK_VERSION);
        assert_eq!(core.manifest.channel, PACK_CHANNEL);
        assert_eq!(core.manifest.profile_schema_version, PROFILE_SCHEMA_VERSION);
        assert_eq!(core.manifest.rollback_policy, "automatic_shell_restore");
        assert!(core.shared_across_projects);
        assert!(core.preserves_profile_on_remove);
        assert!(LocalDockerComputerProvider::require_core_package("unknown-pack").is_err());
    }

    #[test]
    fn pack_version_is_derived_only_from_owned_pack_ids() {
        assert_eq!(
            pack_version_from_id(Some("web-computer-semantic-v21")).as_deref(),
            Some("semantic-v21")
        );
        assert_eq!(pack_version_from_id(Some("unrelated-v21")), None);
        assert_eq!(pack_version_from_id(Some("web-computer-")), None);
        assert_eq!(pack_version_from_id(None), None);
    }

    #[test]
    fn browser_rejects_non_web_schemes_and_controls() {
        assert!(validate_browser_url("https://wiii.example/path").is_ok());
        assert!(validate_browser_url("file:///etc/passwd").is_err());
        assert!(validate_browser_url("javascript:alert(1)").is_err());
        assert!(validate_browser_url("https://wiii.example/\nnext").is_err());
    }

    #[test]
    fn docker_mount_paths_do_not_expose_windows_verbatim_prefixes() {
        if cfg!(windows) {
            assert_eq!(
                external_tool_path(r"\\?\E:\Downloads\wiii"),
                r"E:\Downloads\wiii"
            );
            assert_eq!(
                external_tool_path(r"\\?\UNC\server\share\wiii"),
                r"\\server\share\wiii"
            );
            assert_eq!(
                docker_mount_source(Path::new(r"\\?\E:\Downloads\wiii")).unwrap(),
                "E:/Downloads/wiii"
            );
        }
    }

    #[test]
    fn container_timezone_requires_matching_label_and_environment() {
        let configured = serde_json::json!({
            "Config": {
                "Labels": {"dev.wiii.timezone": "Asia/Ho_Chi_Minh"},
                "Env": ["HOME=/home/neko", "TZ=Asia/Ho_Chi_Minh"]
            }
        });
        assert!(container_time_zone_matches(&configured, "Asia/Ho_Chi_Minh"));

        let stale = serde_json::json!({
            "Config": {
                "Labels": {"dev.wiii.timezone": "Etc/UTC"},
                "Env": ["TZ=Etc/UTC"]
            }
        });
        assert!(!container_time_zone_matches(&stale, "Asia/Ho_Chi_Minh"));
    }

    #[test]
    fn computer_image_limits_competing_chrome_ai_and_idle_health_churn() {
        let policies: Value =
            serde_json::from_str(include_str!("image/chrome-managed-policies.json"))
                .expect("valid managed Chrome policy JSON");
        assert_eq!(policies["AIModeSettings"], 1);
        assert_eq!(policies["GenAILocalFoundationalModelSettings"], 1);

        let dockerfile = include_str!("image/Dockerfile");
        assert!(dockerfile.contains(
            "chrome-managed-policies.json /etc/opt/chrome/policies/managed/wiii-ai.json"
        ));
        assert!(dockerfile.contains("--interval=30s"));
        assert!(dockerfile.contains("--start-interval=1s"));
        assert!(dockerfile.contains("--timeout=5s"));
        assert!(dockerfile.contains("http://127.0.0.1:9234/health"));
        assert!(dockerfile.contains("http://127.0.0.1:9222/json/version"));
        assert!(!dockerfile.contains("--interval=2s"));
    }

    #[test]
    #[ignore = "requires the local Docker Computer runtime"]
    fn live_pack_reconciliation_preserves_profile_volume() {
        assert_eq!(
            std::env::var("WIII_LIVE_PACK_TEST").as_deref(),
            Ok("1"),
            "set WIII_LIVE_PACK_TEST=1 to run this isolated Docker test"
        );

        let token = uuid::Uuid::new_v4().simple().to_string();
        let environment_id = format!("computer-packtest-{}", &token[..12]);
        let root = std::env::temp_dir().join(format!("wiii-pack-live-{token}"));
        let project = root.join("project");
        fs::create_dir_all(&project).expect("create isolated project");
        let project = canonical_project(&project).expect("canonical isolated project");
        let provider = LocalDockerComputerProvider::new(root.join("provider"));
        let names = ProviderNames::new(&environment_id);
        let resources = ComputerResourcePreset::Compact.resources();

        let result = (|| -> Result<(), String> {
            provider.require_daemon()?;
            provider.ensure_image()?;
            let secret = provider.ensure_display_secret(&environment_id)?;
            provider.create_container_with_manifest(
                &environment_id,
                &names,
                &project,
                &secret,
                &resources,
                "web-computer-semantic-previous",
                PACK_CHANNEL,
                PROFILE_SCHEMA_VERSION,
            )?;
            provider.wait_until_ready(&names.container)?;
            provider.docker_checked(
                [
                    "exec",
                    &names.container,
                    "sh",
                    "-lc",
                    "printf pack-v1 > /home/neko/.wiii-pack-test",
                ],
                CONTROL_TIMEOUT,
            )?;

            let discovered = provider
                .resolve(&environment_id, &project)?
                .ok_or_else(|| "old pack was not discovered".to_string())?;
            if discovered.state != ComputerState::Suspended
                || discovered.active_pack_version.as_deref() != Some("semantic-previous")
                || !discovered.pack_update_available
            {
                return Err("old pack was not exposed as an explicit upgrade".to_string());
            }

            let mut invalid_resources = resources.clone();
            invalid_resources.cpus = "invalid".to_string();
            let rollback_error = provider
                .ensure(&environment_id, &project, &invalid_resources)
                .expect_err("invalid replacement must fail and restore the old shell");
            if !rollback_error.starts_with("computer_pack_upgrade_rolled_back:") {
                return Err(format!(
                    "replacement failure did not report a verified rollback: {rollback_error}"
                ));
            }
            if provider.container_exists(&names.rollback_container)? {
                return Err("failed reconciliation left the rollback name occupied".to_string());
            }
            if provider.container_state(&names.container)? != "running" {
                return Err("failed reconciliation did not restart the previous shell".to_string());
            }
            provider.docker_checked(
                [
                    "exec",
                    &names.container,
                    "sh",
                    "-lc",
                    "test \"$(cat /home/neko/.wiii-pack-test)\" = pack-v1",
                ],
                CONTROL_TIMEOUT,
            )?;

            let reconciled = provider.ensure(&environment_id, &project, &resources)?;
            if reconciled.state != ComputerState::Ready
                || reconciled.active_pack_version.as_deref() != Some(PACK_VERSION)
                || reconciled.pack_update_available
            {
                return Err("reconciled pack did not publish the active version".to_string());
            }

            if provider.container_exists(&names.rollback_container)? {
                return Err("successful reconciliation left a rollback shell behind".to_string());
            }
            if !provider
                .verify_container(&names.container, &environment_id, &project)?
                .compatible
            {
                return Err("reconciled shell does not match the active pack manifest".to_string());
            }
            provider.docker_checked(
                [
                    "exec",
                    &names.container,
                    "sh",
                    "-lc",
                    "test \"$(cat /home/neko/.wiii-pack-test)\" = pack-v1",
                ],
                CONTROL_TIMEOUT,
            )?;
            Ok(())
        })();

        if provider
            .container_exists(&names.rollback_container)
            .unwrap_or(false)
        {
            let _ = provider.docker_checked(
                ["rm", "--force", &names.rollback_container],
                CONTROL_TIMEOUT,
            );
        }
        let cleanup = provider.destroy(&environment_id);
        let _ = fs::remove_dir_all(&root);

        result.expect("reconcile isolated Computer pack");
        cleanup.expect("remove isolated Computer pack test resources");
    }
}
