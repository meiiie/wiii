# Graph Refactor Round 48 — 2026-03-29

## Scope

Focused refactor to keep the `Cycles: 0 / Coupling: 0.28` checkpoint stable while reducing static dependency pressure in two compatibility-heavy hubs:

- `app/services/output_processor.py`
- `app/engine/multi_agent/graph.py`

## Changes

### 1. Output processor facade split

Kept `app/services/output_processor.py` as the public compatibility facade, but extracted concrete responsibilities into narrow support modules:

- `app/services/output_thinking_runtime.py`
- `app/services/output_source_runtime.py`
- `app/services/output_response_runtime.py`

Preserved public surface:

- `ProcessingResult`
- `extract_thinking_from_response`
- `OutputProcessor`
- `get_output_processor`
- `init_output_processor`

Result:

- `output_processor.py` reduced to a thin facade
- internal fan-out for `app.services.output_processor` is now `4`
- direct behavior preserved for response formatting, blocked responses, source merging, and singleton lifecycle

### 2. Graph binding consolidation

Reduced static coupling in `app/engine/multi_agent/graph.py` by:

- removing stale static imports left over after previous extractions
- turning several compatibility-only symbols into lazy `__getattr__` exports
- moving more graph-facing helpers behind `graph_runtime_bindings.py`
- replacing the remaining direct OpenAI stream implementation import path with dynamic runtime loading inside graph-local wrappers

Additional bindings centralized into `graph_runtime_bindings.py`:

- visual intent helpers
- public thinking helpers
- code studio context helpers
- code studio surface helpers
- code studio response helpers

Compatibility seams preserved for legacy tests and monkeypatch paths:

- `get_supervisor_agent`
- `get_agent_registry`
- `get_reasoning_tracer`
- `_build_simple_social_fast_path`
- code studio fast-path helpers
- `filter_tools_for_role`
- `time`

## Structural impact

### Local graph dependency reduction

Custom AST import scan:

- `graph.py` internal out-degree: `35 -> 19`

That is a meaningful local reduction even though Sentrux's global coupling score remained at `0.28`.

### Global Sentrux state

`sentrux gate app/` after the round:

- `Quality: 6807`
- `Coupling: 0.28`
- `Cycles: 0`
- `God files: 0`
- `Distance from Main Sequence: 0.31`
- Verdict: `No degradation detected`

Interpretation:

- this round materially reduced static edges in `graph.py`
- but the next coupling bottlenecks are now elsewhere in the graph, so Sentrux did not move globally yet

## Verification

### Compile

- `py_compile` passed for:
  - `app/services/output_processor.py`
  - `app/services/output_response_runtime.py`
  - `app/services/output_source_runtime.py`
  - `app/services/output_thinking_runtime.py`
  - `app/engine/multi_agent/graph.py`
  - `app/engine/multi_agent/graph_runtime_bindings.py`

### Tests

- `tests/unit/test_output_processor.py`
- `tests/unit/test_chat_orchestrator_fallback_runtime.py`
  - `35 passed`

- `tests/unit/test_graph_routing.py`
- `tests/unit/test_sprint54_graph_streaming.py`
- `tests/unit/test_supervisor_agent.py`
- `tests/unit/test_sprint203_natural_conversation.py`
  - `205 passed`

## Notes

- A wider orchestrator batch still hits the pre-existing local environment issue:
  - `ImportError: DeclarativeBase from sqlalchemy.orm`
- That drift was not introduced by this round.

## Recommended next move

The refactor frontier is no longer "remove god files" or "break cycles" — both are already done. The next meaningful target for coupling reduction should be chosen from remaining static hubs with high aggregate load, especially:

- `app.engine.llm_pool`
- `app.core.database`
- `app.engine.multi_agent.graph`

However, the failed earlier experiment on `llm_pool` showed that coupling changes there are easy to get wrong. The safest next step is another targeted hub audit before editing:

1. `app.engine.llm_pool`
2. `app.core.database`
3. `app.services.output_processor` consumers
