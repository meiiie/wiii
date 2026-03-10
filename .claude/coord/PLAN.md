# Coordination Plan

Status: ACTIVE
Owner: architect
Last updated: 2026-03-10

## Objective

Coordinate Wiii implementation in waves so that architecture, implementation, smoke verification, and review can proceed asynchronously without manual copy-paste between roles.

## Global Rules

- Persona, capability, and UI reasoning are reviewed as separate layers.
- A wave is not considered complete until `REVIEW/WAVE-xxx.md` marks it `APPROVED`.
- Claude Code team should update `REPORTS/*.md` and `events.jsonl`, not this file.
- UI-affecting waves must include screenshots and a short smoke summary.
- Stream/tool-affecting waves must include raw SSE or execution trace.

## Wave Order

### WAVE-001
Capability Boundary

Acceptance criteria:
- `direct` path no longer owns code/document/browser responsibilities.
- explicit subagent boundaries are documented and implemented.
- role policy remains intact.

### WAVE-002
Code Studio Capability

Acceptance criteria:
- code/chart/html intents route to `wiii-code-studio`
- delivery-first answers
- chart requests produce real artifact outputs where runtime allows
- terminal sandbox failures fail fast

### WAVE-003
Document Studio Capability

Acceptance criteria:
- docx/xlsx generation lives behind dedicated capability contracts
- file outputs are first-class artifacts
- no text-only fallback when file generation succeeded

### WAVE-004
Interleaved Reasoning UI Rail

Acceptance criteria:
- clear separation between thinking, tool execution, answer, and artifact
- no duplicated summary/body/action_text layers
- completed turns collapse cleanly

### WAVE-005
QA Automation and Regression Gate

Acceptance criteria:
- Playwright smoke coverage for social, tutor, python PNG, word/excel, browser snapshot
- generated screenshots and logs are linked from wave reports
- review checklist is stable enough for repeated use

## Review Gate

The next wave may start only when:
- previous wave status is `APPROVED`, or
- architect explicitly marks it `CANCELLED` in review.

