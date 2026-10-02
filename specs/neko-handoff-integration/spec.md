# Team handoff and Linux runtime integration

Related work: issues #992/#994, draft PRs #993/#995.

Preserve the 2026-10-02 handoff source (45 modified and 37 new files) and integrate Linux packaging, provider brand detection and pinned bundled-runtime preparation without undoing task receipt/root/epoch admission, exact ACP identity, Stop semantics or passive execution receipts.

## Acceptance
- Immutable input archive and verified manifest retained outside the repository
- Source tests, TypeScript, frontend/embed builds, release tests and native gates reported independently
- Explicit exact-source Neko development candidate tested against the actual Wiii task codec and loopback model
- Native paired acceptance is a separate gate; live provider calls never inferred from fixture success
- No downgrade to unscoped sessions when task-v1 is missing

## Non-goals
No merge, release, paid model fallback, credential migration, CSP/sandbox weakening, changes to Neko semantics, or edits to original team source.
