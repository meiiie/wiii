# Graph Refactor Round 42

Date: 2026-03-29

## Scope

This round focused on the `multi_agent` routing core and the remaining real import-cycle pressure around it.

Goals:

1. Extract the large structured-routing body from `SupervisorAgent`.
2. Remove the remaining `tutor_node -> graph` dependency.
3. Re-measure both custom import SCCs and Sentrux cycle metrics.

## Changes

### 1. Supervisor structured routing extraction

Created:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\supervisor_structured_runtime.py`

Extracted:

- `route_structured_impl()`

Updated:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\supervisor.py`

Result:

- `supervisor.py`: `742 -> 566` lines
- `supervisor_structured_runtime.py`: `271` lines

`SupervisorAgent._route_structured()` now acts as a thin compatibility wrapper that still:

- imports `RoutingDecision` at call time
- imports `StructuredInvokeService` at call time
- delegates the full routing flow into `route_structured_impl(...)`

This preserves the existing monkeypatch/test surface while moving the heavy decision logic out of the shell.

### 2. Tutor node cycle cut

Updated:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_node.py`

Changed:

- removed runtime imports from `app.engine.multi_agent.graph`
- now reads:
  - `_get_effective_provider` from `graph_surface_runtime`
  - `_resolve_tool_choice` from `direct_prompts`

This cut the real import back-edge that was recreating a `multi_agent` SCC through:

- `graph`
- `subagent_dispatch`
- `tutor_node`

## Validation

### Compile

Passed:

- `supervisor.py`
- `supervisor_structured_runtime.py`
- `tutor_node.py`

### Focused routing/graph batch

Passed:

- `tests/unit/test_supervisor_agent.py`
- `tests/unit/test_graph_routing.py`
- `tests/unit/test_sprint54_graph_streaming.py`

Result:

- `159 passed`

### Tutor-related batch

Result:

- `101 passed`
- `5 failed`

Failed file:

- `tests/unit/test_sprint52_tutor_tools.py`

These failures are not in touched modules. They are message-string expectation drift around accented Vietnamese output such as:

- expected: `khong kha dung`, `Loi`, `Chua co buoi hoc`
- actual runtime strings: `không khả dụng`, `Lỗi`, `Chưa có buổi học`

That is outside the refactor surface of this round.

## Cycle Measurements

### Custom AST import SCC scan

Result after the tutor-edge cut:

- `AST import SCC count: 0`

This confirms there are no remaining nontrivial import strongly connected components in the backend Python module graph under the current custom scan.

### Sentrux

Latest gate:

- `Quality: 5943`
- `Coupling: 0.29`
- `Cycles: 1`
- `God files: 0`
- `Distance from Main Sequence: 0.31`
- Verdict: `No degradation detected`

Delta from original baseline:

- `Quality: 3581 -> 5943`
- `Coupling: 0.36 -> 0.29`
- `Cycles: 8 -> 1`
- `God files: 9 -> 0`

## Assessment

This round materially improved the architecture in the place that matters most for future `thinking` work:

- the supervisor routing shell is now substantially thinner
- the real import-level `multi_agent` cycle is gone again
- Sentrux cycle pressure dropped from `2` to `1`

At this point, the remaining Sentrux `Cycles: 1` no longer appears to be a plain Python import SCC. It is likely coming from a broader heuristic than raw import cycles, so the next step should be targeted investigation rather than blind file splitting.
