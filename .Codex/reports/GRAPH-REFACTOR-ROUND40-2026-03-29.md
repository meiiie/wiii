# Graph Refactor Round 40 — Cycle Collapse

> Date: 2026-03-29
> Scope: Collapse remaining `multi_agent` import SCCs without changing thinking behavior.

---

## Summary

This round focused on the last structural knot inside `app.engine.multi_agent`.

Key outcomes:

- Extracted the streaming event bus into a standalone module so runtime producers no longer depend on `graph_streaming.py`.
- Added compatibility hooks so older tests that patch `graph_streaming._get_event_queue` or graph-level direct helpers still work.
- Removed the final import-level SCC in the backend app tree.

Custom AST SCC scan result after this round:

- `Nontrivial SCC count: 0`

Sentrux gate after this round:

- `Quality: 3581 -> 5471`
- `Coupling: 0.36 -> 0.29`
- `Cycles: 8 -> 2`
- `God files: 9 -> 0`
- `No degradation detected`

Important note:

- The import-graph SCCs are now gone (`0` by custom AST scan).
- Sentrux still reports `Cycles: 2`, which strongly suggests its remaining cycle metric is broader than simple Python import SCCs.

---

## Main Refactors

### 1. Shared Event Bus Extraction

Created:

- `app/engine/multi_agent/graph_event_bus.py`

Moved shared bus ownership there:

- `_EVENT_QUEUES`
- `_EVENT_QUEUE_CREATED`
- `_get_event_queue()`
- `_register_event_queue()`
- `_discard_event_queue()`
- `_cleanup_stale_queues()`

Updated:

- `app/engine/multi_agent/graph_streaming.py`
- `app/engine/multi_agent/graph_stream_runtime.py`
- `app/engine/multi_agent/graph.py`
- `app/engine/multi_agent/graph_process.py`
- `app/engine/multi_agent/direct_node_runtime.py`
- `app/engine/multi_agent/subagent_dispatch.py`
- `app/engine/multi_agent/supervisor_surface.py`
- `app/engine/multi_agent/agents/memory_agent.py`
- `app/engine/multi_agent/agents/product_search_node.py`
- `app/engine/multi_agent/agents/rag_node.py`
- `app/engine/multi_agent/agents/tutor_node.py`
- `app/engine/multi_agent/subagents/aggregator.py`
- `app/engine/multi_agent/subagents/search/workers.py`
- `app/engine/tools/runtime_context.py`

Compatibility detail:

- `graph_streaming.py` still re-exports event-bus symbols for legacy tests.
- `graph_event_bus._get_event_queue()` now detects monkeypatched `graph_streaming._get_event_queue` and delegates to it.

### 2. Reduced Final `multi_agent` SCC

Before second half of this round, the remaining AST SCC was:

- size `9`
- centered on `graph`, `graph_runtime_bindings`, `direct_execution`, `direct_tool_rounds_runtime`, `agent_nodes`, `product_search_runtime`, and `code_studio_response`

To shrink it, this round also:

- changed `agent_nodes.py` to use `graph_trace_store._get_or_create_tracer`
- changed `product_search_runtime.py` to use `graph_surface_runtime.get_effective_provider_impl`
- created `app/engine/multi_agent/code_studio_patterns.py` and moved Code Studio regex constants there
- created `app/engine/multi_agent/direct_runtime_bindings.py` and moved direct-lane bridge helpers there:
  - `_extract_runtime_target`
  - `_remember_runtime_target`
  - `_truncate_before_code_dump`
  - `_inject_widget_blocks_from_tool_results`
  - `_render_reasoning_fast`
  - `_stream_openai_compatible_answer_with_route`

Compatibility detail:

- `direct_runtime_bindings.py` checks `sys.modules["app.engine.multi_agent.graph"]` for monkeypatched graph-level helpers before falling back to the new shared implementation.
- This preserved tests that still patch:
  - `graph._render_reasoning_fast`
  - `graph._stream_openai_compatible_answer_with_route`

### 3. Runtime Regression Fixes

During the refactor, the following regressions were found and fixed:

- `graph_stream_runtime.py` was missing `import time`
- a few lazy import replacements had indentation drift
- `direct_tool_rounds_runtime.py` still referenced `_graph_module` after the static import was removed

All of those were corrected in the same round.

---

## Verification

### Compile

Passed:

- targeted `py_compile` for all touched event-bus and direct-runtime files

### Test Batches

Passed:

- `tests/unit/test_event_bus.py`
- `tests/unit/test_sprint54_graph_streaming.py`
- `tests/unit/test_graph_routing.py`
- `tests/unit/test_graph_thread_id.py`
- `tests/unit/test_guardian_graph_node.py`
- `153 passed`

Passed:

- `tests/unit/test_supervisor_agent.py`
- `tests/unit/test_graph_routing.py`
- `tests/unit/test_sprint54_graph_streaming.py`
- `tests/unit/test_sprint200_visual_search.py`
- `tests/unit/test_product_search_tools.py`
- `240 passed`

Passed:

- `tests/unit/test_graph_routing.py`
- `tests/unit/test_sprint154_tech_debt.py`
- `tests/unit/test_supervisor_agent.py`
- `tests/unit/test_sprint54_graph_streaming.py`
- `tests/unit/test_sprint200_visual_search.py`
- `281 passed`

Requests warning still appears in local env:

- `RequestsDependencyWarning` for `urllib3/chardet/charset_normalizer`

This warning is unrelated to the refactor.

---

## Structural State After Round 40

Notable line counts:

- `app/engine/multi_agent/graph_event_bus.py`: `51`
- `app/engine/multi_agent/direct_runtime_bindings.py`: `113`
- `app/engine/multi_agent/code_studio_patterns.py`: `33`
- `app/engine/multi_agent/graph_streaming.py`: `492`
- `app/engine/multi_agent/graph_stream_runtime.py`: `277`
- `app/engine/multi_agent/direct_execution.py`: `477`
- `app/engine/multi_agent/direct_tool_rounds_runtime.py`: `501`
- `app/engine/multi_agent/code_studio_response.py`: `237`
- `app/engine/multi_agent/agents/product_search_runtime.py`: `616`
- `app/engine/multi_agent/agent_nodes.py`: `330`

Interpretation:

- The old graph shell no longer owns the event-bus infrastructure.
- Direct-lane runtime helpers now live in a shared bridge rather than forcing imports back into `graph.py`.
- Import-level cycles are effectively eliminated in `app/`.

---

## Remaining Work

The backend is now in a much better place for the future thinking redesign:

- `God files: 0`
- import-level SCCs: `0`
- coupling reduced to `0.29`

The next high-ROI structural step is no longer “split giant files”.
It is:

1. investigate what Sentrux still counts as `Cycles: 2`
2. determine whether those are call-graph cycles, inheritance cycles, or unresolved import heuristics
3. then decide if another cleanup pass is worth it before returning to thinking/system behavior

