# Code Studio Simulation Timeout Diagnosis

Date: 2026-03-19
Scope: local backend debugging for the turn sequence

- `Explain Kimi linear attention in charts`
- `Wiii tạo mô phỏng cho mình được chứ ?`

## What happened

The backend routed the second turn correctly into `code_studio_agent`, selected `tool_create_visual_code`, then stalled for roughly 252 seconds before finishing with only narration text instead of an actual simulation.

Key log evidence from `E:/Sach/Sua/AI_v1/.Codex/reports/local-runs/phase11-local-backend-r2.out.log`:

- `[SUPERVISOR] Routing to: code_studio_agent (method=conservative_fast_path, intent=code_execution, conf=0.95)`
- `[CODE_STUDIO] Runtime-selected tools: ['tool_create_visual_code']`
- `[CODE_STUDIO] ainvoke hard timeout after 240s`
- `[MULTI_AGENT_STREAM] Completed in 251.96s`

## Root cause

There were two issues layered together:

1. The follow-up `Wiii tạo mô phỏng cho mình được chứ ?` was classified as a simulation request, but it was too vague to match any recipe-backed Code Studio fast path.
2. In `_execute_code_studio_tool_rounds()` the timeout fallback response was being overwritten by the original slow task result:
   - Code Studio timed out after 240 seconds.
   - It tried a fallback model call.
   - Then `llm_response = _llm_task.result()` ran unconditionally.
   - If the original task finished late with plain prose and no tool call, that stale result replaced the fallback.

This is why the user saw "Để mình mở khung..." style narration instead of a real inline simulation.

## Fix applied

File: `E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py`

- Added a preflight ambiguity guard for bare simulation asks with no clear phenomenon and no active Code Studio session.
- Added contextual clarifier text that points back to the most recent inline visual title when available.
- Fixed the timeout path so fallback `llm_response` is preserved instead of being overwritten by the cancelled/late primary task.
- Added a required-delivery guard: if `tool_create_visual_code` was required but the LLM returned no tool calls, Code Studio now emits an honest fallback/clarifier instead of leaking empty intention prose.

## Regression coverage

File: `E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_graph_routing.py`

Added tests for:

- ambiguous simulation follow-up detection
- clarifier response using the last inline visual title
- `code_studio_node()` short-circuiting vague simulation turns before expensive generation
- preserving timeout fallback response instead of overwriting it with stale primary output

## Verification

Passed locally:

- `29 passed` — `test_graph_routing.py`
- `16 passed` — `test_code_studio_streaming.py`
- `85 passed` — `test_visual_tools.py`
- `6 passed` — `test_conservative_evolution.py`

## Expected behavior now

For the exact vague follow-up:

- Wiii should no longer sit for ~5 minutes.
- It should answer quickly with a clarification tied to the active topic, for example pointing back to `Kimi linear attention`.
- When Code Studio is required to deliver a simulation/app, stray prose without a tool call should no longer slip through as if the app had been created.
