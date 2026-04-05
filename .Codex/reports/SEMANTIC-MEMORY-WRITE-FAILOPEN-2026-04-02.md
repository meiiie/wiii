# Semantic Memory Write Fail-Open

- Date: `2026-04-02`
- Workspace: `E:\Sach\Sua\AI_v1`

## Why this round happened

Semantic memory read-side had already become more resilient through lexical fallback, but write-side still had brittle paths:

- `semantic_memories.embedding` is `vector(768)` and nullable, so writing `CAST('[]' AS vector)` is invalid.
- `FactExtractor.store_user_fact_upsert()` still returned `False` on embedding outages instead of storing facts without vectors.
- `SemanticMemoryEngine.is_available()` still required embeddings to be alive, so upper layers could bypass memory even when repository-backed fallback paths were healthy.
- `HybridSearchService` could still send an empty query vector into dense search and log a `vector must have at least 1 dimension` style failure.

## Changes

### 1. Save semantic memories with `NULL` embedding when vectors are unavailable

Patched:

- `maritime-ai-service/app/repositories/semantic_memory_repository_runtime.py`

Changes:

- `save_memory()` now emits `NULL` for `embedding` instead of `CAST(:embedding AS vector)` when embedding is empty.
- `upsert_running_summary()` now inserts `NULL` embedding as well.

Result:

- message, user-fact, and summary writes can survive embedding outages without invalid vector casts.

### 2. Fact updates now preserve content even when embedding regeneration fails

Patched:

- `maritime-ai-service/app/repositories/fact_repository_mutation_runtime.py`
- `maritime-ai-service/app/repositories/fact_repository_triples.py`

Changes:

- Added `update_fact_preserve_embedding(...)` to update `content + metadata + importance` without overwriting the existing vector.
- `update_memory_content()` now uses the preserve-embedding update path instead of metadata-only fallback when embedding regeneration is unavailable.
- `update_fact()` now refreshes `importance` from metadata confidence for consistency.

Result:

- fact content no longer stays stale just because a new embedding could not be generated.

### 3. Fact extraction/storage now fail-open instead of aborting

Patched:

- `maritime-ai-service/app/engine/semantic_memory/extraction.py`

Changes:

- embedding generation failures are logged as warnings and converted to `fact_embedding=[]`
- semantic duplicate search is skipped when there is no embedding
- existing facts update via `update_fact_preserve_embedding(...)`
- new facts insert through `save_memory(...)` and require a real persistence success signal

Result:

- Wiii can still remember explicit facts during embedding outages.

### 4. Interaction storage now survives embedding outages

Patched:

- `maritime-ai-service/app/engine/semantic_memory/core.py`

Changes:

- `store_interaction()` now uses a per-text safe embed helper and stores message/response memories with empty embeddings if vector generation fails.
- `SemanticMemoryEngine.is_available()` now depends on repository availability rather than embedding availability.

Result:

- upper layers no longer disable semantic memory just because embeddings are temporarily down
- message/response turns can still be persisted

### 5. Hybrid and fact semantic search now short-circuit cleanly on empty vectors

Patched:

- `maritime-ai-service/app/repositories/fact_repository_query_runtime.py`
- `maritime-ai-service/app/services/hybrid_search_service.py`

Changes:

- fact semantic lookup now returns early on empty embeddings
- hybrid search falls back to sparse-only when query embedding is empty
- dense-only convenience path returns `[]` instead of pushing an empty vector into pgvector

Result:

- retrieval no longer logs dense-search vector dimension failures during embedding outages

## Tests

Focused suites:

- `225 passed`

Key files:

- `maritime-ai-service/tests/unit/test_sprint30_semantic_memory_repo.py`
- `maritime-ai-service/tests/unit/test_sprint30_semantic_memory_core.py`
- `maritime-ai-service/tests/unit/test_sprint47_hybrid_search.py`
- `maritime-ai-service/tests/unit/test_sprint49_fact_extractor.py`
- `maritime-ai-service/tests/unit/test_sprint51_fact_repository.py`
- `maritime-ai-service/tests/unit/test_sprint53_context_retriever.py`
- `maritime-ai-service/tests/unit/test_sprint53_vector_memory_repository.py`
- `maritime-ai-service/tests/unit/test_dense_search_repository_runtime.py`

## Live smoke

Live DB smoke with a forced failing embedding backend confirmed:

- `store_interaction(...) == True`
- `store_user_fact_upsert(...) == True`
- `semantic_memories` rows were created with `embedding IS NULL = true`
- stored rows included:
  - user message
  - assistant response
  - user fact

## Updated benchmark

Latest benchmark:

- `E:\Sach\Sua\AI_v1\.Codex\reports\EMBEDDING-RETRIEVAL-BENCHMARK-2026-04-02-201811.md`
- `E:\Sach\Sua\AI_v1\.Codex\reports\embedding-retrieval-benchmark-2026-04-02-201811.json`

Current truth:

- Gemini query embeddings are still quota-exhausted.
- Semantic context still returns `memories=1, facts=1`.
- Hybrid search now degrades to `sparse_only` instead of surfacing dense-search vector errors.
- Ollama remains blocked by host/model availability on this machine, so local-first policy is persisted but not currently usable at runtime.

## Remaining gap

The main remaining issue is not semantic-memory correctness anymore, but environment/runtime availability:

- `ollama` embedding backend is still unavailable on this machine
- `google` query embeddings are quota-limited
- `openai/openrouter` embedding keys are not configured in the current live runtime snapshot

The code path is now resilient; the next step is mostly provider/runtime hygiene, not another semantic-memory architecture rewrite.
