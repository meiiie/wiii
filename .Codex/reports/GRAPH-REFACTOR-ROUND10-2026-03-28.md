# Graph Refactor Round 10 — 2026-03-28

> Scope: continue structural refactor for clean architecture, without changing thinking behavior
> Focus: `graph_streaming.py` god-file reduction + stream node ownership extraction

---

## 1. Summary

This round targeted the streaming shell again and removed another large slice of mixed responsibilities from:

- `app/engine/multi_agent/graph_streaming.py`

New helper module:

- `app/engine/multi_agent/graph_stream_node_runtime.py`

The goal was not to change public thinking behavior, but to make stream-node ownership clearer so future `thinking` work can happen on stable seams.

---

## 2. What Changed

### 2.1 Extracted stream node helper runtime

Created:

- `app/engine/multi_agent/graph_stream_node_runtime.py`

Moved/refactored into helper functions:

- `emit_tool_call_events_impl()`
- `emit_node_thinking_impl()`
- `emit_document_previews_impl()`
- `emit_web_previews_impl()`
- `emit_product_previews_impl()`

These helpers now own:

- tool call/result event fan-out
- node thinking lifecycle emission
- document preview emission
- direct web preview parsing/emission
- product preview parsing/emission

### 2.2 Simplified `graph_streaming.py`

`graph_streaming.py` now delegates repeated per-node surface work instead of inlining it.

Refactored nodes:

- `rag_agent`
- `tutor_agent`
- `memory_agent`
- `direct`
- `code_studio_agent`
- `product_search_agent`

### 2.3 Removed thin wrappers

Deleted local wrapper layers for:

- `_build_stream_bootstrap()`
- `_emit_stream_finalization()`

`process_with_multi_agent_streaming()` now calls runtime helpers directly.

### 2.4 Deleted dead fallback labels

Removed unused `_WIII_FALLBACK_LABELS` constant from `graph_streaming.py`.

---

## 3. Size Impact

### Before this round

- `graph_streaming.py`: `1261` lines

### After this round

- `graph_streaming.py`: `984` lines
- `graph_stream_node_runtime.py`: `293` lines

Result:

- `graph_streaming.py` is now below the god-file threshold.

---

## 4. Verification

### Compile

Passed:

- `python -m py_compile app/engine/multi_agent/graph_streaming.py`
- `python -m py_compile app/engine/multi_agent/graph_stream_node_runtime.py`

### Tests

Passed:

- `tests/unit/test_sprint54_graph_streaming.py`
- `tests/unit/test_graph_visual_widget_injection.py`
- `tests/unit/test_supervisor_agent.py`
- `tests/unit/test_graph_routing.py`

Observed totals:

- `91 passed`
- `73 passed`

No streaming regression detected in focused test coverage.

### Sentrux

Latest gate result:

- `Quality: 3581 -> 3593`
- `Coupling: 0.36 -> 0.34`
- `Cycles: 8 -> 8`
- `God files: 9 -> 7`
- `Distance from Main Sequence: 0.36`
- Verdict: `No degradation detected`

---

## 5. Why This Matters for Future Thinking Fixes

Before this round, `graph_streaming.py` still mixed:

- stream bootstrap/finalization
- node-specific thinking lifecycle logic
- tool event fan-out
- preview parsing/render preparation
- orchestration loop control

That made it hard to reason about:

- which layer truly owns public stream events
- where duplicate/layered thinking can leak back in
- how to test node-specific stream behavior in isolation

After this round:

- the orchestration shell is thinner
- per-node surface emission is more explicit
- future `thinking` refactors can target helpers instead of cutting into the central loop every time

---

## 6. Remaining Hotspots

Largest backend files after this round include:

- `app/engine/tools/visual_tools.py` — `2751`
- `app/core/config/_settings.py` — `1689`
- `app/api/v1/admin.py` — `1458`
- `app/engine/multi_agent/graph.py` — `1394`
- `app/engine/multi_agent/agents/tutor_node.py` — `1378`
- `app/api/v1/course_generation.py` — `1355`
- `app/engine/search_platforms/adapters/browser_base.py` — `1223`
- `app/repositories/fact_repository.py` — `1122`
- `app/engine/agentic_rag/corrective_rag.py` — `1089`
- `app/engine/tools/visual_pendulum_scaffold.py` — `1083`

Highest-ROI next cuts:

1. `corrective_rag.py`
2. `visual_pendulum_scaffold.py`
3. `fact_repository.py`
4. `browser_base.py`

---

## 7. Recommendation

Continue the current strategy:

1. Keep reducing god files below threshold one by one
2. Prefer helper/runtime extraction over giant rewrites
3. Keep running Sentrux + focused tests after each cut
4. Delay `thinking` quality work until these structural seams stabilize further

This round was a clean architectural win and improved maintainability without broad behavior churn.
