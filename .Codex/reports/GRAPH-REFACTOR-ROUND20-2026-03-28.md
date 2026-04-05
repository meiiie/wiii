# Graph Refactor Round 20

> Date: 2026-03-28
> Scope: continue structural refactor only, no thinking/prompt changes

## What changed

### 1. Streaming dispatch extracted further

- Added [graph_stream_dispatch_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_stream_dispatch_runtime.py)
- [graph_streaming.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_streaming.py) now delegates the large `state_update -> stream events` branch tree to a dedicated runtime helper.

Result:
- `graph_streaming.py`: `895 -> 511` lines

### 2. Direct tool rounds extracted

- Added [direct_tool_rounds_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_tool_rounds_runtime.py)
- [direct_execution.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_execution.py) now keeps wrapper/orchestration only for `_execute_direct_tool_rounds`.

Result:
- `direct_execution.py`: `894 -> 495` lines

### 3. Graph shell entrypoints thinned

- Added [graph_entrypoints_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_entrypoints_runtime.py)
- Extended [guardian_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/guardian_runtime.py) with singleton accessor
- Extended [subagent_dispatch.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/subagent_dispatch.py) with registry builder
- [graph.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py) now delegates graph lifecycle/singleton/subagent registry ownership out of the shell

Result:
- `graph.py`: `899 -> 830` lines

### 4. LLM pool bootstrap extracted

- Added [llm_pool_bootstrap_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/llm_pool_bootstrap_runtime.py)
- [llm_pool.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/llm_pool.py) now delegates provider bootstrap/primary/fallback creation helpers to runtime support

Result:
- `llm_pool.py`: `879 -> 696` lines

### 5. Heartbeat cycle execution extracted

- Extended [heartbeat_runtime_support.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/living_agent/heartbeat_runtime_support.py) with `execute_heartbeat_cycle_impl`
- [heartbeat.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/living_agent/heartbeat.py) now keeps scheduler shell/API while cycle execution lives in support

Result:
- `heartbeat.py`: `898 -> 790` lines

## Verification

### Compile

- `py_compile` pass for all new/modified files in this round

### Tests

Passed:
- `tests/unit/test_sprint54_graph_streaming.py`
- `tests/unit/test_graph_visual_widget_injection.py`
- `tests/unit/test_graph_routing.py`
- `tests/unit/test_supervisor_agent.py`
- `tests/unit/test_graph_thread_id.py`
- `tests/unit/test_guardian_graph_node.py`
- `tests/unit/test_sprint171_heartbeat_audit.py`

Focused batches observed:
- streaming/routing/supervisor batch: `164 passed`
- graph/guardian batch: `180 passed`
- graph compatibility batch after wrapper cleanup: `94 passed`
- heartbeat audit batch: `4 passed`

Known pre-existing red tests still observed in unrelated runtime metadata area:
- [test_llm_runtime_profiles.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_llm_runtime_profiles.py)
- [test_chat_request_flow.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_chat_request_flow.py)

These were already known drift/debt and were not introduced by this refactor round.

## Sentrux

Latest gate:

- `Quality: 3581 -> 3610`
- `Coupling: 0.36 -> 0.32`
- `Cycles: 8 -> 8`
- `God files: 9 -> 4`
- verdict: `No degradation detected`

## Largest files now

- [_settings.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/core/config/_settings.py): `1689`
- [models/schemas.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/models/schemas.py): `896`
- [course_generation.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/course_generation.py): `895`
- [admin.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/admin.py): `895`
- [model_catalog.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/model_catalog.py): `893`
- [corrective_rag.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/agentic_rag/corrective_rag.py): `890`
- [rag_agent.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/agentic_rag/rag_agent.py): `882`
- [context_manager.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/context_manager.py): `880`
- [supervisor.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/supervisor.py): `879`

## Recommended next cuts

Highest ROI next:

1. [_settings.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/core/config/_settings.py)
2. [models/schemas.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/models/schemas.py)
3. [course_generation.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/course_generation.py)
4. [admin.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/admin.py)
5. [corrective_rag.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/agentic_rag/corrective_rag.py)

## Verdict

This round materially improved shell ownership in:

- multi-agent streaming
- direct execution
- graph lifecycle
- LLM pool bootstrap
- living heartbeat cycle execution

The codebase is meaningfully easier to extend than at the start of the session, and the refactors stayed within safe seams while preserving focused test coverage.
