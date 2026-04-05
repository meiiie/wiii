# Thinking Analytical Lane Patch — 2026-03-29

## Goal

Stop analytical turns from inheriting the full cute/companion direct persona, because that was pulling answers for prompts like `phân tích giá dầu` back toward:

- greetings
- self-introduction
- kaomoji / playful framing
- relational openers such as `mình ở đây với bạn...`

while the visible thinking had already moved to a more professional analytical shape.

## Root Cause

`direct_agent` was still built through the full `PromptLoader.build_system_prompt(...)` path for analytical turns.

That path injects:

- full runtime identity card
- expressive voice instructions
- quirks / cute tone anchors
- broader companion-style persona framing

The appended analytical contract helped, but it remained a late override layered on top of a prompt whose base personality was still optimized for general conversation.

## Patch

### Files changed

- `E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_prompts.py`
- `E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/reasoning_narrator_support.py`
- `E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_direct_prompts_analytical_contract.py`
- `E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_reasoning_narrator_action_text.py`

### Main changes

1. Added `_build_direct_analytical_system_prompt(...)`

This prompt:

- keeps Wiii's selfhood
- keeps time/pronoun/runtime grounding
- keeps tools context
- removes the heavy companion/cute base pressure
- explicitly frames the turn as analytical

2. Analytical direct turns now bypass the full base direct persona shell

For:

- `analytical_market`
- `analytical_math`
- `analytical_general`

`_build_direct_system_messages(...)` now uses the lean analytical prompt instead of `loader.build_system_prompt(...)`.

3. Fixed Vietnamese folding bug in narrator support

`fold_text_impl(...)` previously dropped `đ`, so duplicate protection failed for text like:

- `đối chiếu Brent và WTI`

This caused ugly action text such as:

- `Mình sẽ đối chiếu đối chiếu Brent và WTI...`

The fold logic now maps:

- `đ -> d`
- `Đ -> D`

before ASCII folding.

## Tests

Focused tests passing:

- `test_direct_prompts_analytical_contract.py`
- `test_reasoning_narrator_runtime.py`
- `test_reasoning_narrator_action_text.py`

Result:

- `5 passed`

## Live verification

### Oil analysis

Artifacts:

- `E:/Sach/Sua/AI_v1/.Codex/reports/thinking-live-utf8-oil-post-analytical-lane-sync-2026-03-29.json`
- `E:/Sach/Sua/AI_v1/.Codex/reports/thinking-live-utf8-oil-post-analytical-lane-stream-2026-03-29.txt`
- `E:/Sach/Sua/AI_v1/.Codex/reports/thinking-live-utf8-oil-post-analytical-lane-stream-rerun-2-2026-03-29.txt`

Observed:

- sync answer now opens directly with market analysis
- no greeting
- no self-intro
- no companion-style opener
- stream has answer events and no `chào`
- rerun confirms no `đối chiếu đối chiếu`

### Pendulum analysis

Artifacts:

- `E:/Sach/Sua/AI_v1/.Codex/reports/thinking-live-utf8-pendulum-post-analytical-lane-sync-2026-03-29.json`
- `E:/Sach/Sua/AI_v1/.Codex/reports/thinking-live-utf8-pendulum-post-analytical-lane-stream-2026-03-29.txt`

Observed:

- sync answer opens directly with the model/physics framing
- thinking remains analytical
- stream answer begins with content, not greeting

## Current truth after patch

### Improved

- analytical thinking is materially better
- analytical answers for `giá dầu` and `con lắc đơn` are now much closer to a professional system
- stream no longer duplicates `đối chiếu`

### Still not fully solved

- analytical lane can still be too broad in structure or too article-like on some turns
- tool choice for analytical turns may still be more visual than necessary on some prompts
- public thinking is improved, but the next serious step is still to stabilize:
  - analytical routing
  - evidence distillation
  - one true public producer for direct analytical lane

## Recommended next step

Move to **analytical routing + evidence distillation**:

1. keep analytical turns in `direct`
2. choose tools/evidence plan more deliberately
3. make the answer distill the tool results more tightly instead of drifting into long-form generic exposition
