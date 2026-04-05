# Thinking Analytical Routing And Distillation — 2026-03-30

## Goal

Continue from the analytical-lane prompt patch and reduce the next two remaining drifts:

1. analytical text turns still had access to visual/chart tools even when the user only wanted text analysis
2. final analytical answers could still expand into article-like Markdown structure

## Root Cause

### 1. Tool drift

`resolve_visual_intent(query)` already returned `text` for prompts like:

- `phân tích giá dầu`
- `Phân tích về toán học con lắc đơn`

But direct lane still bound:

- `tool_generate_visual`
- `tool_generate_mermaid`
- `tool_generate_interactive_chart`

because those tools were appended broadly into the direct tool bundle.

That gave the model unnecessary freedom to jump from analytical text into visual generation.

### 2. Distillation drift

Even after the analytical prompt patch, some runs could still expand into:

- long report-like structure
- Markdown headings like `###`

This came from the model still having too much freedom in final synthesis shape.

## Patch

### Files changed

- `E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/tool_collection.py`
- `E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_tool_rounds_runtime.py`
- `E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_prompts.py`
- `E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_tool_collection_analytical.py`
- `E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_direct_tool_rounds_runtime.py`

### Main changes

#### A. Strip visual tools from analytical text turns

Added:

- `_infer_direct_thinking_mode(...)` lazy wrapper in `tool_collection.py`
- `_should_strip_visual_tools_for_analytical_text_turn(...)`

Behavior:

- if `thinking_mode` starts with `analytical_`
- and `visual_decision.presentation_intent == "text"`

then direct lane removes:

- `tool_create_visual_code`
- `tool_generate_visual`
- `tool_generate_mermaid`
- `tool_generate_interactive_chart`

This keeps analytical turns on text/data tools unless visual intent is explicit.

#### B. Add mode-aware final synthesis instruction

Added:

- `_build_direct_final_synthesis_instruction(...)` in `direct_tool_rounds_runtime.py`

Behavior:

- market turns: synthesize around current picture -> main forces -> takeaway
- math turns: synthesize around model/assumptions -> derivation -> physical meaning
- general analytical turns: synthesize around claim -> strongest variables/evidence -> conclusion

Also added explicit anti-drift guidance:

- no more tool calls
- prefer compact paragraphs or short bullets
- do not use Markdown headings like `#`, `##`, `###` by default

#### C. Strengthened analytical prompt contract

In `direct_prompts.py`, analytical prompts now explicitly say:

- analytical answers should default to compact paragraphs / short bullets
- do not use Markdown headings unless the user explicitly asks for report-like structure

## Tests

Passing focused tests:

- `test_tool_collection_analytical.py`
- `test_direct_tool_rounds_runtime.py`
- `test_direct_prompts_analytical_contract.py`
- `test_reasoning_narrator_action_text.py`
- `test_reasoning_narrator_runtime.py`

Result:

- `8 passed`

Later tightened subset:

- `5 passed`

## Live verification

### Oil analysis after routing/distillation patch

Artifacts:

- `E:/Sach/Sua/AI_v1/.Codex/reports/thinking-live-utf8-oil-post-routing-sync-2026-03-30.json`
- `E:/Sach/Sua/AI_v1/.Codex/reports/thinking-live-utf8-oil-post-routing-stream-2026-03-30.txt`
- `E:/Sach/Sua/AI_v1/.Codex/reports/thinking-live-utf8-oil-post-routing-headings-rerun-2026-03-30.txt`

#### Sync result

Observed:

- answer opens directly with oil-market analysis
- no greeting
- no companion-style opener
- no `###` in the sync answer

#### Stream rerun result

Observed:

- `has_answer = true`
- `has_visual_tool = false`
- `has_chart_tool = false`
- `has_heading_markers = false`
- `has_chao = false`

This is the cleanest live analytical stream checkpoint so far for `phân tích giá dầu`.

## Current truth

### Improved

- analytical text turns no longer drift into visual tool calls by default
- analytical stream answer is now much closer to a professional text-analysis system
- heading drift is reduced and, on the latest rerun, absent

### Still open

- quality can still vary by run because sync and stream are separate requests
- evidence distillation is better, but not yet sharply “economist-grade” every time
- public thinking is cleaner, but the broader next milestone is still:
  - stronger analytical routing stability
  - richer analytical evidence compression
  - higher-confidence parity between sync and stream content shape

## Recommended next step

Move from “stop drift” to “raise analytical quality”:

1. improve analytical routing confidence for market/math/general queries
2. make evidence distillation more claim-first and less summary-like
3. stabilize sync/stream answer shape for the same analytical prompt
