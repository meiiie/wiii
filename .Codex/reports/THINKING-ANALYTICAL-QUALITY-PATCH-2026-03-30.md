# Thinking Analytical Quality Patch — 2026-03-30

## Goal

Continue from the analytical-lane and routing/distillation patches, then improve the next visible weakness:

- public thinking for analytical turns still sounded scaffolded
- analytical answers still had room to drift toward long report/news-summary shape

## Files changed

- `E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/reasoning_narrator_support.py`
- `E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_prompts.py`
- `E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_tool_rounds_runtime.py`
- `E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_reasoning_narrator_runtime.py`
- `E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_direct_prompts_analytical_contract.py`
- `E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_direct_tool_rounds_runtime.py`

## What changed

### 1. Analytical thinking now speaks in signal/noise language

`reasoning_narrator_support.py`

- `build_analytical_market_summary_impl()` now frames oil/market turns around:
  - baseline driver vs short-term noise
  - which axis is holding the current price floor
  - why the market is in a fragile balance instead of a one-way trend
- `build_analytical_math_summary_impl()` now emphasizes:
  - right formula inside the right model
  - scope/validity of approximations
  - moving from assumptions to physical meaning
- `build_analytical_general_summary_impl()` now emphasizes:
  - separating weighted variables from distraction
  - avoiding smooth-but-empty conclusions

This makes public thinking sound less like a generic scaffold and more like real analytical sorting.

### 2. Analytical answer contract is now more thesis-first

`direct_prompts.py`

- analytical direct prompt now explicitly says:
  - open with a checkable thesis
  - prefer 2-3 dense paragraphs by default
  - only use bullets for checklist/watchlist style turns
  - avoid bold/bullet news-summary shape unless the user asks for it
  - when evidence conflicts, say which axis is carrying the conclusion and which is only noise

### 3. Final no-tool synthesis is tighter

`direct_tool_rounds_runtime.py`

- market synthesis now asks for:
  - one-sentence thesis on the current market footing
  - driver separation instead of news-listing
  - compact prose by default
  - no heading-heavy or bullet-heavy report form
- math synthesis now asks for:
  - thesis on the active model
  - validity scope of approximations
- general analytical synthesis now asks for:
  - thesis-first opening
  - explicit handling of conflicting signals

## Tests

Focused suite:

- `test_reasoning_narrator_runtime.py`
- `test_direct_prompts_analytical_contract.py`
- `test_direct_tool_rounds_runtime.py`

Result:

- `18 passed`

## Live verification

Runtime:

- backend health: `http://localhost:8000/api/v1/health/live` -> `200`
- frontend: `http://localhost:1420` -> `200`

### Sync — `phân tích giá dầu`

Observed `thinking_content`:

- baseline driver vs short-term noise
- price floor / fragile balance language
- variable that can make price turn

Observed answer:

- no greeting
- no companion-style opening
- opens directly with market analysis
- still long, but no longer shaped like a cute companion answer

### Stream — `phân tích giá dầu`

Observed:

- `has_chao = false`
- `has_heading_markers = false`
- `has_visual_tool = false`
- `thinking_mentions_market_balance = true`
- `thinking_mentions_noise = true`
- `answer_mentions_watch = true`

First analytical thinking block now begins as:

- “Với giá dầu, điều dễ sai nhất là nhầm giữa lực kéo nền và phần giá cộng thêm vì rủi ro ngắn hạn.”
- “Mình cần tách riêng OPEC+ và sản lượng, tồn kho và nhịp cung cầu, và địa chính trị để biết đâu là lực giữ mặt bằng giá, đâu chỉ là nhiễu ngắn hạn.”

### Sync — `Phân tích về toán học con lắc đơn`

Observed `thinking_content`:

- “dùng công thức đúng trong một mô hình sai”
- explicitly names model, small-angle assumption, and differential equation

Observed answer:

- still analytical and strong
- still longer than ideal for some UX surfaces, but no longer drifts back to relational framing

## Current truth

This patch materially improved the quality of analytical public thinking.

### Improved

- analytical thinking is no longer just “khung chính đã rõ ra”
- oil turns now mention:
  - baseline driver
  - short-term noise
  - fragile market balance
  - turning variables
- analytical answer contract is more thesis-first and less news-summary-like

### Still open

- oil answers can still run longer than ideal in sync path
- sync vs stream can still vary because they are separate real requests
- tool reflection/action text is still serviceable, but not yet as sharp as the thinking blocks themselves

## Recommended next step

Move from “better analytical frame” to “tighter analytical compression”:

1. shorten analytical answer shape for sync path without losing substance
2. sharpen tool-reflection/action text for market turns
3. improve sync/stream parity for the same analytical prompt
