# Embedding Policy Admin Control - 2026-04-02

## Summary

Embedding runtime policy is now editable and persistable from the admin/runtime surface instead of being audit-only.

Implemented scope:

- backend admin update contract now accepts:
  - `embedding_provider`
  - `embedding_failover_chain`
  - `embedding_model`
- persisted runtime policy now stores and replays the same embedding fields
- runtime save now resets the shared embedding backend and invalidates embedding selectability cache
- desktop runtime editor now exposes embedding provider mode, embedding model, and embedding failover chain

## Key Files

- `maritime-ai-service/app/api/v1/admin.py`
- `maritime-ai-service/app/api/v1/admin_llm_runtime.py`
- `maritime-ai-service/app/api/v1/admin_llm_runtime_support.py`
- `maritime-ai-service/app/api/v1/admin_runtime_bindings.py`
- `maritime-ai-service/app/api/v1/admin_schemas.py`
- `maritime-ai-service/app/services/llm_runtime_policy_service.py`
- `wiii-desktop/src/api/types.ts`
- `wiii-desktop/src/components/runtime/LlmRuntimePolicyEditor.tsx`

## Important Decisions

- `embedding_dimensions` is intentionally not editable from the UI yet.
- Reason: pgvector schema and semantic space compatibility are easier to damage than to recover; V1 keeps dimensions authoritative in backend config/model catalog.
- `embedding_model` is validated against known embedding model contracts; unknown arbitrary model ids are rejected fail-closed.
- `openai` and `openrouter` are treated as compatible for embedding model ownership because they share the same OpenAI-compatible embedding model family.

## Verification

Backend:

- `pytest maritime-ai-service/tests/unit/test_llm_runtime_policy_service.py maritime-ai-service/tests/unit/test_admin_llm_runtime.py -q -p no:capture`
- Result: `10 passed`

Frontend:

- `npm --prefix wiii-desktop run test -- --run src/__tests__/admin-runtime-tab.test.tsx`
- Result: `6 passed`

## Current Truth

- Live default snapshot on this machine is still:
  - `embedding_provider=google`
  - `embedding_model=models/gemini-embedding-001`
  - `embedding_failover_chain=['google', 'openai', 'ollama', 'openrouter']`
- But now admin can move this cleanly to local-first or hybrid fallback without code edits.

## Next Good Step

Use the new admin/runtime controls to test one real policy switch:

- `embedding_provider=auto`
- `embedding_failover_chain=ollama, google, openai`
- `embedding_model=embeddinggemma`

Then rerun memory/retrieval smoke to measure:

- semantic memory recall latency
- hybrid search latency
- whether local-first embeddings keep answer/thinking quality acceptable
