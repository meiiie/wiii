# Graph Refactor Round 49 — 2026-03-29

## Goal

Continue reducing structural coupling without sacrificing the best verified Sentrux checkpoint:

- `Quality: 6808`
- `Coupling: 0.28`
- `Cycles: 0`
- `God files: 0`

## What changed

### 1. Pushed more graph dependencies behind `graph_runtime_bindings`

Expanded [graph_runtime_bindings.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_runtime_bindings.py) so [graph.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py) no longer imports these modules directly:

- `app.engine.tools.invocation`
- `app.engine.tools.runtime_context`
- `app.engine.multi_agent.direct_intent`
- `app.engine.multi_agent.context_injection`
- `app.engine.multi_agent.graph_runtime_helpers`
- visual/code-studio/public-thinking helper clusters already moved in the previous round

This preserved legacy patch paths because `graph.py` still exposes the same names; they now arrive through the compatibility binding layer instead of direct module imports.

### 2. Preserved compatibility seams

Kept or restored patchable symbols required by existing tests, including:

- `filter_tools_for_role`
- `get_reasoning_tracer`
- `_inject_host_context`
- `_build_simple_social_fast_path`
- `time`
- `get_supervisor_agent`

### 3. Rejected and rolled back the `llm_pool` binding experiment

I also tried a similar lazy binding extraction for `llm_pool`, but it did **not** improve the global checkpoint. It reduced local static imports, but Sentrux quality dipped from `6808` to `6806`.

That change was rolled back completely. Current [llm_pool.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/llm_pool.py) is back on the previously verified implementation.

## Results

### Local structural improvement

Custom AST import scan after the graph round:

- `app.engine.multi_agent.graph` internal out-degree: `19 -> 14`

That is a meaningful local cleanup in the most important orchestration shell.

### Global checkpoint

After rolling back the unsuccessful `llm_pool` experiment, Sentrux returned to the best verified state:

- `Quality: 6808`
- `Coupling: 0.28`
- `Cycles: 0`
- `God files: 0`
- `Distance from Main Sequence: 0.31`
- Verdict: `No degradation detected`

## Verification

### Compile

- `py_compile` passed for:
  - [graph.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py)
  - [graph_runtime_bindings.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_runtime_bindings.py)
  - [llm_pool.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/llm_pool.py)

### Tests

Graph-focused batch:

- [test_graph_routing.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_graph_routing.py)
- [test_sprint54_graph_streaming.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_sprint54_graph_streaming.py)
- [test_supervisor_agent.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_supervisor_agent.py)
- [test_sprint203_natural_conversation.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_sprint203_natural_conversation.py)

Result:

- `205 passed`

LLM/runtime batch after rollback:

- [test_llm_failover.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_llm_failover.py)
- [test_llm_pool_multi.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_llm_pool_multi.py)
- [test_admin_llm_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_admin_llm_runtime.py)
- [test_runtime_endpoint_smoke.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_runtime_endpoint_smoke.py)

Result:

- `64 passed`

## Conclusion

This round is worth keeping:

- it preserved the best global checkpoint
- it made `graph.py` materially less coupled at the source level
- it avoided accepting a refactor that looked elegant locally but failed to improve the system globally

## Recommended next target

The next round should again be **checkpoint-preserving** and only touch hubs that are likely to move the global coupling metric, not just local import counts. The best candidates now look like:

1. [app/api/v1/admin.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/admin.py)
2. [app/services/vision_processor.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/services/vision_processor.py)
3. [app/engine/multi_agent/tool_collection.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/tool_collection.py)
