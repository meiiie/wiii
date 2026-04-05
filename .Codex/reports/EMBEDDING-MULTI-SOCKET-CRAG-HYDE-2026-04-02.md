# Embedding Multi-Socket CRAG + HyDE

Date: 2026-04-02

## Summary
- Migrated the remaining live Gemini-only embedding callsites in `app/engine/agentic_rag` to the shared embedding authority.
- Covered:
  - Corrective RAG query embeddings
  - Corrective RAG semantic-cache store path
  - HyDE document embeddings
- Verified that `app/engine/agentic_rag` no longer contains live `gemini_embedding.get_embeddings()` callsites. Remaining matches are only in `__pycache__`.

## Files Changed
- `maritime-ai-service/app/engine/agentic_rag/corrective_rag_process_runtime.py`
- `maritime-ai-service/app/engine/agentic_rag/corrective_rag_runtime_support.py`
- `maritime-ai-service/app/engine/agentic_rag/hyde_generator.py`
- `maritime-ai-service/tests/unit/test_sprint179_visual_rag.py`
- `maritime-ai-service/tests/unit/test_sprint187_advanced_rag.py`
- `maritime-ai-service/tests/unit/test_sprint189b_source_flow.py`
- `maritime-ai-service/tests/unit/test_embedding_runtime_rag_paths.py`

## Behavioral Changes
- CRAG now resolves query vectors through `get_embedding_backend()` via `get_query_embedding_impl()`.
- If query embedding is unavailable, CRAG:
  - skips semantic-cache lookup cleanly
  - skips semantic-cache store cleanly
  - still continues retrieval/grading without forcing a broken vector
- HyDE now resolves document-style embeddings through the same authority via `get_document_embedding_impl()`.
- HyDE still preserves the document-embedding intent (`embed_documents`) instead of collapsing to query-space embedding.

## Validation
- Focused regression suite:
  - `201 passed`
- Suite included:
  - `test_sprint187_advanced_rag.py`
  - `test_sprint189b_source_flow.py`
  - `test_sprint179_visual_rag.py`
  - `test_embedding_runtime_rag_paths.py`
  - `test_corrective_rag_unit.py`

## Notes
- This closes the remaining live Gemini-only embedding dependency inside `agentic_rag`.
- A separate concern still exists for provider coverage:
  - `google`, `openai`, `openrouter`, and `ollama` have a clearer embedding-model story in the current catalog/runtime.
  - `zhipu` chat/runtime is available elsewhere in the system, but its embedding model contract still needs explicit official-model verification before it should be treated as a first-class embedding backend.
