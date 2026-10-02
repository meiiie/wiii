# Local chat workflow completion

## Outcome
A user can start a local chat without selecting a source project, add or open another project, create a fresh conversation inside an existing project, find model controls and keep composing while work runs. A queued message must be visibly distinct from a sent message.

## Invariants
- User-facing project selection is optional; native agent execution always has an explicit root. Quick chats use a unique app-managed empty folder. Never default to home, cwd, or an unrelated recent project.
- No account, provider or permission is silently switched. Model options reflect runtime capability; configuration availability is not authentication proof.
- New-chat navigation must not dispatch, cancel an active session, or destroy its draft.
- Queue records bind session and workspace/task identity. Strict persistence precedes any claim of acceptance. Ambiguous delivery is not automatically retried. Stop/error/restart pauses delivery until explicit review.
- Existing Work/task receipts, epoch fencing, journal recovery, permission prompts and runtime ownership remain authoritative.
- No claim of absolute performance. Report measured environment, workload, samples and limits.

## Delivery slices
1. Explicit new-chat action per project and clearer entry/navigation.
2. Safe quick-chat workspace command, lifecycle and UI with restart coverage.
3. Durable session outbox and explicit controls, with failure and recovery tests.
4. Model/multiple-project native QA and measured performance, updated visual report.

## Risk / rollback
Keep each slice independently revertible. Additive metadata must preserve older snapshots. No deletion/migration of existing sessions/projects. Queue schema changes require backward-compatible readers; rollback must retain queued records for review, never discard pending user intent.
