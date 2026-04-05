# Graph Refactor Round 5 — 2026-03-28

## Summary

This round continued the structural cleanup of the multi-agent backend with a strict goal:

- keep behavior stable,
- preserve existing patch/test seams,
- and push `graph.py` closer to a true orchestration shell.

Two new extractions landed in this round:

1. `openai_stream_runtime.py`
2. `direct_node_runtime.py`
3. `graph_builder_runtime.py`

As a result, `graph.py` moved from roughly `2662` lines at the start of this round down to `1951` lines by the end.

That is the first time in this cleanup effort that `graph.py` is back under the `~2000` line mark.

## What Was Extracted

### 1. OpenAI-compatible/native streaming runtime

New file:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\openai_stream_runtime.py`

Moved out of `graph.py`:

- `_derive_code_stream_session_id`
- `_should_enable_real_code_streaming`
- `_supports_native_answer_streaming`
- `_flatten_langchain_content`
- `_langchain_message_to_openai_payload`
- `_create_openai_compatible_stream_client`
- `_resolve_openai_stream_model_name`
- `_extract_openai_delta_text`
- `_stream_openai_compatible_answer_with_route`

Design note:

- `graph.py` still exposes the old symbol names as thin wrappers.
- This preserves unit tests that patch:
  - `app.engine.multi_agent.graph._create_openai_compatible_stream_client`
  - `app.engine.multi_agent.graph._resolve_openai_stream_model_name`
  - `app.engine.multi_agent.graph._stream_openai_compatible_answer_with_route`

### 2. Direct node runtime

New file:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\direct_node_runtime.py`

Moved out of `graph.py`:

- the full body of `direct_response_node`

Design note:

- `graph.py` now keeps only a thin dependency-injected wrapper around `direct_response_node_impl(...)`.
- This was done specifically to preserve heavy existing test patching around:
  - `_get_or_create_tracer`
  - `_collect_direct_tools`
  - `_bind_direct_tools`
  - `_build_direct_system_messages`
  - `_execute_direct_tool_rounds`
  - `_extract_direct_response`

This is a major architectural win because `direct_response_node` was one of the largest behavior clusters still living directly inside the graph shell.

### 3. Graph builder runtime

New file:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph_builder_runtime.py`

Moved out of `graph.py`:

- the full body of `build_multi_agent_graph`

Design note:

- `graph.py` now delegates graph construction to `build_multi_agent_graph_impl(...)`.
- This keeps node wiring logic isolated from runtime execution concerns.

## Verification

### Compile

Passed:

- `py_compile` for:
  - `graph.py`
  - `openai_stream_runtime.py`
  - `direct_node_runtime.py`
  - `graph_builder_runtime.py`

### Focused Tests

Passed:

1. `tests/unit/test_graph_routing.py`
   - `73 passed`

2. `tests/unit/test_supervisor_agent.py`
   `tests/unit/test_graph_visual_widget_injection.py`
   `tests/unit/test_graph_thread_id.py`
   `tests/unit/test_guardian_graph_node.py`
   `tests/unit/test_sprint75_latency.py`
   - `94 passed`

3. `tests/unit/test_graph_thread_id.py`
   `tests/unit/test_graph_routing.py`
   - `83 passed`

These batches overlap intentionally. The important point is that the seams most exposed by this refactor remain green:

- routing,
- direct lane behavior,
- graph building,
- singleton lifecycle,
- guardian behavior,
- visual widget injection.

### Sentrux

Latest gate result:

- `Quality: 3581 -> 3584`
- `Coupling: 0.36 -> 0.34`
- `Cycles: 8 -> 8`
- `God files: 9 -> 9`
- verdict: `No degradation detected`

Interpretation:

- structural quality improved again,
- coupling improved again,
- no new cycles were introduced,
- but the broader god-file count is unchanged because several large files still remain outside `graph.py`.

## Structural Outcome

### Before this round

- `graph.py` ~ `2662` lines

### After this round

- `graph.py` = `1951` lines

### Why this matters

`graph.py` is now much closer to its intended role:

- orchestration shell,
- dependency bridge,
- lifecycle wrapper,
- node registration shell,

instead of also being:

- provider streaming runtime,
- direct-node execution runtime,
- graph builder,
- subagent dispatch runtime,
- context assembly engine,
- asset loader,
- public thinking owner,
- and process entrypoint all at once.

## Current Top Large Backend Files

After this round, the remaining highest-value refactor targets are:

1. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\tools\visual_tools.py` (`4586`)
2. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph_streaming.py` (`1987`)
3. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\supervisor.py` (`1721`)
4. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\core\config\_settings.py` (`1689`)
5. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\prompts\prompt_loader.py` (`1662`)

## Recommended Next Refactor Cuts

### Priority 1

Refactor `graph_streaming.py`

Why:

- it is now roughly the same size tier as the freshly-cleaned `graph.py`,
- it is tightly coupled to public surface delivery,
- and it is structurally adjacent to future thinking/surface fixes.

### Priority 2

Refactor `supervisor.py`

Why:

- still large,
- owns too many routing and house-voice responsibilities,
- and remains a likely contributor to future surface/thinking drift.

### Priority 3

Refactor `visual_tools.py`

Why:

- it is by far the largest remaining file,
- and it likely keeps the god-file count high even after `graph.py` improved.

## Verdict

This round is a clean architectural win.

- `graph.py` is no longer in the same extreme state it started in.
- direct lane execution is now meaningfully separated from orchestration.
- native/OpenAI-compatible streaming runtime is no longer glued to the graph shell.
- graph construction has been isolated into its own module.

The system is not "finished refactoring", but this round clearly moved the backend toward a cleaner and more durable architecture without sacrificing verified behavior.
