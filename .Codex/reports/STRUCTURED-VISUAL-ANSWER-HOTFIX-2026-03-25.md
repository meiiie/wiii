# Structured Visual Answer Hotfix

Date: 2026-03-25
Owner: LEADER

## Problem

Direct/chart turns could successfully emit `visual_open` and render a real inline chart, but the final answer text still included a fake Markdown image placeholder like:

- `![...](https://example.com/chart-placeholder)`

This created a broken double-render contract:

- the real visual was already present in the chat surface,
- but the answer prose still behaved as if it had to embed an image manually.

## Root Cause

Two gaps existed at the same time:

1. Direct visual prompting did not forbid Markdown image placeholders strongly enough after `tool_generate_visual`.
2. Runtime response cleanup removed legacy widget blocks, but did not strip placeholder image syntax when a structured visual had already been emitted.

## Changes

### Backend

File: `maritime-ai-service/app/engine/multi_agent/graph.py`

- Added `_has_structured_visual_event(...)`
- Added `_sanitize_structured_visual_answer_text(...)`
- Extended direct visual prompt contract:
  - once `tool_generate_visual` has opened the visual in SSE,
  - do not emit `![](...)`,
  - do not emit `example.com/chart-placeholder`,
  - do not emit `[Visual]` / `[Chart]` marker noise
- Applied structured-visual cleanup inside `_inject_widget_blocks_from_tool_results(...)`
- Applied the same cleanup again after `_extract_direct_response(...)` for defense in depth

### Tests

File: `maritime-ai-service/tests/unit/test_graph_visual_widget_injection.py`

- added regression coverage for removing placeholder Markdown after `visual_open`
- added regression coverage that cleanup still runs even when `structured_visuals_enabled=False`

## Verification

### Automated

- `pytest tests/unit/test_graph_visual_widget_injection.py tests/unit/test_supervisor_agent.py tests/unit/test_supervisor_routing_reasoning.py -q -p no:capture`
  - `55 passed`
- `python -m py_compile maritime-ai-service/app/engine/multi_agent/graph.py`
  - pass

### Live SSE Smoke

Prompt:

- `Visual cho mình xem thống kê dữ liệu hiện tại giá dầu mấy ngày gần đây`

Observed after patch:

- route stays on `direct`
- `tool_generate_visual` executes
- `visual_open` fires
- `visual_commit` fires
- final answer contains prose only
- no `example.com/chart-placeholder`
- no fake Markdown image duplication

Smoke artifact:

- `.Codex/tmp/visual-oil-stream-after-placeholder-fix-2026-03-25.txt`

## Residual Risk

- `/api/v1/llm/status` truth is still not perfectly aligned with actual execution truth across providers.
- The `direct` visual lane is cleaner now, but provider/runtime latency can still be high on some turns.
- Browser smoke via a fresh Playwright profile hit the login screen, so the strongest verification in this batch is the backend SSE smoke rather than an authenticated UI replay.
