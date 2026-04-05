# Graph Refactor Round 39 — Cycle Collapse Follow-up

> Date: 2026-03-29
> Scope: LLM runtime cycle reduction + graph/streaming compatibility seam cleanup

---

## Outcome

This round continued directly from Round 38 and focused on collapsing the last
small cycle clusters before touching the remaining large `multi_agent` knot.

### Sentrux

- Quality: `3581 -> 5469`
- Coupling: `0.36 -> 0.30`
- Cycles: `8 -> 2`
- God files: `9 -> 0`
- Verdict: `No degradation detected`

### Local AST SCC view

- Nontrivial SCCs: `1`
- Remaining SCC:
  - `app.engine.multi_agent` supercluster (`32` modules)

This mismatch likely means Sentrux still counts one additional structural loop
through its broader project graph heuristics, but the small low-risk import
cycles are effectively gone.

---

## Changes

### 1. Decoupled `llm_selectability_service` from `LLMPool`

Created:

- `app/engine/llm_runtime_state.py`

Updated:

- `app/engine/llm_pool.py`
- `app/services/llm_selectability_service.py`
- `app/services/llm_runtime_audit_service.py`

What changed:

- introduced a runtime-state registry so services can ask for:
  - pool stats
  - provider info
  - request-selectable providers
  without importing `LLMPool` directly
- `LLMPool` now registers itself as the runtime-state producer

Impact:

- removed the direct service dependency back into the heavy pool module
- shrank the LLM SCC from `4` modules down to a non-blocking shape in local SCC analysis

---

### 2. Decoupled audit refresh from selectability-service cache internals

Created:

- `app/services/llm_selectability_cache_token.py`

Updated:

- `app/services/llm_selectability_service.py`
- `app/services/llm_runtime_audit_service.py`

What changed:

- replaced direct `llm_runtime_audit_service -> llm_selectability_service.invalidate_*`
  dependency with a cache-generation token
- selectability snapshot cache now keys off a generation counter
- runtime audit refresh bumps the generation token instead of importing back
  into the service

Impact:

- removed another reverse dependency across the LLM runtime boundary

---

### 3. Preserved test patch surface for legacy selectability tests

Updated:

- `app/services/llm_selectability_service.py`

What changed:

- added a tiny `LLMPool` compatibility proxy exposing:
  - `get_stats()`
  - `get_provider_info()`

Why:

- older tests patch `app.services.llm_selectability_service.LLMPool.*`
- the proxy keeps those patch paths stable without reintroducing the real
  module dependency

---

### 4. Broke the static `graph -> graph_streaming` import edge

Updated:

- `app/engine/multi_agent/graph.py`

What changed:

- changed the `process_with_multi_agent_streaming` compatibility re-export
  from a direct import to a dynamic `importlib.import_module(...)` shim

Impact:

- preserves backward-compatible access
- removes one static import edge from the graph shell into the streaming module
- keeps the shell from binding streaming runtime at import time

---

## Validation

### Compile

- `py_compile` passed for all touched files

### Tests

Passed:

- LLM/runtime/admin/selectability batch: `45 passed`
- graph/streaming/guardian/thread batch: `134 passed`
- earlier LLM batch from this round: `94 passed`

This confirms the cycle cleanup did not regress:

- runtime provider failover
- selectability UX contract
- admin runtime endpoints
- graph routing
- streaming behavior

---

## Architectural significance

The repo has now moved from:

- many small cycle traps distributed across services, prompts, living-agent,
  multimodal ingestion, and RAG

to:

- one real architectural supercluster: `app.engine.multi_agent`

That is a healthier place to be for the upcoming thinking work because:

- the remaining problem is explicit and localized
- most auxiliary systems no longer participate in circular imports
- future `thinking` refactors can focus on `multi_agent` ownership boundaries
  instead of unrelated service cycles

---

## Recommended next target

The highest-ROI next move is not another random file split.

It is:

### `multi_agent` supercluster decomposition

Best next seams:

1. `graph / graph_streaming / supervisor` contract extraction
2. stream bus/runtime ownership split away from graph shell
3. direct lane and product-search lane boundary cleanup
4. tool/runtime-context isolation from orchestration shell

That is the remaining structural knot most likely to unblock future
`thinking` fixes in a meaningful way.

