# Graph Refactor Round 2 — Safe Cuts for Thinking/Surface Ownership

> Date: 2026-03-28
> Scope: Safe refactor of `graph.py` with focused validation after each cut
> Goal: Reduce orchestration-shell responsibilities before deeper thinking fixes

---

## Summary

This round continued the "safe seam" strategy instead of attacking the hottest 500+ line execution functions.

Three coherent extractions were completed:

1. `direct_social.py`
2. `widget_surface.py`
3. `code_studio_context.py`

These cuts matter because they move more **surface-facing behavior** out of the orchestration shell:

- ultra-short social response ownership
- structured-visual / widget response cleanup
- Code Studio context, progress, ambiguity, missing-tool, and fast-path policy

The result is a meaningfully smaller `graph.py` without destabilizing routing or visual delivery.

---

## Structural Change

### `graph.py` size

- Before this round: ~`4358` lines
- After `direct_social` + `widget_surface` + `code_studio_context`: `3813` lines

Largest remaining functions in `graph.py`:

- `_execute_code_studio_tool_rounds` — `582` lines
- `direct_response_node` — `372` lines
- `code_studio_node` — `297` lines
- `process_with_multi_agent` — `217` lines
- `_execute_pendulum_code_studio_fast_path` — `141` lines
- `build_multi_agent_graph` — `136` lines

Interpretation:

- `graph.py` is still a god file
- but it is now much closer to being a true orchestration shell
- the next cuts should target **execution seams**, not more tiny helpers

---

## Files Created

### [direct_social.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_social.py)

Owns:

- `_build_simple_social_fast_path()`

Purpose:

- remove ultra-short social turn house-voice handling from `graph.py`

### [widget_surface.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/widget_surface.py)

Owns:

- `_has_structured_visual_event()`
- `_sanitize_structured_visual_answer_text()`
- `_inject_widget_blocks_from_tool_results()`

Purpose:

- isolate response-surface cleanup for structured visuals and legacy widget injection

### [code_studio_context.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/code_studio_context.py)

Owns:

- `_get_active_code_studio_session()`
- `_active_code_studio_session()`
- `_active_visual_context()`
- `_last_inline_visual_title()`
- `_ground_simulation_query_from_visual_context()`
- `_build_code_studio_progress_messages()`
- `_format_code_studio_progress_message()`
- `_build_code_studio_retry_status()`
- `_looks_like_ambiguous_simulation_request()`
- `_build_ambiguous_simulation_clarifier()`
- `_build_code_studio_terminal_failure_response()`
- `_build_code_studio_missing_tool_response()`
- `_requires_code_studio_visual_delivery()`
- `_should_use_pendulum_code_studio_fast_path()`
- `_infer_pendulum_fast_path_title()`
- `_should_use_colreg_code_studio_fast_path()`
- `_infer_colreg_fast_path_title()`
- `_should_use_artifact_code_studio_fast_path()`
- `_infer_artifact_fast_path_title()`

Purpose:

- move Code Studio follow-up grounding, progress copy, delivery fallback copy, and fast-path policy out of `graph.py`

---

## Files Modified

### [graph.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py)

Changes:

- rewired imports to new helper modules
- removed in-file definitions that are now owned elsewhere
- kept hot execution functions in place

### [agent_nodes.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/agent_nodes.py)

Changes:

- rewired lazy helper import so `_get_active_code_studio_session()` no longer keeps an unnecessary `agent_nodes -> graph` edge

---

## Validation

### Compile

Passed:

```powershell
python -m py_compile `
  E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\direct_social.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\widget_surface.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\code_studio_context.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agent_nodes.py
```

### Focused pytest

Passed:

```powershell
python -m pytest `
  tests/unit/test_graph_routing.py `
  tests/unit/test_supervisor_agent.py `
  tests/unit/test_graph_visual_widget_injection.py `
  -v -p no:capture --tb=short
```

Result:

- `124 passed`

### Sentrux

Command:

```powershell
E:\Sach\Sua\AI_v1\tools\sentrux.exe gate .
```

Working directory:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app`

Result:

- Quality: `3581 -> 3587`
- Coupling: `0.36 -> 0.35`
- Cycles: `8 -> 8`
- God files: `9 -> 9`
- Verdict: `No degradation detected`

Interpretation:

- coupling improved
- call graph volume dropped
- but `graph.py` is still large enough that Sentrux still counts it as a god file

---

## Why Stop Here

The next remaining cuts are no longer "free":

- `_execute_code_studio_tool_rounds`
- `direct_response_node`
- `code_studio_node`

These functions are hot-path orchestration/execution seams with more failure risk.

Stopping here is intentional:

- we already extracted the low/medium-risk surface and policy logic
- we preserved test stability
- we reduced graph ownership without introducing new cycles

This is a good handoff point before a deeper execution-layer refactor.

---

## Recommended Next Cuts

Highest ROI next:

1. Extract `_execute_pendulum_code_studio_fast_path()` into a dedicated fast-path module
2. Separate `direct_response_node` orchestration from direct execution assembly
3. Pull `_execute_code_studio_tool_rounds()` into a dedicated execution module only after its event/sanitizer seams are frozen

Important caution:

- do **not** move `_sanitize_code_studio_response()` yet without disentangling its hidden dependency chain with `direct_execution.py`

---

## Bottom Line

This round was successful.

- `graph.py` is materially smaller
- surface-related ownership is cleaner
- Code Studio UX policy now has a home outside the orchestration shell
- tests remained green
- Sentrux confirms no regression and mild structural improvement

This does **not** fix Wiii thinking by itself, but it makes the next thinking-focused work much easier and less risky.
