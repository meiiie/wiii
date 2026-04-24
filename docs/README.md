# Repository Documentation Layout

Use this folder for repository-level documentation that explains the product, the codebase, and major implementation decisions.

## Primary Entry Points

- `../README.md`: repository overview and deployment model
- `WIII_PROJECT_MENTAL_MODEL.md`: one-page product and system mental model
- `WIII_ARCHITECTURE_AUDIT.md`: opinionated audit of architectural center, strengths, and risk areas
- `WIII_TECHNICAL_SIMPLIFICATION_ROADMAP.md`: phased simplification plan and first landed slice
- `operations/WIII_DOCUMENTATION_GOVERNANCE.md`: documentation lifecycle, cleanup controls, and issue/PR standards
- `operations/WIII_SYSTEM_CLEANUP_CHECKPOINT_2026-04-24.md`: current operational cleanup checkpoint and runtime truth snapshot
- `../maritime-ai-service/docs/architecture/SYSTEM_ARCHITECTURE.md`: authoritative system architecture
- `../maritime-ai-service/docs/architecture/SYSTEM_FLOW.md`: technical request and streaming flow
- `../maritime-ai-service/docs/integration/WIII_LMS_INTEGRATION.md`: LMS contract and security model
- `../maritime-ai-service/scripts/deploy/README.md`: production deployment runbook
- `../wiii-desktop/README.md`: desktop app architecture and local workflow

## Current Layout

- `plans/`: committed design notes, implementation plans, and sprint writeups
- `operations/`: reviewed operational checkpoints, cleanup governance, release controls, and runtime truth documents
- `assets/`: committed screenshots, diagrams, and other documentation assets

## Rules

- Keep repository-wide documentation here, not in the repository root.
- Put screenshots and other doc assets under `docs/assets/`.
- Put stable planning and design documents under `docs/plans/`.
- Put reviewed cleanup, release, and governance documents under `docs/operations/`.
- Keep desktop-only docs under `wiii-desktop/docs/`.
- Do not commit agent-generated working reports. Keep temporary reports in ignored local scratch paths and promote durable findings into canonical docs.
