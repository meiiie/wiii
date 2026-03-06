# Repository Documentation Layout

Use this folder for repository-level documentation that explains the product, the codebase, and major implementation decisions.

## Primary Entry Points

- `../README.md`: repository overview and deployment model
- `../maritime-ai-service/docs/architecture/SYSTEM_ARCHITECTURE.md`: authoritative system architecture
- `../maritime-ai-service/docs/architecture/SYSTEM_FLOW.md`: technical request and streaming flow
- `../maritime-ai-service/docs/integration/WIII_LMS_INTEGRATION.md`: LMS contract and security model
- `../maritime-ai-service/scripts/deploy/README.md`: production deployment runbook
- `../wiii-desktop/README.md`: desktop app architecture and local workflow

## Current Layout

- `plans/`: committed design notes, implementation plans, and sprint writeups
- `assets/`: committed screenshots, diagrams, and other documentation assets

## Rules

- Keep repository-wide documentation here, not in the repository root.
- Put screenshots and other doc assets under `docs/assets/`.
- Put stable planning and design documents under `docs/plans/`.
- Keep desktop-only docs under `wiii-desktop/docs/`.
- Agent-generated working reports stay under `.claude/reports/` and are intentionally separate from the main docs tree.