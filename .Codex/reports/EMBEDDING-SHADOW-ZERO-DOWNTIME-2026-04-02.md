# Embedding Shadow Zero-Downtime Checkpoint

Date: 2026-04-02

## What Changed

Wiii now has a real shadow-space foundation for embeddings instead of only an in-place re-embed planner.

Implemented:

- Alembic schema for:
  - `embedding_space_registry`
  - `semantic_memory_vectors`
  - `knowledge_embedding_vectors`
- Dimension-specific shadow index service:
  - partial HNSW index per `space_fingerprint + dimensions`
- Registry/runtime authority for active vs shadow embedding spaces
- Semantic memory dual-write path:
  - base row stays in `semantic_memories`
  - shadow vectors can be written into `semantic_memory_vectors`
- Dense/knowledge dual-write path:
  - base row stays in `knowledge_embeddings`
  - shadow vectors can be written into `knowledge_embedding_vectors`
- Read switching:
  - semantic memory search can read from `semantic_memory_vectors`
  - dense search can read from `knowledge_embedding_vectors`
- Admin/operator controls:
  - `plan`
  - `dry-run`
  - `apply shadow`
  - `promote target`

## Current Lifecycle

Cross-space migration is now modeled as:

1. `plan`
2. `prepare shadow`
3. `build shadow indexes`
4. `backfill shadow vectors`
5. `promote target`

This replaces the old assumption that cross-space migration had to be done only as an in-place maintenance rewrite.

## Key Files

- `maritime-ai-service/alembic/versions/046_create_embedding_shadow_tables.py`
- `maritime-ai-service/app/services/embedding_space_registry_service.py`
- `maritime-ai-service/app/services/embedding_shadow_vector_service.py`
- `maritime-ai-service/app/services/embedding_shadow_index_service.py`
- `maritime-ai-service/app/services/embedding_space_migration_service.py`
- `maritime-ai-service/app/repositories/semantic_memory_repository_runtime.py`
- `maritime-ai-service/app/repositories/vector_memory_repository.py`
- `maritime-ai-service/app/repositories/dense_search_repository.py`
- `maritime-ai-service/app/repositories/dense_search_repository_runtime.py`
- `maritime-ai-service/app/api/v1/admin.py`
- `maritime-ai-service/app/api/v1/admin_schemas.py`
- `wiii-desktop/src/api/admin.ts`
- `wiii-desktop/src/api/types.ts`
- `wiii-desktop/src/components/runtime/LlmRuntimePolicyEditor.tsx`

## Verification

Backend:

- `43 passed`
- `38 passed`

Frontend:

- `6 passed`

Focused coverage includes:

- registry fallback + shadow prepare
- semantic memory dual-write
- vector memory shadow read
- dense search shadow read
- dense search shadow write
- migration planner/apply/promote
- shadow index creation
- admin promote endpoint smoke
- desktop runtime tab wiring

## Current Truth

- The architecture now supports zero-downtime style cross-space migration in code.
- `plan` no longer has to describe every cross-space move as maintenance-only.
- `apply shadow` backfills side-table vectors instead of rewriting inline vectors.
- `apply shadow` also creates partial HNSW indexes for the target fingerprint/dimension when possible.
- `promote target` now switches runtime embedding policy + registry read authority together.

## Residual Truth

- This round validated the lifecycle through unit/integration-style smoke, not by running a full live promote on the real operator dataset.
- The shadow tables currently use `double precision[]` side storage plus dimension-aware casting at read time. This is deliberate so different embedding spaces can coexist without breaking the old inline `vector(768)` columns.
- The shadow index layer is now present in code, but this round still verified it through focused tests rather than a full live apply/promote on the real operator dataset.
