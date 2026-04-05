# Embedding Multi-Socket Extension

Date: 2026-04-02
Role: LEADER

## Scope

Extended the new provider-agnostic embedding authority beyond semantic memory into the next critical lanes:

- hybrid search
- text/knowledge ingestion
- multimodal ingestion
- visual memory retrieval/storage
- LMS enrichment fact extraction
- knowledge visualization RAG simulation

Goal: remove hidden `GeminiOptimizedEmbeddings()` pins from user-facing retrieval/memory paths so Wiii no longer loses these capabilities just because Google embeddings are down.

## Implementation

### Shared authority

- Added generic aliases on top of the existing semantic backend singleton in:
  - `maritime-ai-service/app/engine/embedding_runtime.py`
- New public entrypoints:
  - `get_embedding_backend()`
  - `reset_embedding_backend()`

This keeps backward compatibility with `get_semantic_embedding_backend()` while letting retrieval/ingestion lanes depend on a neutral authority name.

### Migrated lanes

- `maritime-ai-service/app/services/hybrid_search_service.py`
  - now resolves embeddings through `get_embedding_backend()`
- `maritime-ai-service/app/services/multimodal_ingestion_service.py`
  - now injects `EmbeddingBackendProtocol`
  - defaults to `get_embedding_backend()`
- `maritime-ai-service/app/services/vision_processor.py`
  - now types embeddings against `EmbeddingBackendProtocol`
- `maritime-ai-service/app/api/v1/knowledge.py`
  - text ingestion now embeds through the shared backend
- `maritime-ai-service/app/integrations/lms/enrichment.py`
  - FactExtractor now receives `get_semantic_embedding_backend()`
- `maritime-ai-service/app/services/knowledge_visualization_service.py`
  - `simulate_rag_flow()` now uses `get_embedding_backend()`
  - returns early if no embedding backend is available
- `maritime-ai-service/app/engine/semantic_memory/visual_memory.py`
  - image-memory store/retrieve now use `get_embedding_backend()`
  - refuses semantic storage when embedding comes back empty
- `maritime-ai-service/app/engine/insight_validator.py`
  - now types embeddings against the shared protocol rather than Gemini-specific class

## Verification

### Focused tests

Command:

```powershell
python -m pytest maritime-ai-service\tests\unit\test_sprint47_hybrid_search.py `
  maritime-ai-service\tests\unit\test_sprint52_ingestion_service.py `
  maritime-ai-service\tests\unit\test_sprint186_visual_memory.py `
  maritime-ai-service\tests\unit\test_sprint191_knowledge_viz.py `
  maritime-ai-service\tests\unit\test_sprint155_lms_integration.py `
  maritime-ai-service\tests\unit\test_sprint136_universal_kb.py `
  maritime-ai-service\tests\unit\test_sprint44_insight_validator.py `
  maritime-ai-service\tests\unit\test_embedding_runtime_migration_paths.py `
  -q -p no:capture
```

Result:

- `325 passed`

### Live smoke

Ran a direct backend smoke in `maritime-ai-service` with:

- `google_api_key = None`
- `embedding_provider = auto`
- failover chain including `openai`
- `embedding_model = text-embedding-3-small`
- `embedding_dimensions = 768`

Observed result:

```python
{'provider': 'openai', 'model': 'text-embedding-3-small', 'dims': 768, 'length': 768}
```

This confirms the shared authority can now fall through to OpenAI embeddings and still satisfy the current `768d` vector space used by retrieval/storage.

## Test updates

Updated existing tests to stop assuming "embedding == Gemini" in these migrated lanes:

- `maritime-ai-service/tests/unit/test_sprint47_hybrid_search.py`
- `maritime-ai-service/tests/unit/test_sprint52_ingestion_service.py`
- `maritime-ai-service/tests/unit/test_sprint186_visual_memory.py`
- `maritime-ai-service/tests/unit/test_sprint191_knowledge_viz.py`
- `maritime-ai-service/tests/unit/test_sprint136_universal_kb.py`

Added focused regression file:

- `maritime-ai-service/tests/unit/test_embedding_runtime_migration_paths.py`

New coverage asserts:

- text ingestion uses the shared embedding authority
- LMS enrichment builds FactExtractor from the shared semantic embedding backend

## Current truth

The core retrieval/memory lanes requested for this round are no longer hard-pinned to Gemini embeddings.

What this fixes:

- semantic retrieval can continue when Google embeddings are unavailable
- hybrid search no longer silently depends on Google embeddings
- text ingestion and multimodal ingestion can use the same shared embedding authority
- visual memory retrieval/storage now shares the same embedding authority and will not pretend success with empty vectors

## Remaining gaps

Still outside this patch scope and still using legacy `get_embeddings()`:

- `maritime-ai-service/app/engine/agentic_rag/corrective_rag_process_runtime.py`
- `maritime-ai-service/app/engine/agentic_rag/corrective_rag_runtime_support.py`
- `maritime-ai-service/app/engine/agentic_rag/hyde_generator.py`

Also important:

- `visual_memory.describe_image()` still depends on Gemini Vision for image description generation.
  - Retrieval/storage embeddings are now provider-agnostic.
  - The image-description step itself is not yet provider-agnostic.

## Recommendation

Next patch should finish the embedding de-Google work in:

1. Corrective RAG query embedding paths
2. HyDE generator
3. Optional later step: provider-agnostic visual description generation for image memory
