# Work status clarity

Owner requested ongoing local UX improvements; GitHub work is deferred as of 2026-10-02. Native evidence shows a terminal Work Run can coexist with a resumed Neko conversation. They are separate identities. Present both facts rather than changing terminal history to make the UI look consistent.

Requirements: label historical Run status separately from current session state; match sessions by exact run binding; do not claim a saved idle snapshot is connected without a runtime; keep unknown outcomes visibly unresolved. Pending agent selection is not counted as an actively executing Run. Provide a direct path to the corresponding session.

Non-goals: no new Run semantics, lifecycle rewrites, replay, changes to permissions, cancellation, task receipt validation, or account/model calls.
