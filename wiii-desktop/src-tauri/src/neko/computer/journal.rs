use super::model::{
    ComputerEnvironment, ComputerEvent, ComputerProjectGrant, ComputerReplayPage,
    ComputerResources, ComputerState, DisplaySeat, SeatState,
};
use chrono::{SecondsFormat, Utc};
use rusqlite::{params, Connection, OptionalExtension, TransactionBehavior};
use serde_json::Value;
use std::path::Path;
use std::sync::{Arc, Mutex, MutexGuard};
use uuid::Uuid;

const MAX_EVENT_PAYLOAD_BYTES: usize = 4 * 1024;
const MAX_REPLAY_LIMIT: u32 = 500;

#[derive(Clone)]
pub(crate) struct ComputerJournal {
    connection: Arc<Mutex<Connection>>,
}

#[derive(Debug, PartialEq)]
pub(crate) enum RequestDecision {
    Execute,
    Replay(Value),
    RecordedError(String),
    UnknownOutcome,
}

type StoredRequest = (String, String, String, Option<String>, Option<String>);

#[derive(Clone, Debug, Eq, PartialEq)]
pub(crate) struct CoworkerBinding {
    pub coworker_id: String,
    pub environment_id: String,
    pub active_project_id: Option<String>,
    pub active_project_name: Option<String>,
    pub active_project_path: Option<String>,
}

pub(crate) struct CoworkerProjectActivation<'a> {
    pub coworker_id: &'a str,
    pub environment_id: &'a str,
    pub project_id: &'a str,
    pub project_name: &'a str,
    pub project_path: &'a str,
    pub state: ComputerState,
    pub resources: &'a ComputerResources,
    pub event_type: &'a str,
}

fn now() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Millis, true)
}

fn lock(connection: &Mutex<Connection>) -> MutexGuard<'_, Connection> {
    connection
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

fn ensure_column(
    connection: &Connection,
    table: &str,
    column: &str,
    declaration: &str,
) -> Result<(), String> {
    let mut statement = connection
        .prepare(&format!("PRAGMA table_info({table})"))
        .map_err(|error| format!("inspect Computer schema failed: {error}"))?;
    let columns = statement
        .query_map([], |row| row.get::<_, String>(1))
        .map_err(|error| format!("read Computer schema failed: {error}"))?
        .collect::<Result<Vec<_>, _>>()
        .map_err(|error| format!("decode Computer schema failed: {error}"))?;
    if !columns.iter().any(|value| value == column) {
        connection
            .execute_batch(&format!(
                "ALTER TABLE {table} ADD COLUMN {column} {declaration}"
            ))
            .map_err(|error| format!("migrate Computer schema failed: {error}"))?;
    }
    Ok(())
}

impl ComputerJournal {
    pub(crate) fn open(path: &Path) -> Result<Self, String> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)
                .map_err(|error| format!("create computer journal directory failed: {error}"))?;
        }
        let connection = Connection::open(path)
            .map_err(|error| format!("open computer journal failed: {error}"))?;
        connection
            .execute_batch(
                "PRAGMA journal_mode=WAL;
                 PRAGMA foreign_keys=ON;
                 PRAGMA busy_timeout=5000;
                 CREATE TABLE IF NOT EXISTS computer_environments (
                   environment_id TEXT PRIMARY KEY,
                   project_name TEXT NOT NULL,
                   project_path TEXT NOT NULL UNIQUE,
                   state TEXT NOT NULL,
                   resources_json TEXT NOT NULL,
                   created_at TEXT NOT NULL,
                   updated_at TEXT NOT NULL
                 );
                 CREATE TABLE IF NOT EXISTS computer_seats (
                   environment_id TEXT PRIMARY KEY
                     REFERENCES computer_environments(environment_id) ON DELETE CASCADE,
                   seat_id TEXT NOT NULL UNIQUE,
                   state TEXT NOT NULL,
                   lease_id TEXT,
                   owner_id TEXT,
                   updated_at TEXT NOT NULL
                 );
                 CREATE TABLE IF NOT EXISTS computer_coworker_bindings (
                   coworker_id TEXT PRIMARY KEY,
                   environment_id TEXT NOT NULL UNIQUE
                     REFERENCES computer_environments(environment_id) ON DELETE CASCADE,
                   active_project_name TEXT,
                   active_project_id TEXT,
                   active_project_path TEXT,
                   created_at TEXT NOT NULL,
                   updated_at TEXT NOT NULL
                 );
                 CREATE TABLE IF NOT EXISTS computer_project_grants (
                   coworker_id TEXT NOT NULL,
                   project_id TEXT,
                   project_name TEXT NOT NULL,
                   project_path TEXT NOT NULL,
                   access_mode TEXT NOT NULL CHECK(access_mode = 'read_write'),
                   created_at TEXT NOT NULL,
                   updated_at TEXT NOT NULL,
                   PRIMARY KEY(coworker_id, project_path)
                 );
                 CREATE INDEX IF NOT EXISTS idx_computer_project_grants_coworker
                   ON computer_project_grants(coworker_id, updated_at DESC);
                 CREATE TABLE IF NOT EXISTS computer_requests (
                   request_id TEXT PRIMARY KEY,
                   method TEXT NOT NULL,
                   target_id TEXT NOT NULL,
                   phase TEXT NOT NULL,
                   result_json TEXT,
                   error_code TEXT,
                   created_at TEXT NOT NULL,
                   updated_at TEXT NOT NULL
                 );
                 CREATE TABLE IF NOT EXISTS computer_events (
                   event_id TEXT PRIMARY KEY,
                   stream_id TEXT NOT NULL,
                   seq INTEGER NOT NULL CHECK(seq > 0),
                   at TEXT NOT NULL,
                   event_type TEXT NOT NULL,
                   environment_id TEXT NOT NULL
                     REFERENCES computer_environments(environment_id) ON DELETE CASCADE,
                   payload_json TEXT NOT NULL,
                   UNIQUE(stream_id, seq)
                 );
                 CREATE INDEX IF NOT EXISTS idx_computer_events_replay
                   ON computer_events(stream_id, seq);",
            )
            .map_err(|error| format!("initialize computer journal failed: {error}"))?;
        ensure_column(
            &connection,
            "computer_coworker_bindings",
            "active_project_id",
            "TEXT",
        )?;
        ensure_column(&connection, "computer_project_grants", "project_id", "TEXT")?;
        connection
            .execute_batch(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_computer_project_grants_identity
                   ON computer_project_grants(coworker_id, project_id);",
            )
            .map_err(|error| format!("index Computer Project identity failed: {error}"))?;
        let journal = Self {
            connection: Arc::new(Mutex::new(connection)),
        };
        journal.recover_incomplete()?;
        Ok(journal)
    }

    #[cfg(test)]
    pub(super) fn in_memory() -> Self {
        let connection = Connection::open_in_memory().unwrap();
        connection
            .execute_batch(
                "PRAGMA foreign_keys=ON;
                 CREATE TABLE computer_environments (
                   environment_id TEXT PRIMARY KEY,
                   project_name TEXT NOT NULL,
                   project_path TEXT NOT NULL UNIQUE,
                   state TEXT NOT NULL,
                   resources_json TEXT NOT NULL,
                   created_at TEXT NOT NULL,
                   updated_at TEXT NOT NULL
                 );
                 CREATE TABLE computer_seats (
                   environment_id TEXT PRIMARY KEY REFERENCES computer_environments(environment_id) ON DELETE CASCADE,
                   seat_id TEXT NOT NULL UNIQUE,
                   state TEXT NOT NULL,
                   lease_id TEXT,
                   owner_id TEXT,
                   updated_at TEXT NOT NULL
                 );
                 CREATE TABLE computer_coworker_bindings (
                   coworker_id TEXT PRIMARY KEY,
                   environment_id TEXT NOT NULL UNIQUE REFERENCES computer_environments(environment_id) ON DELETE CASCADE,
                   active_project_name TEXT,
                   active_project_id TEXT,
                   active_project_path TEXT,
                   created_at TEXT NOT NULL,
                   updated_at TEXT NOT NULL
                 );
                 CREATE TABLE computer_project_grants (
                   coworker_id TEXT NOT NULL,
                   project_id TEXT,
                   project_name TEXT NOT NULL,
                   project_path TEXT NOT NULL,
                   access_mode TEXT NOT NULL CHECK(access_mode = 'read_write'),
                   created_at TEXT NOT NULL,
                   updated_at TEXT NOT NULL,
                   PRIMARY KEY(coworker_id, project_path)
                 );
                 CREATE UNIQUE INDEX idx_computer_project_grants_identity
                   ON computer_project_grants(coworker_id, project_id);
                 CREATE TABLE computer_requests (
                   request_id TEXT PRIMARY KEY,
                   method TEXT NOT NULL,
                   target_id TEXT NOT NULL,
                   phase TEXT NOT NULL,
                   result_json TEXT,
                   error_code TEXT,
                   created_at TEXT NOT NULL,
                   updated_at TEXT NOT NULL
                 );
                 CREATE TABLE computer_events (
                   event_id TEXT PRIMARY KEY,
                   stream_id TEXT NOT NULL,
                   seq INTEGER NOT NULL CHECK(seq > 0),
                   at TEXT NOT NULL,
                   event_type TEXT NOT NULL,
                   environment_id TEXT NOT NULL REFERENCES computer_environments(environment_id) ON DELETE CASCADE,
                   payload_json TEXT NOT NULL,
                   UNIQUE(stream_id, seq)
                 );",
            )
            .unwrap();
        Self {
            connection: Arc::new(Mutex::new(connection)),
        }
    }

    pub(crate) fn begin_request(
        &self,
        request_id: &str,
        method: &str,
        target_id: &str,
    ) -> Result<RequestDecision, String> {
        validate_identifier(request_id, "request ID")?;
        let connection = lock(&self.connection);
        let existing: Option<StoredRequest> = connection
            .query_row(
                "SELECT method, target_id, phase, result_json, error_code
                   FROM computer_requests WHERE request_id = ?1",
                params![request_id],
                |row| {
                    Ok((
                        row.get(0)?,
                        row.get(1)?,
                        row.get(2)?,
                        row.get(3)?,
                        row.get(4)?,
                    ))
                },
            )
            .optional()
            .map_err(|error| format!("read computer request failed: {error}"))?;
        if let Some(stored) = existing {
            return request_decision(stored, method, target_id);
        }
        let timestamp = now();
        connection
            .execute(
                "INSERT INTO computer_requests
                 (request_id, method, target_id, phase, created_at, updated_at)
                 VALUES (?1, ?2, ?3, 'accepted', ?4, ?4)",
                params![request_id, method, target_id, timestamp],
            )
            .map_err(|error| format!("record computer request failed: {error}"))?;
        Ok(RequestDecision::Execute)
    }

    pub(crate) fn existing_request_decision(
        &self,
        request_id: &str,
        method: &str,
        target_id: &str,
    ) -> Result<Option<RequestDecision>, String> {
        validate_identifier(request_id, "request ID")?;
        let connection = lock(&self.connection);
        let existing: Option<StoredRequest> = connection
            .query_row(
                "SELECT method, target_id, phase, result_json, error_code
                   FROM computer_requests WHERE request_id = ?1",
                params![request_id],
                |row| {
                    Ok((
                        row.get(0)?,
                        row.get(1)?,
                        row.get(2)?,
                        row.get(3)?,
                        row.get(4)?,
                    ))
                },
            )
            .optional()
            .map_err(|error| format!("read computer request failed: {error}"))?;
        existing
            .map(|stored| request_decision(stored, method, target_id))
            .transpose()
    }

    pub(crate) fn mark_side_effect_started(&self, request_id: &str) -> Result<(), String> {
        let changed = lock(&self.connection)
            .execute(
                "UPDATE computer_requests SET phase = 'side_effect_started', updated_at = ?2
                 WHERE request_id = ?1 AND phase = 'accepted'",
                params![request_id, now()],
            )
            .map_err(|error| format!("advance computer request failed: {error}"))?;
        if changed != 1 {
            return Err("Computer request is not eligible for its side effect".to_string());
        }
        Ok(())
    }

    pub(crate) fn complete_request(&self, request_id: &str, result: &Value) -> Result<(), String> {
        let encoded = serde_json::to_string(result)
            .map_err(|error| format!("encode computer request result failed: {error}"))?;
        let changed = lock(&self.connection)
            .execute(
                "UPDATE computer_requests
                    SET phase = 'completed', result_json = ?2, error_code = NULL, updated_at = ?3
                  WHERE request_id = ?1 AND phase IN ('accepted', 'side_effect_started')",
                params![request_id, encoded, now()],
            )
            .map_err(|error| format!("complete computer request failed: {error}"))?;
        if changed != 1 {
            return Err("Computer request could not be completed atomically".to_string());
        }
        Ok(())
    }

    pub(crate) fn fail_request(&self, request_id: &str, code: &str) -> Result<(), String> {
        let changed = lock(&self.connection)
            .execute(
                "UPDATE computer_requests
                    SET phase = 'failed', error_code = ?2, updated_at = ?3
                  WHERE request_id = ?1 AND phase IN ('accepted', 'side_effect_started')",
                params![request_id, code, now()],
            )
            .map_err(|error| format!("fail computer request failed: {error}"))?;
        if changed != 1 {
            return Err("Computer request could not be failed atomically".to_string());
        }
        Ok(())
    }

    pub(crate) fn environment_by_project_path(
        &self,
        project_path: &str,
    ) -> Result<Option<String>, String> {
        lock(&self.connection)
            .query_row(
                "SELECT environment_id FROM computer_environments WHERE project_path = ?1",
                params![project_path],
                |row| row.get(0),
            )
            .optional()
            .map_err(|error| format!("find legacy computer environment failed: {error}"))
    }

    pub(crate) fn adopt_legacy_coworker(&self, coworker_id: &str) -> Result<(), String> {
        validate_identifier(coworker_id, "coworker")?;
        let mut connection = lock(&self.connection);
        let tx = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(|error| format!("begin legacy Computer adoption failed: {error}"))?;
        let already_bound: bool = tx
            .query_row(
                "SELECT EXISTS(
                   SELECT 1 FROM computer_coworker_bindings WHERE coworker_id = ?1
                 )",
                params![coworker_id],
                |row| row.get(0),
            )
            .map_err(|error| format!("check legacy Computer adoption failed: {error}"))?;
        if already_bound {
            tx.commit().map_err(|error| {
                format!("finish legacy Computer adoption check failed: {error}")
            })?;
            return Ok(());
        }
        let latest: Option<(String, String, String)> = tx
            .query_row(
                "SELECT environment_id, project_name, project_path
                   FROM computer_environments
                  ORDER BY updated_at DESC, created_at DESC, rowid DESC
                  LIMIT 1",
                [],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
            )
            .optional()
            .map_err(|error| format!("read legacy Computer environments failed: {error}"))?;
        let Some((environment_id, project_name, project_path)) = latest else {
            tx.commit()
                .map_err(|error| format!("finish empty legacy adoption failed: {error}"))?;
            return Ok(());
        };
        let timestamp = now();
        tx.execute(
            "INSERT INTO computer_project_grants
               (coworker_id, project_name, project_path, access_mode, created_at, updated_at)
             SELECT ?1, project_name, project_path, 'read_write', ?2, ?2
               FROM computer_environments
              WHERE 1
             ON CONFLICT(coworker_id, project_path) DO UPDATE SET
               project_name = excluded.project_name,
               access_mode = excluded.access_mode,
               updated_at = excluded.updated_at",
            params![coworker_id, timestamp],
        )
        .map_err(|error| format!("migrate legacy Computer project grants failed: {error}"))?;
        tx.execute(
            "INSERT INTO computer_coworker_bindings
               (coworker_id, environment_id, active_project_name, active_project_path, created_at, updated_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?5)",
            params![
                coworker_id,
                environment_id,
                project_name,
                project_path,
                timestamp
            ],
        )
        .map_err(|error| format!("adopt legacy Computer workstation failed: {error}"))?;
        append_event_tx(
            &tx,
            &environment_id,
            "computer.coworker_adopted",
            serde_json::json!({
                "coworkerId": coworker_id,
                "projectName": project_name,
                "projectPath": project_path
            }),
        )?;
        tx.commit()
            .map_err(|error| format!("commit legacy Computer adoption failed: {error}"))
    }

    pub(crate) fn coworker_binding(
        &self,
        coworker_id: &str,
    ) -> Result<Option<CoworkerBinding>, String> {
        validate_identifier(coworker_id, "coworker")?;
        lock(&self.connection)
            .query_row(
                "SELECT coworker_id, environment_id, active_project_id, active_project_name, active_project_path
                   FROM computer_coworker_bindings WHERE coworker_id = ?1",
                params![coworker_id],
                |row| {
                    Ok(CoworkerBinding {
                        coworker_id: row.get(0)?,
                        environment_id: row.get(1)?,
                        active_project_id: row.get(2)?,
                        active_project_name: row.get(3)?,
                        active_project_path: row.get(4)?,
                    })
                },
            )
            .optional()
            .map_err(|error| format!("read coworker computer binding failed: {error}"))
    }

    pub(crate) fn coworker_binding_for_environment(
        &self,
        environment_id: &str,
    ) -> Result<Option<CoworkerBinding>, String> {
        lock(&self.connection)
            .query_row(
                "SELECT coworker_id, environment_id, active_project_id, active_project_name, active_project_path
                   FROM computer_coworker_bindings WHERE environment_id = ?1",
                params![environment_id],
                |row| {
                    Ok(CoworkerBinding {
                        coworker_id: row.get(0)?,
                        environment_id: row.get(1)?,
                        active_project_id: row.get(2)?,
                        active_project_name: row.get(3)?,
                        active_project_path: row.get(4)?,
                    })
                },
            )
            .optional()
            .map_err(|error| format!("read Computer coworker owner failed: {error}"))
    }

    pub(crate) fn project_grants(
        &self,
        coworker_id: &str,
    ) -> Result<Vec<ComputerProjectGrant>, String> {
        validate_identifier(coworker_id, "coworker")?;
        let connection = lock(&self.connection);
        let mut statement = connection
            .prepare(
                "SELECT coworker_id, project_id, project_name, project_path, access_mode, created_at, updated_at
                   FROM computer_project_grants
                  WHERE coworker_id = ?1
                  ORDER BY updated_at DESC, project_name COLLATE NOCASE ASC",
            )
            .map_err(|error| format!("prepare coworker project grants failed: {error}"))?;
        let rows = statement
            .query_map(params![coworker_id], |row| {
                Ok(ComputerProjectGrant {
                    coworker_id: row.get(0)?,
                    project_id: row.get(1)?,
                    project_name: row.get(2)?,
                    project_path: row.get(3)?,
                    access_mode: row.get(4)?,
                    created_at: row.get(5)?,
                    updated_at: row.get(6)?,
                })
            })
            .map_err(|error| format!("read coworker project grants failed: {error}"))?;
        rows.collect::<Result<Vec<_>, _>>()
            .map_err(|error| format!("decode coworker project grant failed: {error}"))
    }

    pub(crate) fn has_project_grant(
        &self,
        coworker_id: &str,
        project_id: &str,
    ) -> Result<bool, String> {
        validate_identifier(coworker_id, "coworker")?;
        validate_identifier(project_id, "Project ID")?;
        lock(&self.connection)
            .query_row(
                "SELECT EXISTS(
                   SELECT 1
                     FROM computer_project_grants
                    WHERE coworker_id = ?1 AND project_id = ?2
                 )",
                params![coworker_id, project_id],
                |row| row.get(0),
            )
            .map_err(|error| format!("check coworker project grant failed: {error}"))
    }

    pub(crate) fn grant_project(
        &self,
        coworker_id: &str,
        project_id: &str,
        project_name: &str,
        project_path: &str,
    ) -> Result<ComputerProjectGrant, String> {
        validate_identifier(coworker_id, "coworker")?;
        validate_identifier(project_id, "Project ID")?;
        let timestamp = now();
        let mut connection = lock(&self.connection);
        let tx = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(|error| format!("begin Project grant transaction failed: {error}"))?;
        tx.execute(
            "UPDATE computer_project_grants
                    SET project_id = ?2, project_name = ?3, updated_at = ?5
                  WHERE coworker_id = ?1 AND project_path = ?4 AND project_id IS NULL",
            params![
                coworker_id,
                project_id,
                project_name,
                project_path,
                timestamp
            ],
        )
        .map_err(|error| format!("adopt legacy Project grant failed: {error}"))?;
        tx.execute(
            "UPDATE computer_coworker_bindings
                SET active_project_id = ?2, active_project_name = ?3, updated_at = ?5
              WHERE coworker_id = ?1 AND active_project_path = ?4
                AND active_project_id IS NULL",
            params![
                coworker_id,
                project_id,
                project_name,
                project_path,
                timestamp
            ],
        )
        .map_err(|error| format!("adopt legacy active Project failed: {error}"))?;
        tx.execute(
                "INSERT INTO computer_project_grants
                   (coworker_id, project_id, project_name, project_path, access_mode, created_at, updated_at)
                 VALUES (?1, ?2, ?3, ?4, 'read_write', ?5, ?5)
                 ON CONFLICT(coworker_id, project_id) DO UPDATE SET
                   project_name = excluded.project_name,
                   project_path = excluded.project_path,
                   access_mode = excluded.access_mode,
                   updated_at = excluded.updated_at",
                params![coworker_id, project_id, project_name, project_path, timestamp],
            )
            .map_err(|error| format!("grant coworker project access failed: {error}"))?;
        tx.commit()
            .map_err(|error| format!("commit Project grant failed: {error}"))?;
        drop(connection);
        self.project_grants(coworker_id)?
            .into_iter()
            .find(|grant| grant.project_id.as_deref() == Some(project_id))
            .ok_or_else(|| "Coworker project grant was not persisted".to_string())
    }

    pub(crate) fn activate_coworker_project(
        &self,
        activation: CoworkerProjectActivation<'_>,
    ) -> Result<(), String> {
        let CoworkerProjectActivation {
            coworker_id,
            environment_id,
            project_id,
            project_name,
            project_path,
            state,
            resources,
            event_type,
        } = activation;
        validate_identifier(coworker_id, "coworker")?;
        validate_identifier(project_id, "Project ID")?;
        let resources_json = serde_json::to_string(resources)
            .map_err(|error| format!("encode computer resources failed: {error}"))?;
        let timestamp = now();
        let mut connection = lock(&self.connection);
        let tx = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(|error| format!("begin coworker computer activation failed: {error}"))?;
        let existing_binding: Option<(String, Option<String>)> = tx
            .query_row(
                "SELECT environment_id, active_project_id
                   FROM computer_coworker_bindings WHERE coworker_id = ?1",
                params![coworker_id],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .optional()
            .map_err(|error| format!("read coworker binding during activation failed: {error}"))?;
        if existing_binding
            .as_ref()
            .is_some_and(|(value, _)| value != environment_id)
        {
            return Err("Coworker is already bound to another Computer environment".to_string());
        }
        let project_is_granted: bool = tx
            .query_row(
                "SELECT EXISTS(
                   SELECT 1
                     FROM computer_project_grants
                    WHERE coworker_id = ?1 AND project_id = ?2
                 )",
                params![coworker_id, project_id],
                |row| row.get(0),
            )
            .map_err(|error| format!("check project grant during activation failed: {error}"))?;
        if !project_is_granted {
            return Err(
                "project_access_denied: grant this Project to Neko before opening it".to_string(),
            );
        }
        tx.execute(
            "UPDATE computer_project_grants
                SET project_name = ?3, project_path = ?4, updated_at = ?5
              WHERE coworker_id = ?1 AND project_id = ?2",
            params![
                coworker_id,
                project_id,
                project_name,
                project_path,
                timestamp
            ],
        )
        .map_err(|error| format!("refresh Project workspace locator failed: {error}"))?;
        tx.execute(
            "INSERT INTO computer_environments
             (environment_id, project_name, project_path, state, resources_json, created_at, updated_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?6)
             ON CONFLICT(environment_id) DO UPDATE SET
               project_name = excluded.project_name,
               project_path = excluded.project_path,
               state = excluded.state,
               resources_json = excluded.resources_json,
               updated_at = excluded.updated_at",
            params![
                environment_id,
                project_name,
                project_path,
                state.as_str(),
                resources_json,
                timestamp
            ],
        )
        .map_err(|error| format!("prepare coworker computer environment failed: {error}"))?;
        tx.execute(
            "INSERT INTO computer_seats (environment_id, seat_id, state, updated_at)
             VALUES (?1, ?2, 'available', ?3)
             ON CONFLICT(environment_id) DO NOTHING",
            params![environment_id, format!("seat-{environment_id}"), timestamp],
        )
        .map_err(|error| format!("prepare coworker display seat failed: {error}"))?;
        if existing_binding
            .as_ref()
            .is_some_and(|(_, active_project_id)| active_project_id.as_deref() != Some(project_id))
        {
            make_seat_available_tx(
                &tx,
                environment_id,
                "seat.project_switched",
                serde_json::json!({ "coworkerId": coworker_id, "projectId": project_id }),
            )?;
        }
        tx.execute(
            "INSERT INTO computer_coworker_bindings
               (coworker_id, environment_id, active_project_id, active_project_name, active_project_path, created_at, updated_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?6)
             ON CONFLICT(coworker_id) DO UPDATE SET
               active_project_id = excluded.active_project_id,
               active_project_name = excluded.active_project_name,
               active_project_path = excluded.active_project_path,
               updated_at = excluded.updated_at",
            params![coworker_id, environment_id, project_id, project_name, project_path, timestamp],
        )
        .map_err(|error| format!("bind coworker to Computer failed: {error}"))?;
        append_event_tx(
            &tx,
            environment_id,
            event_type,
            serde_json::json!({
                "state": state.as_str(),
                "coworkerId": coworker_id,
                "projectId": project_id,
                "projectName": project_name,
                "projectPath": project_path
            }),
        )?;
        tx.commit()
            .map_err(|error| format!("commit coworker Computer activation failed: {error}"))
    }

    pub(crate) fn revoke_project(
        &self,
        coworker_id: &str,
        project_id: &str,
    ) -> Result<Option<String>, String> {
        validate_identifier(coworker_id, "coworker")?;
        validate_identifier(project_id, "Project ID")?;
        let mut connection = lock(&self.connection);
        let tx = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(|error| format!("begin coworker project revocation failed: {error}"))?;
        let binding: Option<(String, Option<String>)> = tx
            .query_row(
                "SELECT environment_id, active_project_id
                   FROM computer_coworker_bindings WHERE coworker_id = ?1",
                params![coworker_id],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .optional()
            .map_err(|error| format!("read active coworker project failed: {error}"))?;
        tx.execute(
            "DELETE FROM computer_project_grants WHERE coworker_id = ?1 AND project_id = ?2",
            params![coworker_id, project_id],
        )
        .map_err(|error| format!("revoke coworker project access failed: {error}"))?;
        let active_environment = binding.and_then(|(environment_id, active_id)| {
            (active_id.as_deref() == Some(project_id)).then_some(environment_id)
        });
        if let Some(environment_id) = active_environment.as_deref() {
            make_seat_available_tx(
                &tx,
                environment_id,
                "seat.project_revoked",
                serde_json::json!({ "coworkerId": coworker_id, "projectId": project_id }),
            )?;
            tx.execute(
                "UPDATE computer_coworker_bindings
                    SET active_project_id = NULL, active_project_name = NULL,
                        active_project_path = NULL, updated_at = ?2
                  WHERE coworker_id = ?1",
                params![coworker_id, now()],
            )
            .map_err(|error| format!("detach revoked coworker project failed: {error}"))?;
            tx.execute(
                "UPDATE computer_environments SET state = 'suspended', updated_at = ?2
                  WHERE environment_id = ?1",
                params![environment_id, now()],
            )
            .map_err(|error| format!("suspend detached coworker Computer failed: {error}"))?;
            append_event_tx(
                &tx,
                environment_id,
                "computer.project_revoked",
                serde_json::json!({ "coworkerId": coworker_id, "projectId": project_id }),
            )?;
        }
        tx.commit()
            .map_err(|error| format!("commit coworker project revocation failed: {error}"))?;
        Ok(active_environment)
    }

    pub(crate) fn delete_environment(&self, environment_id: &str) -> Result<(), String> {
        let mut connection = lock(&self.connection);
        let tx = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(|error| format!("begin computer removal transaction failed: {error}"))?;
        tx.execute(
            "DELETE FROM computer_project_grants
              WHERE coworker_id IN (
                SELECT coworker_id FROM computer_coworker_bindings WHERE environment_id = ?1
              )",
            params![environment_id],
        )
        .map_err(|error| format!("remove coworker project grants failed: {error}"))?;
        let changed = tx
            .execute(
                "DELETE FROM computer_environments WHERE environment_id = ?1",
                params![environment_id],
            )
            .map_err(|error| format!("remove computer environment state failed: {error}"))?;
        if changed != 1 {
            return Err("Computer environment does not exist".to_string());
        }
        tx.commit()
            .map_err(|error| format!("commit computer removal failed: {error}"))
    }

    pub(crate) fn mark_unknown_outcome(
        &self,
        request_id: &str,
        environment_id: &str,
    ) -> Result<(), String> {
        let mut connection = lock(&self.connection);
        let tx = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(|error| format!("begin computer uncertainty transaction failed: {error}"))?;
        tx.execute(
            "UPDATE computer_requests
                SET phase = 'unknown_outcome', error_code = 'unknown_outcome', updated_at = ?2
              WHERE request_id = ?1",
            params![request_id, now()],
        )
        .map_err(|error| format!("mark computer request uncertain failed: {error}"))?;
        tx.execute(
            "UPDATE computer_environments SET state = 'unknown_outcome', updated_at = ?2
             WHERE environment_id = ?1",
            params![environment_id, now()],
        )
        .map_err(|error| format!("mark computer environment uncertain failed: {error}"))?;
        append_event_tx(
            &tx,
            environment_id,
            "computer.unknown_outcome",
            serde_json::json!({ "requestId": request_id }),
        )?;
        tx.commit()
            .map_err(|error| format!("commit computer uncertainty failed: {error}"))
    }

    pub(crate) fn upsert_environment(
        &self,
        environment_id: &str,
        project_name: &str,
        project_path: &str,
        state: ComputerState,
        resources: &ComputerResources,
        event_type: &str,
    ) -> Result<(), String> {
        let resources_json = serde_json::to_string(resources)
            .map_err(|error| format!("encode computer resources failed: {error}"))?;
        let timestamp = now();
        let mut connection = lock(&self.connection);
        let tx = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(|error| format!("begin computer environment transaction failed: {error}"))?;
        tx.execute(
            "INSERT INTO computer_environments
             (environment_id, project_name, project_path, state, resources_json, created_at, updated_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?6)
             ON CONFLICT(environment_id) DO UPDATE SET
               project_name = excluded.project_name,
               project_path = excluded.project_path,
               state = excluded.state,
               resources_json = excluded.resources_json,
               updated_at = excluded.updated_at",
            params![
                environment_id,
                project_name,
                project_path,
                state.as_str(),
                resources_json,
                timestamp
            ],
        )
        .map_err(|error| format!("save computer environment failed: {error}"))?;
        tx.execute(
            "INSERT INTO computer_seats
             (environment_id, seat_id, state, updated_at)
             VALUES (?1, ?2, 'available', ?3)
             ON CONFLICT(environment_id) DO NOTHING",
            params![environment_id, format!("seat-{environment_id}"), timestamp],
        )
        .map_err(|error| format!("save computer display seat failed: {error}"))?;
        append_event_tx(
            &tx,
            environment_id,
            event_type,
            serde_json::json!({ "state": state.as_str() }),
        )?;
        tx.commit()
            .map_err(|error| format!("commit computer environment failed: {error}"))
    }

    pub(crate) fn environment(
        &self,
        environment_id: &str,
    ) -> Result<Option<ComputerEnvironment>, String> {
        let connection = lock(&self.connection);
        connection
            .query_row(
                "SELECT e.environment_id, e.project_name, e.project_path, e.state,
                        e.resources_json, e.created_at, e.updated_at,
                        s.seat_id, s.state, s.lease_id, s.owner_id, s.updated_at
                   FROM computer_environments e
                   JOIN computer_seats s ON s.environment_id = e.environment_id
                  WHERE e.environment_id = ?1",
                params![environment_id],
                |row| {
                    let state: String = row.get(3)?;
                    let resources_json: String = row.get(4)?;
                    let seat_state: String = row.get(8)?;
                    Ok((
                        row.get::<_, String>(0)?,
                        row.get::<_, String>(1)?,
                        row.get::<_, String>(2)?,
                        state,
                        resources_json,
                        row.get::<_, String>(5)?,
                        row.get::<_, String>(6)?,
                        row.get::<_, String>(7)?,
                        seat_state,
                        row.get::<_, Option<String>>(9)?,
                        row.get::<_, Option<String>>(10)?,
                        row.get::<_, String>(11)?,
                    ))
                },
            )
            .optional()
            .map_err(|error| format!("read computer environment failed: {error}"))?
            .map(|row| {
                Ok(ComputerEnvironment {
                    environment_id: row.0,
                    project_id: None,
                    project_name: row.1,
                    project_path: row.2,
                    provider_kind: "local_docker".to_string(),
                    isolation_class: "shared_container".to_string(),
                    computer_kind: "web_computer".to_string(),
                    operating_system: "Linux · Debian 12".to_string(),
                    semantic_protocol: "neko-computer.semantic.v1".to_string(),
                    active_pack_version: None,
                    pack_update_available: false,
                    state: ComputerState::parse(&row.3)?,
                    project_mount: "/workspace/project".to_string(),
                    attach_url: None,
                    resources: serde_json::from_str(&row.4)
                        .map_err(|error| format!("decode computer resources failed: {error}"))?,
                    seat: DisplaySeat {
                        seat_id: row.7,
                        state: SeatState::parse(&row.8)?,
                        lease_id: row.9,
                        owner_id: row.10,
                        updated_at: row.11,
                    },
                    created_at: row.5,
                    updated_at: row.6,
                })
            })
            .transpose()
    }

    pub(crate) fn active_environment_ids(&self) -> Result<Vec<String>, String> {
        let connection = lock(&self.connection);
        let mut statement = connection
            .prepare(
                "SELECT DISTINCT b.environment_id
                   FROM computer_coworker_bindings b
                   JOIN computer_environments e ON e.environment_id = b.environment_id
                  WHERE b.active_project_id IS NOT NULL AND e.state = 'ready'
                  ORDER BY b.environment_id",
            )
            .map_err(|error| format!("prepare active Computer environments failed: {error}"))?;
        let environments = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(|error| format!("query active Computer environments failed: {error}"))?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|error| format!("read active Computer environment failed: {error}"))?;
        Ok(environments)
    }

    pub(crate) fn set_environment_state(
        &self,
        environment_id: &str,
        state: ComputerState,
        event_type: &str,
    ) -> Result<(), String> {
        let mut connection = lock(&self.connection);
        let tx = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(|error| format!("begin computer state transaction failed: {error}"))?;
        let changed = tx
            .execute(
                "UPDATE computer_environments SET state = ?2, updated_at = ?3
                 WHERE environment_id = ?1",
                params![environment_id, state.as_str(), now()],
            )
            .map_err(|error| format!("update computer state failed: {error}"))?;
        if changed != 1 {
            return Err("Computer environment does not exist".to_string());
        }
        append_event_tx(
            &tx,
            environment_id,
            event_type,
            serde_json::json!({ "state": state.as_str() }),
        )?;
        tx.commit()
            .map_err(|error| format!("commit computer state failed: {error}"))
    }

    pub(crate) fn acquire_seat(
        &self,
        environment_id: &str,
        owner_id: &str,
        user_controlled: bool,
    ) -> Result<DisplaySeat, String> {
        validate_identifier(owner_id, "seat owner")?;
        let mut connection = lock(&self.connection);
        let tx = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(|error| format!("begin seat acquisition failed: {error}"))?;
        let current: (String, Option<String>, Option<String>, String) = tx
            .query_row(
                "SELECT state, lease_id, owner_id, updated_at FROM computer_seats
                 WHERE environment_id = ?1",
                params![environment_id],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
            )
            .map_err(|_| "Computer display seat does not exist".to_string())?;
        let same_owner = current.2.as_deref() == Some(owner_id);
        let human_preempts_agent = user_controlled && current.0 == "agent_controlled";
        if current.0 != "available" && !same_owner && !human_preempts_agent {
            return Err("Computer display seat is already controlled by another owner".to_string());
        }
        let lease_id = if same_owner {
            current
                .1
                .unwrap_or_else(|| format!("lease-{}", Uuid::new_v4()))
        } else {
            format!("lease-{}", Uuid::new_v4())
        };
        let state = if user_controlled {
            SeatState::UserControlled
        } else {
            SeatState::AgentControlled
        };
        let timestamp = now();
        tx.execute(
            "UPDATE computer_seats
                SET state = ?2, lease_id = ?3, owner_id = ?4, updated_at = ?5
              WHERE environment_id = ?1",
            params![
                environment_id,
                state.as_str(),
                lease_id,
                owner_id,
                timestamp
            ],
        )
        .map_err(|error| format!("acquire computer display seat failed: {error}"))?;
        append_event_tx(
            &tx,
            environment_id,
            if user_controlled {
                "seat.user_takeover"
            } else {
                "seat.acquired"
            },
            serde_json::json!({ "ownerId": owner_id, "leaseId": lease_id }),
        )?;
        tx.commit()
            .map_err(|error| format!("commit seat acquisition failed: {error}"))?;
        Ok(DisplaySeat {
            seat_id: format!("seat-{environment_id}"),
            state,
            lease_id: Some(lease_id),
            owner_id: Some(owner_id.to_string()),
            updated_at: timestamp,
        })
    }

    pub(crate) fn release_seat(
        &self,
        environment_id: &str,
        lease_id: &str,
    ) -> Result<DisplaySeat, String> {
        validate_identifier(lease_id, "seat lease")?;
        let mut connection = lock(&self.connection);
        let tx = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(|error| format!("begin seat release failed: {error}"))?;
        let timestamp = now();
        let changed = tx
            .execute(
                "UPDATE computer_seats
                    SET state = 'available', lease_id = NULL, owner_id = NULL, updated_at = ?3
                  WHERE environment_id = ?1 AND lease_id = ?2",
                params![environment_id, lease_id, timestamp],
            )
            .map_err(|error| format!("release computer display seat failed: {error}"))?;
        if changed != 1 {
            return Err("Computer display lease is no longer current".to_string());
        }
        append_event_tx(
            &tx,
            environment_id,
            "seat.released",
            serde_json::json!({ "leaseId": lease_id }),
        )?;
        tx.commit()
            .map_err(|error| format!("commit seat release failed: {error}"))?;
        Ok(DisplaySeat {
            seat_id: format!("seat-{environment_id}"),
            state: SeatState::Available,
            lease_id: None,
            owner_id: None,
            updated_at: timestamp,
        })
    }

    pub(crate) fn append_event(
        &self,
        environment_id: &str,
        event_type: &str,
        payload: Value,
    ) -> Result<(), String> {
        let mut connection = lock(&self.connection);
        let tx = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(|error| format!("begin computer event transaction failed: {error}"))?;
        append_event_tx(&tx, environment_id, event_type, payload)?;
        tx.commit()
            .map_err(|error| format!("commit computer event failed: {error}"))
    }

    pub(crate) fn replay(
        &self,
        environment_id: &str,
        after_seq: u64,
        limit: u32,
    ) -> Result<ComputerReplayPage, String> {
        let limit = limit.clamp(1, MAX_REPLAY_LIMIT);
        let after_seq_sql = i64::try_from(after_seq)
            .map_err(|_| "Computer replay cursor exceeds SQLite range".to_string())?;
        let stream_id = format!("computer:{environment_id}");
        let connection = lock(&self.connection);
        let mut statement = connection
            .prepare(
                "SELECT event_id, stream_id, seq, at, event_type, environment_id, payload_json
                   FROM computer_events
                  WHERE stream_id = ?1 AND seq > ?2
                  ORDER BY seq ASC LIMIT ?3",
            )
            .map_err(|error| format!("prepare computer replay failed: {error}"))?;
        let rows = statement
            .query_map(params![stream_id, after_seq_sql, limit + 1], |row| {
                Ok((
                    row.get::<_, String>(0)?,
                    row.get::<_, String>(1)?,
                    row.get::<_, i64>(2)?,
                    row.get::<_, String>(3)?,
                    row.get::<_, String>(4)?,
                    row.get::<_, String>(5)?,
                    row.get::<_, String>(6)?,
                ))
            })
            .map_err(|error| format!("query computer replay failed: {error}"))?;
        let mut events = Vec::new();
        for row in rows {
            let row = row.map_err(|error| format!("read computer replay event failed: {error}"))?;
            events.push(ComputerEvent {
                event_id: row.0,
                stream_id: row.1,
                seq: u64::try_from(row.2)
                    .map_err(|_| "Computer event sequence is invalid".to_string())?,
                at: row.3,
                event_type: row.4,
                environment_id: row.5,
                payload: serde_json::from_str(&row.6)
                    .map_err(|error| format!("decode computer event failed: {error}"))?,
            });
        }
        let has_more = events.len() > limit as usize;
        events.truncate(limit as usize);
        let next_after_seq = events.last().map(|event| event.seq).unwrap_or(after_seq);
        Ok(ComputerReplayPage {
            stream_id,
            events,
            next_after_seq,
            has_more,
        })
    }

    fn recover_incomplete(&self) -> Result<(), String> {
        let mut connection = lock(&self.connection);
        let tx = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(|error| format!("begin computer recovery failed: {error}"))?;
        tx.execute(
            "UPDATE computer_requests
                SET phase = 'unknown_outcome', error_code = 'unknown_outcome', updated_at = ?1
              WHERE phase NOT IN ('completed', 'failed', 'unknown_outcome')",
            params![now()],
        )
        .map_err(|error| format!("recover computer requests failed: {error}"))?;
        tx.execute(
            "UPDATE computer_environments SET state = 'unknown_outcome', updated_at = ?1
             WHERE state = 'preparing'",
            params![now()],
        )
        .map_err(|error| format!("recover computer environments failed: {error}"))?;
        tx.commit()
            .map_err(|error| format!("commit computer recovery failed: {error}"))
    }
}

fn append_event_tx(
    tx: &rusqlite::Transaction<'_>,
    environment_id: &str,
    event_type: &str,
    payload: Value,
) -> Result<(), String> {
    let payload_json = serde_json::to_string(&payload)
        .map_err(|error| format!("encode computer event failed: {error}"))?;
    if payload_json.len() > MAX_EVENT_PAYLOAD_BYTES {
        return Err("Computer event payload exceeds 4096 bytes".to_string());
    }
    let stream_id = format!("computer:{environment_id}");
    let seq: i64 = tx
        .query_row(
            "SELECT COALESCE(MAX(seq), 0) + 1 FROM computer_events WHERE stream_id = ?1",
            params![stream_id],
            |row| row.get(0),
        )
        .map_err(|error| format!("allocate computer event sequence failed: {error}"))?;
    tx.execute(
        "INSERT INTO computer_events
         (event_id, stream_id, seq, at, event_type, environment_id, payload_json)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
        params![
            Uuid::new_v4().to_string(),
            stream_id,
            seq,
            now(),
            event_type,
            environment_id,
            payload_json
        ],
    )
    .map_err(|error| format!("append computer event failed: {error}"))?;
    Ok(())
}

fn make_seat_available_tx(
    tx: &rusqlite::Transaction<'_>,
    environment_id: &str,
    event_type: &str,
    payload: Value,
) -> Result<bool, String> {
    let changed = tx
        .execute(
            "UPDATE computer_seats
                SET state = 'available', lease_id = NULL, owner_id = NULL, updated_at = ?2
              WHERE environment_id = ?1 AND state != 'available'",
            params![environment_id, now()],
        )
        .map_err(|error| format!("release Computer seat at Project boundary failed: {error}"))?;
    if changed == 0 {
        return Ok(false);
    }
    append_event_tx(tx, environment_id, event_type, payload)?;
    Ok(true)
}

fn request_decision(
    stored: StoredRequest,
    method: &str,
    target_id: &str,
) -> Result<RequestDecision, String> {
    let (stored_method, stored_target, phase, result_json, error_code) = stored;
    if stored_method != method || stored_target != target_id {
        return Err("Computer request ID was already used for another operation".to_string());
    }
    match phase.as_str() {
        "completed" => result_json
            .ok_or_else(|| "Completed computer request has no result".to_string())
            .and_then(|value| {
                serde_json::from_str(&value)
                    .map(RequestDecision::Replay)
                    .map_err(|error| format!("decode computer request result failed: {error}"))
            }),
        "failed" => Ok(RequestDecision::RecordedError(
            error_code.unwrap_or_else(|| "computer_operation_failed".to_string()),
        )),
        _ => Ok(RequestDecision::UnknownOutcome),
    }
}

fn validate_identifier(value: &str, label: &str) -> Result<(), String> {
    if value.is_empty()
        || value.len() > 160
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_' | b':' | b'.'))
    {
        return Err(format!("Invalid {label}"));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn environment(journal: &ComputerJournal) {
        journal
            .upsert_environment(
                "computer-abc",
                "Wiii",
                "C:/wiii",
                ComputerState::Preparing,
                &ComputerResources::default(),
                "computer.preparing",
            )
            .unwrap();
    }

    #[test]
    fn requests_are_idempotent_and_collisions_fail_closed() {
        let journal = ComputerJournal::in_memory();
        assert_eq!(
            journal
                .begin_request("req-1", "computer/ensure", "computer-abc")
                .unwrap(),
            RequestDecision::Execute
        );
        journal
            .complete_request(
                "req-1",
                &serde_json::json!({"environmentId":"computer-abc"}),
            )
            .unwrap();
        assert!(matches!(
            journal
                .begin_request("req-1", "computer/ensure", "computer-abc")
                .unwrap(),
            RequestDecision::Replay(_)
        ));
        assert!(journal
            .begin_request("req-1", "computer/reset", "computer-abc")
            .is_err());
    }

    #[test]
    fn one_seat_rejects_another_owner_and_replays_events() {
        let journal = ComputerJournal::in_memory();
        environment(&journal);
        let seat = journal
            .acquire_seat("computer-abc", "session-one", false)
            .unwrap();
        assert!(journal
            .acquire_seat("computer-abc", "session-two", false)
            .is_err());
        journal
            .release_seat("computer-abc", seat.lease_id.as_deref().unwrap())
            .unwrap();
        let page = journal.replay("computer-abc", 0, 2).unwrap();
        assert_eq!(page.events.len(), 2);
        assert!(page.has_more);
        assert_eq!(page.events[0].seq, 1);
        assert_eq!(page.events[1].seq, 2);
    }

    #[test]
    fn human_takeover_preempts_agent_control_with_a_fresh_lease() {
        let journal = ComputerJournal::in_memory();
        environment(&journal);
        let agent = journal
            .acquire_seat("computer-abc", "agent-session:one", false)
            .unwrap();

        let human = journal
            .acquire_seat("computer-abc", "user:wiii-desktop", true)
            .unwrap();

        assert_eq!(human.state, SeatState::UserControlled);
        assert_eq!(human.owner_id.as_deref(), Some("user:wiii-desktop"));
        assert_ne!(human.lease_id, agent.lease_id);
        assert!(journal
            .release_seat("computer-abc", agent.lease_id.as_deref().unwrap())
            .is_err());
    }

    #[test]
    fn project_switch_and_revocation_release_the_active_seat() {
        let journal = ComputerJournal::in_memory();
        for (project_id, name, path) in [
            ("project-one", "One", "C:/one"),
            ("project-two", "Two", "C:/two"),
        ] {
            journal
                .grant_project("neko", project_id, name, path)
                .unwrap();
        }
        journal
            .activate_coworker_project(CoworkerProjectActivation {
                coworker_id: "neko",
                environment_id: "computer-abc",
                project_id: "project-one",
                project_name: "One",
                project_path: "C:/one",
                state: ComputerState::Ready,
                resources: &ComputerResources::default(),
                event_type: "computer.ready",
            })
            .unwrap();
        journal
            .acquire_seat("computer-abc", "agent-session:one", false)
            .unwrap();

        journal
            .activate_coworker_project(CoworkerProjectActivation {
                coworker_id: "neko",
                environment_id: "computer-abc",
                project_id: "project-two",
                project_name: "Two",
                project_path: "C:/two",
                state: ComputerState::Ready,
                resources: &ComputerResources::default(),
                event_type: "computer.ready",
            })
            .unwrap();
        assert_eq!(
            journal
                .environment("computer-abc")
                .unwrap()
                .unwrap()
                .seat
                .state,
            SeatState::Available,
        );

        journal
            .acquire_seat("computer-abc", "user:wiii-desktop", true)
            .unwrap();
        journal.revoke_project("neko", "project-two").unwrap();
        assert_eq!(
            journal
                .environment("computer-abc")
                .unwrap()
                .unwrap()
                .seat
                .state,
            SeatState::Available,
        );
        let events = journal.replay("computer-abc", 0, 100).unwrap().events;
        assert!(events
            .iter()
            .any(|event| event.event_type == "seat.project_switched"));
        assert!(events
            .iter()
            .any(|event| event.event_type == "seat.project_revoked"));
    }

    #[test]
    fn legacy_project_computers_become_one_coworker_with_revocable_grants() {
        let journal = ComputerJournal::in_memory();
        journal
            .upsert_environment(
                "computer-first",
                "First",
                "C:/first",
                ComputerState::Ready,
                &ComputerResources::default(),
                "computer.ready",
            )
            .unwrap();
        journal
            .upsert_environment(
                "computer-latest",
                "Latest",
                "C:/latest",
                ComputerState::Ready,
                &ComputerResources::default(),
                "computer.ready",
            )
            .unwrap();

        journal.adopt_legacy_coworker("neko").unwrap();

        let binding = journal.coworker_binding("neko").unwrap().unwrap();
        assert_eq!(binding.environment_id, "computer-latest");
        assert_eq!(binding.active_project_path.as_deref(), Some("C:/latest"));
        let grants = journal.project_grants("neko").unwrap();
        assert_eq!(grants.len(), 2);
        assert!(grants.iter().all(|grant| grant.project_id.is_none()));
        assert!(grants.iter().any(|grant| grant.project_path == "C:/first"));
        assert!(grants.iter().any(|grant| grant.project_path == "C:/latest"));
        journal
            .grant_project("neko", "project-latest", "Latest", "C:/latest")
            .unwrap();
        assert!(journal.has_project_grant("neko", "project-latest").unwrap());

        journal.revoke_project("neko", "project-latest").unwrap();
        let binding = journal.coworker_binding("neko").unwrap().unwrap();
        assert_eq!(binding.environment_id, "computer-latest");
        assert_eq!(binding.active_project_path, None);
        assert_eq!(journal.project_grants("neko").unwrap().len(), 1);
        assert!(!journal.has_project_grant("neko", "project-latest").unwrap());
        assert!(journal
            .activate_coworker_project(CoworkerProjectActivation {
                coworker_id: "neko",
                environment_id: "computer-latest",
                project_id: "project-latest",
                project_name: "Latest",
                project_path: "C:/latest",
                state: ComputerState::Preparing,
                resources: &ComputerResources::default(),
                event_type: "computer.preparing",
            })
            .unwrap_err()
            .starts_with("project_access_denied:"));
    }

    #[test]
    fn stable_project_identity_survives_a_workspace_move() {
        let journal = ComputerJournal::in_memory();
        journal
            .grant_project("neko", "project-wiii", "Wiii", "E:/old/wiii")
            .unwrap();
        journal
            .activate_coworker_project(CoworkerProjectActivation {
                coworker_id: "neko",
                environment_id: "computer-neko",
                project_id: "project-wiii",
                project_name: "Wiii",
                project_path: "D:/moved/wiii",
                state: ComputerState::Preparing,
                resources: &ComputerResources::default(),
                event_type: "computer.preparing",
            })
            .unwrap();

        let binding = journal.coworker_binding("neko").unwrap().unwrap();
        assert_eq!(binding.active_project_id.as_deref(), Some("project-wiii"));
        assert_eq!(
            binding.active_project_path.as_deref(),
            Some("D:/moved/wiii")
        );
        let grants = journal.project_grants("neko").unwrap();
        assert_eq!(grants.len(), 1);
        assert_eq!(grants[0].project_id.as_deref(), Some("project-wiii"));
        assert_eq!(grants[0].project_path, "D:/moved/wiii");
    }

    #[test]
    fn opening_a_v1_journal_adds_stable_project_identity_without_data_loss() {
        let path = std::env::temp_dir().join(format!(
            "wiii-computer-v1-migration-{}.sqlite3",
            Uuid::new_v4()
        ));
        let connection = Connection::open(&path).unwrap();
        connection
            .execute_batch(
                "PRAGMA foreign_keys=ON;
                 CREATE TABLE computer_environments (
                   environment_id TEXT PRIMARY KEY,
                   project_name TEXT NOT NULL,
                   project_path TEXT NOT NULL UNIQUE,
                   state TEXT NOT NULL,
                   resources_json TEXT NOT NULL,
                   created_at TEXT NOT NULL,
                   updated_at TEXT NOT NULL
                 );
                 CREATE TABLE computer_coworker_bindings (
                   coworker_id TEXT PRIMARY KEY,
                   environment_id TEXT NOT NULL UNIQUE,
                   active_project_name TEXT,
                   active_project_path TEXT,
                   created_at TEXT NOT NULL,
                   updated_at TEXT NOT NULL
                 );
                 CREATE TABLE computer_project_grants (
                   coworker_id TEXT NOT NULL,
                   project_name TEXT NOT NULL,
                   project_path TEXT NOT NULL,
                   access_mode TEXT NOT NULL,
                   created_at TEXT NOT NULL,
                   updated_at TEXT NOT NULL,
                   PRIMARY KEY(coworker_id, project_path)
                 );
                 INSERT INTO computer_environments VALUES
                   ('computer-neko', 'Wiii', 'E:/old/wiii', 'ready', '{}', 't0', 't0');
                 INSERT INTO computer_coworker_bindings VALUES
                   ('neko', 'computer-neko', 'Wiii', 'E:/old/wiii', 't0', 't0');
                 INSERT INTO computer_project_grants VALUES
                   ('neko', 'Wiii', 'E:/old/wiii', 'read_write', 't0', 't0');",
            )
            .unwrap();
        drop(connection);

        let journal = ComputerJournal::open(&path).unwrap();
        journal
            .grant_project("neko", "project-wiii", "Wiii", "E:/old/wiii")
            .unwrap();
        let binding = journal.coworker_binding("neko").unwrap().unwrap();
        assert_eq!(binding.active_project_id.as_deref(), Some("project-wiii"));
        let grants = journal.project_grants("neko").unwrap();
        assert_eq!(grants.len(), 1);
        assert_eq!(grants[0].project_id.as_deref(), Some("project-wiii"));
        drop(journal);

        for candidate in [
            path.clone(),
            path.with_extension("sqlite3-wal"),
            path.with_extension("sqlite3-shm"),
        ] {
            let _ = std::fs::remove_file(candidate);
        }
    }
}
