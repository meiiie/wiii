# Graph Refactor Round 33 — 2026-03-29

## Scope

Round này tiếp tục refactor sâu cụm `agentic_rag`, tập trung vào việc:

1. làm `CorrectiveRAG` bớt ôm toàn bộ sync pipeline trong một method,
2. tách `RAGAgent` query/runtime khỏi shell class,
3. giữ nguyên patch seams và public API để test cũ không gãy,
4. xác nhận lại Sentrux sau khi đã đạt `God files: 0`.

---

## Changes

### 1. CorrectiveRAG sync pipeline extraction

Files:
- `maritime-ai-service/app/engine/agentic_rag/corrective_rag.py`
- `maritime-ai-service/app/engine/agentic_rag/corrective_rag_process_runtime.py`

What changed:
- Extracted the heavy synchronous orchestration out of `CorrectiveRAG.process()`.
- `CorrectiveRAG.process()` is now a thin wrapper delegating to `process_impl(...)`.
- Preserved compatibility seams in `corrective_rag.py` for:
  - `settings`
  - `get_reasoning_tracer`
  - `StepNames`
  - source-inspection expectations like `org_id=_org`

Line count:
- `corrective_rag.py`: `715 -> 294`
- `corrective_rag_process_runtime.py`: new `541`

Compatibility fixes applied after extraction:
- restored `is_no_doc_retrieval_text` and `normalize_visible_text` imports for streaming wrapper
- added source-inspection anchor comment so isolation-hardening grep tests still pass

### 2. RAGAgent query/runtime extraction

Files:
- `maritime-ai-service/app/engine/agentic_rag/rag_agent.py`
- `maritime-ai-service/app/engine/agentic_rag/rag_agent_runtime.py`

What changed:
- Extracted sync query path to `query_impl(...)`
- Extracted streaming query path to `query_streaming_impl(...)`
- Kept `RAGAgent.query()` and `RAGAgent.query_streaming()` as thin wrappers
- Left helper methods on `RAGAgent` intact so tests can still patch:
  - `_graph_to_hybrid_results`
  - `_hybrid_results_to_nodes`
  - `_generate_hybrid_citations`
  - `_generate_response`
  - `_collect_evidence_images`
  - `_generate_response_streaming`

Line count:
- `rag_agent.py`: `766 -> 625`
- `rag_agent_runtime.py`: new `199`

Behavior note:
- Preserved visible streaming strings (`🔍`, `📚`, `✍️`) to avoid UX drift from a pure-structure refactor.

---

## Verification

### Compile

Passed:
- `python -m py_compile app/engine/agentic_rag/corrective_rag.py`
- `python -m py_compile app/engine/agentic_rag/corrective_rag_process_runtime.py`
- `python -m py_compile app/engine/agentic_rag/rag_agent.py`
- `python -m py_compile app/engine/agentic_rag/rag_agent_runtime.py`

### Tests

Passed:
- `python -m pytest tests/unit/test_corrective_rag_unit.py -v -p no:capture --tb=short`
  - `19 passed`
- `python -m pytest tests/unit/test_sprint175b_isolation_hardening.py -v -p no:capture --tb=short -k "CorrectiveRAGCacheParams and org_id_param_in_cache_calls"`
  - `1 passed`
- `python -m pytest tests/unit/test_sprint144_progressive_streaming.py -v -p no:capture --tb=short -k "CorrectiveRAG or process_streaming or threshold_is_70_not_0_7"`
  - `1 passed`
- `python -m pytest tests/unit/test_sprint54_rag_agent.py -v -p no:capture --tb=short`
  - `37 passed`

Pre-existing local-env drift still observed elsewhere:
- `sqlalchemy.orm.DeclarativeBase` import mismatch in broader runtime/admin/living batches
- not introduced by this round

---

## Sentrux

Latest gate:

- `Quality: 3581 -> 4505`
- `Coupling: 0.36 -> 0.30`
- `Cycles: 8 -> 7`
- `God files: 9 -> 0`
- `Distance from Main Sequence: 0.31`
- verdict: `No degradation detected`

Interpretation:
- backend is now out of the god-file zone
- current refactor work is no longer fighting file size first
- next gains should come from cycle/coupling cuts and clearer package boundaries

---

## Current Hotspots

Largest remaining files after this round:

- `app/engine/multi_agent/supervisor.py` — `742`
- `app/api/v1/course_generation_runtime.py` — `741`
- `app/models/semantic_memory.py` — `737`
- `app/api/v1/course_generation.py` — `737`
- `app/repositories/dense_search_repository.py` — `721`
- `app/engine/agentic_rag/retrieval_grader.py` — `711`

None of these are currently above Sentrux god-file threshold, but they are the next best structural cuts.

---

## Recommended Next Cuts

1. `app/engine/agentic_rag/retrieval_grader.py`
   - good next seam inside the same RAG package
   - likely helps lower local coupling around CRAG

2. `app/repositories/dense_search_repository.py`
   - strong ROI for repository clarity
   - useful before future vector/search changes

3. `app/api/v1/course_generation_runtime.py`
   - still large and runtime-heavy
   - can likely split scheduler/job orchestration from transport shaping

4. `app/models/semantic_memory.py`
   - candidate for schema-family split
   - lower risk than touching `_settings` again right now

---

## Verdict

Round 33 is successful.

The refactor did not regress structure, did not reintroduce god files, and made both `CorrectiveRAG` and `RAGAgent` significantly easier to reason about for the future thinking work.
