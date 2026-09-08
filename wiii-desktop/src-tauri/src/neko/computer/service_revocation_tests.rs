use super::super::model::{ComputerResources, SemanticActionKind, SemanticInputStep};
use super::*;
use std::time::{Duration, Instant};

const INPUT_EVENTS: &str = r#"python3 - <<'PY'
import sys
sys.path.insert(0, '/usr/local/lib/wiii-computer')
import semantic_bridge as bridge
with bridge.CdpConnection(bridge.active_browser_page()) as cdp:
    result = cdp.call('Runtime.evaluate', {'expression': 'JSON.stringify(window.wiiiInputEvents)', 'returnByValue': True})
    print(result['result']['value'])
PY"#;

fn read_events(provider: &LocalDockerComputerProvider, environment: &str) -> Result<Value, String> {
    let result = provider.terminal_exec(environment, INPUT_EVENTS)?;
    if result.exit_code != Some(0) {
        return Err(format!("fixture event read failed: {}", result.stderr));
    }
    serde_json::from_str(result.stdout.trim()).map_err(|error| error.to_string())
}

#[test]
#[ignore = "requires isolated Docker Computer and Chrome"]
fn live_takeover_preempts_native_action_and_preserves_profile() {
    assert_eq!(
        std::env::var("WIII_LIVE_REVOCATION_TEST").as_deref(),
        Ok("1")
    );
    let token = uuid::Uuid::new_v4().simple().to_string();
    let environment_id = format!("computer-revocation-{}", &token[..12]);
    let root = std::env::temp_dir().join(format!("wiii-revocation-{token}"));
    let project = root.join("project");
    std::fs::create_dir_all(&project).unwrap();
    let project = canonical_project(&project.to_string_lossy()).unwrap();
    let provider = Arc::new(LocalDockerComputerProvider::new(root.join("provider")));
    let service = NekoComputerService {
        history: ComputerHistory::in_memory(),
        signal_inbox: SignalInbox::in_memory(),
        journal: ComputerJournal::in_memory(),
        provider: provider.clone(),
        work_plane: provider.clone(),
        operations: Arc::new(Mutex::new(())),
        seats: Arc::new(Mutex::new(())),
    };
    let result = (|| -> Result<(), String> {
        let resources = ComputerResources::default();
        provider.ensure(&environment_id, &project, &resources)?;
        service.journal.upsert_environment(
            &environment_id,
            "Revocation fixture",
            &project.to_string_lossy(),
            ComputerState::Ready,
            &resources,
            "computer.ready",
        )?;
        let setup = provider.terminal_exec(&environment_id, r#"python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, '/usr/local/lib/wiii-computer')
import semantic_bridge as bridge
Path('/home/neko/.revocation-profile-marker').write_text('preserve-fixture-profile')
with bridge.CdpConnection(bridge.active_browser_page()) as cdp:
    cdp.call('Page.bringToFront')
    cdp.call('Runtime.evaluate', {'expression': "document.body.innerHTML='<input id=fixture>'; window.wiiiInputEvents=[]; for(const type of ['keydown','keyup']) document.addEventListener(type,e=>window.wiiiInputEvents.push([type,e.key])); document.querySelector('input').focus()"})
PY"#)?;
        if setup.exit_code != Some(0) {
            return Err(format!("fixture setup failed: {}", setup.stderr));
        }
        let snapshot = provider.semantic_observe(&SemanticObserveRequest {
            environment_id: environment_id.clone(),
            max_nodes: 4,
            scope_ref: Some("workstation:main".to_string()),
            continuation: None,
            since_state_version: None,
            known_node_versions: Vec::new(),
            visual_ref: None,
        })?;
        let browser = snapshot
            .nodes
            .iter()
            .find(|node| node.node_ref == "app:browser")
            .ok_or("Browser launcher missing")?;
        let seat = service.acquire_seat(SeatAcquireRequest {
            request_id: format!("acquire-{token}"),
            environment_id: environment_id.clone(),
            owner_id: "agent:revocation-test".to_string(),
            user_controlled: false,
        })?;
        let request = SemanticActRequest {
            request_id: format!("action-{token}"),
            environment_id: environment_id.clone(),
            lease_id: seat.lease_id.unwrap(),
            state_version: snapshot.state_version,
            target_ref: browser.node_ref.clone(),
            expected_role: browser.role.clone(),
            expected_name: browser.name.clone(),
            action: SemanticActionKind::InputSequence,
            text: None,
            key: None,
            return_observation: false,
            realtime_mode: None,
            input_sequence: ["a", "b", "c", "d"]
                .iter()
                .map(|key| SemanticInputStep {
                    keys: vec![key.to_string()],
                    hold_ms: 2000,
                    wait_ms: 0,
                })
                .collect(),
        };
        let action_service = service.clone();
        let running_request = request.clone();
        let action = std::thread::spawn(move || action_service.semantic_act(running_request));
        let began = Instant::now();
        let mut saw_input = false;
        while began.elapsed() < Duration::from_secs(15) {
            let events = read_events(&provider, &environment_id)?;
            if events.as_array().is_some_and(|events| !events.is_empty()) {
                saw_input = true;
                break;
            }
            if action.is_finished() {
                break;
            }
            std::thread::sleep(Duration::from_millis(40));
        }
        let takeover_started = Instant::now();
        let human = service.acquire_seat(SeatAcquireRequest {
            request_id: format!("takeover-{token}"),
            environment_id: environment_id.clone(),
            owner_id: "user:revocation-test".to_string(),
            user_controlled: true,
        });
        let takeover_elapsed = takeover_started.elapsed();
        let outcome = action.join().map_err(|_| "action thread panicked")??;
        let human = human?;
        if !saw_input {
            return Err(format!(
                "test did not observe an actual held key; outcome: {:?}; detail: {}",
                outcome.code, outcome.detail
            ));
        }
        if outcome.code.as_deref() != Some("semantic_lease_revoked") {
            return Err(format!(
                "active action was not interrupted: {:?}",
                outcome.code
            ));
        }
        if human.state != SeatState::UserControlled {
            return Err("human takeover was not recorded".to_string());
        }
        let events = read_events(&provider, &environment_id)?;
        let rows = events.as_array().ok_or("fixture event list missing")?;
        let downs = rows.iter().filter(|row| row[0] == "keydown").count();
        let ups = rows.iter().filter(|row| row[0] == "keyup").count();
        if downs == 0 || downs >= 4 || downs != ups {
            return Err(format!("held-input cleanup or preemption failed: {events}"));
        }
        let mut queued = request;
        queued.request_id = format!("queued-{token}");
        if service.semantic_act(queued.clone()).is_ok() {
            return Err("native accepted revoked lease".to_string());
        }
        if provider.semantic_act(&queued)?.code.as_deref() != Some("semantic_lease_revoked") {
            return Err("provider accepted queued revoked lease".to_string());
        }
        std::thread::sleep(Duration::from_millis(250));
        if read_events(&provider, &environment_id)? != events {
            return Err("input arrived after takeover acknowledgement".to_string());
        }
        let marker =
            provider.terminal_exec(&environment_id, "cat /home/neko/.revocation-profile-marker")?;
        if marker.stdout.trim() != "preserve-fixture-profile" {
            return Err("profile marker changed".to_string());
        }
        service.release_seat(SeatReleaseRequest {
            request_id: format!("release-{token}"),
            environment_id: environment_id.clone(),
            lease_id: human.lease_id.unwrap(),
        })?;
        eprintln!(
            "actual Chrome takeover: {} ms; key pairs: {}; no post-ack input; profile retained",
            takeover_elapsed.as_millis(),
            downs
        );
        Ok(())
    })();
    let cleanup = provider.destroy(&environment_id);
    if root.starts_with(std::env::temp_dir())
        && root
            .file_name()
            .unwrap()
            .to_string_lossy()
            .starts_with("wiii-revocation-")
    {
        let _ = std::fs::remove_dir_all(&root);
    }
    result.expect("live input revocation");
    cleanup.expect("remove only disposable revocation resources");
}
