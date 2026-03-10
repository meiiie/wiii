# Coordination Mailbox Protocol

This directory is the shared mailbox between the architect/reviewer role and the Claude Code implementation team.

The protocol is intentionally file-based:
- Markdown files are for humans.
- `events.jsonl` is for machines and watchers.
- `STATUS.md` is generated and must not be edited manually.

## Directory Layout

```text
.claude/coord/
|- PLAN.md
|- STATUS.md
|- SCHEMA.md
|- events.jsonl
|- TASKS/
|  |- WAVE-000-TEMPLATE.md
|- REPORTS/
|  |- WAVE-000-TEMPLATE.md
|- REVIEW/
|  |- WAVE-000-TEMPLATE.md
```

## Ownership Rules

- Architect/reviewer writes:
  - `PLAN.md`
  - `TASKS/*.md`
  - `REVIEW/*.md`
- Claude Code implementation team writes:
  - `REPORTS/*.md`
  - `events.jsonl`
- Watcher script writes:
  - `STATUS.md`

Do not edit files outside your ownership zone unless explicitly requested.

## Wave State Machine

Each wave must move through these states:

1. `DRAFT`
2. `READY`
3. `RUNNING`
4. `REVIEW_NEEDED`
5. `APPROVED`

Optional failure states:
- `REJECTED`
- `BLOCKED`
- `CANCELLED`

No implementation wave may start unless the previous wave is `APPROVED` or explicitly `CANCELLED`.

## Standard Flow

1. Architect updates `PLAN.md`.
2. Architect creates `TASKS/WAVE-xxx.md` and appends a `task_ready` event.
3. Claude Code team implements and updates `REPORTS/WAVE-xxx.md`.
4. Claude Code team appends machine-readable events to `events.jsonl`.
5. Watcher script regenerates `STATUS.md`.
6. Architect reviews the report and writes `REVIEW/WAVE-xxx.md`.
7. Architect appends `review_completed` event with `APPROVED`, `REJECTED`, or `BLOCKED`.

## Required Deliverables Per Wave

Every implementation wave should provide:
- files changed
- architecture summary
- smoke/test summary
- screenshot links if UI changed
- raw SSE or execution trace if stream/tool behavior changed
- known issues / residual risks

## Generated Files

- `STATUS.md` is generated from `events.jsonl` and filesystem presence.
- Do not manually edit `STATUS.md`; use the watcher or `-Once` render mode instead.

## Minimal Commands

Render status one time:

```powershell
powershell -ExecutionPolicy Bypass -File .claude/scripts/coord-watch.ps1 -Once
```

Run watcher in background terminal:

```powershell
powershell -ExecutionPolicy Bypass -File .claude/scripts/coord-watch.ps1
```

