# Embedding Runtime Audit Snapshot - 2026-04-02

## What changed

- Added a dedicated embedding selectability service:
  - `maritime-ai-service/app/services/embedding_selectability_service.py`
- Extended embedding runtime helpers so admin/audit can inspect:
  - provider order
  - provider-specific model resolution
  - effective dimensions
  - detailed Ollama probe reason
- Extended admin runtime payload with embedding runtime snapshot:
  - `embedding_provider`
  - `embedding_failover_chain`
  - `embedding_provider_status[]`
- Updated desktop runtime panel to show:
  - embedding provider mode
  - chain
  - per-provider status/reason badges

## Current truth on this machine

Live snapshot from `get_embedding_selectability_snapshot(force_refresh=True)`:

- `google`: selectable, active, model `models/gemini-embedding-001`, `768d`
- `openai`: disabled, `missing_api_key`
- `openrouter`: disabled, `missing_api_key`
- `ollama`: disabled, `host_down`
  - runtime is pointing at `http://host.docker.internal:11434`
  - probe to `/api/tags` timed out in this env
- `zhipu`: disabled, `model_unverified`
  - chat path can still use GLM
  - embeddings stay fail-closed until catalog has a verified contract

## Why this matters

Before this patch, admin/runtime only exposed:

- `embedding_model`
- `embedding_dimensions`
- `embedding_status`

That was not enough to explain why semantic memory or retrieval degraded.

Now admin/runtime can show whether the real blocker is:

- missing API key
- Ollama host down
- local embedding model not installed
- dimension mismatch
- unverified provider contract

## Verification

Backend:

- `pytest maritime-ai-service/tests/unit/test_embedding_runtime.py maritime-ai-service/tests/unit/test_embedding_selectability_service.py maritime-ai-service/tests/unit/test_admin_llm_runtime.py maritime-ai-service/tests/unit/test_runtime_endpoint_smoke.py -q -p no:capture`
- Result: `21 passed`

Frontend:

- `npm --prefix wiii-desktop run test -- --run src/__tests__/admin-runtime-tab.test.tsx`
- Result: `5 passed`

## Notes

- There is still one pre-existing runtime warning in the focused pytest batch related to an `AsyncMock` coroutine not awaited inside the test environment. It did not fail the suite and was not introduced by this patch.
- This round only adds audit/selectability visibility. It does not change the embedding failover decision itself.
