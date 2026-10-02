# Verification
- [x] Reproduce native delta false unfinished-load after a history-only restart saved pending-load
- [x] Regression failed before: restore + strict save + restore must not fabricate load intent
- [x] Keep bound receipt as durable fact; no live runtime is restored
- [x] Preserve explicit begin-load strict-write gate, root/epoch checks, interrupted-load/recovery blocking
- [x] Mapping/store/persistence/recovery focused suite: 275 passed
- [x] Full frontend: 3567 passed / 232 files; tsc, frontend/embed/native QA builds passed
- [x] Native epsilon explicitly closed; two cold restarts retain bound receipt epoch 1, one cancelled native record, no auto-start
- [x] New explicit `again` loads same session/task/Run, epoch 2, fixture response; explicit End still works
- [x] Older ambiguous delta and other recovery-blocked records remain untouched and blocked

Native evidence: UX-13, UX-14 and readonly-restart-result.json in local QA reports. This validates a local fixture and the exact candidate Neko build, not live Bunny or cross-platform release readiness.
