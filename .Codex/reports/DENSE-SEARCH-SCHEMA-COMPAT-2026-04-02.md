# Dense Search Schema Compatibility

- Date: `2026-04-02`
- Workspace: `E:\Sach\Sua\AI_v1`

## Problem

Dense search write paths in `dense_search_repository_runtime.py` still assumed
`knowledge_embeddings.node_id` existed.

Actual production-like local schema on this machine is:

- primary key column: `id` (`uuid`)
- no `node_id` column

This caused ingestion/storage failures like:

- `column "node_id" of relation "knowledge_embeddings" does not exist`

Which meant:

- benchmark text seeding failed
- text ingestion / chunk storage paths could fail on real schema
- retrieval benchmarks were blocked even after embeddings were fixed

## Fix

Patched:

- [dense_search_repository_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/repositories/dense_search_repository_runtime.py)

Changes:

- detect whether `knowledge_embeddings` has `node_id`
- if yes: preserve legacy behavior
- if no: map legacy `node_id` strings onto deterministic UUIDs via `uuid5`
- use the resolved key consistently for:
  - `store_embedding`
  - `upsert_embedding`
  - `store_document_chunk`
  - `delete_embedding`
  - `get_embedding`
- preserve original legacy id in metadata as `legacy_node_id` when running on UUID schema

## Tests

Added:

- [test_dense_search_repository_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_dense_search_repository_runtime.py)

Result:

- `2 passed`

## Verification

After patch:

- benchmark Rule 15 seed stored successfully into `knowledge_embeddings`
- current benchmark seed created `2` rows

See:

- [EMBEDDING-RETRIEVAL-BENCHMARK-2026-04-02-195915.md](E:/Sach/Sua/AI_v1/.Codex/reports/EMBEDDING-RETRIEVAL-BENCHMARK-2026-04-02-195915.md)

Key outcomes from the refreshed benchmark:

- `google_first`
  - query embedding still fails due Gemini quota exhaustion
  - hybrid search returns 2 results because sparse retrieval still works on seeded KB
- `ollama_local_first`
  - query embedding works
  - semantic memory returns `1 fact + 1 relevant memory`
  - hybrid search returns `2 results` in `142.46 ms`

## Current Conclusion

The knowledge retrieval bottleneck was split into two separate issues:

1. embedding provider exhaustion on Gemini
2. dense-search write path incompatibility with current UUID schema

Both are now understood, and the second one has been fixed.
