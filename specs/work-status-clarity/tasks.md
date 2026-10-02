# Tasks
- [x] Review native before evidence and domain/source distinction
- [x] Two initial regression tests failed before implementation
- [x] Implement separate labels and exact Run lookup without mutation
- [x] Full regression/typecheck/build and native visual verification (3561 tests; native labels verified)
- [x] Record before/after evidence and accessible next steps

Native delta launch + explicit close + fresh `again` succeeded against the local fixture. Opening Work then disposes the idle runtime through NekoChillApp unmount cleanup: UI truthfully reports the Run stopped and runtime stopped. Screenshot UX-09 captures this existing navigation-lifetime defect; preserving connected-session continuity requires a separate lifecycle change. No live provider acceptance claimed.

Follow-on visual finding: acceptance requirements used a success check icon before any verification. Replace with a numbered requirements list and explicit non-verdict copy; repeated criterion text must also have distinct React keys. Native before is visible in UX-10.

Criteria clarification verified: full 3564 tests/232 files, TypeScript, desktop/embed/native builds pass. Native screenshot UX-11 shows numbered requirements without success icons, accessible list name, retained stored criterion and matching stopped session. No acceptance state is inferred or persisted.

Unknown-outcome follow-up: show guidance even when runtime is absent/error, with a distinct message if no linked session exists. Two regression cases, full 3566 tests/232 files, tsc and desktop/embed/native builds pass. Native UX-12 confirms alpha remains blocked and unknown with a visible path to inspect its session; no replay or automatic recovery added.
