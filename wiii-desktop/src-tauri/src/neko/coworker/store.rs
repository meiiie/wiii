use super::model::{
    AccountGrant, ActivityEntry, ActivityOutcome, ActivityPage, CoworkerRecordsSnapshot,
    Deliverable, DeliverableKind, NewAccountGrant, NewActivity, NewDeliverable,
};
use chrono::{SecondsFormat, Utc};
use rusqlite::{params, Connection, OptionalExtension};
use std::path::Path;
use std::sync::{Arc, Mutex, MutexGuard};

const MAX_SCOPES: usize = 32;
const MAX_EVIDENCE_REFS: usize = 16;
const MAX_PAGE: u32 = 200;

#[derive(Clone)]
pub struct CoworkerRecords {
    connection: Arc<Mutex<Connection>>,
}

fn now() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Millis, true)
}

fn lock(connection: &Mutex<Connection>) -> MutexGuard<'_, Connection> {
    connection
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

impl CoworkerRecords {
    pub fn open(path: &Path) -> Result<Self, String> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)
                .map_err(|error| format!("create coworker record directory failed: {error}"))?;
        }
        let connection = Connection::open(path)
            .map_err(|error| format!("open coworker records failed: {error}"))?;
        Self::initialize(connection)
    }

    #[cfg(test)]
    pub(crate) fn in_memory() -> Self {
        Self::initialize(Connection::open_in_memory().unwrap()).unwrap()
    }

    fn initialize(connection: Connection) -> Result<Self, String> {
        connection
            .execute_batch(
                "PRAGMA journal_mode=WAL;
                 PRAGMA foreign_keys=ON;
                 PRAGMA busy_timeout=5000;
                 CREATE TABLE IF NOT EXISTS coworker_account_grants (
                   grant_id TEXT PRIMARY KEY,
                   coworker_id TEXT NOT NULL,
                   provider TEXT NOT NULL,
                   display_identity TEXT NOT NULL,
                   scopes_json TEXT NOT NULL,
                   credential_ref TEXT NOT NULL,
                   created_at TEXT NOT NULL,
                   revoked_at TEXT
                 );
                 CREATE INDEX IF NOT EXISTS idx_coworker_account_grants_owner
                   ON coworker_account_grants(coworker_id, created_at DESC);
                 CREATE TABLE IF NOT EXISTS coworker_deliverables (
                   deliverable_id TEXT PRIMARY KEY,
                   coworker_id TEXT NOT NULL,
                   project_id TEXT,
                   kind TEXT NOT NULL,
                   title TEXT NOT NULL,
                   resource_ref TEXT NOT NULL,
                   media_type TEXT,
                   revision TEXT NOT NULL,
                   created_at TEXT NOT NULL
                 );
                 CREATE INDEX IF NOT EXISTS idx_coworker_deliverables_owner
                   ON coworker_deliverables(coworker_id, created_at DESC);
                 CREATE TABLE IF NOT EXISTS coworker_activity (
                   seq INTEGER PRIMARY KEY AUTOINCREMENT,
                   activity_id TEXT NOT NULL UNIQUE,
                   coworker_id TEXT NOT NULL,
                   kind TEXT NOT NULL,
                   subject_ref TEXT NOT NULL,
                   outcome TEXT NOT NULL,
                   operation_id TEXT,
                   approval_ref TEXT,
                   evidence_refs_json TEXT NOT NULL,
                   occurred_at TEXT NOT NULL
                 );
                 CREATE INDEX IF NOT EXISTS idx_coworker_activity_replay
                   ON coworker_activity(coworker_id, seq);",
            )
            .map_err(|error| format!("initialize coworker records failed: {error}"))?;
        Ok(Self {
            connection: Arc::new(Mutex::new(connection)),
        })
    }

    pub fn grant_account(&self, input: NewAccountGrant) -> Result<AccountGrant, String> {
        validate_id(&input.grant_id, "grantId")?;
        validate_id(&input.coworker_id, "coworkerId")?;
        validate_provider(&input.provider)?;
        validate_text(&input.display_identity, "displayIdentity", 256)?;
        validate_credential_ref(&input.credential_ref)?;
        validate_refs(&input.scopes, "scope", MAX_SCOPES)?;
        let encoded_scopes = serde_json::to_string(&input.scopes)
            .map_err(|error| format!("encode account scopes failed: {error}"))?;
        let timestamp = now();
        let connection = lock(&self.connection);
        let inserted = connection
            .execute(
                "INSERT OR IGNORE INTO coworker_account_grants
                 (grant_id, coworker_id, provider, display_identity, scopes_json,
                  credential_ref, created_at, revoked_at)
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, NULL)",
                params![
                    input.grant_id,
                    input.coworker_id,
                    input.provider,
                    input.display_identity,
                    encoded_scopes,
                    input.credential_ref,
                    timestamp
                ],
            )
            .map_err(|error| format!("record AccountGrant failed: {error}"))?;
        let stored = account_grant_by_id(&connection, &input.grant_id)?
            .ok_or_else(|| "AccountGrant insert was not observable".to_string())?;
        if inserted == 0 {
            let credential_matches: bool = connection
                .query_row(
                    "SELECT credential_ref = ?2 FROM coworker_account_grants WHERE grant_id = ?1",
                    params![input.grant_id, input.credential_ref],
                    |row| row.get(0),
                )
                .map_err(|error| format!("verify AccountGrant replay failed: {error}"))?;
            if !credential_matches
                || stored.coworker_id != input.coworker_id
                || stored.provider != input.provider
                || stored.display_identity != input.display_identity
                || stored.scopes != input.scopes
            {
                return Err("account_grant_id_collision".to_string());
            }
        }
        Ok(stored)
    }

    pub fn revoke_account(
        &self,
        coworker_id: &str,
        grant_id: &str,
    ) -> Result<AccountGrant, String> {
        validate_id(coworker_id, "coworkerId")?;
        validate_id(grant_id, "grantId")?;
        let connection = lock(&self.connection);
        connection
            .execute(
                "UPDATE coworker_account_grants SET revoked_at = COALESCE(revoked_at, ?3)
                 WHERE grant_id = ?1 AND coworker_id = ?2",
                params![grant_id, coworker_id, now()],
            )
            .map_err(|error| format!("revoke AccountGrant failed: {error}"))?;
        account_grant_by_id(&connection, grant_id)?
            .filter(|grant| grant.coworker_id == coworker_id)
            .ok_or_else(|| "account_grant_not_found".to_string())
    }

    pub fn account_is_active(&self, coworker_id: &str, grant_id: &str) -> Result<bool, String> {
        validate_id(coworker_id, "coworkerId")?;
        validate_id(grant_id, "grantId")?;
        lock(&self.connection)
            .query_row(
                "SELECT EXISTS(SELECT 1 FROM coworker_account_grants
                 WHERE grant_id = ?1 AND coworker_id = ?2 AND revoked_at IS NULL)",
                params![grant_id, coworker_id],
                |row| row.get(0),
            )
            .map_err(|error| format!("read AccountGrant state failed: {error}"))
    }

    pub(crate) fn active_credential_ref(
        &self,
        coworker_id: &str,
        grant_id: &str,
    ) -> Result<Option<String>, String> {
        validate_id(coworker_id, "coworkerId")?;
        validate_id(grant_id, "grantId")?;
        lock(&self.connection)
            .query_row(
                "SELECT credential_ref FROM coworker_account_grants
                 WHERE grant_id = ?1 AND coworker_id = ?2 AND revoked_at IS NULL",
                params![grant_id, coworker_id],
                |row| row.get(0),
            )
            .optional()
            .map_err(|error| format!("resolve AccountGrant credential boundary failed: {error}"))
    }

    pub fn account_grants(&self, coworker_id: &str) -> Result<Vec<AccountGrant>, String> {
        validate_id(coworker_id, "coworkerId")?;
        let connection = lock(&self.connection);
        let mut statement = connection
            .prepare(
                "SELECT grant_id, coworker_id, provider, display_identity, scopes_json,
                        created_at, revoked_at
                 FROM coworker_account_grants WHERE coworker_id = ?1
                 ORDER BY created_at DESC, grant_id",
            )
            .map_err(|error| format!("prepare AccountGrant list failed: {error}"))?;
        let grants = statement
            .query_map(params![coworker_id], decode_account_grant)
            .map_err(|error| format!("list AccountGrants failed: {error}"))?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|error| format!("decode AccountGrant failed: {error}"))?;
        Ok(grants)
    }

    pub fn record_deliverable(&self, input: NewDeliverable) -> Result<Deliverable, String> {
        validate_id(&input.deliverable_id, "deliverableId")?;
        validate_id(&input.coworker_id, "coworkerId")?;
        if let Some(project_id) = input.project_id.as_deref() {
            validate_id(project_id, "projectId")?;
        }
        validate_text(&input.title, "title", 256)?;
        validate_opaque_ref(&input.resource_ref, "resourceRef")?;
        if let Some(media_type) = input.media_type.as_deref() {
            validate_media_type(media_type)?;
        }
        validate_opaque_ref(&input.revision, "revision")?;
        let connection = lock(&self.connection);
        connection
            .execute(
                "INSERT OR IGNORE INTO coworker_deliverables
                 (deliverable_id, coworker_id, project_id, kind, title, resource_ref,
                  media_type, revision, created_at)
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
                params![
                    input.deliverable_id,
                    input.coworker_id,
                    input.project_id,
                    input.kind.as_str(),
                    input.title,
                    input.resource_ref,
                    input.media_type,
                    input.revision,
                    now()
                ],
            )
            .map_err(|error| format!("record Deliverable failed: {error}"))?;
        let stored = deliverable_by_id(&connection, &input.deliverable_id)?
            .ok_or_else(|| "Deliverable insert was not observable".to_string())?;
        if stored.coworker_id != input.coworker_id
            || stored.project_id != input.project_id
            || stored.kind != input.kind
            || stored.title != input.title
            || stored.resource_ref != input.resource_ref
            || stored.media_type != input.media_type
            || stored.revision != input.revision
        {
            return Err("deliverable_id_collision".to_string());
        }
        Ok(stored)
    }

    pub fn deliverables(&self, coworker_id: &str, limit: u32) -> Result<Vec<Deliverable>, String> {
        validate_id(coworker_id, "coworkerId")?;
        let limit = bounded_limit(limit)?;
        let connection = lock(&self.connection);
        let mut statement = connection
            .prepare(
                "SELECT deliverable_id, coworker_id, project_id, kind, title,
                        resource_ref, media_type, revision, created_at
                 FROM coworker_deliverables WHERE coworker_id = ?1
                 ORDER BY created_at DESC, deliverable_id LIMIT ?2",
            )
            .map_err(|error| format!("prepare Deliverable list failed: {error}"))?;
        let deliverables = statement
            .query_map(params![coworker_id, limit], decode_deliverable)
            .map_err(|error| format!("list Deliverables failed: {error}"))?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|error| format!("decode Deliverable failed: {error}"))?;
        Ok(deliverables)
    }

    pub fn append_activity(&self, input: NewActivity) -> Result<ActivityEntry, String> {
        validate_id(&input.activity_id, "activityId")?;
        validate_id(&input.coworker_id, "coworkerId")?;
        validate_kind(&input.kind)?;
        validate_opaque_ref(&input.subject_ref, "subjectRef")?;
        if let Some(value) = input.operation_id.as_deref() {
            validate_id(value, "operationId")?;
        }
        if let Some(value) = input.approval_ref.as_deref() {
            validate_opaque_ref(value, "approvalRef")?;
        }
        validate_refs(&input.evidence_refs, "evidenceRef", MAX_EVIDENCE_REFS)?;
        let encoded_evidence = serde_json::to_string(&input.evidence_refs)
            .map_err(|error| format!("encode activity evidence failed: {error}"))?;
        let connection = lock(&self.connection);
        connection
            .execute(
                "INSERT OR IGNORE INTO coworker_activity
                 (activity_id, coworker_id, kind, subject_ref, outcome, operation_id,
                  approval_ref, evidence_refs_json, occurred_at)
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
                params![
                    input.activity_id,
                    input.coworker_id,
                    input.kind,
                    input.subject_ref,
                    input.outcome.as_str(),
                    input.operation_id,
                    input.approval_ref,
                    encoded_evidence,
                    now()
                ],
            )
            .map_err(|error| format!("append ActivityLedger failed: {error}"))?;
        let stored = activity_by_id(&connection, &input.activity_id)?
            .ok_or_else(|| "ActivityLedger append was not observable".to_string())?;
        if stored.coworker_id != input.coworker_id
            || stored.kind != input.kind
            || stored.subject_ref != input.subject_ref
            || stored.outcome != input.outcome
            || stored.operation_id != input.operation_id
            || stored.approval_ref != input.approval_ref
            || stored.evidence_refs != input.evidence_refs
        {
            return Err("activity_id_collision".to_string());
        }
        Ok(stored)
    }

    pub fn activity_page(
        &self,
        coworker_id: &str,
        after_seq: u64,
        limit: u32,
    ) -> Result<ActivityPage, String> {
        validate_id(coworker_id, "coworkerId")?;
        let limit = bounded_limit(limit)?;
        let connection = lock(&self.connection);
        let mut statement = connection
            .prepare(
                "SELECT seq, activity_id, coworker_id, kind, subject_ref, outcome,
                        operation_id, approval_ref, evidence_refs_json, occurred_at
                 FROM coworker_activity
                 WHERE coworker_id = ?1 AND seq > ?2 ORDER BY seq LIMIT ?3",
            )
            .map_err(|error| format!("prepare ActivityLedger replay failed: {error}"))?;
        let after_seq = i64::try_from(after_seq)
            .map_err(|_| "afterSeq exceeds the ActivityLedger range".to_string())?;
        let items = statement
            .query_map(params![coworker_id, after_seq, limit + 1], decode_activity)
            .map_err(|error| format!("read ActivityLedger failed: {error}"))?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|error| format!("decode ActivityLedger failed: {error}"))?;
        let mut items = items;
        let next_after_seq = if items.len() > limit as usize {
            items.truncate(limit as usize);
            items.last().map(|entry| entry.seq)
        } else {
            None
        };
        Ok(ActivityPage {
            items,
            next_after_seq,
        })
    }

    pub fn snapshot(&self, coworker_id: &str) -> Result<CoworkerRecordsSnapshot, String> {
        Ok(CoworkerRecordsSnapshot {
            coworker_id: coworker_id.to_string(),
            account_grants: self.account_grants(coworker_id)?,
            deliverables: self.deliverables(coworker_id, 50)?,
            activity: self.activity_page(coworker_id, 0, 100)?,
        })
    }
}

fn account_grant_by_id(
    connection: &Connection,
    grant_id: &str,
) -> Result<Option<AccountGrant>, String> {
    connection
        .query_row(
            "SELECT grant_id, coworker_id, provider, display_identity, scopes_json,
                    created_at, revoked_at
             FROM coworker_account_grants WHERE grant_id = ?1",
            params![grant_id],
            decode_account_grant,
        )
        .optional()
        .map_err(|error| format!("read AccountGrant failed: {error}"))
}

fn decode_account_grant(row: &rusqlite::Row<'_>) -> rusqlite::Result<AccountGrant> {
    let scopes_json: String = row.get(4)?;
    let scopes = serde_json::from_str(&scopes_json).map_err(|error| {
        rusqlite::Error::FromSqlConversionFailure(
            scopes_json.len(),
            rusqlite::types::Type::Text,
            Box::new(error),
        )
    })?;
    let revoked_at: Option<String> = row.get(6)?;
    Ok(AccountGrant {
        grant_id: row.get(0)?,
        coworker_id: row.get(1)?,
        provider: row.get(2)?,
        display_identity: row.get(3)?,
        scopes,
        active: revoked_at.is_none(),
        created_at: row.get(5)?,
        revoked_at,
    })
}

fn deliverable_by_id(
    connection: &Connection,
    deliverable_id: &str,
) -> Result<Option<Deliverable>, String> {
    connection
        .query_row(
            "SELECT deliverable_id, coworker_id, project_id, kind, title,
                    resource_ref, media_type, revision, created_at
             FROM coworker_deliverables WHERE deliverable_id = ?1",
            params![deliverable_id],
            decode_deliverable,
        )
        .optional()
        .map_err(|error| format!("read Deliverable failed: {error}"))
}

fn decode_deliverable(row: &rusqlite::Row<'_>) -> rusqlite::Result<Deliverable> {
    let kind: String = row.get(3)?;
    let kind = DeliverableKind::parse(&kind).map_err(|error| {
        rusqlite::Error::FromSqlConversionFailure(
            kind.len(),
            rusqlite::types::Type::Text,
            error.into(),
        )
    })?;
    Ok(Deliverable {
        deliverable_id: row.get(0)?,
        coworker_id: row.get(1)?,
        project_id: row.get(2)?,
        kind,
        title: row.get(4)?,
        resource_ref: row.get(5)?,
        media_type: row.get(6)?,
        revision: row.get(7)?,
        created_at: row.get(8)?,
    })
}

fn activity_by_id(
    connection: &Connection,
    activity_id: &str,
) -> Result<Option<ActivityEntry>, String> {
    connection
        .query_row(
            "SELECT seq, activity_id, coworker_id, kind, subject_ref, outcome,
                    operation_id, approval_ref, evidence_refs_json, occurred_at
             FROM coworker_activity WHERE activity_id = ?1",
            params![activity_id],
            decode_activity,
        )
        .optional()
        .map_err(|error| format!("read ActivityLedger entry failed: {error}"))
}

fn decode_activity(row: &rusqlite::Row<'_>) -> rusqlite::Result<ActivityEntry> {
    let outcome: String = row.get(5)?;
    let outcome = ActivityOutcome::parse(&outcome).map_err(|error| {
        rusqlite::Error::FromSqlConversionFailure(
            outcome.len(),
            rusqlite::types::Type::Text,
            error.into(),
        )
    })?;
    let evidence_json: String = row.get(8)?;
    let evidence_refs = serde_json::from_str(&evidence_json).map_err(|error| {
        rusqlite::Error::FromSqlConversionFailure(
            evidence_json.len(),
            rusqlite::types::Type::Text,
            Box::new(error),
        )
    })?;
    Ok(ActivityEntry {
        seq: u64::try_from(row.get::<_, i64>(0)?).map_err(|error| {
            rusqlite::Error::FromSqlConversionFailure(
                0,
                rusqlite::types::Type::Integer,
                Box::new(error),
            )
        })?,
        activity_id: row.get(1)?,
        coworker_id: row.get(2)?,
        kind: row.get(3)?,
        subject_ref: row.get(4)?,
        outcome,
        operation_id: row.get(6)?,
        approval_ref: row.get(7)?,
        evidence_refs,
        occurred_at: row.get(9)?,
    })
}

fn bounded_limit(limit: u32) -> Result<u32, String> {
    if (1..=MAX_PAGE).contains(&limit) {
        Ok(limit)
    } else {
        Err(format!("limit must be between 1 and {MAX_PAGE}"))
    }
}

fn validate_id(value: &str, field: &str) -> Result<(), String> {
    if value.is_empty()
        || value.len() > 128
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_' | b':' | b'.'))
    {
        Err(format!("{field} is invalid"))
    } else {
        Ok(())
    }
}

fn validate_provider(value: &str) -> Result<(), String> {
    if value.is_empty()
        || value.len() > 64
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || byte == b'-')
    {
        Err("provider is invalid".to_string())
    } else {
        Ok(())
    }
}

fn validate_kind(value: &str) -> Result<(), String> {
    validate_provider(value).map_err(|_| "activity kind is invalid".to_string())
}

fn validate_text(value: &str, field: &str, max: usize) -> Result<(), String> {
    if value.trim().is_empty() || value.len() > max || value.chars().any(char::is_control) {
        Err(format!("{field} is invalid"))
    } else {
        Ok(())
    }
}

fn validate_credential_ref(value: &str) -> Result<(), String> {
    validate_opaque_ref(value, "credentialRef")?;
    let scheme = value.split(':').next().unwrap_or_default();
    if matches!(
        scheme,
        "keyring" | "oauth" | "computer-profile" | "managed-connector"
    ) {
        Ok(())
    } else {
        Err("credentialRef boundary is unsupported".to_string())
    }
}

fn validate_refs(values: &[String], field: &str, max_items: usize) -> Result<(), String> {
    if values.is_empty() || values.len() > max_items {
        return Err(format!("{field} list is invalid"));
    }
    for value in values {
        validate_opaque_ref(value, field)?;
    }
    Ok(())
}

fn validate_opaque_ref(value: &str, field: &str) -> Result<(), String> {
    if value.is_empty()
        || value.len() > 512
        || value.chars().any(char::is_whitespace)
        || value.contains("//")
        || value.contains('\\')
        || value.contains('?')
        || value.contains('=')
        || value.contains("-----BEGIN")
    {
        Err(format!("{field} must be an opaque reference"))
    } else {
        Ok(())
    }
}

fn validate_media_type(value: &str) -> Result<(), String> {
    if value.len() > 128
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'/' | b'.' | b'+' | b'-'))
    {
        Err("mediaType is invalid".to_string())
    } else {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn account() -> NewAccountGrant {
        NewAccountGrant {
            grant_id: "grant-mail-neko".to_string(),
            coworker_id: "wiii-coworker-neko".to_string(),
            provider: "gmail".to_string(),
            display_identity: "Neko work mailbox".to_string(),
            scopes: vec!["gmail.readonly".to_string()],
            credential_ref: "computer-profile:neko:gmail".to_string(),
        }
    }

    #[test]
    fn account_grant_is_idempotent_and_revocable_without_exposing_credentials() {
        let records = CoworkerRecords::in_memory();
        let granted = records.grant_account(account()).unwrap();
        assert!(granted.active);
        assert_eq!(records.grant_account(account()).unwrap(), granted);
        assert_eq!(
            records
                .active_credential_ref("wiii-coworker-neko", "grant-mail-neko")
                .unwrap()
                .as_deref(),
            Some("computer-profile:neko:gmail")
        );
        let public_json = serde_json::to_string(&granted).unwrap();
        assert!(!public_json.contains("computer-profile"));

        let revoked = records
            .revoke_account("wiii-coworker-neko", "grant-mail-neko")
            .unwrap();
        assert!(!revoked.active);
        assert!(!records
            .account_is_active("wiii-coworker-neko", "grant-mail-neko")
            .unwrap());
        assert!(records
            .active_credential_ref("wiii-coworker-neko", "grant-mail-neko")
            .unwrap()
            .is_none());
    }

    #[test]
    fn id_collision_fails_closed() {
        let records = CoworkerRecords::in_memory();
        records.grant_account(account()).unwrap();
        let mut collision = account();
        collision.provider = "outlook".to_string();
        assert_eq!(
            records.grant_account(collision).unwrap_err(),
            "account_grant_id_collision"
        );
    }

    #[test]
    fn deliverables_and_activity_are_bounded_source_references() {
        let records = CoworkerRecords::in_memory();
        let deliverable = records
            .record_deliverable(NewDeliverable {
                deliverable_id: "deliverable-quarterly-report".to_string(),
                coworker_id: "wiii-coworker-neko".to_string(),
                project_id: Some("project-wiii".to_string()),
                kind: DeliverableKind::Report,
                title: "Quarterly report".to_string(),
                resource_ref: "project:file:reports/q3.pdf".to_string(),
                media_type: Some("application/pdf".to_string()),
                revision: "sha256:abc123".to_string(),
            })
            .unwrap();
        assert_eq!(
            records
                .record_deliverable(NewDeliverable {
                    deliverable_id: deliverable.deliverable_id.clone(),
                    coworker_id: deliverable.coworker_id.clone(),
                    project_id: deliverable.project_id.clone(),
                    kind: deliverable.kind,
                    title: deliverable.title.clone(),
                    resource_ref: deliverable.resource_ref.clone(),
                    media_type: deliverable.media_type.clone(),
                    revision: deliverable.revision.clone(),
                })
                .unwrap(),
            deliverable
        );

        let activity = records
            .append_activity(NewActivity {
                activity_id: "activity-report-created".to_string(),
                coworker_id: "wiii-coworker-neko".to_string(),
                kind: "deliverable-created".to_string(),
                subject_ref: "deliverable:quarterly-report".to_string(),
                outcome: ActivityOutcome::Completed,
                operation_id: Some("op-report-created".to_string()),
                approval_ref: Some("approval:project-write".to_string()),
                evidence_refs: vec!["evidence:file-revision".to_string()],
            })
            .unwrap();
        assert_eq!(activity.seq, 1);
        let snapshot = records.snapshot("wiii-coworker-neko").unwrap();
        assert_eq!(snapshot.deliverables.len(), 1);
        assert_eq!(snapshot.activity.items, vec![activity]);
    }

    #[test]
    fn raw_urls_paths_and_secret_shaped_refs_are_rejected() {
        let records = CoworkerRecords::in_memory();
        for credential_ref in [
            "https://accounts.example/token",
            "C:\\Users\\Neko\\token.json",
            "oauth:access_token=secret",
            "plain-secret",
        ] {
            let mut input = account();
            input.grant_id = format!("grant-{}", credential_ref.len());
            input.credential_ref = credential_ref.to_string();
            assert!(records.grant_account(input).is_err());
        }
    }

    #[test]
    fn activity_replay_has_an_opaque_bounded_cursor() {
        let records = CoworkerRecords::in_memory();
        for index in 0..3 {
            records
                .append_activity(NewActivity {
                    activity_id: format!("activity-{index}"),
                    coworker_id: "wiii-coworker-neko".to_string(),
                    kind: "test-event".to_string(),
                    subject_ref: format!("subject:{index}"),
                    outcome: ActivityOutcome::Completed,
                    operation_id: None,
                    approval_ref: None,
                    evidence_refs: vec![format!("evidence:{index}")],
                })
                .unwrap();
        }
        let first = records.activity_page("wiii-coworker-neko", 0, 2).unwrap();
        assert_eq!(first.items.len(), 2);
        let second = records
            .activity_page("wiii-coworker-neko", first.next_after_seq.unwrap(), 2)
            .unwrap();
        assert_eq!(second.items.len(), 1);
        assert!(second.next_after_seq.is_none());
    }
}
