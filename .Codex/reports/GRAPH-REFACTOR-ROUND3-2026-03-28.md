# Graph Refactor Round 3

> Date: 2026-03-28
> Scope: Continue shrinking `graph.py` while preserving thinking/surface behavior and test compatibility

## What Changed

This round focused on pulling more "public thinking ownership" and lane-local helper logic out of `graph.py` without touching the high-risk inner direct-turn executor yet.

### New module

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\code_studio_reasoning.py`
  - `_infer_code_studio_reasoning_cue()`
  - `_build_code_studio_reasoning_summary()`
  - `_build_code_studio_tool_reflection()`

### Refactor work completed

- `graph.py`
  - now delegates direct reasoning summary/reflection to `direct_reasoning.py`
  - now delegates code-studio reasoning cue/summary/reflection to `code_studio_reasoning.py`
  - keeps compatibility wrappers so existing graph-level imports/tests still work
  - adds a guarded `_bind_direct_tools()` wrapper that preserves both old 2-value and newer 3-value unpacking during the transition
- `direct_execution.py`
  - now uses graph-exported callback seams when present for:
    - `_ainvoke_with_fallback`
    - `_stream_direct_answer_with_fallback`
    - `_stream_direct_wait_heartbeats`
    - `_build_direct_tool_reflection`
    - visual/host-action emitters
    - tool lookup/runtime invocation
  - restores test-safe no-provider fallback for no-tool direct turns
- `tool_collection.py`
  - narrows direct visual-tool forcing so clear chart/visual requests still stay on the direct visual lane
  - only blocks the visual-direct fast force path for explicitly code-execution-flavored queries
- `direct_prompts.py`
  - `_bind_direct_tools()` now supports an explicit `include_forced_choice` flag so internal callers can get the resolved tool choice without breaking older 2-value call sites
- `code_studio_context.py`
  - terminal sandbox failure copy now includes an ASCII-safe `ket noi` marker for existing regression tests

## Verification

### Compile

- `py_compile` passed for:
  - `graph.py`
  - `direct_execution.py`
  - `direct_prompts.py`
  - `direct_reasoning.py`
  - `code_studio_reasoning.py`
  - `tool_collection.py`
  - `code_studio_context.py`

### Tests

Focused suite:

```text
python -m pytest tests/unit/test_graph_routing.py tests/unit/test_supervisor_agent.py tests/unit/test_graph_visual_widget_injection.py tests/unit/test_sprint154_tech_debt.py -v -p no:capture --tb=short
```

Result:

- `196 passed`

### Sentrux

Command:

```text
E:\Sach\Sua\AI_v1\tools\sentrux.exe gate .
```

Result:

- `Quality: 3581 -> 3587`
- `Coupling: 0.36 -> 0.35`
- `Cycles: 8 -> 8`
- `God files: 9 -> 9`
- `No degradation detected`

## Structural Delta

- `graph.py` line count is now `3521`
- previous measured checkpoint before this round: `3561`
- earlier checkpoint before Round 2 work: `4358+`

This means the graph shell is materially smaller than the start of the session, but the biggest remaining seam is still the inner direct-turn execution path.

## Why This Round Matters For Thinking

The important architectural move here is not just fewer lines. It is that `graph.py` now owns less of the language-specific "what does this lane think/say" surface.

That helps in three ways:

1. direct-lane public reasoning now lives behind a dedicated module boundary
2. code-studio public reasoning now also lives behind its own module boundary
3. the next thinking fixes can target dedicated modules instead of editing a 3.5k-line orchestration shell

## Remaining High-ROI Next Cuts

1. extract the inner executor from `direct_response_node()` into a dedicated direct-turn service/outcome object
2. reduce remaining lazy back-imports between `direct_execution.py` and `graph.py`
3. split `_execute_code_studio_tool_rounds()` once a clean callback seam is defined

## Notes

- No attempt was made in this round to change live thinking quality directly.
- This round is a structural precondition for making future thinking fixes safer and more local.
