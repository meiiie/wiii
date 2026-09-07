use serde::Serialize;
use std::collections::BTreeSet;
use wiii_desktop_lib::realtime_motor::{
    ContinuousMotorRunner, MotorCapabilityTier, MotorControlState, MotorController, MotorDecision,
    MotorDecisionKind, MotorEvent, MotorFrame, MotorGoal, MotorGoalKind, MotorIntent,
    MotorInterrupt, MotorLeaseAuthority, MotorRisk, MotorRunReport, MotorRunnerConfig, MotorSeat,
    MotorStopReason, MotorTermination, MOTOR_INTENT_SCHEMA,
};

#[derive(Default)]
struct FakeSeat {
    releases: u64,
}

impl MotorSeat for FakeSeat {
    fn apply(&mut self, _control: &MotorControlState) -> Result<u64, String> {
        Ok(1_000)
    }

    fn release_all(&mut self) -> Result<u64, String> {
        self.releases += 1;
        Ok(500)
    }
}

struct FakeController {
    decisions: u64,
    terminate_after: Option<u64>,
}

impl MotorController for FakeController {
    fn policy_id(&self) -> &str {
        "fake-reactive-cpu-v1"
    }

    fn tier(&self) -> MotorCapabilityTier {
        MotorCapabilityTier::ReactiveCpu
    }

    fn infer(
        &mut self,
        _intent: &MotorIntent,
        frame: &MotorFrame,
        _intent_age_us: u64,
    ) -> Result<MotorDecision, String> {
        self.decisions += 1;
        let kind = if self.terminate_after == Some(self.decisions) {
            MotorDecisionKind::GoalReached
        } else {
            MotorDecisionKind::Continue
        };
        Ok(MotorDecision {
            frame_sequence: frame.sequence,
            inference_us: 20_000,
            confidence_per_mille: 940,
            kind,
            control: MotorControlState {
                held_keys: vec!["KeyW".to_string()],
                pointer: None,
            },
            evidence: vec!["deterministic fake-controller decision".to_string()],
        })
    }
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct SafetyOutcome {
    reason: MotorStopReason,
    cleanup_confirmed: bool,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct BenchmarkOutput {
    schema_version: &'static str,
    mode: &'static str,
    incoming_hz: u64,
    target_control_hz: u64,
    report: MotorRunReport,
    watchdog: SafetyOutcome,
    human_takeover: SafetyOutcome,
    passed: bool,
}

fn intent(id: &str, horizon_ms: u32) -> MotorIntent {
    MotorIntent {
        schema_version: MOTOR_INTENT_SCHEMA.to_string(),
        intent_id: id.to_string(),
        state_version: "sha256:initial".to_string(),
        target_ref: "surface:fake-canvas".to_string(),
        goal: MotorGoal {
            kind: MotorGoalKind::Navigate,
            instruction: "reach the verified target".to_string(),
        },
        horizon_ms,
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

fn authority() -> MotorLeaseAuthority {
    MotorLeaseAuthority {
        environment_id: "environment-fake".to_string(),
        lease_id: "lease-fake".to_string(),
        project_id: "project-fake".to_string(),
        target_ref: "surface:fake-canvas".to_string(),
        expires_at_us: 30_000_000,
    }
}

fn frame(sequence: u64, captured_at_us: u64) -> MotorFrame {
    MotorFrame {
        sequence,
        state_version: format!("sha256:frame-{sequence}"),
        target_ref: "surface:fake-canvas".to_string(),
        content_digest: format!("sha256:pixels-{sequence}"),
        width: 192,
        height: 192,
        capture_started_at_us: captured_at_us - 3_000,
        captured_at_us,
    }
}

fn runner(terminate_after: Option<u64>) -> ContinuousMotorRunner<FakeController, FakeSeat> {
    ContinuousMotorRunner::new(
        FakeController {
            decisions: 0,
            terminate_after,
        },
        FakeSeat::default(),
        MotorRunnerConfig {
            watchdog_us: 250_000,
            progress_every_frames: 20,
            allowed_keys: BTreeSet::from(["KeyW".to_string()]),
        },
    )
    .expect("fake runner configuration must be valid")
}

fn cleanup(event: &MotorEvent) -> bool {
    event
        .report
        .as_ref()
        .is_some_and(|report| report.held_input_cleanup_confirmed)
}

fn main() {
    let start_us = 1_000_000;
    let mut continuous = runner(Some(200));
    continuous
        .start(
            intent("benchmark-continuous", 10_000),
            authority(),
            start_us,
        )
        .expect("continuous benchmark must start");
    let mut terminal = None;
    let mut sequence = 0;
    for control_tick in 0..200_u64 {
        let tick_start = start_us + control_tick * 50_000;
        for offset in [10_000_u64, 26_667, 43_334] {
            sequence += 1;
            continuous
                .submit_frame(frame(sequence, tick_start + offset))
                .expect("fake frame must be accepted");
        }
        if let Some(event) = continuous
            .step(tick_start + 44_334)
            .expect("continuous step must succeed")
        {
            if event.reason.is_some() {
                terminal = Some(event);
                break;
            }
        }
    }
    let report = terminal
        .expect("fake controller must terminate")
        .report
        .expect("terminal event must contain a report");

    let mut watchdog_runner = runner(None);
    watchdog_runner
        .start(intent("benchmark-watchdog", 1_500), authority(), start_us)
        .expect("watchdog benchmark must start");
    let watchdog_event = watchdog_runner
        .step(start_us + 250_000)
        .expect("watchdog step must succeed")
        .expect("watchdog must emit an event");
    let watchdog = SafetyOutcome {
        reason: watchdog_event.reason.clone().expect("watchdog reason"),
        cleanup_confirmed: cleanup(&watchdog_event),
    };

    let mut takeover_runner = runner(None);
    takeover_runner
        .start(intent("benchmark-takeover", 1_500), authority(), start_us)
        .expect("takeover benchmark must start");
    takeover_runner
        .submit_frame(frame(1, start_us + 10_000))
        .expect("takeover frame must be accepted");
    takeover_runner
        .step(start_us + 11_000)
        .expect("takeover action must run");
    let takeover_event = takeover_runner
        .interrupt(MotorStopReason::HumanTakeover, start_us + 20_000)
        .expect("human takeover must stop the runner");
    let human_takeover = SafetyOutcome {
        reason: takeover_event.reason.clone().expect("takeover reason"),
        cleanup_confirmed: cleanup(&takeover_event),
    };

    let passed = report.processed_frames == 200
        && report.dropped_frames == 400
        && report.stale_actions == 0
        && report.achieved_hz >= 20.0
        && report.latency.end_to_end.p95_us < 50_000
        && report.held_input_cleanup_confirmed
        && watchdog.reason == MotorStopReason::WatchdogExpired
        && watchdog.cleanup_confirmed
        && human_takeover.reason == MotorStopReason::HumanTakeover
        && human_takeover.cleanup_confirmed;
    let output = BenchmarkOutput {
        schema_version: "wiii-motor-benchmark.v1",
        mode: "deterministic_fake_continuous",
        incoming_hz: 60,
        target_control_hz: 20,
        report,
        watchdog,
        human_takeover,
        passed,
    };
    println!(
        "{}",
        serde_json::to_string_pretty(&output).expect("benchmark output must serialize")
    );
    if !passed {
        std::process::exit(1);
    }
}
