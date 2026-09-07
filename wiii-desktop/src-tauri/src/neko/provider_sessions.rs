//! Read-only discovery of provider-owned sessions.
//!
//! Discovery never creates a Wiii session. Official structured surfaces are
//! preferred. A provider without a machine-readable list may opt into an
//! explicitly bounded, read-only compatibility index; native conversation
//! history and credentials remain owned by the provider.

use super::provider::{resolve, spawn_owned, terminate_child_tree, OwnedChild};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashSet;
use std::fs::{self, File};
use std::io::{BufRead, BufReader, Read, Write};
use std::path::{Path, PathBuf};
use std::process::{ChildStdin, Command, Stdio};
use std::sync::mpsc::{self, Receiver};
use std::thread;
use std::time::{Duration, Instant};

const RPC_RESPONSE_TIMEOUT: Duration = Duration::from_secs(12);
const CLI_DISCOVERY_TIMEOUT: Duration = Duration::from_secs(15);
const DISCOVERY_POLL_INTERVAL: Duration = Duration::from_millis(25);
const MAX_RPC_FRAME_BYTES: usize = 4 * 1024 * 1024;
const MAX_CLI_OUTPUT_BYTES: usize = 4 * 1024 * 1024;
const MAX_DISCOVERED_SESSIONS: usize = 2_000;
const MAX_GEMINI_PROJECTS: usize = 8;
const MAX_CLAUDE_METADATA_BYTES: u64 = 256 * 1024;
const MAX_CLAUDE_METADATA_LINES: usize = 256;
const CODEX_TOP_LEVEL_SOURCE_KINDS: &[&str] = &["cli", "vscode", "exec", "appServer", "unknown"];

#[derive(Deserialize, Serialize, Clone, Debug, Eq, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ProviderSessionScope {
    All,
    KnownProjects,
}

#[derive(Deserialize, Serialize, Clone, Debug, Eq, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ProviderSessionRecord {
    pub provider_id: String,
    pub native_session_id: String,
    pub title: String,
    pub workspace_path: Option<String>,
    pub created_at: Option<String>,
    pub updated_at: Option<String>,
    pub model: Option<String>,
    pub state: Option<String>,
    pub can_resume: bool,
}

#[derive(Deserialize, Serialize, Clone, Debug, Eq, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ProviderSessionCatalog {
    pub provider_id: String,
    pub scope: ProviderSessionScope,
    pub complete: bool,
    pub detail: Option<String>,
    pub sessions: Vec<ProviderSessionRecord>,
}

fn bounded(value: Option<&str>, fallback: &str, max_chars: usize) -> String {
    let value = value
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .unwrap_or(fallback);
    value.chars().take(max_chars).collect()
}

fn optional_bounded(value: Option<&str>, max_chars: usize) -> Option<String> {
    value
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(|value| value.chars().take(max_chars).collect())
}

fn timestamp_seconds(value: Option<i64>) -> Option<String> {
    value
        .and_then(|seconds| DateTime::<Utc>::from_timestamp(seconds, 0))
        .map(|timestamp| timestamp.to_rfc3339())
}

fn timestamp_millis(value: Option<i64>) -> Option<String> {
    value
        .and_then(DateTime::<Utc>::from_timestamp_millis)
        .map(|timestamp| timestamp.to_rfc3339())
}

fn provider_error(value: &Value) -> String {
    value
        .get("message")
        .and_then(Value::as_str)
        .unwrap_or("provider returned an unknown JSON-RPC error")
        .chars()
        .take(1_024)
        .collect()
}

struct RpcProbe {
    child: OwnedChild,
    stdin: Option<ChildStdin>,
    lines: Receiver<Result<String, String>>,
}

impl RpcProbe {
    fn start(provider_id: &str) -> Result<Self, String> {
        let resolved = resolve(provider_id).map_err(|error| error.to_string())?;
        let args = resolved.definition.launch_args(None)?;
        let mut command = Command::new(&resolved.program);
        command
            .args(args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null());
        let mut child = spawn_owned(&mut command).map_err(|error| error.to_string())?;
        let stdin = match child.child.stdin.take() {
            Some(stdin) => stdin,
            None => {
                let cleanup = terminate_child_tree(&mut child);
                return Err(format!(
                    "provider discovery stdin is unavailable{}",
                    cleanup
                        .err()
                        .map(|error| format!("; cleanup was not proven: {error}"))
                        .unwrap_or_default()
                ));
            }
        };
        let stdout = match child.child.stdout.take() {
            Some(stdout) => stdout,
            None => {
                let cleanup = terminate_child_tree(&mut child);
                return Err(format!(
                    "provider discovery stdout is unavailable{}",
                    cleanup
                        .err()
                        .map(|error| format!("; cleanup was not proven: {error}"))
                        .unwrap_or_default()
                ));
            }
        };
        let (sender, lines) = mpsc::sync_channel(64);
        thread::Builder::new()
            .name(format!("neko-{provider_id}-session-discovery"))
            .spawn(move || {
                let mut reader = BufReader::new(stdout);
                loop {
                    let mut line = String::new();
                    match reader.read_line(&mut line) {
                        Ok(0) => {
                            let _ = sender.send(Err("provider discovery stream closed".into()));
                            return;
                        }
                        Ok(_) if line.len() > MAX_RPC_FRAME_BYTES => {
                            let _ = sender
                                .send(Err("provider discovery frame exceeded the limit".into()));
                            return;
                        }
                        Ok(_) => {
                            if sender.send(Ok(line)).is_err() {
                                return;
                            }
                        }
                        Err(error) => {
                            let _ = sender
                                .send(Err(format!("provider discovery read failed: {error}")));
                            return;
                        }
                    }
                }
            })
            .map_err(|error| {
                let cleanup = terminate_child_tree(&mut child);
                format!(
                    "provider discovery reader could not start: {error}{}",
                    cleanup
                        .err()
                        .map(|cleanup| format!("; cleanup was not proven: {cleanup}"))
                        .unwrap_or_default()
                )
            })?;
        Ok(Self {
            child,
            stdin: Some(stdin),
            lines,
        })
    }

    fn send(&mut self, value: &Value) -> Result<(), String> {
        let stdin = self
            .stdin
            .as_mut()
            .ok_or_else(|| "provider discovery stdin is closed".to_string())?;
        serde_json::to_writer(&mut *stdin, value)
            .map_err(|error| format!("provider discovery request encoding failed: {error}"))?;
        stdin
            .write_all(b"\n")
            .and_then(|_| stdin.flush())
            .map_err(|error| format!("provider discovery request write failed: {error}"))
    }

    fn notify(&mut self, method: &str, params: Value) -> Result<(), String> {
        self.send(&json!({ "jsonrpc": "2.0", "method": method, "params": params }))
    }

    fn request(&mut self, id: u64, method: &str, params: Value) -> Result<Value, String> {
        self.send(&json!({
            "jsonrpc": "2.0",
            "id": id,
            "method": method,
            "params": params,
        }))?;
        let deadline = Instant::now() + RPC_RESPONSE_TIMEOUT;
        loop {
            let remaining = deadline.saturating_duration_since(Instant::now());
            if remaining.is_zero() {
                return Err(format!("provider discovery request timed out: {method}"));
            }
            let line = self
                .lines
                .recv_timeout(remaining)
                .map_err(|error| format!("provider discovery response timed out: {error}"))??;
            let response: Value = serde_json::from_str(line.trim())
                .map_err(|error| format!("provider discovery emitted invalid JSON: {error}"))?;
            if response.get("id").and_then(Value::as_u64) != Some(id) {
                continue;
            }
            if let Some(error) = response.get("error") {
                return Err(provider_error(error));
            }
            return response
                .get("result")
                .cloned()
                .ok_or_else(|| "provider discovery response has no result".to_string());
        }
    }

    fn finish(mut self) -> Result<(), String> {
        drop(self.stdin.take());
        terminate_child_tree(&mut self.child)
            .map_err(|error| format!("provider discovery cleanup was not proven: {error}"))
    }
}

fn with_rpc_probe<T>(
    provider_id: &str,
    operation: impl FnOnce(&mut RpcProbe) -> Result<T, String>,
) -> Result<T, String> {
    let mut probe = RpcProbe::start(provider_id)?;
    let result = operation(&mut probe);
    let cleanup = probe.finish();
    match (result, cleanup) {
        (Ok(value), Ok(())) => Ok(value),
        (Err(error), Ok(())) => Err(error),
        (Ok(_), Err(cleanup)) => Err(cleanup),
        (Err(error), Err(cleanup)) => Err(format!("{error}; {cleanup}")),
    }
}

fn discover_codex() -> Result<ProviderSessionCatalog, String> {
    with_rpc_probe("codex", |probe| {
        probe.request(
            1,
            "initialize",
            json!({
                "clientInfo": { "name": "wiii", "title": "Wiii", "version": env!("CARGO_PKG_VERSION") },
                "capabilities": { "experimentalApi": true, "requestAttestation": false }
            }),
        )?;
        probe.notify("initialized", json!({}))?;
        let mut cursor: Option<String> = None;
        let mut seen_cursors = HashSet::new();
        let mut sessions = Vec::new();
        let mut request_id = 2;
        let mut complete = true;
        loop {
            let result = probe.request(
                request_id,
                "thread/list",
                json!({
                    "cursor": cursor,
                    "limit": 100,
                    "sortKey": "updated_at",
                    "sortDirection": "desc",
                    // Omitting this field only returns Codex's `cli` and
                    // `vscode` defaults. Neko Chill is a cross-client session
                    // supervisor, so include every top-level interactive
                    // source while keeping provider-native subagents nested
                    // under their owning conversation.
                    "sourceKinds": CODEX_TOP_LEVEL_SOURCE_KINDS
                }),
            )?;
            request_id += 1;
            for item in result
                .get("data")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
            {
                let Some(id) = item.get("id").and_then(Value::as_str) else {
                    continue;
                };
                sessions.push(ProviderSessionRecord {
                    provider_id: "codex".into(),
                    native_session_id: bounded(Some(id), "Codex session", 256),
                    title: bounded(
                        item.get("name")
                            .and_then(Value::as_str)
                            .or_else(|| item.get("preview").and_then(Value::as_str)),
                        "Phiên Codex",
                        160,
                    ),
                    workspace_path: optional_bounded(
                        item.get("cwd").and_then(Value::as_str),
                        2_048,
                    ),
                    created_at: timestamp_seconds(item.get("createdAt").and_then(Value::as_i64)),
                    updated_at: timestamp_seconds(item.get("updatedAt").and_then(Value::as_i64)),
                    model: optional_bounded(item.get("modelProvider").and_then(Value::as_str), 128),
                    state: optional_bounded(
                        item.get("status")
                            .and_then(|status| status.get("type"))
                            .and_then(Value::as_str),
                        64,
                    ),
                    can_resume: true,
                });
                if sessions.len() >= MAX_DISCOVERED_SESSIONS {
                    complete = false;
                    break;
                }
            }
            if !complete {
                break;
            }
            let next = result
                .get("nextCursor")
                .and_then(Value::as_str)
                .map(str::to_string);
            match next {
                Some(next) if seen_cursors.insert(next.clone()) => cursor = Some(next),
                Some(_) => return Err("Codex returned a repeated session cursor".into()),
                None => break,
            }
        }
        Ok(ProviderSessionCatalog {
            provider_id: "codex".into(),
            scope: ProviderSessionScope::All,
            complete,
            detail: (!complete).then(|| "Danh sách đã chạm giới hạn an toàn 2.000 phiên.".into()),
            sessions,
        })
    })
}

fn discover_acp(provider_id: &str, provider_name: &str) -> Result<ProviderSessionCatalog, String> {
    with_rpc_probe(provider_id, |probe| {
        let initialized = probe.request(
            1,
            "initialize",
            json!({
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": { "readTextFile": false, "writeTextFile": false },
                    "terminal": false
                },
                "clientInfo": { "name": "wiii", "title": "Wiii", "version": env!("CARGO_PKG_VERSION") }
            }),
        )?;
        let supports_list = initialized
            .pointer("/agentCapabilities/sessionCapabilities/list")
            .is_some();
        if !supports_list {
            return Ok(ProviderSessionCatalog {
                provider_id: provider_id.into(),
                scope: ProviderSessionScope::All,
                complete: false,
                detail: Some(format!(
                    "{provider_name} chưa quảng bá session/list qua ACP; Wiii vẫn có thể quản các phiên do Wiii tạo."
                )),
                sessions: Vec::new(),
            });
        }
        let mut cursor: Option<String> = None;
        let mut seen_cursors = HashSet::new();
        let mut sessions = Vec::new();
        let mut request_id = 2;
        let mut complete = true;
        loop {
            let result = probe.request(
                request_id,
                "session/list",
                cursor
                    .as_ref()
                    .map(|cursor| json!({ "cursor": cursor }))
                    .unwrap_or_else(|| json!({})),
            )?;
            request_id += 1;
            for item in result
                .get("sessions")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
            {
                let Some(id) = item.get("sessionId").and_then(Value::as_str) else {
                    continue;
                };
                sessions.push(ProviderSessionRecord {
                    provider_id: provider_id.into(),
                    native_session_id: bounded(Some(id), "Neko session", 256),
                    title: bounded(
                        item.get("title").and_then(Value::as_str),
                        &format!("Phiên {provider_name}"),
                        160,
                    ),
                    workspace_path: optional_bounded(
                        item.get("cwd").and_then(Value::as_str),
                        2_048,
                    ),
                    created_at: None,
                    updated_at: optional_bounded(item.get("updatedAt").and_then(Value::as_str), 64),
                    model: optional_bounded(
                        item.pointer("/_meta/model").and_then(Value::as_str),
                        128,
                    ),
                    state: Some("saved".into()),
                    can_resume: true,
                });
                if sessions.len() >= MAX_DISCOVERED_SESSIONS {
                    complete = false;
                    break;
                }
            }
            if !complete {
                break;
            }
            let next = result
                .get("nextCursor")
                .and_then(Value::as_str)
                .map(str::to_string);
            match next {
                Some(next) if seen_cursors.insert(next.clone()) => cursor = Some(next),
                Some(_) => return Err("Neko Core returned a repeated session cursor".into()),
                None => break,
            }
        }
        Ok(ProviderSessionCatalog {
            provider_id: provider_id.into(),
            scope: ProviderSessionScope::All,
            complete,
            detail: (!complete).then(|| "Danh sách đã chạm giới hạn an toàn 2.000 phiên.".into()),
            sessions,
        })
    })
}

fn claude_projects_directory() -> Option<PathBuf> {
    std::env::var_os("CLAUDE_CONFIG_DIR")
        .map(PathBuf::from)
        .or_else(|| {
            std::env::var_os(if cfg!(windows) { "USERPROFILE" } else { "HOME" })
                .map(PathBuf::from)
                .map(|home| home.join(".claude"))
        })
        .map(|config| config.join("projects"))
}

#[derive(Default)]
struct ClaudeSessionMetadata {
    cwd: Option<String>,
    created_at: Option<String>,
    ai_title: Option<String>,
    custom_title: Option<String>,
}

fn parse_claude_session_metadata_reader(reader: impl BufRead) -> ClaudeSessionMetadata {
    let mut metadata = ClaudeSessionMetadata::default();
    for line in reader.lines().take(MAX_CLAUDE_METADATA_LINES) {
        let Ok(line) = line else { break };
        let Ok(value) = serde_json::from_str::<Value>(&line) else {
            continue;
        };
        if metadata.cwd.is_none() {
            metadata.cwd = optional_bounded(value.get("cwd").and_then(Value::as_str), 2_048);
        }
        if metadata.created_at.is_none() {
            metadata.created_at =
                optional_bounded(value.get("timestamp").and_then(Value::as_str), 64);
        }
        match value.get("type").and_then(Value::as_str) {
            Some("custom-title") => {
                metadata.custom_title =
                    optional_bounded(value.get("customTitle").and_then(Value::as_str), 160);
            }
            Some("ai-title") => {
                metadata.ai_title =
                    optional_bounded(value.get("aiTitle").and_then(Value::as_str), 160);
            }
            _ => {}
        }
    }
    metadata
}

fn parse_claude_session_metadata(path: &Path) -> Result<ClaudeSessionMetadata, String> {
    let file = File::open(path)
        .map_err(|error| format!("cannot open Claude session metadata: {error}"))?;
    Ok(parse_claude_session_metadata_reader(BufReader::new(
        file.take(MAX_CLAUDE_METADATA_BYTES),
    )))
}

fn discover_claude() -> Result<ProviderSessionCatalog, String> {
    let Some(projects_directory) = claude_projects_directory() else {
        return Ok(ProviderSessionCatalog {
            provider_id: "claude".into(),
            scope: ProviderSessionScope::All,
            complete: false,
            detail: Some("Không xác định được thư mục cấu hình Claude Code.".into()),
            sessions: Vec::new(),
        });
    };
    if !projects_directory.is_dir() {
        return Ok(ProviderSessionCatalog {
            provider_id: "claude".into(),
            scope: ProviderSessionScope::All,
            complete: true,
            detail: Some("Claude Code chưa có chỉ mục phiên local trên máy này.".into()),
            sessions: Vec::new(),
        });
    }

    let mut candidates = Vec::new();
    let mut skipped = 0usize;
    for project in fs::read_dir(&projects_directory)
        .map_err(|error| format!("cannot read Claude project index: {error}"))?
    {
        let Ok(project) = project else {
            skipped += 1;
            continue;
        };
        let project_path = project.path();
        if !project_path.is_dir() || project.file_name() == "subagents" {
            continue;
        }
        let Ok(entries) = fs::read_dir(&project_path) else {
            skipped += 1;
            continue;
        };
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|value| value.to_str()) != Some("jsonl") {
                continue;
            }
            let Some(stem) = path
                .file_stem()
                .and_then(|value| value.to_str())
                .map(str::to_owned)
            else {
                skipped += 1;
                continue;
            };
            if stem.starts_with("agent-") {
                continue;
            }
            let modified = entry
                .metadata()
                .ok()
                .and_then(|metadata| metadata.modified().ok());
            candidates.push((path, stem, modified));
        }
    }
    candidates.sort_by_key(|candidate| std::cmp::Reverse(candidate.2));

    let complete = candidates.len() <= MAX_DISCOVERED_SESSIONS && skipped == 0;
    let mut sessions = Vec::new();
    for (path, native_session_id, modified) in candidates.into_iter().take(MAX_DISCOVERED_SESSIONS)
    {
        let metadata = match parse_claude_session_metadata(&path) {
            Ok(metadata) => metadata,
            Err(_) => {
                skipped += 1;
                ClaudeSessionMetadata::default()
            }
        };
        let updated_at = modified
            .map(DateTime::<Utc>::from)
            .map(|timestamp| timestamp.to_rfc3339());
        sessions.push(ProviderSessionRecord {
            provider_id: "claude".into(),
            native_session_id: bounded(Some(&native_session_id), "Claude session", 256),
            title: metadata
                .custom_title
                .or(metadata.ai_title)
                .unwrap_or_else(|| "Phiên Claude Code".into()),
            workspace_path: metadata.cwd,
            created_at: metadata.created_at,
            updated_at,
            model: None,
            state: Some("saved".into()),
            // The index is useful for finding native sessions, but this Wiii
            // build does not yet ship the dedicated Claude stream-json driver.
            can_resume: false,
        });
    }

    Ok(ProviderSessionCatalog {
        provider_id: "claude".into(),
        scope: ProviderSessionScope::All,
        complete: complete && skipped == 0,
        detail: Some(format!(
            "Đã lập chỉ mục read-only {} phiên Claude Code; không đọc credential hoặc sao chép transcript. Live adapter Claude chưa bật trong bản này{}.",
            sessions.len(),
            if skipped > 0 { "; một số file metadata không đọc được" } else { "" }
        )),
        sessions,
    })
}

fn cleanup_after_capture(child: &mut OwnedChild, error: String) -> String {
    match terminate_child_tree(child) {
        Ok(()) => error,
        Err(cleanup) => format!("{error}; provider discovery cleanup was not proven: {cleanup}"),
    }
}

fn capture_cli(provider_id: &str, args: &[&str], cwd: Option<&str>) -> Result<String, String> {
    let resolved = resolve(provider_id).map_err(|error| error.to_string())?;
    let mut command = Command::new(&resolved.program);
    command
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null());
    if let Some(cwd) = cwd {
        command.current_dir(cwd);
    }
    let mut child = spawn_owned(&mut command).map_err(|error| error.to_string())?;
    let stdout = match child.child.stdout.take() {
        Some(stdout) => stdout,
        None => {
            return Err(cleanup_after_capture(
                &mut child,
                "provider discovery stdout is unavailable".into(),
            ))
        }
    };
    let (sender, receiver) = mpsc::sync_channel(1);
    thread::Builder::new()
        .name(format!("neko-{provider_id}-session-catalog"))
        .spawn(move || {
            let mut captured = Vec::new();
            let result = stdout
                .take((MAX_CLI_OUTPUT_BYTES + 1) as u64)
                .read_to_end(&mut captured)
                .map(|_| captured)
                .map_err(|error| error.to_string());
            let _ = sender.send(result);
        })
        .map_err(|error| {
            cleanup_after_capture(
                &mut child,
                format!("provider discovery reader could not start: {error}"),
            )
        })?;

    let deadline = Instant::now() + CLI_DISCOVERY_TIMEOUT;
    let status = loop {
        match child.child.try_wait() {
            Ok(Some(status)) => break status,
            Ok(None) if Instant::now() >= deadline => {
                return Err(cleanup_after_capture(
                    &mut child,
                    "provider session discovery timed out".into(),
                ));
            }
            Ok(None) => thread::sleep(DISCOVERY_POLL_INTERVAL),
            Err(error) => {
                return Err(cleanup_after_capture(
                    &mut child,
                    format!("provider discovery wait failed: {error}"),
                ));
            }
        }
    };
    terminate_child_tree(&mut child)
        .map_err(|error| format!("provider discovery cleanup was not proven: {error}"))?;
    let output = receiver
        .recv_timeout(Duration::from_secs(1))
        .map_err(|error| format!("provider discovery output did not close: {error}"))??;
    if output.len() > MAX_CLI_OUTPUT_BYTES {
        return Err("provider discovery output exceeded the limit".into());
    }
    if !status.success() {
        return Err(format!("provider session discovery exited with {status}"));
    }
    String::from_utf8(output)
        .map_err(|error| format!("provider discovery output is not UTF-8: {error}"))
}

fn discover_opencode() -> Result<ProviderSessionCatalog, String> {
    let output = capture_cli(
        "opencode",
        &["session", "list", "--format", "json", "--max-count", "2000"],
        None,
    )?;
    let items: Vec<Value> = serde_json::from_str(&output)
        .map_err(|error| format!("OpenCode session list returned invalid JSON: {error}"))?;
    let sessions = items
        .into_iter()
        .filter_map(|item| {
            let id = item.get("id")?.as_str()?;
            Some(ProviderSessionRecord {
                provider_id: "opencode".into(),
                native_session_id: bounded(Some(id), "OpenCode session", 256),
                title: bounded(
                    item.get("title").and_then(Value::as_str),
                    "Phiên OpenCode",
                    160,
                ),
                workspace_path: optional_bounded(
                    item.get("directory").and_then(Value::as_str),
                    2_048,
                ),
                created_at: timestamp_millis(item.get("created").and_then(Value::as_i64)),
                updated_at: timestamp_millis(item.get("updated").and_then(Value::as_i64)),
                model: None,
                state: Some("saved".into()),
                can_resume: true,
            })
        })
        .collect();
    Ok(ProviderSessionCatalog {
        provider_id: "opencode".into(),
        scope: ProviderSessionScope::All,
        complete: true,
        detail: None,
        sessions,
    })
}

fn parse_gemini_sessions(output: &str, workspace_path: &str) -> Vec<ProviderSessionRecord> {
    output
        .lines()
        .filter_map(|line| {
            let line = line.trim();
            let (_, rest) = line.split_once(". ")?;
            let open = rest.rfind(" [")?;
            let id = rest.get(open + 2..)?.strip_suffix(']')?;
            let title_with_time = rest.get(..open)?.trim();
            let title = title_with_time
                .rfind(" (")
                .and_then(|index| title_with_time.get(..index))
                .unwrap_or(title_with_time);
            Some(ProviderSessionRecord {
                provider_id: "gemini".into(),
                native_session_id: bounded(Some(id), "Gemini session", 256),
                title: bounded(Some(title), "Phiên Gemini CLI", 160),
                workspace_path: Some(workspace_path.to_string()),
                created_at: None,
                updated_at: None,
                model: None,
                state: Some("saved".into()),
                can_resume: true,
            })
        })
        .collect()
}

fn discover_gemini(workspace_paths: &[String]) -> Result<ProviderSessionCatalog, String> {
    let mut sessions = Vec::new();
    let mut seen = HashSet::new();
    let mut scanned = 0usize;
    for workspace_path in workspace_paths
        .iter()
        .filter(|path| std::path::Path::new(path).is_absolute())
        .take(MAX_GEMINI_PROJECTS)
    {
        scanned += 1;
        let output = capture_cli("gemini", &["--list-sessions"], Some(workspace_path))?;
        for session in parse_gemini_sessions(&output, workspace_path) {
            if seen.insert(session.native_session_id.clone()) {
                sessions.push(session);
            }
        }
    }
    let truncated = workspace_paths.len() > MAX_GEMINI_PROJECTS;
    Ok(ProviderSessionCatalog {
        provider_id: "gemini".into(),
        scope: ProviderSessionScope::KnownProjects,
        complete: !truncated,
        detail: Some(if scanned == 0 {
            "Gemini CLI chỉ cho liệt kê theo project; hãy mở hoặc gắn folder để Neko quét phiên của project đó.".into()
        } else if truncated {
            format!("Đã quét {scanned} project gần nhất; Gemini CLI không có API liệt kê toàn máy.")
        } else {
            format!("Đã quét {scanned} project đã biết; Gemini CLI không có API liệt kê toàn máy.")
        }),
        sessions,
    })
}

pub fn discover(
    provider_id: &str,
    workspace_paths: &[String],
) -> Result<ProviderSessionCatalog, String> {
    match provider_id {
        "codex" => discover_codex(),
        "neko" => discover_acp("neko", "Neko Core"),
        "gemini" => discover_gemini(workspace_paths),
        "opencode" => discover_opencode(),
        "claude" => discover_claude(),
        "cursor" => discover_acp("cursor", "Cursor Agent"),
        "copilot" => discover_acp("copilot", "GitHub Copilot CLI"),
        _ => Err(format!("unknown Neko provider '{provider_id}'")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_gemini_project_session_rows_without_treating_headers_as_sessions() {
        let output = r#"
Available sessions for this project (2):

  1. Fix authentication (2 hours ago) [11111111-1111-1111-1111-111111111111]
  2. Review tests (just now, current) [22222222-2222-2222-2222-222222222222]
"#;
        let sessions = parse_gemini_sessions(output, r"E:\Projects\wiii");
        assert_eq!(sessions.len(), 2);
        assert_eq!(sessions[0].title, "Fix authentication");
        assert_eq!(
            sessions[1].native_session_id,
            "22222222-2222-2222-2222-222222222222"
        );
        assert_eq!(
            sessions[1].workspace_path.as_deref(),
            Some(r"E:\Projects\wiii")
        );
    }

    #[test]
    fn codex_catalog_includes_desktop_threads_without_promoting_native_subagents() {
        assert!(CODEX_TOP_LEVEL_SOURCE_KINDS.contains(&"appServer"));
        assert!(!CODEX_TOP_LEVEL_SOURCE_KINDS
            .iter()
            .any(|source| source.starts_with("subAgent")));
    }

    #[test]
    fn claude_catalog_reads_only_bounded_metadata_and_prefers_explicit_title() {
        let input = concat!(
            "{\"type\":\"user\",\"cwd\":\"E:\\\\Projects\\\\wiii\",\"timestamp\":\"2026-08-24T01:02:03Z\",\"message\":{\"content\":\"private prompt\"}}\n",
            "{\"type\":\"ai-title\",\"aiTitle\":\"Refactor auth\"}\n",
            "{\"type\":\"custom-title\",\"customTitle\":\"Authentication\"}\n",
        );
        let metadata = parse_claude_session_metadata_reader(std::io::Cursor::new(input));
        assert_eq!(metadata.cwd.as_deref(), Some(r"E:\Projects\wiii"));
        assert_eq!(metadata.created_at.as_deref(), Some("2026-08-24T01:02:03Z"));
        assert_eq!(metadata.custom_title.as_deref(), Some("Authentication"));
        assert_eq!(metadata.ai_title.as_deref(), Some("Refactor auth"));
    }
}
