# Plan

- Share task prompt formatting between visible read-only composer and dispatch, including acceptance criteria.
- Carry criteria from Work form into launch request.
- Retain existing Work attachment callback before dispatch.
- Add explicit-target sendPromptToSession; keep existing sendPrompt wrapper for active composer callers. Capture target before asynchronous barriers.
- Guard repeated launch clicks synchronously with a component-local ref, in addition to disabled state.
- Reuse existing task receipt/root/epoch, persistence, permission and uncertain-outcome guards.

Tests: fail before/pass after task launch, criteria visibility, binding order/failure, active-tab race, double click, preserved manual draft; full frontend gates and exact native recheck.

Rollback: isolated UX commit atop local integration checkpoint 8fadade77cd87b773d2152b24e7d1bac820f02da; no persisted schema change or migration.
