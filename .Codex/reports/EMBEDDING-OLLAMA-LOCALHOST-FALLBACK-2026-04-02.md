# Embedding Ollama Localhost Fallback - 2026-04-02

## Problem

Embedding runtime audit was reporting:

- `ollama -> host_down`

But on this workstation, `Ollama /api/tags` is reachable on `localhost:11434`.

The real issue was:

- configured runtime URL pointed at `host.docker.internal`
- that host was not reachable from the current desktop/backend environment
- so the audit mislabeled the embedding backend as fully down

## Fix

Updated `app/engine/embedding_runtime.py` so the Ollama embedding probe now:

1. tries the configured URL first
2. if it looks like a local bridge URL, also tries local candidates:
   - `localhost`
   - `127.0.0.1`
   - `host.docker.internal`
3. reuses the resolved live base URL for the actual embedding backend if the probe succeeds

This means the runtime no longer says `host_down` just because one local alias is wrong.

## Verification

Focused tests:

- `pytest maritime-ai-service/tests/unit/test_embedding_runtime.py maritime-ai-service/tests/unit/test_embedding_selectability_service.py maritime-ai-service/tests/unit/test_admin_llm_runtime.py maritime-ai-service/tests/unit/test_runtime_endpoint_smoke.py -q -p no:capture`
- Result: `22 passed`

Added regression coverage for:

- falling back from `host.docker.internal` to `localhost`
- keeping fail-closed behavior when the model is still not installed

## Current truth after patch

Live embedding selectability snapshot on this machine:

- `google`: selectable
- `openai`: disabled, `missing_api_key`
- `openrouter`: disabled, `missing_api_key`
- `ollama`: disabled, `model_missing`
- `zhipu`: disabled, `model_unverified`

This is the correct diagnosis now:

- Ollama host is reachable through a local alias
- but the configured embedding model is not installed locally yet

## Impact

This makes admin/runtime audit more trustworthy for local-first deployments.

It also clarifies the next real action item:

- install a compatible local embedding model such as `embeddinggemma`
  or
- configure a live fallback embedding provider such as OpenAI
