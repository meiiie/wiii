# Graph Refactor Round 51 - 2026-03-29

## Checkpoint

Current best verified checkpoint after this round:

- Quality: `6814`
- Coupling: `0.28`
- Cycles: `0`
- God files: `0`
- Distance from Main Sequence: `0.31`
- Sentrux verdict: `No degradation detected`

This round did not push coupling below `0.28`, but it improved structural quality again while preserving the clean-cycle/god-file state.

## Completed and Kept

### 1. `supervisor.py` lazy runtime bindings

Created:

- `app/engine/multi_agent/supervisor_runtime_bindings.py`

Updated:

- `app/engine/multi_agent/supervisor.py`

What changed:

- Moved runtime-only imports behind bindings:
  - routing schema/service
  - synthesis helpers
  - visual intent resolver
  - domain registry / skill handbook
  - orchestration planner
  - LLM fallback helpers
- Preserved important patchable symbols on `supervisor.py`, especially `AgentConfigRegistry`.

Local effect:

- internal app-module import count: `18 -> 10`

Verification:

- `python -m pytest tests/unit/test_supervisor_agent.py tests/unit/test_graph_routing.py tests/unit/test_sprint54_graph_streaming.py tests/unit/test_sprint203_natural_conversation.py -q -p no:capture --tb=short`
- Result: `205 passed`

### 2. `product_search_runtime.py` orchestration cleanup

Created:

- `app/engine/multi_agent/agents/product_search_runtime_bindings.py`

Updated:

- `app/engine/multi_agent/agents/product_search_runtime.py`

What changed:

- Moved LLM selection, tool bundle loading, query planning, runtime tool selection, search registry access, and curation into a bindings module.
- Left `product_search_runtime.py` as a much thinner orchestration layer.

Local effect:

- internal app-module import count: `18 -> 2`

Verification:

- `python -m pytest tests/unit/test_product_search_tools.py tests/unit/test_sprint150_deep_search.py tests/unit/test_sprint200_visual_search.py -q -p no:capture --tb=short`
- Result: `121 passed`

### 3. `search_platforms` package boundary made lazy

Updated:

- `app/engine/search_platforms/__init__.py`

What changed:

- Replaced eager package imports with lazy `__getattr__` exports for:
  - base contracts
  - registry
  - circuit breaker
  - `ChainedAdapter`
- Converted `init_search_platforms()` to load adapters and factories on demand instead of importing all adapters up front.

Local effect:

- internal app-module import count: `15 -> 0`

Verification:

- `python -m pytest tests/unit/test_sprint149_search_platforms.py tests/unit/test_sprint151_websosanh.py tests/unit/test_sprint152_browser_scraping.py tests/unit/test_sprint155_facebook_group.py tests/unit/test_product_search_tools.py -q -p no:capture --tb=short`
- Result: `221 passed`

This was the most valuable keeper of the round from a global metric perspective; after this cut Sentrux moved from `6813 -> 6814`.

### 4. `chat_service_runtime.py` bootstrap bindings

Created:

- `app/services/chat_service_runtime_bindings.py`

Updated:

- `app/services/chat_service_runtime.py`

What changed:

- Moved bootstrap imports for RAG, guardrails, repositories, prompt/memory services, tool init, and orchestrator init behind call-time bindings.
- Kept the bootstrap function behaviorally stable and compatible with `ChatService._init_optional(...)`.

Local effect:

- internal app-module import count: `14 -> 1`

Verification:

- `python -m pytest tests/unit/test_sprint30_chat_service.py tests/unit/test_chat_completion_endpoint_support.py tests/unit/test_runtime_endpoint_smoke.py -q -p no:capture --tb=short`
- Result: `21 passed`

## Attempted and Rolled Back

### `graph_streaming.py` full bindings pass

Attempt:

- created `app/engine/multi_agent/graph_streaming_runtime_bindings.py`
- reduced local internal imports from `17 -> 5`

Why rolled back:

- Sentrux quality regressed from `6813 -> 6812`
- a broader lifecycle test sweep also exposed an existing supervisor-lifecycle drift

Decision:

- reverted the `graph_streaming` bindings pass completely
- kept the repo on the better verified checkpoint instead of forcing the change through

## Interpretation

At this stage, the project is no longer suffering from obvious structural debt categories:

- no god files
- no cycles
- no broad regression from refactoring

The remaining `Coupling: 0.28` appears to be held by a small number of legitimate central hubs rather than by easy package-shell wins.

## Best Next Targets

The next realistic candidates if the goal is to push below `0.28` are:

1. `app/engine/llm_pool.py`
2. `app/engine/multi_agent/graph.py`
3. `app/engine/multi_agent/graph_streaming.py` (but only with a more selective cut than the rolled-back one)
4. `app/services/output_processor.py` or other response/runtime hubs if new evidence suggests they are dominating coupling

## Recommendation

Do not chase the metric mechanically now.

The repo is already in a structurally strong state, and from here on the right strategy is:

1. identify one central hub
2. make one selective cut
3. keep only changes that improve or preserve the global checkpoint

That is the pattern that kept the codebase moving forward without reopening instability.
