use serde_json::Value;
use std::{fs, path::PathBuf};

fn tauri_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn read_json(relative: &str) -> Value {
    let path = tauri_root().join(relative);
    let text = fs::read_to_string(&path)
        .unwrap_or_else(|error| panic!("failed to read {}: {error}", path.display()));
    serde_json::from_str(&text)
        .unwrap_or_else(|error| panic!("failed to parse {}: {error}", path.display()))
}

#[test]
fn csp_is_enabled_with_required_fail_closed_directives() {
    let config = read_json("tauri.conf.json");
    let csp = config["app"]["security"]["csp"]
        .as_object()
        .expect("desktop CSP must be a directive map");

    assert_eq!(csp["object-src"], "'none'");
    assert_eq!(csp["base-uri"], "'self'");
    assert_eq!(csp["form-action"], "'self'");
    assert!(!csp["script-src"]
        .as_str()
        .unwrap_or_default()
        .contains("'unsafe-eval'"));
}

#[test]
fn splash_has_only_its_startup_command_and_notification_permission_query() {
    let splash = read_json("capabilities/splash.json");
    assert_eq!(splash["windows"], serde_json::json!(["splashscreen"]));
    assert_eq!(
        splash["permissions"],
        serde_json::json!([
            "allow-close-splash",
            "notification:allow-is-permission-granted"
        ])
    );
}

#[test]
fn every_workbench_capability_excludes_the_splash_window() {
    for name in [
        "workbench-base",
        "workbench-files",
        "workbench-network",
        "workbench-agents",
        "workbench-computer",
        "workbench-notifications",
        "workbench-models",
    ] {
        let capability = read_json(&format!("capabilities/{name}.json"));
        assert_eq!(capability["windows"], serde_json::json!(["main"]), "{name}");
    }
}

#[test]
fn application_quit_is_granted_only_to_the_main_workbench() {
    for entry in fs::read_dir(tauri_root().join("capabilities")).unwrap() {
        let path = entry.unwrap().path();
        if path.extension().and_then(|value| value.to_str()) != Some("json") {
            continue;
        }
        let capability: Value = serde_json::from_str(&fs::read_to_string(&path).unwrap()).unwrap();
        let can_quit = capability["permissions"]
            .as_array()
            .unwrap()
            .iter()
            .any(|permission| {
                permission
                    .as_str()
                    .or_else(|| permission.get("identifier").and_then(Value::as_str))
                    == Some("allow-quit-app")
            });
        if can_quit {
            assert_eq!(capability["identifier"], "workbench-base");
            assert_eq!(capability["windows"], serde_json::json!(["main"]));
        }
    }
    let base = read_json("capabilities/workbench-base.json");
    assert!(base["permissions"]
        .as_array()
        .unwrap()
        .contains(&serde_json::json!("allow-quit-app")));
}

#[test]
fn local_model_configuration_is_granted_only_to_the_main_workbench() {
    for entry in fs::read_dir(tauri_root().join("capabilities")).unwrap() {
        let path = entry.unwrap().path();
        if path.extension().and_then(|value| value.to_str()) != Some("json") {
            continue;
        }
        let capability: Value = serde_json::from_str(&fs::read_to_string(path).unwrap()).unwrap();
        for permission in capability["permissions"].as_array().unwrap() {
            let id = permission
                .as_str()
                .or_else(|| permission.get("identifier").and_then(Value::as_str));
            if matches!(
                id,
                Some("allow-local-model-status" | "allow-local-model-save")
            ) {
                assert_eq!(capability["identifier"], "workbench-models");
                assert_eq!(capability["windows"], serde_json::json!(["main"]));
            }
        }
    }
    assert_eq!(
        read_json("capabilities/workbench-models.json")["permissions"],
        serde_json::json!(["allow-local-model-status", "allow-local-model-save"])
    );
}

#[test]
fn native_http_scope_has_no_global_remote_wildcard() {
    let network = read_json("capabilities/workbench-network.json");
    let rendered = serde_json::to_string(&network).expect("network capability is serializable");
    assert!(!rendered.contains("https://**"));
    assert!(rendered.contains("https://wiii.holilihu.online/**"));
}

#[test]
fn tauri_config_enables_only_the_reviewed_capability_set() {
    let config = read_json("tauri.conf.json");
    assert_eq!(
        config["app"]["security"]["capabilities"],
        serde_json::json!([
            "splash",
            "workbench-base",
            "workbench-files",
            "workbench-network",
            "workbench-agents",
            "workbench-computer",
            "workbench-notifications",
            "workbench-models"
        ])
    );
}

#[test]
fn main_webview_has_no_raw_agent_process_primitive() {
    let agents = read_json("capabilities/workbench-agents.json");
    let windows = agents["windows"]
        .as_array()
        .expect("agent capability declares windows");
    assert_eq!(windows, serde_json::json!(["main"]).as_array().unwrap());
    let permissions = agents["permissions"]
        .as_array()
        .expect("agent capability declares permissions")
        .iter()
        .map(|entry| {
            entry
                .as_str()
                .or_else(|| entry.get("identifier").and_then(serde_json::Value::as_str))
                .expect("permission is a string or scoped identifier")
        })
        .collect::<Vec<_>>();

    let mut granted = permissions;
    granted.sort_unstable();
    let mut reviewed = vec![
        "allow-neko-control-provider-list",
        "allow-neko-control-provider-profiles",
        "allow-neko-control-provider-sessions",
        "allow-neko-control-session-list",
        "allow-neko-control-session-start",
        "allow-neko-control-session-write",
        "allow-neko-control-session-cancel",
        // Session-only legacy migration: native proof, no caller PID/path.
        "allow-neko-control-legacy-lease-recover",
        "allow-neko-control-events-read",
    ];
    reviewed.sort_unstable();
    assert_eq!(
        granted, reviewed,
        "agent capability grants an unreviewed permission set"
    );
}

#[test]
fn main_webview_computer_authority_is_explicit_and_coworker_grant_scoped() {
    let computer = read_json("capabilities/workbench-computer.json");
    assert_eq!(computer["windows"], serde_json::json!(["main"]));

    let mut granted = computer["permissions"]
        .as_array()
        .expect("computer capability declares permissions")
        .iter()
        .map(|entry| {
            entry
                .as_str()
                .expect("computer permissions are identifiers")
        })
        .collect::<Vec<_>>();
    granted.sort_unstable();

    let mut reviewed = vec![
        "allow-neko-computer-app-events-poll",
        "allow-neko-computer-browser-navigate",
        "allow-neko-computer-coworker-status",
        "allow-neko-computer-doctor",
        "allow-neko-computer-ensure",
        "allow-neko-computer-events-read",
        "allow-neko-computer-history-delete",
        "allow-neko-computer-history-query",
        "allow-neko-computer-history-set-enabled",
        "allow-neko-computer-history-status",
        "allow-neko-computer-package-install",
        "allow-neko-computer-package-remove",
        "allow-neko-computer-project-grant",
        "allow-neko-computer-project-revoke",
        "allow-neko-computer-remove",
        "allow-neko-computer-reset",
        "allow-neko-computer-resume",
        "allow-neko-computer-seat-acquire",
        "allow-neko-computer-seat-release",
        "allow-neko-computer-semantic-act",
        "allow-neko-computer-semantic-observe",
        "allow-neko-computer-suspend",
        "allow-neko-computer-terminal-exec",
        "allow-neko-computer-work-plane-describe",
        "allow-neko-computer-work-plane-execute",
        "allow-neko-computer-work-plane-query",
        "allow-neko-signal-inbox-claim",
        "allow-neko-signal-inbox-consult",
        "allow-neko-signal-inbox-defer",
        "allow-neko-signal-inbox-resolve",
        "allow-neko-signal-inbox-revoke-account",
    ];
    reviewed.sort_unstable();

    assert_eq!(
        granted, reviewed,
        "computer capability grants an unreviewed permission set"
    );
}
