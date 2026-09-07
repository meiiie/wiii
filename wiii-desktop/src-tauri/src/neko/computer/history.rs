use super::model::{
    ComputerHistoryEntry, ComputerHistoryPage, ComputerHistoryStatus, SemanticActResult,
};
use super::protected_key::{load_or_create, random_nonce};
use chacha20poly1305::aead::{Aead, KeyInit, Payload};
use chacha20poly1305::{Key, XChaCha20Poly1305, XNonce};
use chrono::{Duration, SecondsFormat, Utc};
use rusqlite::{params, Connection, TransactionBehavior};
use std::path::Path;
use std::sync::{Arc, Mutex, MutexGuard};
#[cfg(test)]
use uuid::Uuid;

const RETENTION_DAYS: u32 = 30;
const MAX_ENTRIES: u64 = 10_000;
const MAX_QUERY_LIMIT: u32 = 200;
const CIPHER_NAME: &str = "xchacha20-poly1305";
#[cfg(windows)]
const KEY_PROTECTION: &str = "windows-dpapi-current-user";
#[cfg(not(windows))]
const KEY_PROTECTION: &str = "app-private-file";

#[derive(Clone)]
pub(crate) struct ComputerHistory {
    connection: Arc<Mutex<Connection>>,
    cipher: Arc<XChaCha20Poly1305>,
    last_error: Arc<Mutex<Option<String>>>,
}

fn lock<T>(value: &Mutex<T>) -> MutexGuard<'_, T> {
    value
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

fn now() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Millis, true)
}

fn aad(environment_id: &str, seq: u64, at: &str) -> Vec<u8> {
    format!("wiii-computer-history-v1\0{environment_id}\0{seq}\0{at}").into_bytes()
}

impl ComputerHistory {
    pub(crate) fn open(root: &Path) -> Result<Self, String> {
        std::fs::create_dir_all(root)
            .map_err(|error| format!("create Computer History directory failed: {error}"))?;
        let key = load_or_create(&root.join("computer-history-v1.key"), "Computer History")?;
        let connection = Connection::open(root.join("computer-history-v1.sqlite3"))
            .map_err(|error| format!("open Computer History failed: {error}"))?;
        connection
            .execute_batch(
                "PRAGMA journal_mode=WAL;
                 PRAGMA busy_timeout=5000;
                 CREATE TABLE IF NOT EXISTS computer_history (
                   seq INTEGER PRIMARY KEY AUTOINCREMENT,
                   at TEXT NOT NULL,
                   environment_id TEXT NOT NULL,
                   nonce BLOB NOT NULL,
                   ciphertext BLOB NOT NULL
                 );
                 CREATE INDEX IF NOT EXISTS idx_computer_history_environment
                   ON computer_history(environment_id, seq DESC);
                 CREATE TABLE IF NOT EXISTS computer_history_settings (
                   singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                   enabled INTEGER NOT NULL CHECK(enabled IN (0, 1))
                 );
                 INSERT OR IGNORE INTO computer_history_settings(singleton, enabled) VALUES(1, 0);",
            )
            .map_err(|error| format!("initialize Computer History failed: {error}"))?;
        Ok(Self {
            connection: Arc::new(Mutex::new(connection)),
            cipher: Arc::new(XChaCha20Poly1305::new(Key::from_slice(&key))),
            last_error: Arc::new(Mutex::new(None)),
        })
    }

    pub(crate) fn append_action(&self, result: &SemanticActResult) -> Result<(), String> {
        let outcome = self.append_action_inner(result);
        self.remember_outcome(&outcome);
        outcome
    }

    fn append_action_inner(&self, result: &SemanticActResult) -> Result<(), String> {
        if !self.enabled()? {
            return Ok(());
        }
        let at = now();
        let mut connection = lock(&self.connection);
        let transaction = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(|error| format!("begin Computer History write failed: {error}"))?;
        transaction
            .execute(
                "INSERT INTO computer_history(at, environment_id, nonce, ciphertext)
                 VALUES(?1, ?2, X'', X'')",
                params![at, result.environment_id],
            )
            .map_err(|error| format!("reserve Computer History entry failed: {error}"))?;
        let seq_sql = transaction.last_insert_rowid();
        let seq = u64::try_from(seq_sql)
            .map_err(|_| "Computer History sequence is invalid".to_string())?;
        let entry = ComputerHistoryEntry {
            seq,
            at: at.clone(),
            environment_id: result.environment_id.clone(),
            outcome: result.outcome.clone(),
            action: result.action.clone(),
            target_ref: result.target_ref.clone(),
            before_state_version: result.before_state_version.clone(),
            after_state_version: result.after_state_version.clone(),
            verified: result.verified,
            effect: result.effect.clone(),
            route: result.route.clone(),
            evidence: result.evidence.clone(),
            code: result.code.clone(),
        };
        let plaintext = serde_json::to_vec(&entry)
            .map_err(|error| format!("encode Computer History entry failed: {error}"))?;
        let nonce = random_nonce();
        let ciphertext = self
            .cipher
            .encrypt(
                XNonce::from_slice(&nonce),
                Payload {
                    msg: &plaintext,
                    aad: &aad(&result.environment_id, seq, &at),
                },
            )
            .map_err(|_| "encrypt Computer History entry failed".to_string())?;
        transaction
            .execute(
                "UPDATE computer_history SET nonce = ?1, ciphertext = ?2 WHERE seq = ?3",
                params![nonce.as_slice(), ciphertext, seq_sql],
            )
            .map_err(|error| format!("write Computer History entry failed: {error}"))?;
        let cutoff = (Utc::now() - Duration::days(i64::from(RETENTION_DAYS)))
            .to_rfc3339_opts(SecondsFormat::Millis, true);
        transaction
            .execute(
                "DELETE FROM computer_history WHERE at < ?1",
                params![cutoff],
            )
            .map_err(|error| format!("prune Computer History retention failed: {error}"))?;
        transaction
            .execute(
                "DELETE FROM computer_history
                 WHERE seq NOT IN (SELECT seq FROM computer_history ORDER BY seq DESC LIMIT ?1)",
                params![i64::try_from(MAX_ENTRIES).unwrap_or(i64::MAX)],
            )
            .map_err(|error| format!("prune Computer History capacity failed: {error}"))?;
        transaction
            .commit()
            .map_err(|error| format!("commit Computer History failed: {error}"))
    }

    pub(crate) fn status(&self) -> Result<ComputerHistoryStatus, String> {
        let entry_count_sql: i64 = lock(&self.connection)
            .query_row("SELECT COUNT(*) FROM computer_history", [], |row| {
                row.get(0)
            })
            .map_err(|error| format!("read Computer History status failed: {error}"))?;
        let entry_count = u64::try_from(entry_count_sql)
            .map_err(|_| "Computer History count is invalid".to_string())?;
        Ok(ComputerHistoryStatus {
            available: true,
            enabled: self.enabled()?,
            encrypted: true,
            cipher: CIPHER_NAME.to_string(),
            key_protection: KEY_PROTECTION.to_string(),
            retention_days: RETENTION_DAYS,
            entry_count,
            last_error: lock(&self.last_error).clone(),
        })
    }

    pub(crate) fn set_enabled(&self, enabled: bool) -> Result<ComputerHistoryStatus, String> {
        lock(&self.connection)
            .execute(
                "UPDATE computer_history_settings SET enabled = ?1 WHERE singleton = 1",
                params![enabled],
            )
            .map_err(|error| format!("update Computer History setting failed: {error}"))?;
        self.status()
    }

    fn enabled(&self) -> Result<bool, String> {
        lock(&self.connection)
            .query_row(
                "SELECT enabled FROM computer_history_settings WHERE singleton = 1",
                [],
                |row| row.get(0),
            )
            .map_err(|error| format!("read Computer History setting failed: {error}"))
    }

    pub(crate) fn query(
        &self,
        environment_id: &str,
        before_seq: Option<u64>,
        limit: u32,
    ) -> Result<ComputerHistoryPage, String> {
        let limit = limit.clamp(1, MAX_QUERY_LIMIT);
        let before_seq = before_seq
            .and_then(|value| i64::try_from(value).ok())
            .unwrap_or(i64::MAX);
        let connection = lock(&self.connection);
        let mut statement = connection
            .prepare(
                "SELECT seq, at, nonce, ciphertext
                 FROM computer_history
                 WHERE environment_id = ?1 AND seq < ?2
                 ORDER BY seq DESC LIMIT ?3",
            )
            .map_err(|error| format!("prepare Computer History query failed: {error}"))?;
        let rows = statement
            .query_map(
                params![environment_id, before_seq, i64::from(limit + 1)],
                |row| {
                    Ok((
                        row.get::<_, i64>(0)?,
                        row.get::<_, String>(1)?,
                        row.get::<_, Vec<u8>>(2)?,
                        row.get::<_, Vec<u8>>(3)?,
                    ))
                },
            )
            .map_err(|error| format!("query Computer History failed: {error}"))?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|error| format!("read Computer History failed: {error}"))?;
        let has_more = rows.len() > limit as usize;
        let mut entries = Vec::with_capacity(rows.len().min(limit as usize));
        for (seq_sql, at, nonce, ciphertext) in rows.into_iter().take(limit as usize) {
            let seq = u64::try_from(seq_sql)
                .map_err(|_| "Computer History sequence is invalid".to_string())?;
            if nonce.len() != 24 {
                let error = "Computer History nonce is invalid".to_string();
                self.remember_outcome(&Err(error.clone()));
                return Err(error);
            }
            let plaintext = self
                .cipher
                .decrypt(
                    XNonce::from_slice(&nonce),
                    Payload {
                        msg: &ciphertext,
                        aad: &aad(environment_id, seq, &at),
                    },
                )
                .map_err(|_| "decrypt Computer History entry failed".to_string())?;
            let entry: ComputerHistoryEntry = serde_json::from_slice(&plaintext)
                .map_err(|error| format!("decode Computer History entry failed: {error}"))?;
            entries.push(entry);
        }
        let next_before_seq = has_more
            .then(|| entries.last().map(|entry| entry.seq))
            .flatten();
        let page = ComputerHistoryPage {
            entries,
            next_before_seq,
            has_more,
        };
        self.remember_outcome(&Ok(()));
        Ok(page)
    }

    pub(crate) fn delete(&self, environment_id: &str) -> Result<u64, String> {
        let deleted = lock(&self.connection)
            .execute(
                "DELETE FROM computer_history WHERE environment_id = ?1",
                params![environment_id],
            )
            .map_err(|error| format!("delete Computer History failed: {error}"))?;
        self.remember_outcome(&Ok(()));
        u64::try_from(deleted).map_err(|_| "Computer History delete count is invalid".to_string())
    }

    fn remember_outcome(&self, outcome: &Result<(), String>) {
        *lock(&self.last_error) = outcome.as_ref().err().cloned();
    }

    #[cfg(test)]
    pub(crate) fn in_memory() -> Self {
        let connection = Connection::open_in_memory().unwrap();
        connection
            .execute_batch(
                "CREATE TABLE computer_history (
                   seq INTEGER PRIMARY KEY AUTOINCREMENT,
                   at TEXT NOT NULL,
                   environment_id TEXT NOT NULL,
                   nonce BLOB NOT NULL,
                   ciphertext BLOB NOT NULL
                 );
                 CREATE INDEX idx_computer_history_environment
                   ON computer_history(environment_id, seq DESC);
                 CREATE TABLE computer_history_settings (
                   singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                   enabled INTEGER NOT NULL CHECK(enabled IN (0, 1))
                 );
                 INSERT INTO computer_history_settings(singleton, enabled) VALUES(1, 1);",
            )
            .unwrap();
        Self {
            connection: Arc::new(Mutex::new(connection)),
            cipher: Arc::new(XChaCha20Poly1305::new(Key::from_slice(&[7_u8; 32]))),
            last_error: Arc::new(Mutex::new(None)),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::neko::computer::model::{SemanticActionKind, SemanticActionOutcome};

    fn result() -> SemanticActResult {
        SemanticActResult {
            environment_id: "computer-test".to_string(),
            outcome: SemanticActionOutcome::Completed,
            code: None,
            detail: "not persisted".to_string(),
            action: SemanticActionKind::Invoke,
            target_ref: "app:browser".to_string(),
            before_state_version: "sha256:before".to_string(),
            after_state_version: "sha256:after".to_string(),
            verified: true,
            effect: Some("confirmed".to_string()),
            route: Some("workstation_launcher".to_string()),
            evidence: vec!["window_created".to_string()],
            escalation: None,
            visual_patch: None,
            clock: None,
            observation: None,
        }
    }

    #[test]
    fn encrypted_history_round_trips_without_persisting_detail() {
        let root = std::env::temp_dir().join(format!("wiii-history-{}", Uuid::new_v4()));
        let history = ComputerHistory::open(&root).unwrap();
        assert!(!history.status().unwrap().enabled);
        history.set_enabled(true).unwrap();
        history.append_action(&result()).unwrap();
        let page = history.query("computer-test", None, 10).unwrap();
        assert_eq!(page.entries.len(), 1);
        assert_eq!(page.entries[0].target_ref, "app:browser");
        let database = std::fs::read(root.join("computer-history-v1.sqlite3")).unwrap();
        assert!(!database
            .windows(b"not persisted".len())
            .any(|value| value == b"not persisted"));
        assert_eq!(history.delete("computer-test").unwrap(), 1);
        drop(history);
        let _ = std::fs::remove_dir_all(root);
    }
}
