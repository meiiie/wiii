# Embedding Space Admin Visibility - 2026-04-02

## What changed
- Added admin/runtime visibility for the active embedding space, policy contract, tracked vs untracked vector rows, and per-table fingerprint breakdown.
- Added migration previews so the runtime tab now shows whether a target embedding model is same-space, blocked, or requires re-embed before switching.
- Reused the same-space guardrail logic instead of duplicating transition rules in the UI.
- Added a real embedding-space migration planner/executor layer with maintenance-aware semantics, instead of leaving migration as an implicit manual operation.
- Added admin API endpoints for migration orchestration:
  - `POST /api/v1/admin/llm-runtime/embedding-space/plan`
  - `POST /api/v1/admin/llm-runtime/embedding-space/migrate`
- Wired the runtime tab to call those endpoints for the currently selected embedding model, so operators can trigger a guarded plan/dry-run directly from the admin UI.
- Hardened migration previews to fail-closed when database audit/candidate counting is unavailable, so admin/runtime still serializes safely in degraded environments.

## Files
- `maritime-ai-service/app/services/embedding_space_runtime_service.py`
- `maritime-ai-service/app/services/embedding_space_guard.py`
- `maritime-ai-service/app/services/embedding_space_migration_service.py`
- `maritime-ai-service/app/api/v1/admin.py`
- `maritime-ai-service/app/api/v1/admin_llm_runtime.py`
- `maritime-ai-service/app/api/v1/admin_schemas.py`
- `maritime-ai-service/scripts/plan_embedding_space_migration.py`
- `maritime-ai-service/tests/unit/test_embedding_space_migration_service.py`
- `maritime-ai-service/tests/unit/test_runtime_endpoint_smoke.py`
- `wiii-desktop/src/components/runtime/LlmRuntimePolicyEditor.tsx`
- `wiii-desktop/src/api/admin.ts`
- `wiii-desktop/src/api/types.ts`

## Verification
- Backend focused migration/runtime/admin batch: `46 passed`
- Frontend: `6 passed`

## Current live snapshot
- Active contract: `ollama:embeddinggemma:768`
- Policy contract: `ollama:embeddinggemma:768`
- Embedded rows tracked by audit: `64`
- Preview count exposed in admin/runtime: `5`
- Migration matrix now marks `gemini-embedding-2-preview`, `models/gemini-embedding-001`, and `text-embedding-3-large` as `re-embed required` instead of pretending same-dimension means same-space.
- Planner artifact: `embedding-space-migration-2026-04-02-224932.json`
- Current plan truth for `text-embedding-3-small`:
  - target contract = `openai:text-embedding-3-small:1536`
  - same space = `false`
  - transition allowed = `false`
  - maintenance required = `true`
  - candidate rows = `64`

## Current direction
- Admin can now see the real vector-space contract instead of inferring it from provider badges.
- The runtime tab can warn before an unsafe embedding-model switch, rather than after save.
- Admin/operator now has a guarded plan/dry-run path for future re-embed operations, not just passive warnings.
- This closes the loop between the same-space backend guard, migration planning semantics, and the actual operator UX.
