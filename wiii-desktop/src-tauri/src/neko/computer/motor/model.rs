use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

pub const MOTOR_CAPABILITY: &str = "dev.wiii.motor.v1";
pub const MOTOR_PROTOCOL: &str = "wiii-motor.v1";
pub const MOTOR_INTENT_SCHEMA: &str = "wiii-motor-intent.v1";
pub const MOTOR_EVENT_SCHEMA: &str = "wiii-motor-event.v1";

const MAX_ID_BYTES: usize = 128;
const MAX_REF_BYTES: usize = 192;
const MAX_INSTRUCTION_BYTES: usize = 512;
const MAX_POLICY_BYTES: usize = 128;
const MAX_EVIDENCE_ITEMS: usize = 8;
const MAX_EVIDENCE_BYTES: usize = 192;
const MAX_KEYS: usize = 8;

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MotorCapabilityManifest {
    pub protocol: String,
    pub methods: Vec<String>,
    pub intent_schema: String,
    pub event_schema: String,
}

impl MotorCapabilityManifest {
    pub fn v1() -> Self {
        Self {
            protocol: MOTOR_PROTOCOL.to_string(),
            methods: vec![
                "wiii/motor/v1/start".to_string(),
                "wiii/motor/v1/cancel".to_string(),
                "wiii/motor/v1/status".to_string(),
            ],
            intent_schema: MOTOR_INTENT_SCHEMA.to_string(),
            event_schema: MOTOR_EVENT_SCHEMA.to_string(),
        }
    }

    pub fn validate(&self) -> Result<(), String> {
        if self != &Self::v1() {
            return Err("Motor capability manifest does not match dev.wiii.motor.v1".to_string());
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MotorGoalKind {
    Navigate,
    Track,
    Interact,
    Evade,
    Hold,
    Explore,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MotorGoal {
    pub kind: MotorGoalKind,
    pub instruction: String,
}

#[derive(Clone, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MotorTermination {
    GoalReached,
    Blocked,
    Uncertain,
}

#[derive(Clone, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MotorInterrupt {
    HumanTakeover,
    PolicyBoundary,
    SurfaceLost,
    LeaseLost,
    ProjectRevoked,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MotorRisk {
    Low,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct MotorIntent {
    pub schema_version: String,
    pub intent_id: String,
    pub state_version: String,
    pub target_ref: String,
    pub goal: MotorGoal,
    pub horizon_ms: u32,
    pub termination: Vec<MotorTermination>,
    pub interrupt_on: Vec<MotorInterrupt>,
    pub risk: MotorRisk,
}

impl MotorIntent {
    pub fn validate(&self) -> Result<(), String> {
        if self.schema_version != MOTOR_INTENT_SCHEMA {
            return Err("Unsupported MotorIntent schemaVersion".to_string());
        }
        validate_token("intentId", &self.intent_id, MAX_ID_BYTES)?;
        validate_token("stateVersion", &self.state_version, MAX_REF_BYTES)?;
        validate_token("targetRef", &self.target_ref, MAX_REF_BYTES)?;
        validate_text(
            "goal.instruction",
            &self.goal.instruction,
            MAX_INSTRUCTION_BYTES,
        )?;
        reject_embedded_authority(&self.goal.instruction)?;
        if !(100..=10_000).contains(&self.horizon_ms) {
            return Err("MotorIntent horizonMs must be between 100 and 10000".to_string());
        }
        validate_unique_bounded("termination", &self.termination, 1, 8)?;
        validate_unique_bounded("interruptOn", &self.interrupt_on, 1, 8)?;
        for required in [
            MotorInterrupt::HumanTakeover,
            MotorInterrupt::PolicyBoundary,
            MotorInterrupt::SurfaceLost,
        ] {
            if !self.interrupt_on.contains(&required) {
                return Err(format!(
                    "MotorIntent interruptOn must contain {}",
                    serde_json::to_string(&required).unwrap_or_default()
                ));
            }
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct MotorLeaseAuthority {
    pub environment_id: String,
    pub lease_id: String,
    pub project_id: String,
    pub target_ref: String,
    pub expires_at_us: u64,
}

impl MotorLeaseAuthority {
    pub fn validate_for(&self, intent: &MotorIntent, now_us: u64) -> Result<(), String> {
        validate_token("environmentId", &self.environment_id, MAX_REF_BYTES)?;
        validate_token("leaseId", &self.lease_id, MAX_REF_BYTES)?;
        validate_token("projectId", &self.project_id, MAX_REF_BYTES)?;
        validate_token("authority.targetRef", &self.target_ref, MAX_REF_BYTES)?;
        if self.target_ref != intent.target_ref {
            return Err("Motor target is outside the inherited Computer lease".to_string());
        }
        if self.expires_at_us <= now_us {
            return Err("Inherited Computer lease has expired".to_string());
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct MotorFrame {
    pub sequence: u64,
    pub state_version: String,
    pub target_ref: String,
    pub content_digest: String,
    pub width: u32,
    pub height: u32,
    pub capture_started_at_us: u64,
    pub captured_at_us: u64,
}

impl MotorFrame {
    pub fn validate(&self) -> Result<(), String> {
        validate_token("frame.stateVersion", &self.state_version, MAX_REF_BYTES)?;
        validate_token("frame.targetRef", &self.target_ref, MAX_REF_BYTES)?;
        validate_token("frame.contentDigest", &self.content_digest, MAX_REF_BYTES)?;
        if self.sequence == 0 {
            return Err("Motor frame sequence must be positive".to_string());
        }
        if self.width == 0 || self.height == 0 || self.width > 7680 || self.height > 4320 {
            return Err("Motor frame dimensions are outside the supported range".to_string());
        }
        if self.captured_at_us < self.capture_started_at_us {
            return Err("Motor frame capture timestamps are reversed".to_string());
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MotorPointerButton {
    Primary,
    Secondary,
    Middle,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct MotorPointerState {
    pub x_per_mille: u16,
    pub y_per_mille: u16,
    #[serde(default)]
    pub held_buttons: Vec<MotorPointerButton>,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct MotorControlState {
    #[serde(default)]
    pub held_keys: Vec<String>,
    pub pointer: Option<MotorPointerState>,
}

impl MotorControlState {
    pub fn validate(&self, allowed_keys: &BTreeSet<String>) -> Result<(), String> {
        if self.held_keys.len() > MAX_KEYS {
            return Err("Motor action holds too many keys".to_string());
        }
        let mut unique = BTreeSet::new();
        for key in &self.held_keys {
            validate_token("held key", key, 32)?;
            if !allowed_keys.contains(key) {
                return Err(format!("Motor action key is not allowlisted: {key}"));
            }
            if !unique.insert(key) {
                return Err(format!("Motor action repeats held key: {key}"));
            }
        }
        if let Some(pointer) = &self.pointer {
            if pointer.x_per_mille > 1000 || pointer.y_per_mille > 1000 {
                return Err("Motor pointer coordinates must be normalized to 0..1000".to_string());
            }
            if pointer.held_buttons.len() > 3 {
                return Err("Motor action holds too many pointer buttons".to_string());
            }
            let unique = pointer.held_buttons.iter().collect::<BTreeSet<_>>();
            if unique.len() != pointer.held_buttons.len() {
                return Err("Motor action repeats a held pointer button".to_string());
            }
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MotorDecisionKind {
    Continue,
    GoalReached,
    Blocked,
    Uncertain,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct MotorDecision {
    pub frame_sequence: u64,
    pub inference_us: u64,
    pub confidence_per_mille: u16,
    pub kind: MotorDecisionKind,
    pub control: MotorControlState,
    #[serde(default)]
    pub evidence: Vec<String>,
}

impl MotorDecision {
    pub fn validate(&self, allowed_keys: &BTreeSet<String>) -> Result<(), String> {
        if self.inference_us == 0 || self.inference_us > 10_000_000 {
            return Err("Motor inference duration is outside the supported range".to_string());
        }
        if self.confidence_per_mille > 1000 {
            return Err("Motor confidence must be normalized to 0..1000".to_string());
        }
        self.control.validate(allowed_keys)?;
        validate_evidence(&self.evidence)
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MotorCapabilityTier {
    ReactiveCpu,
    VisionAction,
    RemoteByoc,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MotorEventKind {
    Started,
    Progress,
    Terminated,
    Uncertain,
    Blocked,
    Interrupted,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MotorStopReason {
    GoalReached,
    Blocked,
    Uncertain,
    Cancelled,
    HorizonExpired,
    WatchdogExpired,
    HumanTakeover,
    PolicyBoundary,
    SurfaceLost,
    LeaseLost,
    ProjectRevoked,
    ControllerFailed,
    DispatchFailed,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MotorLatencySample {
    pub capture_us: u64,
    pub inference_us: u64,
    pub dispatch_us: u64,
    pub end_to_end_us: u64,
    pub intent_age_us: u64,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MotorPercentiles {
    pub p50_us: u64,
    pub p95_us: u64,
    pub p99_us: u64,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MotorLatencyReport {
    pub capture: MotorPercentiles,
    pub inference: MotorPercentiles,
    pub dispatch: MotorPercentiles,
    pub end_to_end: MotorPercentiles,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MotorRunReport {
    pub intent_id: String,
    pub policy_id: String,
    pub tier: MotorCapabilityTier,
    pub processed_frames: u64,
    pub dropped_frames: u64,
    pub stale_actions: u64,
    pub achieved_hz: f64,
    pub held_input_cleanup_confirmed: bool,
    pub latency: MotorLatencyReport,
    pub stop_reason: Option<MotorStopReason>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct MotorEvent {
    pub schema_version: String,
    pub sequence: u64,
    pub intent_id: String,
    pub kind: MotorEventKind,
    pub at_us: u64,
    pub state_version: Option<String>,
    pub reason: Option<MotorStopReason>,
    pub confidence_per_mille: Option<u16>,
    pub policy_id: String,
    pub tier: MotorCapabilityTier,
    pub replayed: bool,
    #[serde(default)]
    pub evidence: Vec<String>,
    pub report: Option<MotorRunReport>,
}

impl MotorEvent {
    pub fn validate(&self) -> Result<(), String> {
        if self.schema_version != MOTOR_EVENT_SCHEMA {
            return Err("Unsupported MotorEvent schemaVersion".to_string());
        }
        validate_token("event.intentId", &self.intent_id, MAX_ID_BYTES)?;
        validate_token("event.policyId", &self.policy_id, MAX_POLICY_BYTES)?;
        validate_evidence(&self.evidence)?;
        if self.sequence == 0 {
            return Err("Motor event sequence must be positive".to_string());
        }
        if self.confidence_per_mille.is_some_and(|value| value > 1000) {
            return Err("Motor event confidence must be normalized to 0..1000".to_string());
        }
        Ok(())
    }
}

fn validate_token(label: &str, value: &str, max_bytes: usize) -> Result<(), String> {
    if value.is_empty() || value.len() > max_bytes {
        return Err(format!("{label} must contain 1..={max_bytes} bytes"));
    }
    if value
        .chars()
        .any(|ch| ch.is_control() || ch.is_whitespace())
    {
        return Err(format!(
            "{label} must be an opaque token without whitespace"
        ));
    }
    Ok(())
}

fn validate_text(label: &str, value: &str, max_bytes: usize) -> Result<(), String> {
    if value.trim().is_empty() || value.len() > max_bytes {
        return Err(format!("{label} must contain 1..={max_bytes} bytes"));
    }
    if value.chars().any(|ch| ch.is_control() && ch != '\t') {
        return Err(format!("{label} contains control characters"));
    }
    Ok(())
}

fn validate_unique_bounded<T: Ord + Clone>(
    label: &str,
    values: &[T],
    min: usize,
    max: usize,
) -> Result<(), String> {
    if values.len() < min || values.len() > max {
        return Err(format!("{label} must contain {min}..={max} entries"));
    }
    if values.iter().cloned().collect::<BTreeSet<_>>().len() != values.len() {
        return Err(format!("{label} contains duplicate entries"));
    }
    Ok(())
}

fn validate_evidence(values: &[String]) -> Result<(), String> {
    if values.len() > MAX_EVIDENCE_ITEMS {
        return Err("Motor evidence contains too many entries".to_string());
    }
    for value in values {
        validate_text("Motor evidence", value, MAX_EVIDENCE_BYTES)?;
    }
    Ok(())
}

fn reject_embedded_authority(value: &str) -> Result<(), String> {
    let lower = value.to_ascii_lowercase();
    let forbidden = [
        "http://",
        "https://",
        "file://",
        "docker://",
        "leaseid",
        "lease_id",
        "environmentid",
        "environment_id",
        "password=",
        "token=",
        "secret=",
        "api_key",
        "apikey",
        "xpath=",
        "selector=",
        "click(",
        "mouse(",
        "keydown",
        "keyup",
        "powershell",
        "cmd.exe",
        "/bin/",
        "c:/",
        "d:/",
        "e:/",
        " x=",
        " y=",
        " x:",
        " y:",
    ];
    if forbidden.iter().any(|needle| lower.contains(needle)) || value.contains('\\') {
        return Err(
            "Motor goal contains authority, credential, selector or provider data".to_string(),
        );
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn intent() -> MotorIntent {
        MotorIntent {
            schema_version: MOTOR_INTENT_SCHEMA.to_string(),
            intent_id: "intent-1".to_string(),
            state_version: "sha256:frame-1".to_string(),
            target_ref: "surface:canvas-1".to_string(),
            goal: MotorGoal {
                kind: MotorGoalKind::Navigate,
                instruction: "reach the visible exit".to_string(),
            },
            horizon_ms: 1500,
            termination: vec![
                MotorTermination::GoalReached,
                MotorTermination::Blocked,
                MotorTermination::Uncertain,
            ],
            interrupt_on: vec![
                MotorInterrupt::HumanTakeover,
                MotorInterrupt::PolicyBoundary,
                MotorInterrupt::SurfaceLost,
            ],
            risk: MotorRisk::Low,
        }
    }

    #[test]
    fn capability_manifest_is_exact_and_versioned() {
        let manifest = MotorCapabilityManifest::v1();
        manifest.validate().unwrap();
        assert_eq!(manifest.protocol, MOTOR_PROTOCOL);
        assert_eq!(manifest.methods.len(), 3);
    }

    #[test]
    fn intent_rejects_provider_authority_and_unbounded_horizon() {
        let mut request = intent();
        request.goal.instruction = "open docker://provider with token=secret".to_string();
        assert!(request.validate().unwrap_err().contains("authority"));

        let mut request = intent();
        request.horizon_ms = 60_000;
        assert!(request.validate().unwrap_err().contains("horizonMs"));

        let mut request = intent();
        request.goal.instruction = "click(x=120,y=300)".to_string();
        assert!(request.validate().unwrap_err().contains("authority"));
    }

    #[test]
    fn lease_authority_is_internal_and_target_bound() {
        let request = intent();
        let authority = MotorLeaseAuthority {
            environment_id: "environment-1".to_string(),
            lease_id: "lease-1".to_string(),
            project_id: "project-1".to_string(),
            target_ref: "surface:other".to_string(),
            expires_at_us: 20_000,
        };
        assert!(authority
            .validate_for(&request, 10_000)
            .unwrap_err()
            .contains("outside"));
        assert!(!serde_json::to_string(&request).unwrap().contains("lease-1"));
    }

    #[test]
    fn controller_output_is_normalized_and_allowlisted() {
        let allowed = BTreeSet::from(["KeyW".to_string()]);
        let control = MotorControlState {
            held_keys: vec!["KeyW".to_string()],
            pointer: Some(MotorPointerState {
                x_per_mille: 500,
                y_per_mille: 1001,
                held_buttons: vec![],
            }),
        };
        assert!(control.validate(&allowed).is_err());
    }
}
