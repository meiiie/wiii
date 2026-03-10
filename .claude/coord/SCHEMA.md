# Coordination Event Schema

`events.jsonl` is append-only. One JSON object per line.

## Required Fields

- `ts`: ISO-8601 timestamp with timezone
- `actor`: one of `architect`, `reviewer`, `claude-code`, `tester`, `watcher`
- `wave`: wave identifier, for example `WAVE-001`
- `type`: event type
- `status`: wave status
- `summary`: short human-readable message

## Optional Fields

- `links`: array of relative repo paths
- `artifacts`: array of relative repo paths
- `notes`: free-form short text

## Recommended Event Types

- `plan_updated`
- `task_ready`
- `run_started`
- `report_updated`
- `smoke_completed`
- `review_started`
- `review_completed`
- `wave_blocked`
- `wave_cancelled`

## Example

```json
{"ts":"2026-03-10T10:00:00+07:00","actor":"architect","wave":"WAVE-001","type":"task_ready","status":"READY","summary":"Capability boundary wave published","links":[".claude/coord/TASKS/WAVE-001.md"]}
{"ts":"2026-03-10T10:15:00+07:00","actor":"claude-code","wave":"WAVE-001","type":"run_started","status":"RUNNING","summary":"Started implementation"}
{"ts":"2026-03-10T11:20:00+07:00","actor":"claude-code","wave":"WAVE-001","type":"report_updated","status":"REVIEW_NEEDED","summary":"Implementation and smoke report ready","links":[".claude/coord/REPORTS/WAVE-001.md"]}
{"ts":"2026-03-10T11:50:00+07:00","actor":"architect","wave":"WAVE-001","type":"review_completed","status":"APPROVED","summary":"Wave approved","links":[".claude/coord/REVIEW/WAVE-001.md"]}
```

## Status Authority

- `events.jsonl` is the machine-readable source of truth for current wave status.
- `REVIEW/*.md` is the human-readable source of truth for approval reasoning.

If they differ, review files win for interpretation and events must be corrected by appending a new event.

