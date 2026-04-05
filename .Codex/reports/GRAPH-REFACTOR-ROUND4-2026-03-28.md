# Graph Refactor Round 4

> Date: 2026-03-28  
> Scope: Continue structural extraction from `app/engine/multi_agent/graph.py` without changing behavior contracts

## Summary

This round continued the “graph as orchestration shell” cleanup.

Main outcome:

- `graph.py` reduced from about `3521` lines at the start of this round to `2662` lines now
- Sentrux stayed green on every rerun
- coupling improved slightly again
- critical graph-routing and thread-id tests stayed green

## New Modules Extracted

### 1. `subagent_dispatch.py`

Extracted the Phase 4 parallel dispatch helpers:

- `_emit_subagent_event_impl`
- `_run_rag_subagent_impl`
- `_run_tutor_subagent_impl`
- `_run_search_subagent_impl`
- `parallel_dispatch_node_impl`

`graph.py` keeps thin wrappers so existing tests can still patch:

- `_SUBAGENT_ADAPTERS`
- `parallel_dispatch_node`

This preserved legacy test seams while removing the subagent orchestration body from the god file.

### 2. `code_studio_assets.py`

Extracted Code Studio resource-loading concerns:

- `_load_code_studio_visual_skills`
- `_load_code_studio_example`
- related caches and filename maps

This moves asset/cache behavior out of the graph shell and clarifies the separation between:

- orchestration
- prompt/asset loading
- runtime execution

### 3. `graph_support.py`

Extracted lightweight graph support helpers:

- `_build_turn_local_state_defaults`
- `_build_recent_conversation_context`
- `route_decision`
- `_build_domain_config`
- `_get_domain_greetings`
- `_generate_session_summary_bg`

These helpers are utility/support concerns and no longer need to sit inside the main orchestration file.

### 4. `graph_process.py`

Extracted the sync process entrypoint body:

- `process_with_multi_agent_impl`
- `_serialize_langchain_messages`
- `_apply_graph_context_prompts`
- `_build_invoke_config`
- `_upsert_thread_view`
- `_build_process_result_payload`

`graph.py` now keeps `process_with_multi_agent(...)` as a compatibility wrapper that injects graph-owned callbacks.

This is one of the highest-leverage extractions in the session because it removes request lifecycle setup from the graph shell:

- initial state assembly
- prompt/context injection
- invoke config building
- graph invocation
- thread upsert
- usage logging
- result shaping

## Structural Delta

### `graph.py` size

- before this round: `3521` lines
- after subagent + asset extraction: `2989` lines
- after support + process extraction: `2662` lines

### Sentrux

Latest gate result:

- `Quality: 3581 -> 3585`
- `Coupling: 0.36 -> 0.35`
- `Cycles: 8 -> 8`
- `God files: 9 -> 9`
- verdict: `No degradation detected`

Interpretation:

- refactor direction remains healthy
- graph shell is materially smaller
- coupling nudged down again
- but the project still has broader god-file/cycle work remaining outside this single seam

## Verification

### Compile

Passed:

- `graph.py`
- `subagent_dispatch.py`
- `code_studio_assets.py`
- `graph_support.py`
- `graph_process.py`

### Focused tests that passed

- `tests/unit/test_graph_thread_id.py` → `10 passed`
- `tests/unit/test_phase4_aggregator.py -k "ParallelDispatchNode or GraphIntegration"` → `10 passed`
- `tests/unit/test_graph_routing.py`
- `tests/unit/test_supervisor_agent.py`
- `tests/unit/test_graph_visual_widget_injection.py`
- `tests/unit/test_sprint154_tech_debt.py`

Important stable batch:

- `257 passed, 7 deselected`

### Known failures observed during wider batch

The broader run including `tests/unit/test_sprint79_memory_hardening.py` surfaced old environment-sensitive failures unrelated to this refactor:

- `ImportError: cannot import name 'DeclarativeBase' from sqlalchemy.orm`

This indicates a local SQLAlchemy environment mismatch, not a new regression introduced by the graph extractions.

One small regression from extraction did appear and was fixed immediately:

- missing fallback greeting key `thanks` after moving domain helper logic

After the fix:

- `TestGetDomainGreetings::test_fallback_has_english_greetings` passed again

## Architectural Impact

This round materially improved the clean-architecture direction of the multi-agent shell:

- `graph.py` now owns less resource loading
- `graph.py` now owns less subagent fan-out logic
- `graph.py` now owns less sync request-entry lifecycle code
- helper seams are more testable in isolation
- future thinking work will have a clearer boundary between:
  - orchestration shell
  - public thinking producers
  - subagent dispatch
  - request processing
  - Code Studio asset loading

## Recommended Next Cuts

Highest-value next seams:

1. guardian shell extraction
2. singleton/checkpointer access extraction
3. remaining direct/code-studio orchestration wrappers
4. `graph_streaming.py` god-file reduction in parallel

Most likely next ROI:

- keep `graph.py` as the orchestration builder + node registration shell only
- move more runtime/service concerns into dedicated helper modules

