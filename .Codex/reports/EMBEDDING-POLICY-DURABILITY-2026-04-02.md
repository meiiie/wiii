# Embedding Policy Durability - 2026-04-02

## Summary

Wiii's embedding runtime policy is now durable again across backend restarts.

Two bugs were fixed together:

1. `embedding_dimensions` was not part of the persisted LLM runtime policy schema, so the value was silently dropped on save/restore.
2. The sync database engine tried `postgresql+psycopg://` first, but this environment runs SQLAlchemy 1.4, which cannot load that dialect plugin cleanly. Persisted runtime policy therefore failed-soft and never actually reached PostgreSQL.

## Changes

- Added `embedding_dimensions` to persisted runtime policy field handling.
- Added integer sanitization with bounds `128..4096` in `llm_runtime_policy_service`.
- Added `embedding_dimensions` to the admin update schema.
- Added sync PostgreSQL dialect fallback in `app/core/database.py`:
  - prefer `postgresql+psycopg://`
  - automatically fall back to `postgresql+psycopg2://` when the dialect is unavailable

## Verification

- Focused tests:
  - `test_database.py`
  - `test_llm_runtime_policy_service.py`
  - `test_admin_llm_runtime.py`
- Result: `22 passed`

Live persistence verification:

- `persist_current_llm_runtime_policy()` -> success
- repository reload -> `embedding_dimensions = 768`
- runtime snapshot -> `embedding_provider = auto`
- runtime snapshot -> `embedding_failover_chain = ['ollama', 'openai', 'google']`
- runtime snapshot -> `embedding_model = embeddinggemma`
- runtime snapshot -> `embedding_dimensions = 768`

## Current Live Embedding Policy

- provider: `auto`
- failover chain: `ollama -> openai -> google`
- model: `embeddinggemma`
- dimensions: `768`

## Notes

- Ollama is now the active local-first embedding backend on this machine.
- OpenAI remains the cloud fallback tier when a key is present.
- Google stays in the chain, but it is no longer the single point of failure for semantic memory retrieval.
