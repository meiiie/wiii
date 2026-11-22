# Retire Work, preserve scoped conversations

Issue: [wiii#1072](https://github.com/meiiie/wiii/issues/1072).

The native desktop has no Work screen, menu or task launcher. Old conversations and retired Work snapshot bytes remain intact.

## Recovery acceptance

1. A genuine fixed-active-task conversation created before removal retains its transcript and original backend after upgrade and normal tray Quit/relaunch.
2. The existing explicit recovery button can recover a known Linux PID-1 task-writer lock only after native proof of physical quiescence, terminal execution and matching transcript, receipt and canonical root.
3. Active writers, unknown outcomes, changed/malformed checkpoints, uncertain receipts and unsupported lease formats remain blocked. No unscoped fallback, automatic load or prompt replay.
4. Recovery preserves checkpoint/receipt identity and only permits a later explicit send. A strict save failure stays locked and recovery remains retryable after a one-time lease removal.
5. Continuation must validate a fresh receipt, retain the same backend/context, and leave Work snapshot bytes unchanged. CI and risk-focused review must pass before merge.

## Non-goals

No Wiii Service, workspace/sidebar redesign, new Work management UI or Neko Core release/shutdown changes. No new cross-platform stale-lock policy beyond existing Linux PID-1 compatibility.
