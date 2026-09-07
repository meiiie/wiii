use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use wiii_desktop_lib::gmail_signal_adapter::{
    GmailHistoryClient, GmailHistoryError, GmailHistoryPage, GmailReconciliationSnapshot,
    GmailSignalAdapter, GmailSyncOutcome,
};

struct BootstrapClient;

impl GmailHistoryClient for BootstrapClient {
    fn grant_is_active(&self, _account_grant_ref: &str) -> Result<bool, GmailHistoryError> {
        Ok(true)
    }

    fn current_history_id(&self, _account_grant_ref: &str) -> Result<String, GmailHistoryError> {
        Ok("100".to_string())
    }

    fn list_history(
        &self,
        _account_grant_ref: &str,
        _start_history_id: &str,
        _page_token: Option<&str>,
        _max_results: u32,
    ) -> Result<GmailHistoryPage, GmailHistoryError> {
        panic!("bootstrap must not read history")
    }

    fn reconcile(
        &self,
        _account_grant_ref: &str,
        _max_messages: usize,
    ) -> Result<GmailReconciliationSnapshot, GmailHistoryError> {
        panic!("bootstrap must not reconcile")
    }
}

#[test]
fn exported_gmail_adapter_bootstraps_only_an_encrypted_cursor() {
    let suffix = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let root = std::env::temp_dir().join(format!("wiii-gmail-adapter-contract-{suffix}"));
    let adapter = GmailSignalAdapter::open(&root, Arc::new(BootstrapClient)).unwrap();

    let report = adapter.sync("grant-mail").unwrap();
    assert_eq!(report.outcome, GmailSyncOutcome::Bootstrapped);
    assert_eq!(report.next_history_id.as_deref(), Some("100"));

    drop(adapter);
    let database = std::fs::read(root.join("signal-inbox-v1.sqlite3")).unwrap();
    assert!(!database
        .windows(b"grant-mail".len())
        .any(|window| window == b"grant-mail"));
    std::fs::remove_dir_all(root).unwrap();
}
