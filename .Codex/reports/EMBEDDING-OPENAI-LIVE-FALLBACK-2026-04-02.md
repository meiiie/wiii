# Embedding OpenAI Live Fallback

- Date: `2026-04-02`
- Workspace: `E:\Sach\Sua\AI_v1`

## What was done

This round focused on turning embedding failover from a design into a live, working fallback path.

### Runtime policy applied

The live embedding policy was persisted as:

- `embedding_provider=auto`
- `embedding_failover_chain=['ollama','google','openai']`
- `embedding_model=embeddinggemma`
- `embedding_dimensions=768`

OpenAI embeddings were configured in runtime so the system had a real cloud fallback while:

- `ollama` is currently unavailable on this machine
- `google` query embeddings are quota-exhausted

## Live smoke

A targeted smoke test forced the embedding runtime into:

- provider mode: `auto`
- chain: `google -> openai -> ollama`
- canonical dimensions: `768`

Result:

- backend promoted to `openai`
- model resolved to `text-embedding-3-small`
- query embedding succeeded with `768d`

This verified that the multi-socket embedding runtime really can fail over from Gemini to OpenAI on this machine.

## Benchmark

Benchmark report:

- `E:\Sach\Sua\AI_v1\.Codex\reports\EMBEDDING-RETRIEVAL-BENCHMARK-2026-04-02-205158.md`
- `E:\Sach\Sua\AI_v1\.Codex\reports\embedding-retrieval-benchmark-2026-04-02-205158.json`

### `google_openai_auto`

- active backend: `openai / text-embedding-3-small / 768d`
- raw query embedding: `4889.34 ms`
- raw document embedding: `655.95 ms`
- semantic context: `2050.69 ms`
- hybrid search: `673.9 ms`
- observation: `provider_promoted_to_openai`

### `ollama_local_first`

- `ollama` was still unavailable (`host_down`)
- runtime skipped to `google`, then promoted to `openai`
- active backend: `openai / text-embedding-3-small / 768d`
- raw query embedding: `2207.31 ms`
- raw document embedding: `728.08 ms`
- semantic context: `364.17 ms`
- hybrid search: `318.83 ms`
- observation: `provider_promoted_to_openai`

## Current truth

- OpenAI fallback for embeddings is now **working live**.
- Semantic memory retrieval stays healthy even while Gemini query embeddings are failing.
- Hybrid retrieval stays healthy and no longer dies on empty vectors.
- The main blocker for true local-first is still environment availability of Ollama, not embedding runtime logic.

## Residual note

The current runtime snapshot still shows `openrouter` as usable when an OpenAI-compatible key is configured. That is a configuration-surface ambiguity in the broader OpenAI/OpenRouter credential model, not a blocker for the OpenAI fallback path itself.
