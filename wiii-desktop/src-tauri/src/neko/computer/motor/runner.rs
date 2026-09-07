use super::model::{
    MotorCapabilityTier, MotorControlState, MotorDecision, MotorDecisionKind, MotorEvent,
    MotorEventKind, MotorFrame, MotorIntent, MotorLatencyReport, MotorLatencySample,
    MotorLeaseAuthority, MotorPercentiles, MotorRunReport, MotorStopReason, MOTOR_EVENT_SCHEMA,
};
use std::collections::{BTreeSet, HashMap};

pub trait MotorController {
    fn policy_id(&self) -> &str;
    fn tier(&self) -> MotorCapabilityTier;
    fn infer(
        &mut self,
        intent: &MotorIntent,
        frame: &MotorFrame,
        intent_age_us: u64,
    ) -> Result<MotorDecision, String>;
}

pub trait MotorSeat {
    fn apply(&mut self, control: &MotorControlState) -> Result<u64, String>;
    fn release_all(&mut self) -> Result<u64, String>;
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct MotorRunnerConfig {
    pub watchdog_us: u64,
    pub progress_every_frames: u64,
    pub allowed_keys: BTreeSet<String>,
}

impl Default for MotorRunnerConfig {
    fn default() -> Self {
        Self {
            watchdog_us: 250_000,
            progress_every_frames: 10,
            allowed_keys: BTreeSet::from([
                "ArrowDown".to_string(),
                "ArrowLeft".to_string(),
                "ArrowRight".to_string(),
                "ArrowUp".to_string(),
                "KeyA".to_string(),
                "KeyD".to_string(),
                "KeyS".to_string(),
                "KeyW".to_string(),
                "Space".to_string(),
            ]),
        }
    }
}

impl MotorRunnerConfig {
    pub fn validate(&self) -> Result<(), String> {
        if !(10_000..=5_000_000).contains(&self.watchdog_us) {
            return Err("Motor watchdog must be between 10ms and 5s".to_string());
        }
        if !(1..=10_000).contains(&self.progress_every_frames) {
            return Err("Motor progress cadence is outside the supported range".to_string());
        }
        if self.allowed_keys.is_empty() || self.allowed_keys.len() > 64 {
            return Err("Motor key allowlist must contain 1..=64 entries".to_string());
        }
        Ok(())
    }
}

struct ActiveRun {
    intent: MotorIntent,
    authority: MotorLeaseAuthority,
    started_at_us: u64,
    last_activity_at_us: u64,
    pending_frame: Option<MotorFrame>,
    last_submitted_sequence: u64,
    last_processed_sequence: u64,
    processed_frames: u64,
    dropped_frames: u64,
    stale_actions: u64,
    held_input: bool,
    cleanup_confirmed: bool,
    first_action_at_us: Option<u64>,
    last_action_at_us: Option<u64>,
    samples: Vec<MotorLatencySample>,
}

pub struct ContinuousMotorRunner<C: MotorController, S: MotorSeat> {
    controller: C,
    seat: S,
    config: MotorRunnerConfig,
    active: Option<ActiveRun>,
    operations: HashMap<String, MotorIntent>,
    terminal_events: HashMap<String, MotorEvent>,
    next_event_sequence: u64,
}

impl<C: MotorController, S: MotorSeat> ContinuousMotorRunner<C, S> {
    pub fn new(controller: C, seat: S, config: MotorRunnerConfig) -> Result<Self, String> {
        config.validate()?;
        let policy_id = controller.policy_id();
        if policy_id.is_empty()
            || policy_id.len() > 128
            || policy_id.chars().any(char::is_whitespace)
        {
            return Err("Motor controller policyId is invalid".to_string());
        }
        Ok(Self {
            controller,
            seat,
            config,
            active: None,
            operations: HashMap::new(),
            terminal_events: HashMap::new(),
            next_event_sequence: 1,
        })
    }

    pub fn start(
        &mut self,
        intent: MotorIntent,
        authority: MotorLeaseAuthority,
        now_us: u64,
    ) -> Result<MotorEvent, String> {
        intent.validate()?;
        if let Some(existing) = self.operations.get(&intent.intent_id) {
            if existing != &intent {
                return Err("Motor intentId was already used for a different operation".to_string());
            }
            if let Some(event) = self.terminal_events.get(&intent.intent_id) {
                let mut replay = event.clone();
                replay.replayed = true;
                return Ok(replay);
            }
            if self
                .active
                .as_ref()
                .is_some_and(|run| run.intent.intent_id == intent.intent_id)
            {
                return Ok(self.event(
                    &intent.intent_id,
                    MotorEventKind::Started,
                    now_us,
                    None,
                    Some(intent.state_version.clone()),
                    None,
                    vec!["idempotent replay; existing motor session remains active".to_string()],
                    None,
                    true,
                ));
            }
        }
        authority.validate_for(&intent, now_us)?;
        if self.active.is_some() {
            return Err("A Motor session already owns the Computer seat".to_string());
        }
        self.operations
            .insert(intent.intent_id.clone(), intent.clone());
        self.active = Some(ActiveRun {
            intent: intent.clone(),
            authority,
            started_at_us: now_us,
            last_activity_at_us: now_us,
            pending_frame: None,
            last_submitted_sequence: 0,
            last_processed_sequence: 0,
            processed_frames: 0,
            dropped_frames: 0,
            stale_actions: 0,
            held_input: false,
            cleanup_confirmed: false,
            first_action_at_us: None,
            last_action_at_us: None,
            samples: vec![],
        });
        Ok(self.event(
            &intent.intent_id,
            MotorEventKind::Started,
            now_us,
            None,
            Some(intent.state_version),
            None,
            vec!["bounded local motor controller started".to_string()],
            None,
            false,
        ))
    }

    pub fn submit_frame(&mut self, frame: MotorFrame) -> Result<bool, String> {
        frame.validate()?;
        let run = self
            .active
            .as_mut()
            .ok_or_else(|| "No active Motor session".to_string())?;
        if frame.target_ref != run.intent.target_ref {
            return Err("Motor frame belongs to a different target surface".to_string());
        }
        if frame.sequence <= run.last_submitted_sequence {
            run.dropped_frames = run.dropped_frames.saturating_add(1);
            return Ok(false);
        }
        if run.pending_frame.replace(frame.clone()).is_some() {
            run.dropped_frames = run.dropped_frames.saturating_add(1);
        }
        run.last_submitted_sequence = frame.sequence;
        Ok(true)
    }

    pub fn step(&mut self, now_us: u64) -> Result<Option<MotorEvent>, String> {
        let stop = {
            let run = self
                .active
                .as_ref()
                .ok_or_else(|| "No active Motor session".to_string())?;
            if now_us >= run.authority.expires_at_us {
                Some(MotorStopReason::LeaseLost)
            } else if now_us.saturating_sub(run.started_at_us)
                >= u64::from(run.intent.horizon_ms) * 1000
            {
                Some(MotorStopReason::HorizonExpired)
            } else if run.pending_frame.is_none()
                && now_us.saturating_sub(run.last_activity_at_us) >= self.config.watchdog_us
            {
                Some(MotorStopReason::WatchdogExpired)
            } else {
                None
            }
        };
        if let Some(reason) = stop {
            return self.stop(reason, now_us).map(Some);
        }

        let frame = match self
            .active
            .as_mut()
            .and_then(|run| run.pending_frame.take())
        {
            Some(frame) => frame,
            None => return Ok(None),
        };
        let intent = self.active.as_ref().unwrap().intent.clone();
        let intent_age_us = now_us.saturating_sub(self.active.as_ref().unwrap().started_at_us);
        let decision = match self.controller.infer(&intent, &frame, intent_age_us) {
            Ok(decision) => decision,
            Err(_) => {
                return self
                    .stop(MotorStopReason::ControllerFailed, now_us)
                    .map(Some)
            }
        };
        if decision.validate(&self.config.allowed_keys).is_err() {
            return self
                .stop(MotorStopReason::ControllerFailed, now_us)
                .map(Some);
        }
        if decision.frame_sequence != frame.sequence {
            if let Some(run) = self.active.as_mut() {
                run.stale_actions = run.stale_actions.saturating_add(1);
            }
            return Ok(None);
        }
        if self
            .active
            .as_ref()
            .is_some_and(|run| frame.sequence <= run.last_processed_sequence)
        {
            if let Some(run) = self.active.as_mut() {
                run.stale_actions = run.stale_actions.saturating_add(1);
            }
            return Ok(None);
        }
        let dispatch_us = match self.seat.apply(&decision.control) {
            Ok(duration) => duration,
            Err(_) => return self.stop(MotorStopReason::DispatchFailed, now_us).map(Some),
        };
        let completed_at_us = now_us
            .saturating_add(decision.inference_us)
            .saturating_add(dispatch_us);
        let sample = MotorLatencySample {
            capture_us: frame
                .captured_at_us
                .saturating_sub(frame.capture_started_at_us),
            inference_us: decision.inference_us,
            dispatch_us,
            end_to_end_us: completed_at_us.saturating_sub(frame.capture_started_at_us),
            intent_age_us,
        };
        let should_report = {
            let run = self.active.as_mut().unwrap();
            run.last_processed_sequence = frame.sequence;
            run.processed_frames = run.processed_frames.saturating_add(1);
            run.last_activity_at_us = completed_at_us;
            run.held_input = !decision.control.held_keys.is_empty()
                || decision
                    .control
                    .pointer
                    .as_ref()
                    .is_some_and(|pointer| !pointer.held_buttons.is_empty());
            run.first_action_at_us.get_or_insert(completed_at_us);
            run.last_action_at_us = Some(completed_at_us);
            run.samples.push(sample);
            run.processed_frames
                .is_multiple_of(self.config.progress_every_frames)
        };
        let terminal = match decision.kind {
            MotorDecisionKind::Continue => None,
            MotorDecisionKind::GoalReached => Some(MotorStopReason::GoalReached),
            MotorDecisionKind::Blocked => Some(MotorStopReason::Blocked),
            MotorDecisionKind::Uncertain => Some(MotorStopReason::Uncertain),
        };
        if let Some(reason) = terminal {
            return self.stop(reason, completed_at_us).map(Some);
        }
        if should_report {
            let report = self.current_report(None);
            return Ok(Some(self.event(
                &intent.intent_id,
                MotorEventKind::Progress,
                completed_at_us,
                None,
                Some(frame.state_version),
                Some(decision.confidence_per_mille),
                decision.evidence,
                report,
                false,
            )));
        }
        Ok(None)
    }

    pub fn interrupt(
        &mut self,
        reason: MotorStopReason,
        now_us: u64,
    ) -> Result<MotorEvent, String> {
        if !matches!(
            reason,
            MotorStopReason::Cancelled
                | MotorStopReason::HumanTakeover
                | MotorStopReason::PolicyBoundary
                | MotorStopReason::SurfaceLost
                | MotorStopReason::LeaseLost
                | MotorStopReason::ProjectRevoked
        ) {
            return Err("Motor interrupt reason is not externally actionable".to_string());
        }
        self.stop(reason, now_us)
    }

    pub fn is_active(&self) -> bool {
        self.active.is_some()
    }

    pub fn terminal_event(&self, intent_id: &str) -> Option<&MotorEvent> {
        self.terminal_events.get(intent_id)
    }

    pub fn into_parts(self) -> (C, S) {
        (self.controller, self.seat)
    }

    fn stop(&mut self, reason: MotorStopReason, now_us: u64) -> Result<MotorEvent, String> {
        let mut run = self
            .active
            .take()
            .ok_or_else(|| "No active Motor session".to_string())?;
        let release_result = self.seat.release_all();
        run.held_input = false;
        run.cleanup_confirmed = release_result.is_ok();
        let event_kind = match reason {
            MotorStopReason::GoalReached => MotorEventKind::Terminated,
            MotorStopReason::Blocked => MotorEventKind::Blocked,
            MotorStopReason::Uncertain => MotorEventKind::Uncertain,
            _ => MotorEventKind::Interrupted,
        };
        let evidence = if run.cleanup_confirmed {
            vec!["all held input released".to_string()]
        } else {
            vec!["held-input release could not be confirmed".to_string()]
        };
        let report = Some(build_report(
            &run,
            self.controller.policy_id(),
            self.controller.tier(),
            Some(reason.clone()),
        ));
        let event = self.event(
            &run.intent.intent_id,
            event_kind,
            now_us,
            Some(reason),
            None,
            None,
            evidence,
            report,
            false,
        );
        self.terminal_events
            .insert(run.intent.intent_id.clone(), event.clone());
        if release_result.is_err() {
            return Err("Motor stopped but held-input cleanup could not be confirmed".to_string());
        }
        Ok(event)
    }

    fn current_report(&self, reason: Option<MotorStopReason>) -> Option<MotorRunReport> {
        self.active.as_ref().map(|run| {
            build_report(
                run,
                self.controller.policy_id(),
                self.controller.tier(),
                reason,
            )
        })
    }

    #[allow(clippy::too_many_arguments)]
    fn event(
        &mut self,
        intent_id: &str,
        kind: MotorEventKind,
        at_us: u64,
        reason: Option<MotorStopReason>,
        state_version: Option<String>,
        confidence_per_mille: Option<u16>,
        evidence: Vec<String>,
        report: Option<MotorRunReport>,
        replayed: bool,
    ) -> MotorEvent {
        let event = MotorEvent {
            schema_version: MOTOR_EVENT_SCHEMA.to_string(),
            sequence: self.next_event_sequence,
            intent_id: intent_id.to_string(),
            kind,
            at_us,
            state_version,
            reason,
            confidence_per_mille,
            policy_id: self.controller.policy_id().to_string(),
            tier: self.controller.tier(),
            replayed,
            evidence,
            report,
        };
        self.next_event_sequence = self.next_event_sequence.saturating_add(1);
        event
    }
}

fn build_report(
    run: &ActiveRun,
    policy_id: &str,
    tier: MotorCapabilityTier,
    stop_reason: Option<MotorStopReason>,
) -> MotorRunReport {
    let achieved_hz = match (run.first_action_at_us, run.last_action_at_us) {
        (Some(first), Some(last)) if run.processed_frames > 1 && last > first => {
            (run.processed_frames - 1) as f64 * 1_000_000.0 / (last - first) as f64
        }
        (Some(_), Some(last)) if last > run.started_at_us => {
            1_000_000.0 / (last - run.started_at_us) as f64
        }
        _ => 0.0,
    };
    MotorRunReport {
        intent_id: run.intent.intent_id.clone(),
        policy_id: policy_id.to_string(),
        tier,
        processed_frames: run.processed_frames,
        dropped_frames: run.dropped_frames,
        stale_actions: run.stale_actions,
        achieved_hz,
        held_input_cleanup_confirmed: run.cleanup_confirmed,
        latency: latency_report(&run.samples),
        stop_reason,
    }
}

fn latency_report(samples: &[MotorLatencySample]) -> MotorLatencyReport {
    MotorLatencyReport {
        capture: percentiles(samples.iter().map(|sample| sample.capture_us)),
        inference: percentiles(samples.iter().map(|sample| sample.inference_us)),
        dispatch: percentiles(samples.iter().map(|sample| sample.dispatch_us)),
        end_to_end: percentiles(samples.iter().map(|sample| sample.end_to_end_us)),
    }
}

fn percentiles(values: impl Iterator<Item = u64>) -> MotorPercentiles {
    let mut values = values.collect::<Vec<_>>();
    values.sort_unstable();
    MotorPercentiles {
        p50_us: percentile(&values, 50),
        p95_us: percentile(&values, 95),
        p99_us: percentile(&values, 99),
    }
}

fn percentile(values: &[u64], percentile: usize) -> u64 {
    if values.is_empty() {
        return 0;
    }
    let rank = (percentile * values.len()).div_ceil(100);
    values[rank.saturating_sub(1).min(values.len() - 1)]
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::neko::computer::motor::{
        MotorGoal, MotorGoalKind, MotorInterrupt, MotorRisk, MotorTermination, MOTOR_INTENT_SCHEMA,
    };

    #[derive(Default)]
    struct FakeSeat {
        applied: Vec<MotorControlState>,
        release_count: usize,
        fail_dispatch: bool,
    }

    impl MotorSeat for FakeSeat {
        fn apply(&mut self, control: &MotorControlState) -> Result<u64, String> {
            if self.fail_dispatch {
                return Err("simulated dispatch failure".to_string());
            }
            self.applied.push(control.clone());
            Ok(1_000)
        }

        fn release_all(&mut self) -> Result<u64, String> {
            self.release_count += 1;
            Ok(500)
        }
    }

    struct FakeController {
        next_kind: MotorDecisionKind,
        wrong_frame: bool,
        invalid_key: bool,
    }

    impl MotorController for FakeController {
        fn policy_id(&self) -> &str {
            "fake-deterministic-v1"
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
            Ok(MotorDecision {
                frame_sequence: if self.wrong_frame {
                    frame.sequence.saturating_sub(1)
                } else {
                    frame.sequence
                },
                inference_us: 20_000,
                confidence_per_mille: 900,
                kind: self.next_kind.clone(),
                control: MotorControlState {
                    held_keys: vec![if self.invalid_key { "KeyX" } else { "KeyW" }.to_string()],
                    pointer: None,
                },
                evidence: vec!["fake controller observed forward route".to_string()],
            })
        }
    }

    fn intent(id: &str) -> MotorIntent {
        MotorIntent {
            schema_version: MOTOR_INTENT_SCHEMA.to_string(),
            intent_id: id.to_string(),
            state_version: "sha256:initial".to_string(),
            target_ref: "surface:canvas".to_string(),
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

    fn authority() -> MotorLeaseAuthority {
        MotorLeaseAuthority {
            environment_id: "environment-1".to_string(),
            lease_id: "lease-1".to_string(),
            project_id: "project-1".to_string(),
            target_ref: "surface:canvas".to_string(),
            expires_at_us: 10_000_000,
        }
    }

    fn frame(sequence: u64, captured_at_us: u64) -> MotorFrame {
        MotorFrame {
            sequence,
            state_version: format!("sha256:frame-{sequence}"),
            target_ref: "surface:canvas".to_string(),
            content_digest: format!("sha256:pixels-{sequence}"),
            width: 192,
            height: 192,
            capture_started_at_us: captured_at_us - 5_000,
            captured_at_us,
        }
    }

    fn build_runner(
        next_kind: MotorDecisionKind,
    ) -> ContinuousMotorRunner<FakeController, FakeSeat> {
        ContinuousMotorRunner::new(
            FakeController {
                next_kind,
                wrong_frame: false,
                invalid_key: false,
            },
            FakeSeat::default(),
            MotorRunnerConfig {
                progress_every_frames: 1,
                ..MotorRunnerConfig::default()
            },
        )
        .unwrap()
    }

    #[test]
    fn newest_frame_wins_and_latency_is_reported() {
        let mut runner = build_runner(MotorDecisionKind::Continue);
        runner
            .start(intent("intent-newest"), authority(), 100_000)
            .unwrap();
        runner.submit_frame(frame(1, 110_000)).unwrap();
        runner.submit_frame(frame(2, 120_000)).unwrap();
        runner.submit_frame(frame(3, 130_000)).unwrap();

        let event = runner.step(135_000).unwrap().unwrap();
        let report = event.report.unwrap();
        assert_eq!(report.processed_frames, 1);
        assert_eq!(report.dropped_frames, 2);
        assert_eq!(report.stale_actions, 0);
        assert_eq!(report.latency.capture.p95_us, 5_000);
        assert_eq!(report.latency.inference.p95_us, 20_000);
        assert_eq!(report.latency.dispatch.p95_us, 1_000);
        assert_eq!(report.latency.end_to_end.p95_us, 31_000);
    }

    #[test]
    fn human_takeover_releases_held_input_immediately() {
        let mut runner = build_runner(MotorDecisionKind::Continue);
        runner
            .start(intent("intent-human"), authority(), 100_000)
            .unwrap();
        runner.submit_frame(frame(1, 110_000)).unwrap();
        runner.step(115_000).unwrap();

        let event = runner
            .interrupt(MotorStopReason::HumanTakeover, 140_000)
            .unwrap();
        assert_eq!(event.kind, MotorEventKind::Interrupted);
        assert_eq!(event.reason, Some(MotorStopReason::HumanTakeover));
        assert!(event.report.as_ref().unwrap().held_input_cleanup_confirmed);
        let (_, seat) = runner.into_parts();
        assert_eq!(seat.release_count, 1);
    }

    #[test]
    fn watchdog_and_dispatch_failure_fail_closed() {
        let mut runner = build_runner(MotorDecisionKind::Continue);
        runner
            .start(intent("intent-watchdog"), authority(), 100_000)
            .unwrap();
        let event = runner.step(350_000).unwrap().unwrap();
        assert_eq!(event.reason, Some(MotorStopReason::WatchdogExpired));
        let (_, seat) = runner.into_parts();
        assert_eq!(seat.release_count, 1);

        let mut runner = build_runner(MotorDecisionKind::Continue);
        runner.seat.fail_dispatch = true;
        runner
            .start(intent("intent-dispatch"), authority(), 100_000)
            .unwrap();
        runner.submit_frame(frame(1, 110_000)).unwrap();
        let event = runner.step(115_000).unwrap().unwrap();
        assert_eq!(event.reason, Some(MotorStopReason::DispatchFailed));
        let (_, seat) = runner.into_parts();
        assert_eq!(seat.release_count, 1);
    }

    #[test]
    fn operation_identity_is_replay_safe_and_collision_safe() {
        let mut runner = build_runner(MotorDecisionKind::GoalReached);
        let request = intent("intent-idempotent");
        runner.start(request.clone(), authority(), 100_000).unwrap();
        runner.submit_frame(frame(1, 110_000)).unwrap();
        let terminal = runner.step(115_000).unwrap().unwrap();
        assert_eq!(terminal.reason, Some(MotorStopReason::GoalReached));

        let mut expired_authority = authority();
        expired_authority.expires_at_us = 150_000;
        let replay = runner
            .start(request.clone(), expired_authority, 200_000)
            .unwrap();
        assert!(replay.replayed);
        assert_eq!(replay.sequence, terminal.sequence);

        let mut collision = request;
        collision.goal.instruction = "follow the visible target".to_string();
        assert!(runner
            .start(collision, authority(), 200_000)
            .unwrap_err()
            .contains("different operation"));
    }

    #[test]
    fn stale_controller_output_is_never_dispatched() {
        let mut runner = build_runner(MotorDecisionKind::Continue);
        runner.controller.wrong_frame = true;
        runner
            .start(intent("intent-stale"), authority(), 100_000)
            .unwrap();
        runner.submit_frame(frame(2, 110_000)).unwrap();
        assert!(runner.step(115_000).unwrap().is_none());
        let (_, seat) = runner.into_parts();
        assert!(seat.applied.is_empty());
    }

    #[test]
    fn invalid_controller_output_fails_closed_and_releases_input() {
        let mut runner = build_runner(MotorDecisionKind::Continue);
        runner.controller.invalid_key = true;
        runner
            .start(intent("intent-invalid-output"), authority(), 100_000)
            .unwrap();
        runner.submit_frame(frame(1, 110_000)).unwrap();
        let event = runner.step(115_000).unwrap().unwrap();
        assert_eq!(event.reason, Some(MotorStopReason::ControllerFailed));
        assert!(event.report.as_ref().unwrap().held_input_cleanup_confirmed);
        let (_, seat) = runner.into_parts();
        assert!(seat.applied.is_empty());
        assert_eq!(seat.release_count, 1);
    }
}
