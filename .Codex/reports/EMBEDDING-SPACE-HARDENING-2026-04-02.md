# Embedding Space Hardening - 2026-04-02

## Summary

Wiii's embedding runtime was made mathematically stricter and operationally cleaner:

- `same-space only` guard is now enforced for persistent embeddings and retrieval.
- legacy rows in `semantic_memories` and `knowledge_embeddings` were re-embedded into the active canonical space.
- runtime/admin/selectability now expose cross-family providers as `space_mismatch` instead of silently treating them as safe fallbacks.

This closes the last major gap between:

- provider-agnostic embedding plumbing
- and actual vector-space correctness in a shared `pgvector` index.

## What changed

### 1. Same-space enforcement

The embedding runtime no longer treats all `768d` providers as interchangeable.

- Added provider/model compatibility rule in:
  - `maritime-ai-service/app/engine/model_catalog.py`
- Enforced compatible provider resolution in:
  - `maritime-ai-service/app/engine/embedding_runtime.py`
- Updated embedding selectability reasons in:
  - `maritime-ai-service/app/services/embedding_selectability_service.py`

Result:

- `embeddinggemma` index space can now only resolve through `ollama`
- `text-embedding-3-small/large` can resolve through `openai` or `openrouter`
- cross-family fallbacks like `embeddinggemma -> text-embedding-3-small` are blocked for persistent vector paths

### 2. Embedding-space metadata hygiene

Metadata stamping now prefers the active embedding backend contract, not just static settings.

- Updated:
  - `maritime-ai-service/app/services/embedding_space_guard.py`

Also patched mutation/update paths so rows do not lose fingerprint metadata when embedding-bearing records are updated:

- `maritime-ai-service/app/repositories/fact_repository_mutation_runtime.py`
- `maritime-ai-service/app/repositories/fact_repository_triples.py`

### 3. Legacy row re-embedding

Added re-embed service:

- `maritime-ai-service/app/services/legacy_embedding_reembed_service.py`

Added executable script:

- `maritime-ai-service/scripts/reembed_legacy_embedding_rows.py`

This service:

- scans only rows with live embeddings but missing `_embedding_space` / `embedding_space_fingerprint`
- re-embeds with the active runtime backend
- writes back the embedding plus stamped metadata
- broadcasts embedding refresh version after success

## Live execution result

Applied with:

- active backend: `ollama / embeddinggemma / 768d`
- batch size: `16`

Result JSON:

- `.Codex/reports/legacy-embedding-reembed-2026-04-02-221932.json`

Counts:

- `semantic_memories`: `62 scanned`, `62 updated`, `0 failed`
- `knowledge_embeddings`: `2 scanned`, `2 updated`, `0 failed`

## Post-migration audit

Post-apply audit is now clean:

- `semantic_memories`: `embedded=62`, `tracked=62`, `untracked=0`
- `knowledge_embeddings`: `embedded=2`, `tracked=2`, `untracked=0`
- warnings: none

Canonical fingerprint now present in both tables:

- `ollama:embeddinggemma:768`

## Runtime snapshot after hardening

Current live embedding selectability:

- `ollama`: usable, active, model=`embeddinggemma`
- `google`: blocked=`space_mismatch`
- `openai`: blocked=`missing_api_key`
- `openrouter`: blocked=`missing_api_key`
- `zhipu`: blocked=`space_mismatch`

This is intentional and correct for the current canonical index space.

## Retrieval benchmark after hardening

Benchmark artifact:

- `.Codex/reports/EMBEDDING-RETRIEVAL-BENCHMARK-2026-04-02-222012.md`
- `.Codex/reports/embedding-retrieval-benchmark-2026-04-02-222012.json`

Observed on `ollama_local_first`:

- query embed: `3931.94 ms`
- document embed: `277.81 ms`
- semantic context: `307.42 ms`
- hybrid search: `628.9 ms`
- semantic context returned `1 fact + 1 relevant memory`
- hybrid search returned `2` results

## Tests

Focused suites passed:

- `111 passed` across embedding runtime/selectability/space guard/re-embed/fact/admin touched suites
- follow-up focused rerun after final logging patch: `23 passed`

## Current truth

Wiii embeddings are now in a significantly more correct state:

- the shared index is no longer allowed to drift across embedding families
- legacy untracked vectors have been normalized into the current canonical space
- runtime truth, admin truth, DB truth, and benchmark truth are aligned again

## Next sensible step

If we want to go beyond this point cleanly, the next architectural step is not another ad-hoc fallback.
It is one of these:

1. keep `embeddinggemma` as the canonical local-first production index
2. or deliberately migrate to a new canonical space such as `text-embedding-3-small/768`
3. or add true multi-index support if Wiii needs multiple embedding families at once

What should not be done anymore:

- silently mixing different embedding model families inside the same persistent retrieval index
