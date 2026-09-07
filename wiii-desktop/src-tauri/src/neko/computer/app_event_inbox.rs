use super::model::{SignalAdmissionOutcome, SignalIngress, SignalKind, SignalPriority};
use super::signal_inbox::SignalInbox;
use super::watcher::{AppEventKind, WatcherBatch};
use chrono::{DateTime, Duration, SecondsFormat, Utc};

const SOURCE_ID: &str = "wiii.app-events.v1";
const SIGNAL_TTL_DAYS: i64 = 7;

#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub(crate) struct AppEventMaterialization {
    pub events: usize,
    pub inserted: usize,
    pub coalesced: usize,
    pub deduplicated: usize,
    pub gap_detected: bool,
}

#[derive(Clone)]
pub(crate) struct AppEventInboxAdapter {
    inbox: SignalInbox,
}

impl AppEventInboxAdapter {
    pub(crate) fn new(inbox: SignalInbox) -> Self {
        Self { inbox }
    }

    pub(crate) fn cursor(&self, environment_id: &str) -> Result<Option<String>, String> {
        Ok(self
            .inbox
            .cursor(SOURCE_ID, &workstation_authority(environment_id))?
            .map(|checkpoint| checkpoint.source_cursor))
    }

    pub(crate) fn materialize(
        &self,
        environment_id: &str,
        batch: WatcherBatch,
    ) -> Result<AppEventMaterialization, String> {
        let account_grant_ref = workstation_authority(environment_id);
        let mut inputs = batch
            .events
            .iter()
            .map(|event| {
                let observed_at = DateTime::parse_from_rfc3339(&event.observed_at)
                    .map(|value| value.with_timezone(&Utc))
                    .map_err(|_| "Computer app-event observedAt is invalid".to_string())?;
                Ok(SignalIngress {
                    source_id: SOURCE_ID.to_string(),
                    account_grant_ref: account_grant_ref.clone(),
                    app_id: event.app_id.clone(),
                    resource_ref: event.resource_ref.clone(),
                    kind: signal_kind(event.kind),
                    source_cursor: event.cursor.clone(),
                    dedupe_key: event.event_id.clone(),
                    observed_at: timestamp(observed_at),
                    available_at: None,
                    expires_at: timestamp(observed_at + Duration::days(SIGNAL_TTL_DAYS)),
                    priority_class: signal_priority(event.kind),
                    content_available: false,
                    gap_detected: batch.gap_detected,
                })
            })
            .collect::<Result<Vec<_>, String>>()?;

        if batch.gap_detected && inputs.is_empty() {
            let observed_at = Utc::now();
            inputs.push(SignalIngress {
                source_id: SOURCE_ID.to_string(),
                account_grant_ref: account_grant_ref.clone(),
                app_id: "workstation".to_string(),
                resource_ref: "workstation:main".to_string(),
                kind: SignalKind::Conflict,
                source_cursor: batch.cursor.clone(),
                dedupe_key: format!("reconcile:{}", batch.cursor),
                observed_at: timestamp(observed_at),
                available_at: None,
                expires_at: timestamp(observed_at + Duration::days(SIGNAL_TTL_DAYS)),
                priority_class: SignalPriority::High,
                content_available: false,
                gap_detected: true,
            });
        }

        let admissions = if inputs.is_empty() {
            self.inbox.advance_cursor(
                SOURCE_ID,
                &account_grant_ref,
                &batch.cursor,
                batch.gap_detected,
            )?;
            Vec::new()
        } else {
            let last_cursor = inputs
                .last()
                .map(|input| input.source_cursor.as_str())
                .unwrap_or_default();
            if last_cursor != batch.cursor {
                return Err(
                    "Computer app-event page cursor does not match its last event".to_string(),
                );
            }
            self.inbox.ingest_batch(inputs)?
        };

        let mut report = AppEventMaterialization {
            events: batch.events.len(),
            gap_detected: batch.gap_detected,
            ..AppEventMaterialization::default()
        };
        for admission in admissions {
            match admission.outcome {
                SignalAdmissionOutcome::Inserted => report.inserted += 1,
                SignalAdmissionOutcome::Coalesced => report.coalesced += 1,
                SignalAdmissionOutcome::Deduplicated => report.deduplicated += 1,
            }
        }
        Ok(report)
    }
}

fn workstation_authority(environment_id: &str) -> String {
    format!("workstation:{environment_id}")
}

fn signal_kind(kind: AppEventKind) -> SignalKind {
    match kind {
        AppEventKind::ContentChanged => SignalKind::ContentChanged,
        AppEventKind::StateChanged => SignalKind::StateChanged,
        AppEventKind::AttentionRequired => SignalKind::AttentionRequired,
    }
}

fn signal_priority(kind: AppEventKind) -> SignalPriority {
    match kind {
        AppEventKind::AttentionRequired => SignalPriority::High,
        AppEventKind::ContentChanged => SignalPriority::Normal,
        AppEventKind::StateChanged => SignalPriority::Low,
    }
}

fn timestamp(value: DateTime<Utc>) -> String {
    value.to_rfc3339_opts(SecondsFormat::Millis, true)
}

#[cfg(test)]
mod tests {
    use super::super::model::SignalInboxConsultRequest;
    use super::super::watcher::{AppEventSignal, WatcherSourceKind, APP_EVENTS_PROTOCOL};
    use super::*;

    fn batch(cursor: &str, gap_detected: bool, events: Vec<AppEventSignal>) -> WatcherBatch {
        WatcherBatch {
            source: WatcherSourceKind::AtSpi,
            source_id: "atspi".to_string(),
            cursor: cursor.to_string(),
            gap_detected,
            events,
        }
    }

    fn event(id: &str, cursor: &str, kind: AppEventKind) -> AppEventSignal {
        AppEventSignal {
            event_id: id.to_string(),
            cursor: cursor.to_string(),
            app_id: "browser".to_string(),
            resource_ref: "app:browser".to_string(),
            kind,
            observed_at: timestamp(Utc::now()),
        }
    }

    #[test]
    fn materializes_content_free_events_with_dedupe_and_cursor_resume() {
        let inbox = SignalInbox::in_memory();
        let adapter = AppEventInboxAdapter::new(inbox.clone());
        let source = batch(
            "atspi:0123456789abcdef:2",
            false,
            vec![
                event(
                    "event-1",
                    "atspi:0123456789abcdef:1",
                    AppEventKind::ContentChanged,
                ),
                event(
                    "event-2",
                    "atspi:0123456789abcdef:2",
                    AppEventKind::AttentionRequired,
                ),
            ],
        );
        let first = adapter
            .materialize("computer-neko", source.clone())
            .unwrap();
        let replay = adapter.materialize("computer-neko", source).unwrap();

        assert_eq!(first.events, 2);
        assert_eq!(first.inserted, 2);
        assert_eq!(replay.deduplicated, 2);
        assert_eq!(
            adapter.cursor("computer-neko").unwrap().as_deref(),
            Some("atspi:0123456789abcdef:2")
        );
        let summary = inbox
            .consult(SignalInboxConsultRequest { max_refs: 8 })
            .unwrap();
        assert_eq!(summary.ready_count, 2);
        assert_eq!(summary.gap_count, 0);
    }

    #[test]
    fn empty_restart_gap_becomes_one_reconciliation_signal() {
        let inbox = SignalInbox::in_memory();
        let adapter = AppEventInboxAdapter::new(inbox.clone());
        let report = adapter
            .materialize(
                "computer-neko",
                batch("atspi:fedcba9876543210:0", true, Vec::new()),
            )
            .unwrap();

        assert!(report.gap_detected);
        assert_eq!(report.inserted, 1);
        let summary = inbox
            .consult(SignalInboxConsultRequest { max_refs: 8 })
            .unwrap();
        assert_eq!(summary.gap_count, 1);
        assert_eq!(summary.ready_count, 1);
    }

    #[test]
    fn page_cursor_mismatch_fails_closed() {
        let adapter = AppEventInboxAdapter::new(SignalInbox::in_memory());
        let error = adapter
            .materialize(
                "computer-neko",
                batch(
                    "atspi:0123456789abcdef:2",
                    false,
                    vec![event(
                        "event-1",
                        "atspi:0123456789abcdef:1",
                        AppEventKind::StateChanged,
                    )],
                ),
            )
            .unwrap_err();
        assert!(error.contains("page cursor"));
    }

    #[test]
    fn protocol_name_stays_aligned_with_the_watcher_contract() {
        assert_eq!(APP_EVENTS_PROTOCOL, "dev.wiii.app-events.v1");
    }
}
