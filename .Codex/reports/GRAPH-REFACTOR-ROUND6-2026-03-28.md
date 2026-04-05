# Graph/Supervisor/Streaming Refactor Round 6

> Date: 2026-03-28
> Scope: continue shrinking orchestration god files without changing routing/stream contracts

## Summary

This round continued the backend clean-architecture push focused on orchestration-heavy modules.
Two major extractions landed safely:

1. `graph_streaming.py` surface/helper extraction was fully wired.
2. `supervisor.py` routing/support extraction was completed.
3. `graph.py` extracted the large Code Studio tool-round executor.

These changes preserve existing public seams in the original modules by leaving thin wrappers in place, so tests and monkeypatching still target the same module-level names.

## New Modules

- `E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_stream_surface.py`
- `E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/supervisor_surface.py`
- `E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/code_studio_tool_rounds.py`

## Key File Size Changes

- `graph_streaming.py`: `1987 -> 1659` lines
- `supervisor.py`: `1721 -> 1328` lines
- `graph.py`: `1951 -> 1428` lines

## What Moved

### `graph_streaming.py`
Moved helper/surface ownership to `graph_stream_surface.py`:
- bus-event conversion
- narration collapse/delta filtering
- fallback narration rendering
- English/Vietnamese detection + answer streaming
- thinking extraction / label cleaning

`graph_streaming.py` now keeps wrappers so tests that patch names like `_convert_bus_event` or `_extract_thinking_content` still work.

### `supervisor.py`
Moved routing heuristics + visible reasoning support to `supervisor_surface.py`:
- router text normalization
- short social/chatter/identity/capability heuristics
- compact-prompt decision support
- routing hint shaping
- recent-turn summarization and visible-reasoning quoting
- supervisor visible reasoning rendering helper
- routing-reason finalization helpers

`supervisor.py` now behaves more like an orchestration shell around the actual `SupervisorAgent` lifecycle.

### `graph.py`
Moved the largest remaining Code Studio tool loop to `code_studio_tool_rounds.py`:
- `_execute_code_studio_tool_rounds`

`graph.py` now delegates to `execute_code_studio_tool_rounds_impl(...)` while injecting graph-local helpers for:
- runtime/provider behavior
- progress formatting
- code-studio reasoning helpers
- visual event emission
- widget/structured visual post-processing

This preserved direct test patch points in `test_graph_routing.py`.

## Verification

### Compile
- `python -m py_compile ...graph_streaming.py ...graph_stream_surface.py` ?
- `python -m py_compile ...supervisor.py ...supervisor_surface.py` ?
- `python -m py_compile ...graph.py ...code_studio_tool_rounds.py` ?

### Tests
- `tests/unit/test_sprint54_graph_streaming.py` ? `40 passed`
- `tests/unit/test_supervisor_agent.py` + `tests/unit/test_graph_routing.py` ? `119 passed`
- `tests/unit/test_graph_routing.py` + `tests/unit/test_graph_visual_widget_injection.py` + `tests/unit/test_supervisor_agent.py` ? `124 passed`

## Sentrux

Latest gate after this round:

- `Quality: 3581 -> 3580`
- `Coupling: 0.36 -> 0.34`
- `Cycles: 8 -> 8`
- `God files: 9 -> 7`
- Verdict: `No degradation detected`

Note:
- Quality score dipped slightly vs baseline, but structural signals improved in the areas we were targeting:
  - coupling improved
  - god-file count dropped materially
  - no regression gate triggered

## Current Remaining 1500+ Files

- `visual_tools.py` ? `4586`
- `_settings.py` ? `1689`
- `prompt_loader.py` ? `1662`
- `graph_streaming.py` ? `1659`
- `corrective_rag.py` ? `1619`

## Recommendation For Next Cut

Highest-ROI next targets:
1. `graph_streaming.py` ? extract `process_with_multi_agent_streaming` body into a dedicated runtime/process module
2. `prompt_loader.py` ? split overlay/cascade loaders from prompt composition
3. `corrective_rag.py` ? extract grading/rewrite sub-pipelines

For the current Wiii/thinking roadmap, `graph_streaming.py` remains the most strategically important next god file because it still owns the public stream contract.
