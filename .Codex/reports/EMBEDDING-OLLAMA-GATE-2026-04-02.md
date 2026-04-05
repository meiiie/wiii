# Embedding Ollama Gate

Date: 2026-04-02

## Summary
- Hardened the shared embedding runtime so Ollama embeddings only initialize when the configured local embedding model is actually installed.
- This prevents the runtime from advertising a local-first embedding fallback that does not exist on the machine.

## Changes
- Added a local Ollama model probe in `app/engine/embedding_runtime.py`
  - builds `/api/tags` URL from the configured base URL
  - checks whether the configured embedding model is installed
- `provider="ollama"` now fails closed if:
  - the Ollama endpoint is unreachable
  - the configured embedding model is missing locally
- Added tests covering:
  - fail-closed when model is not installed
  - successful backend initialization when the model is present

## Verification
- Focused tests:
  - `11 passed`
- Local smoke:
  - forcing `embedding_provider='ollama'`
  - forcing `embedding_model='embeddinggemma'`
  - result:
    - `available=False`
    - `provider=None`
    - `model=None`

## Current Local State
- `http://localhost:11434/api/tags` is reachable
- Installed local/chat models include:
  - `gemma3:4b`
  - `qwen3:4b-instruct-2507-q4_K_M`
  - `qwen3:4b-thinking-2507-q4_K_M`
  - cloud-linked entries such as `minimax-m2.5:cloud`, `deepseek-v3.1:671b-cloud`
- `embeddinggemma` is **not** installed locally right now

## Meaning
- Wiii now has a clean local-first embedding fallback path for Ollama in architecture,
  but this specific workstation cannot use it yet until a compatible local embedding model is installed.
