# Implementation Plan: Neko Durable Runtime Authority

**Branch**: `codex/941-feat-neko-durable-runtime` | **Date**: 2026-08-23 | **Spec**: `specs/941-neko-durable-runtime/spec.md`
**Issue**: #941

## Summary

### Same-conversation recovery follow-up (#1050)

Renderer hydration still cannot reattach an existing ACP transport. Rather than
hand debugging work to the user, offer **Dừng phiên cũ và tiếp tục**. Reuse native
`session/cancel` with its existing idempotency key, owned process-tree teardown
and terminal journal transaction; do not add PID-based control or another RPC.

- The control-client wrapper accepts an optional Task + exact AgentSession
  allowlist. Unscoped bootstrap/close behavior stays unchanged. Snapshot this
  allowlist before stopping; do not sweep unrelated or newly appeared sessions.
- Serialize recovery with the existing per-session close operation. Wait for
  dispatch/runtime holds, reject visible live ownership, stop selected orphans,
  then re-list and replay **all** authoritative executions of this Task. A
  cancellation receipt or missing record alone does not clear uncertainty.
- Keep `closePending` through a strict checkpoint save. The ephemeral
  `nativeRecoveryRequired` flag allows retry after a failed write; it is not
  stored as native truth and never authorizes dispatch. Retain replay cursors in
  memory across a partial write, preventing duplicated checkpoint sequences.
- Only then expose `exited`/ready-to-send in the same local session. Keep
  `backendSessionId`, task mapping, transcript and composer draft unchanged.
  The next explicit user send loads the saved conversation in a fresh process;
  recovery itself never starts a model turn or resumes the paused outbox.
- Native unavailability, unknown ownership, failed termination, missing active
  projections and invalid task admission fail closed with a retry action,
  without asking the user to inspect journals. No false stopped/reattached claim.

**Verification:** deferred native-stop + persistence gates, repeated clicks,
strict-write retry, stale/missing/uncertain catalogs, exact-scope cancellation,
UI action/progress, real native reload -> recover -> explicit same-chat reply.
Keep hard-restart/outbox-review safety coverage as a separate failure path.

**Risk / rollback:** reuse the native authority and existing additive facts;
no wire/schema or credential changes. Revert this action to the conservative
read-only restore state. Do not clear uncertain journal rows to recover a chat.

This is an incremental update of the existing feature plan/contracts, not a new
Spec Kit feature. The setup-plan template copy would overwrite this established
plan; its PowerShell wrapper is also unavailable on the Linux workstation.

### Original runtime slice

Replace the raw Tauri process utility exposed to `main` with an in-process
Rust `NekoRuntime`. Rust owns approved provider resolution, process/session
lifecycle, idempotency records and a replayable SQLite WAL lifecycle journal.
Current ACP and Codex protocol parsing remains TypeScript-side. No UI redesign,
worktree manager or standalone daemon is included.

## Technical Context

**Language/Version**: Rust 2021/Tauri 2; TypeScript 5/React 18

**Dependencies**: `rusqlite` with bundled SQLite, `uuid`, `chrono`; existing
Tauri events and provider adapters

**Storage**: one local SQLite database in the Tauri app-local-data directory;
WAL, foreign keys and bounded lifecycle records

**Testing**: Rust unit/integration tests, Vitest control-client/driver tests,
TypeScript, embed build and Tauri security-contract tests

**Target**: Windows, macOS and Linux desktop; browser continues to fail closed

## Constitution Check

- **I Native Runtime Ownership**: Rust/Neko becomes local lifecycle authority;
  provider protocols remain adapters. PASS.
- **II Living Memory With Tenant Safety**: no memory or tenant data changes;
  no provider credentials enter SQLite. PASS.
- **III Streaming-First UX**: existing live provider stream remains; durable
  lifecycle replay is additive. PASS.
- **IV Safe Tools And Host Control**: raw executable/PID capability is removed
  from the privileged WebView. PASS.
- **V Multi-Agent Change Discipline**: issue #941, one runtime/security slice,
  explicit non-goals, tests and rollback. PASS.

## Implementation shape

```text
src-tauri/src/neko/
|-- mod.rs              NekoRuntime facade and process ownership
|-- provider.rs         approved native provider catalog/probes
|-- journal.rs          SQLite schema, idempotency and replay
`-- lifecycle.rs        pure run/operation transitions and recovery

src-tauri/src/commands/neko_agent.rs
`-- provider/session/events commands only

src/neko/control-client.ts
`-- Tauri adapter using provider/session IDs, never program/args/PID
```

The runtime stores `Arc`-backed inner state so bounded stdout readers and
dedicated process monitors can update the same process table and journal.
Process exit is observed independently from pipe EOF. Tauri setup opens the
database and manages the runtime. App exit asks the runtime to cancel owned
processes.

## Migration and compatibility

The current Neko UI does not yet create ADE Task/Run/Environment records. Its
driver factory supplies namespaced `legacy-local/*` execution references to
the native service. This is a compatibility binding only and does not create
or claim Wiii ADE entities.

No visible message or provider session is rewritten. The new database starts
as an additive local lifecycle journal. Hydration may append a bounded
runtime-only reconciliation checkpoint after it consumes native replay. Those
new discriminators are written to `neko-chill-native-runtime.json`, not the
shared Workbench v2 transcript snapshot, so the previous desktop release can
still hydrate conversations during rollback. Unknown, unavailable or corrupt
journal/checkpoint state fails local Neko hydration instead of silently deleting
data or respawning an agent.

## Risk and rollback

- **Security**: highest risk is accidentally retaining a raw native command or
  leaking a resolved binary path. Contract tests inspect capabilities and
  serialized detection responses.
- **Durability**: SQLite is additive; no old data migration. Recovery never
  retries an uncertain operation.
- **Provider regression**: freeze the three current launch contracts in Rust
  tests and run affected TypeScript suites.
- **Rollback**: revert the complete PR/release. Do not restore raw spawn as a
  partial hotfix. The additive SQLite journal and native-checkpoint companion
  store can remain unused by older builds; the shared v2 transcript remains
  backward-readable.

## Verification

1. Rust tests for lifecycle, provider registry, journal ordering/replay,
   idempotency, recovery and schema secret exclusion.
2. Tauri security contract proving raw process permissions are absent.
3. Focused Vitest for control client, driver factory, session/runtime paths.
4. Full Rust and desktop tests, TypeScript, web/embed builds and hygiene.
5. No screenshot: this phase intentionally changes authority, not visible UI.
