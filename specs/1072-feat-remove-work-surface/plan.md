# Implementation Plan: retired scoped recovery

**Branch**: `codex/1072-feat-remove-work-surface` | **Spec**: [spec.md](spec.md)

## Summary

Retain feature removal. Extend only explicit native compatibility recovery for known scoped PID-1 locks. Reuse the existing recovery button; never load or send during recovery.

## Technical Context

TypeScript/React/Zustand and Rust/Tauri; no new dependencies or durable schema. Read-only Core JSON checkpoint and retired Work snapshot, Wiii JSON transcript/mapping, native SQLite journal. Linux PID-namespace compatibility only; other platforms/formats fail closed. Bounded regular-file reads, no directory search to choose a lease and no provider call during recovery.

## Constitution Check

Pre-research/post-design: PASS. Native authority proves process/root facts; receipts remain correlation, not grants. History and unknown outcomes remain intact, no automatic replay/fallback. No tenant/Service changes. Issue-linked scope, explicit rollback and adversarial/native checks.

## Project Structure

- `src-tauri/src/neko/legacy_lease.rs`: select compatibility store from persisted scope; verify exact checkpoint/receipt/root, execution/attach correlation and namespace absence before removing one immutable dead lease.
- `src/neko/control-client.ts`: scoped recovery requires positive native proof; unsupported/no-op results cannot clear a mapping.
- `src/neko-chill/task-scope-mapping.ts`: writer-unavailable retry transition preserving backend/receipt identity.
- `src/neko-chill/stores/session-{native-recovery,recovery-actions}.ts`: existing affordance/actions; strict save before unlocking, restore blocked state on save failure.
- Focused Rust/Vitest tests plus real native upgrade acceptance.

Paths above are relative to `wiii-desktop/`. Supporting artifacts: [research](research.md), [data model](data-model.md), [contract](contracts/scoped-recovery.md), [verification](quickstart.md).

## Risk and rollback

Only one proven-dead compatibility lock may be removed. No transcript, checkpoint, Work snapshot or unknown native fact is deleted or rewritten. Revert restores blocked recovery; never recreate a removed dead lock. Later Core load still independently validates root, authority/configuration, expected activation and exclusive writer ownership.

## Verification

Focused Rust and Vitest regressions, TypeScript, full desktop tests/embed build, diff checks, genuine old-task native upgrade/explicit recovery/continuation and snapshot comparison. New CI and risk-focused review are required before merge. No constitutional exceptions.
