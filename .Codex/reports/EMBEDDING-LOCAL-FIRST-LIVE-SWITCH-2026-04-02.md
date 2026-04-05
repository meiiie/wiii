# Embedding Local-First Live Switch

- Date: `2026-04-02`
- Workspace: `E:\Sach\Sua\AI_v1`

## What Changed

Persisted runtime embedding policy was switched to local-first:

- `embedding_provider = auto`
- `embedding_failover_chain = ['ollama', 'google', 'openai']`
- `embedding_model = embeddinggemma`
- `embedding_dimensions = 768`

Verification in-process after applying and persisting:

- active backend: `ollama / embeddinggemma`
- persisted record now contains the same embedding policy fields
- selectability snapshot:
  - `ollama`: usable, active
  - `google`: usable, standby
  - `openai`: blocked by missing API key
  - `openrouter`: blocked by missing API key
  - `zhipu`: fail-closed for embeddings (`model_unverified`)

## Benchmark Truth

See:

- [EMBEDDING-RETRIEVAL-BENCHMARK-2026-04-02-195059.md](E:/Sach/Sua/AI_v1/.Codex/reports/EMBEDDING-RETRIEVAL-BENCHMARK-2026-04-02-195059.md)
- [embedding-retrieval-benchmark-2026-04-02-195059.json](E:/Sach/Sua/AI_v1/.Codex/reports/embedding-retrieval-benchmark-2026-04-02-195059.json)

Important observations:

- `google_first` is currently degraded for retrieval because Gemini embeddings hit `429 RESOURCE_EXHAUSTED`.
- `ollama_local_first` successfully produced:
  - query embedding `768d`
  - document embedding `768d`
  - semantic context retrieval with `1 fact + 1 relevant memory`
- Ollama local-first therefore works as a real operational fallback, not just a theoretical config.

## Database State

Current PostgreSQL counts:

- `semantic_memories = 718`
- `knowledge_embeddings = 0`
- `organization_documents = 0`
- `admin_runtime_settings = 2`

Meaning:

- semantic memory has data
- knowledge-base retrieval is currently empty because there are no ingested organization documents and no dense knowledge embeddings
- hybrid search cannot improve until ingestion repopulates `knowledge_embeddings`

## Current Conclusion

The embedding runtime is now in a healthier state than before:

- memory/retrieval no longer depend solely on Gemini embeddings
- local-first embeddings are operational through Ollama
- the next bottleneck is not embeddings anymore, but knowledge ingestion state

## Best Next Step

Restore or seed knowledge ingestion so that:

- `organization_documents > 0`
- `knowledge_embeddings > 0`

Only after that will hybrid search and RAG retrieval become meaningfully benchmarkable again.
