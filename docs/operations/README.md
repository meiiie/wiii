# Wiii Operations Documentation

This directory contains controlled operational documentation for Wiii.

Operational docs are different from exploratory reports:

- They describe the current source of truth for release, cleanup, governance, and runtime decisions.
- They are expected to be reviewed through issue and pull request flow.
- They must include status, date, scope, evidence, and follow-up ownership when relevant.

## Documents

- `WIII_DOCUMENTATION_GOVERNANCE.md`: documentation lifecycle, retention, issue/PR standards, and cleanup controls.
- `WIII_SYSTEM_CLEANUP_CHECKPOINT_2026-04-24.md`: current cleanup checkpoint consolidated from runtime and pipeline research.
- `WIII_REPOSITORY_HYGIENE_AUDIT_2026-04-24.md`: final cleanup verification, retained local artifacts, and rebuild instructions.

## Promotion Rule

Working reports may start in `.Codex/reports/` or `.claude/reports/`, but any report that should guide engineering work must be promoted here or into the relevant product area docs before it becomes authoritative.
