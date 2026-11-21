# Implementation plan

- Reuse the existing quick-chat and project navigation callbacks on an action-first NekoOverview; add direct project shortcuts.
- Keep the unified session catalog and its filters; remove explanatory subtitles, not session capabilities.
- Collapse agent management with native disclosure. The existing focus request opens the disclosure before focusing its heading.
- Reflow ProjectHome into a centered heading/composer/starter group; retain its launch, profile, account and draft logic.
- Remove ready-state setup notices and shorten recovery copy. Keep technical details in disclosure and disabled-action tooltips.
- Preserve ACP, permission, persisted stores and managed authentication boundaries; no dependencies or schema changes.

## Verification
Focused home/readiness, composer, catalog and sidebar Vitest suites; TypeScript and production desktop build. Native recorded walkthrough covers fresh home, quick chat, project draft, runtime disclosure, saved sessions and compact layout. CI and Devin Review must settle before merge; never publish a release.

## Risk and rollback
Navigation and focus are the main behavioral risks. Revert this UI-only commit to restore the prior hierarchy; no data migration or runtime rollback is necessary.
