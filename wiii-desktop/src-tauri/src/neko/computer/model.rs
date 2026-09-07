use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ComputerState {
    Preparing,
    Ready,
    Suspended,
    Error,
    UnknownOutcome,
}

impl ComputerState {
    pub(crate) fn as_str(&self) -> &'static str {
        match self {
            Self::Preparing => "preparing",
            Self::Ready => "ready",
            Self::Suspended => "suspended",
            Self::Error => "error",
            Self::UnknownOutcome => "unknown_outcome",
        }
    }

    pub(crate) fn parse(value: &str) -> Result<Self, String> {
        match value {
            "preparing" => Ok(Self::Preparing),
            "ready" => Ok(Self::Ready),
            "suspended" => Ok(Self::Suspended),
            "error" => Ok(Self::Error),
            "unknown_outcome" => Ok(Self::UnknownOutcome),
            _ => Err(format!("unknown computer state: {value}")),
        }
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SeatState {
    Available,
    AgentControlled,
    UserControlled,
}

impl SeatState {
    pub(crate) fn as_str(&self) -> &'static str {
        match self {
            Self::Available => "available",
            Self::AgentControlled => "agent_controlled",
            Self::UserControlled => "user_controlled",
        }
    }

    pub(crate) fn parse(value: &str) -> Result<Self, String> {
        match value {
            "available" => Ok(Self::Available),
            "agent_controlled" => Ok(Self::AgentControlled),
            "user_controlled" => Ok(Self::UserControlled),
            _ => Err(format!("unknown seat state: {value}")),
        }
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerResources {
    pub cpus: String,
    pub memory_bytes: u64,
    pub pids_limit: u32,
    pub shared_memory_bytes: u64,
    pub temporary_storage_bytes: u64,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ComputerResourcePreset {
    #[default]
    Auto,
    Compact,
    Balanced,
    Performance,
}

impl ComputerResourcePreset {
    pub(crate) fn resources(&self) -> ComputerResources {
        match self {
            Self::Compact => ComputerResources {
                cpus: "1.0".to_string(),
                memory_bytes: 2 * 1024 * 1024 * 1024,
                pids_limit: 768,
                shared_memory_bytes: 512 * 1024 * 1024,
                temporary_storage_bytes: 384 * 1024 * 1024,
            },
            Self::Performance => ComputerResources {
                cpus: "4.0".to_string(),
                memory_bytes: 8 * 1024 * 1024 * 1024,
                pids_limit: 1536,
                shared_memory_bytes: 2 * 1024 * 1024 * 1024,
                temporary_storage_bytes: 1024 * 1024 * 1024,
            },
            Self::Auto | Self::Balanced => ComputerResources::default(),
        }
    }

    pub(crate) fn recommend(cpus: Option<u32>, memory_bytes: Option<u64>) -> Self {
        match (cpus, memory_bytes) {
            (Some(cpu), Some(memory)) if cpu >= 12 && memory >= 24 * 1024 * 1024 * 1024 => {
                Self::Performance
            }
            (Some(cpu), Some(memory)) if cpu <= 4 || memory < 8 * 1024 * 1024 * 1024 => {
                Self::Compact
            }
            _ => Self::Balanced,
        }
    }
}

impl Default for ComputerResources {
    fn default() -> Self {
        Self {
            cpus: "2.0".to_string(),
            memory_bytes: 4 * 1024 * 1024 * 1024,
            pids_limit: 1024,
            shared_memory_bytes: 1024 * 1024 * 1024,
            temporary_storage_bytes: 512 * 1024 * 1024,
        }
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DisplaySeat {
    pub seat_id: String,
    pub state: SeatState,
    pub lease_id: Option<String>,
    pub owner_id: Option<String>,
    pub updated_at: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerEnvironment {
    pub environment_id: String,
    pub project_id: Option<String>,
    pub project_name: String,
    pub project_path: String,
    pub provider_kind: String,
    pub isolation_class: String,
    pub computer_kind: String,
    pub operating_system: String,
    pub semantic_protocol: String,
    #[serde(default)]
    pub active_pack_version: Option<String>,
    #[serde(default)]
    pub pack_update_available: bool,
    pub state: ComputerState,
    pub project_mount: String,
    pub attach_url: Option<String>,
    pub resources: ComputerResources,
    pub seat: DisplaySeat,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerProjectGrant {
    pub coworker_id: String,
    pub project_id: Option<String>,
    pub project_name: String,
    pub project_path: String,
    pub access_mode: String,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CoworkerComputerStatus {
    pub coworker_id: String,
    pub environment_id: Option<String>,
    pub active_project_id: Option<String>,
    pub active_project_path: Option<String>,
    pub environment: Option<ComputerEnvironment>,
    pub grants: Vec<ComputerProjectGrant>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SemanticBounds {
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub height: i32,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SemanticScreen {
    pub width: u32,
    pub height: u32,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SemanticFrame {
    pub version: String,
    pub scope: String,
    pub observation_model: String,
    pub action_model: String,
    pub coordinates: String,
    #[serde(default)]
    pub modalities: Vec<String>,
    pub interaction: Option<SemanticInteraction>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SemanticInteraction {
    pub mode: String,
    pub target_ref: Option<String>,
    #[serde(default)]
    pub input_actions: Vec<SemanticActionKind>,
    pub keymap_source: String,
    #[serde(default)]
    pub shortcuts: Vec<String>,
    pub feedback: String,
    pub clock_mode: Option<String>,
    #[serde(default)]
    pub clock_modes: Vec<String>,
    pub clock_watchdog_ms: Option<u32>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SemanticAdapter {
    pub id: String,
    pub version: String,
    #[serde(default)]
    pub capabilities: Vec<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SemanticNode {
    #[serde(rename = "ref")]
    pub node_ref: String,
    pub parent_ref: Option<String>,
    pub app_id: Option<String>,
    pub role: String,
    pub name: String,
    pub description: Option<String>,
    pub value: Option<String>,
    pub states: Vec<String>,
    pub actions: Vec<SemanticActionKind>,
    pub bounds: Option<SemanticBounds>,
    #[serde(default)]
    pub sources: Vec<String>,
    #[serde(default)]
    pub shortcuts: Vec<String>,
    #[serde(default)]
    pub version: String,
    pub adapter: Option<SemanticAdapter>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SemanticProjection {
    Full,
    Delta,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SemanticSnapshot {
    pub protocol_version: String,
    pub environment_id: String,
    pub state_version: String,
    pub captured_at: String,
    pub platform: String,
    pub screen: SemanticScreen,
    pub active_window_ref: Option<String>,
    pub frame: Option<SemanticFrame>,
    pub nodes: Vec<SemanticNode>,
    pub truncated: bool,
    pub scope_ref: Option<String>,
    #[serde(default = "default_semantic_projection")]
    pub projection: SemanticProjection,
    pub next_continuation: Option<String>,
    pub delta_from_state_version: Option<String>,
    #[serde(default)]
    pub removed_refs: Vec<String>,
    pub visual_patch: Option<SemanticVisualPatch>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SemanticVisualPatch {
    #[serde(rename = "ref")]
    pub node_ref: String,
    pub mime_type: String,
    pub width: u32,
    pub height: u32,
    pub sha256: String,
    pub data: String,
}

fn default_semantic_projection() -> SemanticProjection {
    SemanticProjection::Full
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SemanticKnownNodeVersion {
    #[serde(rename = "ref")]
    pub node_ref: String,
    pub version: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SemanticObserveRequest {
    pub environment_id: String,
    #[serde(default = "default_semantic_node_limit")]
    pub max_nodes: u32,
    pub scope_ref: Option<String>,
    pub continuation: Option<String>,
    pub since_state_version: Option<String>,
    #[serde(default)]
    pub known_node_versions: Vec<SemanticKnownNodeVersion>,
    pub visual_ref: Option<String>,
}

fn default_semantic_node_limit() -> u32 {
    400
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SemanticActionKind {
    Focus,
    Invoke,
    SetText,
    PressKey,
    InputSequence,
}

impl SemanticActionKind {
    pub(crate) fn as_str(&self) -> &'static str {
        match self {
            Self::Focus => "focus",
            Self::Invoke => "invoke",
            Self::SetText => "set_text",
            Self::PressKey => "press_key",
            Self::InputSequence => "input_sequence",
        }
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SemanticInputStep {
    pub keys: Vec<String>,
    pub hold_ms: u32,
    #[serde(default)]
    pub wait_ms: u32,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SemanticRealtimeMode {
    Continuous,
    Stepped,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SemanticClockResult {
    pub mode: SemanticRealtimeMode,
    pub active_ms: u32,
    pub watchdog_ms: u32,
    pub deadline_ms: Option<u64>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SemanticActRequest {
    pub request_id: String,
    pub environment_id: String,
    pub lease_id: String,
    pub state_version: String,
    pub target_ref: String,
    pub expected_role: String,
    pub expected_name: String,
    pub action: SemanticActionKind,
    pub text: Option<String>,
    pub key: Option<String>,
    #[serde(default)]
    pub input_sequence: Vec<SemanticInputStep>,
    #[serde(default)]
    pub return_observation: bool,
    pub realtime_mode: Option<SemanticRealtimeMode>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SemanticActionOutcome {
    Completed,
    Rejected,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SemanticActResult {
    pub environment_id: String,
    pub outcome: SemanticActionOutcome,
    pub code: Option<String>,
    pub detail: String,
    pub action: SemanticActionKind,
    pub target_ref: String,
    pub before_state_version: String,
    pub after_state_version: String,
    pub verified: bool,
    pub effect: Option<String>,
    pub route: Option<String>,
    #[serde(default)]
    pub evidence: Vec<String>,
    pub escalation: Option<String>,
    pub visual_patch: Option<SemanticVisualPatch>,
    pub clock: Option<SemanticClockResult>,
    pub observation: Option<SemanticSnapshot>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkPlaneDescribeRequest {
    pub environment_id: String,
    pub project_id: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkCapability {
    pub id: String,
    pub version: String,
    pub resource_types: Vec<String>,
    pub input_schema: serde_json::Value,
    pub mutating: bool,
    pub risk: String,
    pub approval: String,
    pub retry: String,
    pub reversible: bool,
    pub max_input_bytes: u32,
    pub evidence: Vec<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkResource {
    #[serde(rename = "ref")]
    pub resource_ref: String,
    pub resource_type: String,
    pub name: String,
    pub parent_ref: Option<String>,
    pub revision: String,
    pub media_type: Option<String>,
    pub capabilities: Vec<String>,
    pub source: String,
    pub metadata: serde_json::Value,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkPlaneDescriptor {
    pub protocol_version: String,
    pub source_authority: String,
    pub resource_model: String,
    pub transaction_model: String,
    pub root: WorkResource,
    pub capabilities: Vec<WorkCapability>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum WorkQueryView {
    Children,
    Content,
    Spreadsheet,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkPlaneQueryRequest {
    pub environment_id: String,
    pub project_id: String,
    #[serde(rename = "resourceRef")]
    pub resource_ref: String,
    pub view: WorkQueryView,
    #[serde(default = "default_work_query_items")]
    pub max_items: u32,
    #[serde(default)]
    pub offset: u64,
    #[serde(default = "default_work_query_bytes")]
    pub max_bytes: u32,
    pub sheet: Option<String>,
    pub range: Option<String>,
}

fn default_work_query_items() -> u32 {
    100
}

fn default_work_query_bytes() -> u32 {
    64 * 1024
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkPlaneQueryResult {
    pub protocol_version: String,
    pub resource: WorkResource,
    pub items: Vec<WorkResource>,
    pub data: serde_json::Value,
    pub truncated: bool,
    pub next_offset: Option<u64>,
    pub evidence: Vec<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkPlaneTransactionRequest {
    pub request_id: String,
    pub environment_id: String,
    pub project_id: String,
    pub capability_id: String,
    pub capability_version: String,
    pub target_ref: String,
    pub if_revision: String,
    pub input: serde_json::Value,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum WorkTransactionOutcome {
    Completed,
    Rejected,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkChange {
    #[serde(rename = "ref")]
    pub resource_ref: String,
    pub kind: String,
    pub before_revision: Option<String>,
    pub after_revision: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkPlaneTransactionResult {
    pub protocol_version: String,
    pub outcome: WorkTransactionOutcome,
    pub code: Option<String>,
    pub detail: String,
    pub capability_id: String,
    pub target_ref: String,
    pub before_revision: String,
    pub after_revision: String,
    pub changes: Vec<WorkChange>,
    pub evidence: Vec<String>,
    pub reversible: bool,
    pub recovery: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerHistoryEntry {
    pub seq: u64,
    pub at: String,
    pub environment_id: String,
    pub outcome: SemanticActionOutcome,
    pub action: SemanticActionKind,
    pub target_ref: String,
    pub before_state_version: String,
    pub after_state_version: String,
    pub verified: bool,
    pub effect: Option<String>,
    pub route: Option<String>,
    #[serde(default)]
    pub evidence: Vec<String>,
    pub code: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerHistoryStatus {
    pub available: bool,
    pub enabled: bool,
    pub encrypted: bool,
    pub cipher: String,
    pub key_protection: String,
    pub retention_days: u32,
    pub entry_count: u64,
    pub last_error: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerHistorySetEnabledRequest {
    pub enabled: bool,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerHistoryQuery {
    pub environment_id: String,
    pub before_seq: Option<u64>,
    #[serde(default = "default_computer_history_limit")]
    pub limit: u32,
}

fn default_computer_history_limit() -> u32 {
    50
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerHistoryPage {
    pub entries: Vec<ComputerHistoryEntry>,
    pub next_before_seq: Option<u64>,
    pub has_more: bool,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerHistoryDeleteRequest {
    pub environment_id: String,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SignalKind {
    ContentChanged,
    StateChanged,
    AttentionRequired,
    Conflict,
    ApprovalRequired,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SignalPriority {
    Low,
    Normal,
    High,
    Urgent,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SignalState {
    Pending,
    Claimed,
    Deferred,
    Resolved,
    Expired,
    DeadLetter,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SignalOutcome {
    Handled,
    Ignored,
    Failed,
    Revoked,
    UnknownExternalOutcome,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SignalIngress {
    pub source_id: String,
    pub account_grant_ref: String,
    pub app_id: String,
    pub resource_ref: String,
    pub kind: SignalKind,
    pub source_cursor: String,
    pub dedupe_key: String,
    pub observed_at: String,
    pub available_at: Option<String>,
    pub expires_at: String,
    pub priority_class: SignalPriority,
    pub content_available: bool,
    #[serde(default)]
    pub gap_detected: bool,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SignalAdmissionOutcome {
    Inserted,
    Coalesced,
    Deduplicated,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SignalAdmission {
    pub outcome: SignalAdmissionOutcome,
    pub signal_id: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SignalClaim {
    pub worker_id: String,
    pub lease_id: String,
    pub expires_at: String,
    pub attempt: u32,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SignalItem {
    pub signal_id: String,
    pub source_id: String,
    pub account_grant_ref: String,
    pub app_id: String,
    pub resource_ref: String,
    pub kind: SignalKind,
    pub source_cursor: String,
    pub observed_at: String,
    pub available_at: String,
    pub expires_at: String,
    pub priority_class: SignalPriority,
    pub state: SignalState,
    pub claim: Option<SignalClaim>,
    pub content_available: bool,
    pub gap_detected: bool,
    pub coalesced_count: u32,
    pub last_outcome: Option<SignalOutcome>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SignalCount {
    pub source_id: String,
    pub state: SignalState,
    pub priority_class: SignalPriority,
    pub count: u64,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SignalInboxSummary {
    pub protocol_version: String,
    pub encrypted: bool,
    pub item_count: u64,
    pub ready_count: u64,
    pub gap_count: u64,
    pub counts: Vec<SignalCount>,
    pub pending_refs: Vec<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SignalInboxConsultRequest {
    #[serde(default = "default_signal_ref_limit")]
    pub max_refs: u32,
}

fn default_signal_ref_limit() -> u32 {
    8
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SignalClaimRequest {
    pub worker_id: String,
    #[serde(default = "default_signal_claim_limit")]
    pub max_items: u32,
    #[serde(default = "default_signal_lease_seconds")]
    pub lease_seconds: u32,
}

fn default_signal_claim_limit() -> u32 {
    1
}

fn default_signal_lease_seconds() -> u32 {
    120
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SignalDeferRequest {
    pub signal_id: String,
    pub lease_id: String,
    pub operation_id: String,
    pub available_at: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SignalResolveRequest {
    pub signal_id: String,
    pub lease_id: String,
    pub operation_id: String,
    pub outcome: SignalOutcome,
    pub source_revision: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SignalAccountRevokeRequest {
    pub account_grant_ref: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerDoctor {
    pub supported: bool,
    pub runtime_ready: bool,
    pub package_ready: bool,
    pub docker_cli: bool,
    pub daemon_ready: bool,
    pub image_ready: bool,
    pub provider_kind: String,
    pub isolation_class: String,
    pub available_cpus: Option<u32>,
    pub available_memory_bytes: Option<u64>,
    pub recommended_preset: ComputerResourcePreset,
    pub packages: Vec<ComputerPackageStatus>,
    pub storage: ComputerStorageSummary,
    pub detail: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ComputerPackageState {
    Installed,
    NotInstalled,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerPackageStatus {
    pub package_id: String,
    pub display_name: String,
    pub description: String,
    pub state: ComputerPackageState,
    pub manifest: ComputerPackManifest,
    pub installed_bytes: Option<u64>,
    pub shared_across_projects: bool,
    pub preserves_profile_on_remove: bool,
    pub capabilities: Vec<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerPackManifest {
    pub schema_version: String,
    pub version: String,
    pub channel: String,
    pub ai_frame_version: String,
    pub profile_schema_version: u32,
    pub upgrade_policy: String,
    pub rollback_policy: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerStorageSummary {
    pub package_store_kind: String,
    pub profile_store_kind: String,
    pub project_store_kind: String,
    pub location_selectable: bool,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerEnsureRequest {
    pub request_id: String,
    #[serde(default = "default_coworker_id")]
    pub coworker_id: String,
    pub project_id: String,
    pub project_name: String,
    pub project_path: String,
    #[serde(default)]
    pub resource_preset: ComputerResourcePreset,
}

fn default_coworker_id() -> String {
    "wiii-coworker-neko".to_string()
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerCoworkerRequest {
    #[serde(default = "default_coworker_id")]
    pub coworker_id: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerProjectGrantRequest {
    pub request_id: String,
    #[serde(default = "default_coworker_id")]
    pub coworker_id: String,
    pub project_id: String,
    pub project_name: String,
    pub project_path: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerProjectRevokeRequest {
    pub request_id: String,
    #[serde(default = "default_coworker_id")]
    pub coworker_id: String,
    pub project_id: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerLifecycleRequest {
    pub request_id: String,
    pub environment_id: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerResetRequest {
    pub request_id: String,
    pub environment_id: String,
    pub confirmation: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerRemoveRequest {
    pub request_id: String,
    pub environment_id: String,
    pub confirmation: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerPackageRequest {
    pub request_id: String,
    #[serde(default = "default_coworker_id")]
    pub coworker_id: String,
    pub package_id: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SeatAcquireRequest {
    pub request_id: String,
    pub environment_id: String,
    pub owner_id: String,
    pub user_controlled: bool,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SeatReleaseRequest {
    pub request_id: String,
    pub environment_id: String,
    pub lease_id: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TerminalExecRequest {
    pub request_id: String,
    pub environment_id: String,
    pub command: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TerminalExecResult {
    pub environment_id: String,
    pub exit_code: Option<i32>,
    pub stdout: String,
    pub stderr: String,
    pub truncated: bool,
    pub replayed_without_output: bool,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BrowserNavigateRequest {
    pub request_id: String,
    pub environment_id: String,
    pub url: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerEvent {
    pub event_id: String,
    pub stream_id: String,
    pub seq: u64,
    pub at: String,
    #[serde(rename = "type")]
    pub event_type: String,
    pub environment_id: String,
    pub payload: serde_json::Value,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComputerReplayPage {
    pub stream_id: String,
    pub events: Vec<ComputerEvent>,
    pub next_after_seq: u64,
    pub has_more: bool,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn automatic_resources_are_bounded_by_host_capacity() {
        assert_eq!(
            ComputerResourcePreset::recommend(Some(4), Some(6 * 1024 * 1024 * 1024)),
            ComputerResourcePreset::Compact
        );
        assert_eq!(
            ComputerResourcePreset::recommend(Some(8), Some(16 * 1024 * 1024 * 1024)),
            ComputerResourcePreset::Balanced
        );
        assert_eq!(
            ComputerResourcePreset::recommend(Some(16), Some(32 * 1024 * 1024 * 1024)),
            ComputerResourcePreset::Performance
        );
    }

    #[test]
    fn resource_presets_never_delegate_raw_runtime_flags_to_the_renderer() {
        let compact = ComputerResourcePreset::Compact.resources();
        let performance = ComputerResourcePreset::Performance.resources();
        assert_eq!(compact.cpus, "1.0");
        assert_eq!(compact.memory_bytes, 2 * 1024 * 1024 * 1024);
        assert_eq!(performance.cpus, "4.0");
        assert_eq!(performance.memory_bytes, 8 * 1024 * 1024 * 1024);
    }

    #[test]
    fn semantic_actions_have_a_small_provider_neutral_vocabulary() {
        assert_eq!(SemanticActionKind::Focus.as_str(), "focus");
        assert_eq!(SemanticActionKind::Invoke.as_str(), "invoke");
        assert_eq!(SemanticActionKind::SetText.as_str(), "set_text");
        assert_eq!(SemanticActionKind::PressKey.as_str(), "press_key");
        assert_eq!(SemanticActionKind::InputSequence.as_str(), "input_sequence");
        assert_eq!(default_semantic_node_limit(), 400);
    }

    #[test]
    fn computer_environment_accepts_journal_entries_before_pack_versioning() {
        let environment: ComputerEnvironment = serde_json::from_value(serde_json::json!({
            "environmentId": "computer-1",
            "projectId": "project-1",
            "projectName": "Project",
            "projectPath": "C:\\Project",
            "providerKind": "docker",
            "isolationClass": "container",
            "computerKind": "web",
            "operatingSystem": "Linux",
            "semanticProtocol": "neko-computer.semantic.v1",
            "state": "ready",
            "projectMount": "/workspace/project",
            "attachUrl": null,
            "resources": {
                "cpus": "2.0",
                "memoryBytes": 4294967296_u64,
                "pidsLimit": 1024,
                "sharedMemoryBytes": 1073741824_u64,
                "temporaryStorageBytes": 536870912_u64
            },
            "seat": {
                "seatId": "display-1",
                "state": "available",
                "leaseId": null,
                "ownerId": null,
                "updatedAt": "2026-09-02T00:00:00Z"
            },
            "createdAt": "2026-09-02T00:00:00Z",
            "updatedAt": "2026-09-02T00:00:00Z"
        }))
        .expect("legacy computer environment should remain readable");

        assert_eq!(environment.active_pack_version, None);
        assert!(!environment.pack_update_available);
    }
}
