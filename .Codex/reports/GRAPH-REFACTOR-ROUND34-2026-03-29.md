# Graph Refactor Round 34 — 2026-03-29

## Scope

Round này tiếp tục refactor sau khi backend đã đạt `God files: 0`, tập trung vào 2 hotspot có ROI cao trong path RAG/search:

1. `retrieval_grader.py`
2. `dense_search_repository.py`

Mục tiêu là giảm trách nhiệm dồn cục trong từng module nhưng vẫn giữ nguyên các public methods và patch seams mà test hiện tại đang bám vào.

---

## Changes

### 1. RetrievalGrader support extraction

Files:
- `maritime-ai-service/app/engine/agentic_rag/retrieval_grader.py`
- `maritime-ai-service/app/engine/agentic_rag/retrieval_grader_support.py`

What changed:
- Extracted batch-grading and feedback helpers into `retrieval_grader_support.py`
- Kept these methods on `RetrievalGrader` as wrappers:
  - `_batch_grade_structured`
  - `_batch_grade_legacy`
  - `_sequential_grade_documents`
  - `_parse_batch_response`
  - `_build_feedback_direct`
  - `_generate_feedback`

Compatibility fixes:
- restored lazy import of `extract_thinking_from_response` so unit tests can still patch the original path
- restored accented Vietnamese feedback text expected by existing tests
- structured grading now prefers `llm.with_structured_output(...)` when available, then falls back to `StructuredInvokeService`

Line count:
- `retrieval_grader.py`: `711 -> 632`
- `retrieval_grader_support.py`: new `232`

### 2. DenseSearchRepository CRUD extraction

Files:
- `maritime-ai-service/app/repositories/dense_search_repository.py`
- `maritime-ai-service/app/repositories/dense_search_repository_runtime.py`

What changed:
- Kept `search()` and pool/search-specific SQL local, because tests inspect and exercise those paths heavily
- Extracted CRUD/runtime methods:
  - `store_embedding`
  - `upsert_embedding`
  - `store_document_chunk`
  - `delete_embedding`
  - `get_embedding`
  - `count_embeddings`
  - `close`

Support module responsibilities:
- pgvector string conversion
- org resolution
- org-scoped CRUD SQL
- connection close/count helpers

Line count:
- `dense_search_repository.py`: `721 -> 475`
- `dense_search_repository_runtime.py`: new `332`

---

## Verification

### Compile

Passed:
- `python -m py_compile app/engine/agentic_rag/retrieval_grader.py`
- `python -m py_compile app/engine/agentic_rag/retrieval_grader_support.py`
- `python -m py_compile app/repositories/dense_search_repository.py`
- `python -m py_compile app/repositories/dense_search_repository_runtime.py`

### Tests

RetrievalGrader:
- `python -m pytest tests/unit/test_sprint44_retrieval_grader.py -v -p no:capture --tb=short`
  - `35 passed`
- `python -m pytest tests/unit/test_sprint67_structured_outputs.py -v -p no:capture --tb=short -k "RetrievalGraderStructured or RetrievalGraderLegacy"`
  - `7 passed`

DenseSearchRepository:
- `python -m pytest tests/unit/test_sprint170b_pgvector_overhaul.py tests/unit/test_sprint160_data_isolation.py tests/unit/test_sprint170c_tenant_hardening.py -v -p no:capture --tb=short -k "DenseSearch or SearchRepoOrgIsolation or DenseSearchOrgFiltering"`
  - `18 passed`
- `python -m pytest tests/unit/test_connection_pool_config.py tests/unit/test_sprint47_hybrid_search.py -v -p no:capture --tb=short -k "DenseSearch or store_embedding or delete_embedding or close"`
  - `4 passed`

---

## Sentrux

Latest gate after this round:

- `Quality: 3581 -> 4504`
- `Coupling: 0.36 -> 0.30`
- `Cycles: 8 -> 7`
- `God files: 9 -> 0`
- `Distance from Main Sequence: 0.31`
- verdict: `No degradation detected`

Interpretation:
- this round kept the structural win stable
- backend remains out of the god-file zone
- top remaining gains are now mostly about cycle/coupling reduction and package-boundary cleanup, not giant-file surgery

---

## Current Hotspots

Largest remaining modules:

- `app/engine/multi_agent/supervisor.py` — `742`
- `app/api/v1/course_generation_runtime.py` — `741`
- `app/models/semantic_memory.py` — `737`
- `app/api/v1/course_generation.py` — `737`
- `app/engine/tools/visual_payload_runtime.py` — `708`
- `app/core/security.py` — `708`
- `app/engine/multi_agent/subagents/search/workers_runtime.py` — `705`

These are not god files anymore, but they are still the best candidates for the next clean-architecture cuts.

---

## Recommended Next Cuts

1. `app/models/semantic_memory.py`
   - good schema-family split candidate
   - low runtime blast radius

2. `app/core/security.py`
   - high centrality, likely helps coupling if split carefully

3. `app/api/v1/course_generation_runtime.py`
   - still dense, but should be refactored after stabilizing model/repository layer cuts

4. `app/engine/tools/visual_payload_runtime.py`
   - good candidate once visual runtime policy drift is intentionally addressed

---

## Verdict

Round 34 is successful.

This round did not chase line count blindly. It reduced ownership density in both the retrieval grader and dense repository while preserving the behavior seams that the current test suite relies on. That keeps the project moving toward clean architecture without destabilizing the search path.
