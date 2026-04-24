# Wiii System Cleanup Checkpoint

Status: Active checkpoint

Date: 2026-04-24

Scope: documentation cleanup, runtime truth consolidation, release-stabilization inputs

Non-scope: source code fixes, database migration repair, broad artifact deletion

## Executive Summary

Wiii has a strong product core, but the repository currently carries too many parallel truth surfaces. Runtime behavior, agent reports, legacy docs, and local generated artifacts are not cleanly separated.

This checkpoint consolidates the current research into one operational source of truth for cleanup planning. It should be used to drive follow-up issues and focused implementation PRs, not as a substitute for those fixes.

## Current Runtime Truth

Observed on 2026-04-24:

- Frontend dev app served at `http://localhost:1420`.
- Docker production-like backend served through nginx at `http://localhost:8080`.
- App, nginx, PostgreSQL, Valkey, MinIO, and OpenSandbox containers were healthy.
- App container memory was about `1.02 GiB / 2.842 GiB`; this did not indicate an immediate memory leak.
- `/api/v1/health/live` returned alive.
- `/api/v1/llm/status` exposed Google as primary and Zhipu as fallback; Google runtime model was `gemini-2.5-flash`, Zhipu runtime model was `glm-5`.

Runtime feature state sampled from the running app:

- `environment=production`
- `enable_multi_tenant=True`
- `enable_org_admin=True`
- `enable_lms_integration=False`
- `enable_lms_token_exchange=False`
- `enable_mcp_server=True`
- `enable_mcp_tool_server=True`
- `enable_living_agent=False`
- `enable_natural_conversation=True`
- `enable_host_context=True`
- `enable_host_actions=True`
- `enable_unified_skill_index=True`
- `enable_intelligent_tool_selection=True`
- `enable_wiii_runner=True`
- `enable_corrective_rag=True`
- `enable_hyde=True`
- `enable_adaptive_rag=True`
- `enable_visual_rag=True`
- `enable_visual_memory=True`
- `enable_cross_platform_identity=True`
- `enable_cross_platform_memory=True`
- `enable_google_oauth=True`

## Active Chat Pipeline

The live chat path is:

```text
wiii-desktop
-> useSSEStream
-> POST /api/v1/chat/stream/v3
-> require_auth
-> ChatOrchestrator.prepare_turn
-> InputProcessor.build_context
-> WiiiRunner
-> guardian/supervisor/selected agent
-> synthesizer/output
-> finalize_response_turn
-> chat_history/thread_views/background memory tasks
```

The active orchestrator is `WiiiRunner`. LangGraph references should be treated as historical or compatibility context unless a specific file proves otherwise.

## Critical Blockers

| Priority | Area | Finding | Required action |
|---|---|---|---|
| P0 | Database migrations | PostgreSQL reports Alembic revision `047`, while local source/container migrations are available only through `046`. `alembic current` fails because revision `047` is missing. | Locate the missing migration or create a reconciliation plan after comparing live schema to revision `046`. |
| P0 | Auth and memory | Production API-key mode canonicalizes all legacy users to `api-client`. This is secure for API-key auth, but unsafe for per-user long-term memory. | Use OAuth/JWT or LMS token exchange for real user memory. Globally block long-term memory reads/writes for service identities. |
| P0 | Stream persistence | User messages can be persisted before assistant finalization. Interrupted streams may leave user-only turns. | Add turn status tracking and tests for disconnect, provider failure, tool timeout, and normal stream completion. |
| P0 | Tool registry | LMS/course tool registration references `ToolCategory.LMS`, but the enum currently lacks `LMS`. | Add the enum value or remap tools to an explicit existing category, then test feature-gated registration. |
| P1 | Config drift | `.env.production` contains duplicate `ENABLE_MULTI_TENANT`; runtime resolves to `True`. | Remove duplicate key through a reviewed config PR. |
| P1 | Tool surface | Tool availability is fragmented across direct, tutor, code studio, LMS, visual, host action, MCP, and registry paths. | Generate a tool capability matrix by agent, role, and feature flag. |
| P1 | Docs drift | Some docs still imply LangGraph is primary, and agent/report paths are split across `.Codex` and `.claude`. | Normalize documentation ownership and mark historical references clearly. |

## Cleanup Inventory

Safe generated artifact candidates after confirming no build is running:

- `wiii-desktop/src-tauri/target`, about `8.45 GB`, ignored, rebuildable.
- `wiii-desktop/dist`, ignored, rebuildable.
- `wiii-desktop/test-results`, ignored test output.
- `wiii-desktop/playwright/screenshots`, untracked screenshots.
- Root `test-results`, `.ruff_cache`, `pytest-cache-files-*`, ignored caches.
- `maritime-ai-service/.pytest_cache`, ignored cache.
- Ignored root log files.

Reproducible but costly dependency candidates:

- `maritime-ai-service/.venv`, about `1.36 GB`.
- `wiii-desktop/node_modules`, about `704 MB`.
- Sidecar dependency directories under `.Codex/external/*`.

High-risk cleanup targets requiring a separate retention decision:

- `docs/assets/screenshots`, because assets may be referenced by docs.
- `maritime-ai-service/data`, because it contains domain data.
- Untracked source-like files such as ingestion scripts, local analyses, and new Playwright configs.

## Documentation Decisions In This Checkpoint

This checkpoint establishes:

- `docs/operations/` as the canonical location for operational governance and cleanup checkpoints.
- `.Codex/reports/` and `.claude/reports/` as retired local scratch paths, not canonical source-of-truth locations.
- Untracked scratch reports from the current research were deleted after their findings were consolidated into this checkpoint.
- Legacy tracked report trees were removed from source control after the canonical operations docs were established.
- Future report output should stay ignored unless promoted into `docs/operations/`, `docs/plans/`, or the relevant product documentation area.

## Cleanup Execution Update

Executed on 2026-04-24:

- Removed tracked non-canonical report trees: `.Codex/reports/`, `.claude/reports/`, `maritime-ai-service/.claude/reports/`, and nested `maritime-ai-service/.Codex/reports/`.
- Removed local generated/dependency artifacts: `wiii-desktop/node_modules`, `maritime-ai-service/.venv`, `.Codex/external`, `.Codex/tmp`, Tauri target, Vite dist outputs, test results, screenshots, logs, caches, and Python `__pycache__` directories.
- Removed ignored old planning/checkpoint notes and unrelated sample PDFs that were outside canonical documentation/data paths.
- Updated `.gitignore` so `.Codex/reports/`, `.Codex/external/`, `.Codex/tmp/`, and `.claude/reports/` stay out of source control, including nested `.Codex` locations.
- Left source-like untracked files for explicit triage instead of deleting them as generic junk.

Known residue:

- Several root `pytest-cache-files-*` directories remain at `0 KB` because Windows denied deletion. They are ignored and should be retried after reboot or with corrected ACLs if necessary.

## Follow-Up Backlog

Recommended issue sequence:

1. Repair Alembic revision `047` drift before schema work.
2. Implement global service-identity memory policy.
3. Harden stream lifecycle persistence and add regression tests.
4. Fix `ToolCategory.LMS` registration drift.
5. Generate a runtime feature and tool capability matrix.
6. Remove duplicate production env keys.
7. Triage source-like untracked files and decide whether they belong in source, docs, or deletion.
8. Reinstall local dependencies only when development resumes: `npm install` in `wiii-desktop` and virtualenv setup in `maritime-ai-service`.

## Verification Notes

This checkpoint is documentation-only. It consolidates existing runtime observations and does not claim that code blockers are fixed.

For this cleanup PR, verification should be limited to:

- `git diff --check --cached`
- Confirming only intended documentation files are staged.
- Confirming removed scratch reports are represented by canonical docs in `docs/operations/`.
