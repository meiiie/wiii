use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct NewAccountGrant {
    pub grant_id: String,
    pub coworker_id: String,
    pub provider: String,
    pub display_identity: String,
    pub scopes: Vec<String>,
    pub credential_ref: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AccountGrant {
    pub grant_id: String,
    pub coworker_id: String,
    pub provider: String,
    pub display_identity: String,
    pub scopes: Vec<String>,
    pub active: bool,
    pub created_at: String,
    pub revoked_at: Option<String>,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum DeliverableKind {
    File,
    MessageDraft,
    Report,
    ChangeSet,
}

impl DeliverableKind {
    pub(crate) fn as_str(self) -> &'static str {
        match self {
            Self::File => "file",
            Self::MessageDraft => "message_draft",
            Self::Report => "report",
            Self::ChangeSet => "change_set",
        }
    }

    pub(crate) fn parse(value: &str) -> Result<Self, String> {
        match value {
            "file" => Ok(Self::File),
            "message_draft" => Ok(Self::MessageDraft),
            "report" => Ok(Self::Report),
            "change_set" => Ok(Self::ChangeSet),
            _ => Err(format!("unknown deliverable kind: {value}")),
        }
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct NewDeliverable {
    pub deliverable_id: String,
    pub coworker_id: String,
    pub project_id: Option<String>,
    pub kind: DeliverableKind,
    pub title: String,
    pub resource_ref: String,
    pub media_type: Option<String>,
    pub revision: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Deliverable {
    pub deliverable_id: String,
    pub coworker_id: String,
    pub project_id: Option<String>,
    pub kind: DeliverableKind,
    pub title: String,
    pub resource_ref: String,
    pub media_type: Option<String>,
    pub revision: String,
    pub created_at: String,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ActivityOutcome {
    Completed,
    Blocked,
    Failed,
    Unknown,
    HandedOff,
}

impl ActivityOutcome {
    pub(crate) fn as_str(self) -> &'static str {
        match self {
            Self::Completed => "completed",
            Self::Blocked => "blocked",
            Self::Failed => "failed",
            Self::Unknown => "unknown",
            Self::HandedOff => "handed_off",
        }
    }

    pub(crate) fn parse(value: &str) -> Result<Self, String> {
        match value {
            "completed" => Ok(Self::Completed),
            "blocked" => Ok(Self::Blocked),
            "failed" => Ok(Self::Failed),
            "unknown" => Ok(Self::Unknown),
            "handed_off" => Ok(Self::HandedOff),
            _ => Err(format!("unknown activity outcome: {value}")),
        }
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct NewActivity {
    pub activity_id: String,
    pub coworker_id: String,
    pub kind: String,
    pub subject_ref: String,
    pub outcome: ActivityOutcome,
    pub operation_id: Option<String>,
    pub approval_ref: Option<String>,
    pub evidence_refs: Vec<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ActivityEntry {
    pub seq: u64,
    pub activity_id: String,
    pub coworker_id: String,
    pub kind: String,
    pub subject_ref: String,
    pub outcome: ActivityOutcome,
    pub operation_id: Option<String>,
    pub approval_ref: Option<String>,
    pub evidence_refs: Vec<String>,
    pub occurred_at: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ActivityPage {
    pub items: Vec<ActivityEntry>,
    pub next_after_seq: Option<u64>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CoworkerRecordsSnapshot {
    pub coworker_id: String,
    pub account_grants: Vec<AccountGrant>,
    pub deliverables: Vec<Deliverable>,
    pub activity: ActivityPage,
}
