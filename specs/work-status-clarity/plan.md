# Plan and evidence

Use memoized maps for the latest stored Run per task and existing exact Run→session binding. Preserve previous last-array-entry/latest-Run selection semantics. Extract the Work row markup into a small presentational component, with separate Run/session labels. Keep history and current-connection explanation in task detail. Counter uses latest Run states running/verifying, not Task's broad phase.

Tests: pending launch not counted; cancelled Run stays cancelled with a connected resumed session; saved idle snapshot not advertised connected; unrelated session not borrowed; existing native outcome projection unchanged. Run full frontend/typecheck/build/embed gates and inspect exact native result. No persistent schema migration.

Rollback: isolated presentation-only commit atop93c0b4c; no data rewrite.
