//! Explicit migration for retired PID-only locks in Wiii's Linux PID namespaces.
//! Never takes over a live/unknown execution or a newer Core lease format.
use super::journal::SessionRecord;
use serde::Deserialize;
use std::path::Path;

#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct LegacyLeaseRequest {
    pub client_session_id: String,
    pub backend_session_id: String,
}

#[cfg(test)]
mod request_tests {
    use super::LegacyLeaseRequest;
    use serde_json::json;

    #[test]
    fn recovery_request_cannot_supply_paths_pids_or_native_proof() {
        let request = json!({"clientSessionId": "local", "backendSessionId": "backend"});
        assert!(serde_json::from_value::<LegacyLeaseRequest>(request.clone()).is_ok());
        for field in [
            "pid",
            "path",
            "home",
            "records",
            "quiescent",
            "agentSessionId",
            "receipt",
            "root",
            "scope",
            "taskScope",
            "nativeProof",
        ] {
            let mut forged = request.clone();
            forged[field] = json!(1);
            assert!(serde_json::from_value::<LegacyLeaseRequest>(forged).is_err());
        }
    }
}

pub const BUSY: &str = "neko_legacy_recovery_busy";

/// Native-only physical proof. Never deserialized from renderer input and never
/// changes the task outcomes in its catalog (which may remain uncertain).
pub struct QuiescentNekoCatalog {
    records: Vec<SessionRecord>,
}

pub(crate) fn prove_quiescent(
    records: Vec<SessionRecord>,
    active_ids: &[String],
) -> Result<QuiescentNekoCatalog, String> {
    if active_ids.iter().any(
        |id| match records.iter().find(|r| &r.agent_session_id == id) {
            Some(record) => record.provider_id == "neko",
            None => true,
        },
    ) {
        return Err(BUSY.into());
    }
    #[cfg(target_os = "linux")]
    confirm_no_namespaced_writers()?;
    Ok(QuiescentNekoCatalog { records })
}

/// The caller must hold native start admission closed and prove physical Neko
/// quiescence; journal task outcomes alone are not a process-liveness oracle.
pub fn recover(
    home: &Path,
    app_data: &Path,
    request: &LegacyLeaseRequest,
    native_proof: impl FnOnce() -> Result<QuiescentNekoCatalog, String>,
) -> Result<bool, String> {
    let id = &request.backend_session_id;
    if id.is_empty()
        || id.len() > 128
        || !id
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b"._-".contains(&b))
        || !id.as_bytes()[0].is_ascii_alphanumeric()
        || id.ends_with('.')
    {
        return Err("Invalid backend session identity".into());
    }
    #[cfg(target_os = "linux")]
    {
        linux::recover(home, app_data, request, native_proof)
    }
    #[cfg(not(target_os = "linux"))]
    {
        let _ = (home, app_data, native_proof);
        Ok(false)
    }
}

#[cfg(target_os = "linux")]
pub(crate) fn confirm_no_namespaced_writers() -> Result<(), String> {
    // SAFETY: getuid has no arguments or memory-safety preconditions.
    linux::confirm_no_sandboxes(Path::new("/proc"), unsafe { libc::getuid() })
}

#[cfg(target_os = "linux")]
mod linux {
    use super::*;
    use crate::neko::lifecycle::{OperationPhase, RunState};
    use serde_json::Value;
    use std::fs::{self, File, OpenOptions};
    use std::io::Read;
    use std::os::unix::fs::{MetadataExt, OpenOptionsExt};

    /// All Linux native provider launches use the PID-namespace supervisor in
    /// linux_containment.rs, including legacy 1.9.3. Its outer bwrap keeps this
    /// argv while the guest is alive; guest PID 1 cannot outlive that supervisor.
    /// Scan read-only kernel facts, not stored PIDs. An unreadable same-user
    /// process is uncertainty, not proof of absence. No command lines are logged.
    pub(super) fn confirm_no_sandboxes(proc_root: &Path, uid: u32) -> Result<(), String> {
        let inspect = || "Cannot prove native process quiescence".to_string();
        let bounded = |path: &Path, limit: u64| -> Result<Option<Vec<u8>>, String> {
            let mut file = match File::open(path) {
                Ok(file) => file.take(limit + 1),
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
                Err(_) => return Err(inspect()),
            };
            let mut bytes = Vec::new();
            match file.read_to_end(&mut bytes) {
                Ok(_) if bytes.len() as u64 <= limit => Ok(Some(bytes)),
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(None),
                _ => Err(inspect()),
            }
        };
        for entry in fs::read_dir(proc_root).map_err(|_| inspect())? {
            let entry = entry.map_err(|_| inspect())?;
            let name = entry.file_name();
            let Some(pid) = name.to_str() else { continue };
            if pid.is_empty() || !pid.bytes().all(|b| b.is_ascii_digit()) {
                continue;
            }
            let Some(status) = bounded(&entry.path().join("status"), 16_384)? else {
                continue;
            };
            let status = String::from_utf8_lossy(&status);
            let owner = status
                .lines()
                .find_map(|line| line.strip_prefix("Uid:"))
                .and_then(|line| line.split_whitespace().next())
                .and_then(|real_uid| real_uid.parse::<u32>().ok())
                .ok_or_else(inspect)?;
            if owner != uid {
                continue;
            }
            let Some(argv) = bounded(&entry.path().join("cmdline"), 65_536)? else {
                continue;
            };
            let options: Vec<_> = argv
                .split(|b| *b == 0)
                .skip(1)
                .take_while(|arg| *arg != b"--")
                .collect();
            if [
                b"--unshare-pid".as_slice(),
                b"--as-pid-1",
                b"--die-with-parent",
            ]
            .iter()
            .all(|flag| options.contains(flag))
            {
                return Err(BUSY.into());
            }
        }
        Ok(())
    }

    fn terminal(record: &SessionRecord) -> bool {
        matches!(
            record.state,
            RunState::Completed | RunState::Failed | RunState::Cancelled
        ) && matches!(
            record.operation_phase,
            OperationPhase::Completed | OperationPhase::Failed
        ) && record.continuity != "unknown_outcome"
    }

    #[derive(Deserialize)]
    #[serde(rename_all = "camelCase", deny_unknown_fields)]
    struct LegacyLock {
        pid: u32,
        token: String,
        acquired_at: String,
    }

    fn read_regular(path: &Path, limit: u64) -> Result<(Vec<u8>, fs::Metadata), String> {
        let mut file = OpenOptions::new()
            .read(true)
            .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK)
            .open(path)
            .map_err(|_| "Cannot safely read recovery metadata")?;
        let metadata = file
            .metadata()
            .map_err(|_| "Cannot inspect recovery metadata")?;
        if !metadata.is_file() || metadata.nlink() != 1 || metadata.len() > limit {
            return Err("Unsafe recovery metadata".into());
        }
        let mut bytes = Vec::new();
        (&mut file)
            .take(limit + 1)
            .read_to_end(&mut bytes)
            .map_err(|_| "Cannot read recovery metadata")?;
        if bytes.len() as u64 > limit {
            return Err("Recovery metadata exceeds its bound".into());
        }
        Ok((bytes, metadata))
    }

    fn millis(value: &str) -> Option<i64> {
        chrono::DateTime::parse_from_rfc3339(value)
            .ok()
            .map(|at| at.timestamp_millis())
    }

    fn owns_lease(
        snapshot: &Value,
        request: &LegacyLeaseRequest,
        records: &[SessionRecord],
        acquired: Option<i64>,
        scoped: bool,
    ) -> bool {
        let Some(saved) = snapshot.get(format!("session:{}", request.client_session_id)) else {
            return false;
        };
        let entry = &saved["entry"];
        if entry["id"].as_str() != Some(&request.client_session_id)
            || entry["agentId"] != "neko"
            || entry["backendSessionId"].as_str() != Some(&request.backend_session_id)
            || entry["taskScope"].is_null() == scoped
        {
            return false;
        }
        let task_id = if entry["execution"].is_null() {
            format!("legacy-local/task/{}", request.client_session_id)
        } else if let Some(id) = entry["execution"]["taskId"]
            .as_str()
            .filter(|id| !id.is_empty())
        {
            id.to_owned()
        } else {
            return false;
        };
        let Some(workspace) = entry["workspace"]["path"]
            .as_str()
            .and_then(|p| Path::new(p).canonicalize().ok())
        else {
            return false;
        };
        let Some(events) = saved["events"].as_array() else {
            return false;
        };
        events.iter().any(|event| {
            let provider = &event["data"]["provider"];
            let extensions = &provider["providerCapabilities"]["extensions"];
            let Some(attached) = event["at"].as_i64() else {
                return false;
            };
            if event["v"] != 1
                || event["visibility"] != "runtime"
                || event["data"]["type"] != "runtime-attached"
                || provider["providerId"] != "neko"
                || provider["sessionId"].as_str() != Some(&request.client_session_id)
                || provider["backendSessionId"].as_str() != Some(&request.backend_session_id)
            {
                return false;
            }
            records.iter().any(|native| {
                let Some(started) = millis(&native.created_at) else {
                    return false;
                };
                let Some(ended) = millis(&native.updated_at) else {
                    return false;
                };
                native.provider_id == "neko"
                    && terminal(native)
                    && native.task_id == task_id
                    && (!scoped
                        || (entry["execution"]["runId"].as_str() == Some(&native.run_id)
                            && entry["execution"]["environmentId"].as_str()
                                == Some(&native.environment_id)))
                    && extensions["nativeAgentSessionId"].as_str() == Some(&native.agent_session_id)
                    && extensions["nativeRunId"].as_str() == Some(&native.run_id)
                    && Path::new(&native.workspace_path)
                        .canonicalize()
                        .ok()
                        .as_ref()
                        == Some(&workspace)
                    && started <= attached
                    && acquired.is_none_or(|acquired| started <= acquired && acquired <= attached)
                    && attached <= ended
            })
        })
    }

    /// This does not grant a workspace or rotate an activation. Core must still
    /// independently validate authority/configuration and a later explicit load.
    fn scoped_checkpoint_matches(
        saved: &Value,
        checkpoint: &Value,
        request: &LegacyLeaseRequest,
    ) -> bool {
        let entry = &saved[format!("session:{}", request.client_session_id)]["entry"];
        let scope = &entry["taskScope"];
        let receipt = &scope["receipt"];
        let protocol = &checkpoint["taskProtocol"];
        let hex_id = |value: &Value| {
            value
                .as_str()
                .is_some_and(|id| id.len() == 32 && id.bytes().all(|b| b.is_ascii_hexdigit()))
        };
        let Some(workspace) = entry["workspace"]["path"]
            .as_str()
            .and_then(|path| Path::new(path).canonicalize().ok())
        else {
            return false;
        };
        let Some(root) = workspace.to_str() else {
            return false;
        };
        let Some(label) = receipt["label"].as_str() else {
            return false;
        };
        let Some(tasks) = checkpoint["tasks"].as_array() else {
            return false;
        };
        let active = tasks
            .iter()
            .filter(|task| task["id"] == receipt["id"])
            .collect::<Vec<_>>();
        matches!(checkpoint["schemaVersion"].as_u64(), Some(2 | 3))
            && checkpoint["id"].as_str() == Some(&request.backend_session_id)
            && hex_id(&checkpoint["id"])
            && hex_id(&receipt["id"])
            && hex_id(&receipt["activationId"])
            && checkpoint["id"] != receipt["id"]
            && checkpoint["id"] != receipt["activationId"]
            && receipt["id"] != receipt["activationId"]
            && checkpoint["canonicalRoot"].as_str() == Some(root)
            && checkpoint["activeTaskId"] == receipt["id"]
            && active.len() == 1
            && active[0]["label"] == receipt["label"]
            && active[0]["canonicalRoot"].as_str() == Some(root)
            && !label.trim().is_empty()
            && label.len() <= 256
            && !label.chars().any(char::is_control)
            && scope["version"] == 1
            && scope["mode"] == "fixed-active-task"
            && (scope["state"] == "bound"
                || (scope["state"] == "recovery-required"
                    && scope["reason"] == "writer-unavailable"))
            && scope["threadId"].as_str() == Some(&request.client_session_id)
            && scope["backendSessionId"].as_str() == Some(&request.backend_session_id)
            && scope["execution"] == entry["execution"]
            && scope["execution"].is_object()
            && scope["projectId"] == entry["projectId"]
            && scope["workspacePath"] == entry["workspace"]["path"]
            && scope["authorizedRoot"].as_str() == Some(root)
            && scope["label"] == receipt["label"]
            && receipt["version"] == 1
            && receipt["mode"] == "fixed-active-task"
            && receipt["root"].as_str() == Some(root)
            && receipt["activationEpoch"]
                .as_u64()
                .is_some_and(|epoch| epoch > 0 && epoch <= 9_007_199_254_740_991)
            && protocol["version"] == 1
            && protocol["mode"] == "fixed-active-task"
            && protocol["activationEpoch"] == receipt["activationEpoch"]
            && protocol["activationId"] == receipt["activationId"]
    }

    fn recover_scoped(
        home: &Path,
        app_data: &Path,
        request: &LegacyLeaseRequest,
        snapshot: &Value,
        native_proof: impl FnOnce() -> Result<QuiescentNekoCatalog, String>,
    ) -> Result<bool, String> {
        let core = home.join(".neko-core");
        let sessions = core.join("task-sessions");
        for directory in [&core, &sessions] {
            if !fs::symlink_metadata(directory).is_ok_and(|meta| meta.file_type().is_dir()) {
                return Err("Unsafe Core task session directory".into());
            }
        }
        let path = sessions.join(format!("{}.lock", request.backend_session_id));
        let lock = match fs::symlink_metadata(&path) {
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => None,
            Err(_) => return Err("Cannot inspect task lease".into()),
            Ok(_) => Some(read_regular(&path, 4_096)?),
        };
        let acquired = if let Some((bytes, _)) = &lock {
            let value: Value = serde_json::from_slice(bytes).map_err(|_| "Malformed task lease")?;
            let object = value.as_object().ok_or("Malformed task lease")?;
            if object
                .keys()
                .any(|key| !["pid", "token", "acquiredAt"].contains(&key.as_str()))
            {
                return Ok(false); // Future Core formats remain Core-owned.
            }
            let lease: LegacyLock =
                serde_json::from_value(value).map_err(|_| "Malformed task lease")?;
            if lease.pid != 1 {
                return Ok(false);
            }
            if lease.token.len() != 32 || !lease.token.bytes().all(|b| b.is_ascii_hexdigit()) {
                return Err("Malformed task lease".into());
            }
            Some(
                millis(&lease.acquired_at)
                    .filter(|at| *at >= 0)
                    .ok_or("Invalid task lease time")?,
            )
        } else {
            None
        };
        let checkpoint_path = sessions.join(format!("{}.json", request.backend_session_id));
        let (bytes, identity) = read_regular(&checkpoint_path, 64 * 1024 * 1024)?;
        let checkpoint: Value =
            serde_json::from_slice(&bytes).map_err(|_| "Malformed task checkpoint")?;
        if !scoped_checkpoint_matches(snapshot, &checkpoint, request) {
            return Err("Cannot prove scoped checkpoint identity".into());
        }
        // Also required when retrying a removal whose later strict save failed.
        let records = native_proof()?.records;
        let entry = &snapshot[format!("session:{}", request.client_session_id)]["entry"];
        if records.iter().any(|native| {
            native.provider_id == "neko"
                && entry["execution"]["taskId"].as_str() == Some(&native.task_id)
                && !terminal(native)
        }) || !owns_lease(snapshot, request, &records, acquired, true)
        {
            return Err("Cannot prove terminal scoped lease ownership".into());
        }
        let (current, current_identity) = read_regular(&checkpoint_path, 64 * 1024 * 1024)?;
        let (saved, _) =
            read_regular(&app_data.join("neko-chill-sessions.json"), 64 * 1024 * 1024)?;
        let saved: Value =
            serde_json::from_slice(&saved).map_err(|_| "Cannot recheck scoped mapping")?;
        let key = format!("session:{}", request.client_session_id);
        if current != bytes
            || identity.dev() != current_identity.dev()
            || identity.ino() != current_identity.ino()
            || saved[&key] != snapshot[&key]
        {
            return Err("Scoped recovery identity changed".into());
        }
        if let Some((bytes, identity)) = lock {
            let (current, current_identity) = read_regular(&path, 4_096)?;
            if current != bytes
                || identity.dev() != current_identity.dev()
                || identity.ino() != current_identity.ino()
            {
                return Err("Task lease changed during recovery".into());
            }
            fs::remove_file(&path).map_err(|_| "Cannot remove verified task lease")?;
            File::open(&sessions)
                .and_then(|dir| dir.sync_all())
                .map_err(|_| "Cannot save task lease recovery")?;
        } else {
            match fs::symlink_metadata(&path) {
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
                _ => return Err("Cannot prove task writer remained absent".into()),
            }
        }
        Ok(true)
    }

    pub(super) fn recover(
        home: &Path,
        app_data: &Path,
        request: &LegacyLeaseRequest,
        native_proof: impl FnOnce() -> Result<QuiescentNekoCatalog, String>,
    ) -> Result<bool, String> {
        let store = app_data.join("neko-chill-sessions.json");
        if store.exists() {
            let (bytes, _) = read_regular(&store, 64 * 1024 * 1024)?;
            let snapshot: Value =
                serde_json::from_slice(&bytes).map_err(|_| "Malformed saved sessions")?;
            if !snapshot[format!("session:{}", request.client_session_id)]["entry"]["taskScope"]
                .is_null()
            {
                return recover_scoped(home, app_data, request, &snapshot, native_proof);
            }
        }
        let core = home.join(".neko-core");
        let sessions = core.join("sessions");
        for directory in [&core, &sessions] {
            match fs::symlink_metadata(directory) {
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(false),
                Ok(meta) if meta.file_type().is_dir() => {}
                _ => return Err("Unsafe Core session directory".into()),
            }
        }
        let path = sessions.join(format!("{}.json.lock", request.backend_session_id));
        match fs::symlink_metadata(&path) {
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(false),
            Err(_) => return Err("Cannot inspect session lease".into()),
            _ => {}
        }
        let (bytes, identity) = read_regular(&path, 4_096)?;
        let value: Value = serde_json::from_slice(&bytes).map_err(|_| "Malformed session lease")?;
        // Unknown/additional fields include the new heartbeat format: Core owns it.
        let object = value.as_object().ok_or("Malformed session lease")?;
        if object
            .keys()
            .any(|key| !["pid", "token", "acquiredAt"].contains(&key.as_str()))
        {
            return Ok(false);
        }
        let legacy =
            serde_json::from_value::<LegacyLock>(value).map_err(|_| "Malformed legacy lease")?;
        if legacy.pid != 1 {
            return Ok(false);
        }
        if legacy.token.len() != 32 || !legacy.token.bytes().all(|b| b.is_ascii_hexdigit()) {
            return Err("Malformed legacy lease".into());
        }
        let acquired = millis(&legacy.acquired_at)
            .filter(|at| *at >= 0)
            .ok_or("Invalid legacy lease time")?;
        // The runtime holds its operation mutex across this callback and unlink.
        // Missing/new-format locks need no global stop; mutation always does.
        let records = native_proof()?.records;
        let (store, _) =
            read_regular(&app_data.join("neko-chill-sessions.json"), 64 * 1024 * 1024)?;
        let snapshot: Value =
            serde_json::from_slice(&store).map_err(|_| "Cannot prove saved session ownership")?;
        if !owns_lease(&snapshot, request, &records, Some(acquired), false) {
            return Err("Cannot prove legacy lease ownership".into());
        }
        // No compliant writer can replace this PID-1 lease while it exists;
        // both old and new Core conservatively refuse it. Still reject changed
        // bytes/inode/hardlinks before the one-time unlink; never scan a folder.
        let (current, current_identity) = read_regular(&path, 4_096)?;
        if current != bytes
            || current_identity.dev() != identity.dev()
            || current_identity.ino() != identity.ino()
        {
            return Err("Session lease changed during recovery".into());
        }
        fs::remove_file(&path).map_err(|_| "Cannot remove verified legacy lease")?;
        File::open(&sessions)
            .and_then(|dir| dir.sync_all())
            .map_err(|_| "Cannot save legacy lease recovery")?;
        Ok(true)
    }
}

#[cfg(all(test, target_os = "linux"))]
mod tests {
    use super::*;
    use crate::neko::lifecycle::{OperationPhase, RunState};
    use serde_json::{json, Value};
    use std::fs;
    use std::path::PathBuf;

    struct Fixture {
        root: PathBuf,
        request: LegacyLeaseRequest,
        record: SessionRecord,
        saved: Value,
    }
    impl Fixture {
        fn new() -> Self {
            let root = std::env::temp_dir().join(format!("wiii-legacy-{}", uuid::Uuid::new_v4()));
            fs::create_dir_all(root.join(".neko-core/sessions")).unwrap();
            let request = LegacyLeaseRequest {
                client_session_id: "thread".into(),
                backend_session_id: "backend".into(),
            };
            let record = SessionRecord {
                agent_session_id: "native".into(),
                run_id: "run".into(),
                task_id: "legacy-local/task/thread".into(),
                environment_id: "env".into(),
                provider_id: "neko".into(),
                provider_version: Some("1.9.3".into()),
                workspace_path: root.to_string_lossy().into(),
                state: RunState::Cancelled,
                operation_phase: OperationPhase::Completed,
                continuity: "active".into(),
                pid: Some(12345),
                created_at: "2026-08-23T00:00:00Z".into(),
                updated_at: "2026-08-23T00:00:03Z".into(),
            };
            let at = chrono::DateTime::parse_from_rfc3339("2026-08-23T00:00:02Z")
                .unwrap()
                .timestamp_millis();
            let saved = json!({"session:thread": {"entry": {"id": "thread", "agentId": "neko", "backendSessionId": "backend",
                "workspace": {"path": root}}, "messages": [{"role": "user", "text": "kept"}], "events": [{
                "v": 1, "visibility": "runtime", "at": at,
                "data": {"type": "runtime-attached", "provider": {"providerId": "neko", "sessionId": "thread", "backendSessionId": "backend",
                "providerCapabilities": {"extensions": {"nativeAgentSessionId": "native", "nativeRunId": "run"}}}}
            }]}});
            let this = Self {
                root,
                request,
                record,
                saved,
            };
            this.save();
            this.lease(json!({"pid": 1, "token": "0123456789abcdef0123456789abcdef", "acquiredAt": "2026-08-23T00:00:01Z"}));
            this
        }
        fn path(&self) -> PathBuf {
            self.root.join(".neko-core/sessions/backend.json.lock")
        }
        fn store(&self) -> PathBuf {
            self.root.join("neko-chill-sessions.json")
        }
        fn save(&self) {
            fs::write(self.store(), serde_json::to_vec(&self.saved).unwrap()).unwrap();
        }
        fn lease(&self, value: Value) {
            fs::write(self.path(), serde_json::to_vec(&value).unwrap()).unwrap();
        }
        fn recover(&self) -> Result<bool, String> {
            recover(&self.root, &self.root, &self.request, || {
                Ok(QuiescentNekoCatalog {
                    records: vec![self.record.clone()],
                })
            })
        }
        fn refused(&self) {
            let original = fs::read(self.path()).unwrap();
            assert!(self.recover().is_err());
            assert_eq!(fs::read(self.path()).unwrap(), original);
        }
    }
    impl Drop for Fixture {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.root);
        }
    }

    const TASK_BACKEND: &str = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    struct ScopedFixture {
        base: Fixture,
        checkpoint: Value,
    }
    impl ScopedFixture {
        fn new() -> Self {
            let mut base = Fixture::new();
            base.request.backend_session_id = TASK_BACKEND.into();
            base.record.task_id = "host-task".into();
            base.record.provider_version = Some("1.9.4".into());
            let root = base.root.canonicalize().unwrap();
            let receipt = json!({"version": 1, "mode": "fixed-active-task", "id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "activationId": "cccccccccccccccccccccccccccccccc", "activationEpoch": 1, "label": "Kept task", "root": root});
            let execution = json!({"taskId": "host-task", "runId": "run", "environmentId": "env"});
            let entry = &mut base.saved["session:thread"]["entry"];
            entry["backendSessionId"] = json!(TASK_BACKEND);
            entry["projectId"] = json!("project");
            entry["execution"] = execution.clone();
            entry["taskScope"] = json!({"version": 1, "mode": "fixed-active-task", "state": "recovery-required",
                "reason": "writer-unavailable", "threadId": "thread", "backendSessionId": TASK_BACKEND,
                "projectId": "project", "execution": execution, "workspacePath": base.root, "authorizedRoot": root,
                "label": "Kept task", "receipt": receipt});
            base.saved["session:thread"]["events"][0]["data"]["provider"]["backendSessionId"] =
                json!(TASK_BACKEND);
            let checkpoint = json!({"schemaVersion": 2, "id": TASK_BACKEND, "canonicalRoot": root,
                "createdAt": "2026-08-23T00:00:01Z", "activeTaskId": receipt["id"],
                "taskProtocol": {"version": 1, "mode": "fixed-active-task", "activationEpoch": 1, "activationId": receipt["activationId"]},
                "tasks": [{"id": receipt["id"], "label": "Kept task", "canonicalRoot": root, "messages": [{"role": "user", "content": "kept context"}]}]});
            fs::create_dir_all(base.root.join(".neko-core/task-sessions")).unwrap();
            let this = Self { base, checkpoint };
            fs::copy(this.base.path(), this.path()).unwrap();
            this.save();
            this
        }
        fn path(&self) -> PathBuf {
            self.base
                .root
                .join(format!(".neko-core/task-sessions/{TASK_BACKEND}.lock"))
        }
        fn checkpoint_path(&self) -> PathBuf {
            self.path().with_extension("json")
        }
        fn save(&self) {
            self.base.save();
            fs::write(
                self.checkpoint_path(),
                serde_json::to_vec(&self.checkpoint).unwrap(),
            )
            .unwrap();
        }
        fn recover_with(
            &self,
            proof: impl FnOnce() -> Result<QuiescentNekoCatalog, String>,
        ) -> Result<bool, String> {
            recover(&self.base.root, &self.base.root, &self.base.request, proof)
        }
        fn recover(&self) -> Result<bool, String> {
            self.recover_with(|| {
                Ok(QuiescentNekoCatalog {
                    records: vec![self.base.record.clone()],
                })
            })
        }
        fn refused(&self) {
            let bytes = fs::read(self.path()).unwrap();
            assert!(self.recover().is_err());
            assert_eq!(fs::read(self.path()).unwrap(), bytes);
        }
    }

    #[test]
    fn scoped_recovery_preserves_context_and_receipt_and_can_retry_after_one_time_removal() {
        let f = ScopedFixture::new();
        let history = fs::read(f.base.store()).unwrap();
        let checkpoint = fs::read(f.checkpoint_path()).unwrap();
        let colliding_legacy = f
            .base
            .root
            .join(format!(".neko-core/sessions/{TASK_BACKEND}.json.lock"));
        fs::write(&colliding_legacy, "untouched legacy collision").unwrap();
        assert_eq!(f.recover(), Ok(true));
        assert!(!f.path().exists());
        // A strict frontend save may fail after unlink. Full proof is still
        // required for the missing-lock retry; it cannot strand the transcript.
        assert_eq!(f.recover(), Ok(true));
        assert_eq!(fs::read(f.base.store()).unwrap(), history);
        assert_eq!(fs::read(f.checkpoint_path()).unwrap(), checkpoint);
        assert_eq!(
            fs::read_to_string(colliding_legacy).unwrap(),
            "untouched legacy collision"
        );
    }

    #[test]
    fn scoped_recovery_handles_later_activations_without_confusing_original_checkpoint_creation_time(
    ) {
        let mut f = ScopedFixture::new();
        let activation = json!("dddddddddddddddddddddddddddddddd");
        f.checkpoint["taskProtocol"]["activationEpoch"] = json!(2);
        f.checkpoint["taskProtocol"]["activationId"] = activation.clone();
        f.base.saved["session:thread"]["entry"]["taskScope"]["receipt"]["activationEpoch"] =
            json!(2);
        f.base.saved["session:thread"]["entry"]["taskScope"]["receipt"]["activationId"] =
            activation;
        f.base.record.created_at = "2026-08-23T00:00:10Z".into();
        f.base.record.updated_at = "2026-08-23T00:00:13Z".into();
        f.base.saved["session:thread"]["events"][0]["at"] =
            json!(chrono::DateTime::parse_from_rfc3339("2026-08-23T00:00:12Z")
                .unwrap()
                .timestamp_millis());
        fs::write(
            f.path(),
            serde_json::to_vec(
                &json!({"pid": 1, "token": "0123456789abcdef0123456789abcdef",
            "acquiredAt": "2026-08-23T00:00:11Z"}),
            )
            .unwrap(),
        )
        .unwrap();
        f.save();
        assert_eq!(f.recover(), Ok(true));
        assert_eq!(f.recover(), Ok(true));
    }

    #[test]
    fn scoped_recovery_refuses_foreign_or_uncertain_checkpoint_receipt_and_execution() {
        for field in [
            "epoch",
            "activation",
            "task",
            "root",
            "label",
            "schema",
            "backend",
            "mapping",
            "run",
            "environment",
            "native",
            "unknown",
            "phase",
            "continuity",
            "no-attach",
            "time",
        ] {
            let mut f = ScopedFixture::new();
            match field {
                "epoch" => f.checkpoint["taskProtocol"]["activationEpoch"] = json!(2),
                "activation" => {
                    f.checkpoint["taskProtocol"]["activationId"] =
                        json!("dddddddddddddddddddddddddddddddd")
                }
                "task" => f.checkpoint["activeTaskId"] = json!("dddddddddddddddddddddddddddddddd"),
                "root" => f.checkpoint["canonicalRoot"] = json!("/"),
                "label" => f.checkpoint["tasks"][0]["label"] = json!("foreign label"),
                "schema" => f.checkpoint["schemaVersion"] = json!(4),
                "backend" => {
                    f.base.saved["session:thread"]["entry"]["backendSessionId"] = json!("foreign")
                }
                "mapping" => {
                    f.base.saved["session:thread"]["entry"]["taskScope"]["reason"] =
                        json!("load-response-uncertain")
                }
                "run" => f.base.record.run_id = "foreign".into(),
                "environment" => f.base.record.environment_id = "foreign".into(),
                "native" => f.base.record.agent_session_id = "foreign".into(),
                "unknown" => f.base.record.state = RunState::UnknownOutcome,
                "phase" => f.base.record.operation_phase = OperationPhase::UnknownOutcome,
                "continuity" => f.base.record.continuity = "unknown_outcome".into(),
                "no-attach" => f.base.saved["session:thread"]["events"] = json!([]),
                "time" => fs::write(f.path(), serde_json::to_vec(&json!({"pid": 1,
                    "token": "0123456789abcdef0123456789abcdef", "acquiredAt": "2026-08-23T00:00:04Z"})).unwrap()).unwrap(),
                _ => unreachable!(),
            }
            f.save();
            f.refused();
        }
        let f = ScopedFixture::new();
        fs::remove_file(f.path()).unwrap();
        let mut unknown = f.base.record.clone();
        unknown.state = RunState::UnknownOutcome;
        assert!(f
            .recover_with(|| Ok(QuiescentNekoCatalog {
                records: vec![unknown]
            }))
            .is_err());
    }

    #[test]
    fn scoped_live_process_and_live_namespace_refuse_the_lock_even_with_terminal_catalog_metadata()
    {
        use std::io::{BufRead, BufReader};
        use std::process::{Command, Stdio};
        let f = ScopedFixture::new();
        let bytes = fs::read(f.path()).unwrap();
        assert_eq!(
            f.recover_with(|| prove_quiescent(vec![f.base.record.clone()], &["native".into()])),
            Err(BUSY.into())
        );
        let mut child = Command::new("bwrap")
            .args([
                "--unshare-pid",
                "--as-pid-1",
                "--die-with-parent",
                "--dev-bind",
                "/",
                "/",
                "--proc",
                "/proc",
                "--",
                "/bin/sh",
                "-c",
                "echo ready; read input",
            ])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap();
        let mut line = String::new();
        let ready = BufReader::new(child.stdout.take().unwrap()).read_line(&mut line);
        // No retained process handle in the catalog: native /proc proof must
        // still detect the real live namespace before touching the task lock.
        let result = f.recover_with(|| prove_quiescent(vec![f.base.record.clone()], &[]));
        let _ = child.kill();
        let _ = child.wait();
        assert!(ready.is_ok());
        assert_eq!(line.trim(), "ready");
        assert_eq!(result, Err(BUSY.into()));
        assert_eq!(fs::read(f.path()).unwrap(), bytes);
    }

    #[test]
    fn scoped_recovery_refuses_unsafe_files_and_checkpoint_or_lease_races() {
        for field in [
            "symlink",
            "hardlink",
            "oversized",
            "checkpoint-race",
            "mapping-race",
            "lock-race",
            "inode-race",
        ] {
            let f = ScopedFixture::new();
            let original = fs::read(f.path()).unwrap();
            match field {
                "symlink" => {
                    fs::rename(f.checkpoint_path(), f.base.root.join("original-checkpoint"))
                        .unwrap();
                    std::os::unix::fs::symlink(
                        f.base.root.join("original-checkpoint"),
                        f.checkpoint_path(),
                    )
                    .unwrap();
                }
                "hardlink" => fs::hard_link(
                    f.checkpoint_path(),
                    f.base.root.join("second-checkpoint-link"),
                )
                .unwrap(),
                "oversized" => fs::File::create(f.checkpoint_path())
                    .unwrap()
                    .set_len(64 * 1024 * 1024 + 1)
                    .unwrap(),
                _ => {}
            }
            let result = f.recover_with(|| {
                match field {
                    "checkpoint-race" => fs::write(f.checkpoint_path(), b"{}").unwrap(),
                    "mapping-race" => fs::write(f.base.store(), b"{}").unwrap(),
                    "lock-race" => fs::write(f.path(), b"{}").unwrap(),
                    "inode-race" => {
                        fs::rename(f.path(), f.base.root.join("original-lock")).unwrap();
                        fs::write(f.path(), &original).unwrap();
                    }
                    _ => {}
                }
                Ok(QuiescentNekoCatalog {
                    records: vec![f.base.record.clone()],
                })
            });
            assert!(result.is_err(), "{field}");
            assert!(f.path().exists());
            if field != "lock-race" {
                assert_eq!(fs::read(f.path()).unwrap(), original);
            }
        }
    }

    #[test]
    fn scoped_recovery_never_takes_new_format_or_non_namespace_locks() {
        for lease in [
            json!({"pid": 42, "token": "0123456789abcdef0123456789abcdef", "acquiredAt": "2026-08-23T00:00:01Z"}),
            json!({"pid": 1, "token": "0123456789abcdef0123456789abcdef", "acquiredAt": "2026-08-23T00:00:01Z", "startTime": "1234"}),
        ] {
            let f = ScopedFixture::new();
            let bytes = serde_json::to_vec(&lease).unwrap();
            fs::write(f.path(), &bytes).unwrap();
            assert_eq!(
                f.recover_with(|| panic!("unsupported format requires no mutation or global stop")),
                Ok(false)
            );
            assert_eq!(fs::read(f.path()).unwrap(), bytes);
        }
    }

    #[test]
    fn removes_only_owned_stale_lease_once_without_changing_transcript_or_other_locks() {
        let fixture = Fixture::new();
        let original = fs::read(fixture.store()).unwrap();
        let other = fixture.path().with_file_name("other.json.lock");
        fs::write(&other, "untouched").unwrap();
        assert_eq!(fixture.recover(), Ok(true));
        assert!(!fixture.path().exists());
        assert_eq!(fixture.recover(), Ok(false));
        assert_eq!(fs::read(fixture.store()).unwrap(), original);
        assert_eq!(fs::read_to_string(other).unwrap(), "untouched");
    }

    #[test]
    fn supports_legacy_work_sessions_without_crossing_their_task_binding() {
        let mut fixture = Fixture::new();
        fixture.saved["session:thread"]["entry"]["execution"] = json!({"taskId": "owned-work"});
        fixture.save();
        fixture.refused();
        fixture.record.task_id = "owned-work".into();
        assert_eq!(fixture.recover(), Ok(true));
    }

    #[test]
    fn never_mutates_without_native_physical_quiescence_proof() {
        let fixture = Fixture::new();
        for ids in [
            vec![fixture.record.agent_session_id.clone()],
            vec!["unregistered".into()],
        ] {
            assert!(
                matches!(prove_quiescent(vec![fixture.record.clone()], &ids), Err(e) if e == BUSY)
            );
        }
        let fixture = Fixture::new();
        assert!(
            recover(&fixture.root, &fixture.root, &fixture.request, || Err(
                "unproven process supervision".into()
            ))
            .is_err()
        );
        assert!(fixture.path().exists());
    }

    #[test]
    fn unrelated_historical_outcome_does_not_override_native_physical_proof() {
        let fixture = Fixture::new();
        let mut historical = fixture.record.clone();
        historical.agent_session_id = "old-unknown".into();
        historical.task_id = "another-task".into();
        historical.state = RunState::UnknownOutcome;
        historical.operation_phase = OperationPhase::UnknownOutcome;
        historical.continuity = "unknown_outcome".into();
        let original = historical.clone();
        // The native callback has independently proven no sandbox/process alive.
        assert_eq!(
            recover(&fixture.root, &fixture.root, &fixture.request, || Ok(
                QuiescentNekoCatalog {
                    records: vec![fixture.record.clone(), historical]
                }
            )),
            Ok(true)
        );
        assert_eq!(original.state, RunState::UnknownOutcome);
        assert_eq!(original.operation_phase, OperationPhase::UnknownOutcome);
    }

    #[test]
    fn namespace_scan_refuses_live_inaccessible_or_malformed_processes() {
        let fixture = Fixture::new();
        let proc_root = fixture.root.join("proc");
        let pid = proc_root.join("123");
        fs::create_dir_all(&pid).unwrap();
        fs::write(pid.join("status"), "Name:\tbwrap\nUid:\t42\t42\t42\t42\n").unwrap();
        for argv in [
            b"/usr/bin/bwrap\0--unshare-pid\0--as-pid-1\0--die-with-parent\0--dev-bind\0/\0/\0--\0neko\0acp\0".as_slice(),
            b"bwrap\0--as-pid-1\0--die-with-parent\0--unshare-pid\0--ro-bind\0/\0/\0--\0neko\0",
        ] {
            fs::write(pid.join("cmdline"), argv).unwrap();
            assert_eq!(linux::confirm_no_sandboxes(&proc_root, 42), Err(BUSY.into()));
        }
        fs::write(pid.join("cmdline"), b"node\0dev-server.js\0").unwrap();
        assert_eq!(linux::confirm_no_sandboxes(&proc_root, 42), Ok(()));
        // Arguments after the command delimiter are not supervisor flags.
        fs::write(
            pid.join("cmdline"),
            b"node\0--\0--unshare-pid\0--as-pid-1\0--die-with-parent\0",
        )
        .unwrap();
        assert_eq!(linux::confirm_no_sandboxes(&proc_root, 42), Ok(()));
        fs::write(pid.join("cmdline"), b"").unwrap();
        assert_eq!(linux::confirm_no_sandboxes(&proc_root, 42), Ok(()));
        fs::write(pid.join("cmdline"), vec![b'x'; 65_537]).unwrap();
        assert!(linux::confirm_no_sandboxes(&proc_root, 42).is_err());
        fs::remove_file(pid.join("cmdline")).unwrap();
        fs::create_dir(pid.join("cmdline")).unwrap();
        assert!(linux::confirm_no_sandboxes(&proc_root, 42).is_err());
        fs::write(pid.join("status"), b"missing user identity").unwrap();
        assert!(linux::confirm_no_sandboxes(&proc_root, 42).is_err());
        assert!(fixture.path().exists());
    }

    #[test]
    fn kernel_supervisor_remains_observable_without_a_runtime_process_handle() {
        use std::io::{BufRead, BufReader};
        use std::process::{Command, Stdio};
        let fixture = Fixture::new();
        let mut child = Command::new("bwrap")
            .args([
                "--unshare-pid",
                "--as-pid-1",
                "--die-with-parent",
                "--dev-bind",
                "/",
                "/",
                "--proc",
                "/proc",
                "--",
                "/bin/sh",
                "-c",
                "echo ready; read input",
            ])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap();
        let mut line = String::new();
        let ready = BufReader::new(child.stdout.take().unwrap()).read_line(&mut line);
        let proc_root = fixture.root.join("kernel-observation");
        let pid = proc_root.join(child.id().to_string());
        fs::create_dir_all(&pid).unwrap();
        let observed = (|| -> Result<(), String> {
            for name in ["status", "cmdline"] {
                let bytes =
                    fs::read(format!("/proc/{}/{name}", child.id())).map_err(|e| e.to_string())?;
                fs::write(pid.join(name), bytes).map_err(|e| e.to_string())?;
            }
            // Only this actual kernel observation is visible to the scanner,
            // so an unrelated process on the workstation cannot mask a failure.
            linux::confirm_no_sandboxes(&proc_root, unsafe { libc::getuid() })
        })();
        let _ = child.kill();
        let _ = child.wait();
        assert!(ready.is_ok());
        assert_eq!(line.trim(), "ready");
        assert_eq!(observed, Err(BUSY.into()));
        assert!(fixture.path().exists());
    }

    #[test]
    fn refuses_foreign_identity_or_workspace_and_unadmitted_backend() {
        for field in [
            "task",
            "run",
            "native",
            "workspace",
            "provider",
            "phase",
            "state",
            "continuity",
            "backend",
            "no-attach",
            "scoped",
        ] {
            let mut fixture = Fixture::new();
            match field {
                "task" => fixture.record.task_id = "foreign-task".into(),
                "run" => fixture.record.run_id = "foreign-run".into(),
                "native" => fixture.record.agent_session_id = "foreign-native".into(),
                "workspace" => fixture.record.workspace_path = "/".into(),
                "provider" => fixture.record.provider_id = "claude".into(),
                "phase" => fixture.record.operation_phase = OperationPhase::UnknownOutcome,
                "state" => fixture.record.state = RunState::UnknownOutcome,
                "continuity" => fixture.record.continuity = "unknown_outcome".into(),
                "backend" => {
                    fixture.saved["session:thread"]["entry"]["backendSessionId"] = json!("foreign")
                }
                "no-attach" => fixture.saved["session:thread"]["events"] = json!([]),
                "scoped" => {
                    fixture.saved["session:thread"]["entry"]["taskScope"] =
                        json!({"state": "bound"})
                }
                _ => unreachable!(),
            }
            fixture.save();
            fixture.refused();
        }
    }

    #[test]
    fn requires_original_lease_to_predate_successful_admission_not_merely_native_exit() {
        for at in [
            "2026-08-22T23:59:59Z",
            "2026-08-23T00:00:02.500Z",
            "2026-08-23T00:00:04Z",
            "invalid",
        ] {
            let fixture = Fixture::new();
            fixture.lease(
                json!({"pid": 1, "token": "0123456789abcdef0123456789abcdef", "acquiredAt": at}),
            );
            fixture.refused();
        }
    }

    #[test]
    fn leaves_new_formats_and_host_pid_locks_to_core_without_requiring_global_stop() {
        for value in [
            json!({"pid": 1, "token": "0123456789abcdef0123456789abcdef", "acquiredAt": "2026-08-23T00:00:01Z", "heartbeatAt": "new"}),
            json!({"pid": 42, "token": "0123456789abcdef0123456789abcdef", "acquiredAt": "2026-08-23T00:00:01Z"}),
        ] {
            let fixture = Fixture::new();
            fixture.lease(value);
            let before = fs::read(fixture.path()).unwrap();
            assert_eq!(
                recover(&fixture.root, &fixture.root, &fixture.request, || panic!(
                    "no mutation requires no global stop"
                )),
                Ok(false)
            );
            assert_eq!(fs::read(fixture.path()).unwrap(), before);
        }
    }

    #[test]
    fn malformed_legacy_fields_do_not_pretend_to_be_a_new_core_format() {
        for value in [
            json!([]),
            json!({"pid": 1}),
            json!({"pid": 1, "token": 42, "acquiredAt": false}),
        ] {
            let fixture = Fixture::new();
            fixture.lease(value);
            fixture.refused();
        }
    }

    #[test]
    fn refuses_symlinks_hardlinks_oversized_and_malformed_metadata() {
        for mode in [
            "symlink",
            "hardlink",
            "oversized",
            "malformed",
            "store-link",
            "directory-link",
        ] {
            let fixture = Fixture::new();
            let outside = fixture.root.join("untouched");
            fs::write(&outside, "untouched").unwrap();
            match mode {
                "symlink" => {
                    fs::remove_file(fixture.path()).unwrap();
                    std::os::unix::fs::symlink(&outside, fixture.path()).unwrap();
                }
                "hardlink" => {
                    fs::hard_link(fixture.path(), fixture.root.join("second-link")).unwrap()
                }
                "oversized" => fs::write(fixture.path(), vec![b'x'; 4_097]).unwrap(),
                "malformed" => fs::write(fixture.path(), "{bad").unwrap(),
                "store-link" => {
                    fs::remove_file(fixture.store()).unwrap();
                    std::os::unix::fs::symlink(&outside, fixture.store()).unwrap();
                }
                "directory-link" => {
                    let dir = fixture.root.join(".neko-core/sessions");
                    fs::rename(&dir, fixture.root.join("old")).unwrap();
                    std::os::unix::fs::symlink(fixture.root.join("old"), dir).unwrap();
                }
                _ => unreachable!(),
            }
            assert!(fixture.recover().is_err(), "{mode}");
            assert_eq!(fs::read_to_string(outside).unwrap(), "untouched");
        }
    }

    #[test]
    fn refuses_changed_bytes_or_inode_between_quiescence_check_and_unlink() {
        for replace_inode in [false, true] {
            let fixture = Fixture::new();
            let before = fs::read(fixture.path()).unwrap();
            let result = recover(&fixture.root, &fixture.root, &fixture.request, || {
                if replace_inode {
                    fs::rename(fixture.path(), fixture.root.join("old-lock")).unwrap();
                    fs::write(fixture.path(), &before).unwrap();
                } else {
                    fixture.lease(json!({"pid": 1, "token": "new-format", "heartbeatAt": "live"}));
                }
                Ok(QuiescentNekoCatalog {
                    records: vec![fixture.record.clone()],
                })
            });
            assert!(result.is_err());
            assert!(fixture.path().exists());
        }
    }

    #[test]
    fn rejects_paths_instead_of_accepting_renderer_supplied_filenames() {
        for id in [
            "../backend",
            "/backend",
            "backend/child",
            "backend\\child",
            "",
            ".hidden",
            "tail.",
        ] {
            let mut fixture = Fixture::new();
            fixture.request.backend_session_id = id.into();
            fixture.refused();
        }
    }
}
