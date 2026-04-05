# Tutor Live Thinking Recovery

Date: 2026-04-05

## What was broken

- `tutor_rule15_visual` live runs had correct answers but empty visible thinking.
- `sync` and `stream` already carried authoritative `provider/model`, but tutor rail still showed only `thinking_start/thinking_end` with no `thinking_delta`.
- `rule15_explain` and `rule15_visual` were both affected in different ways:
  - `rule15_explain`: search-backed tutor flow had no post-tool thought on the live path.
  - `rule15_visual`: visual follow-up often produced answer/tool-shaped continuation text that could not be safely surfaced.

## Root cause

- Tutor relied on native continuation text after tool execution, but when that continuation came back empty or answerish, the lane had no safe fallback.
- The live path therefore reached final answer synthesis without any tutor-visible continuation to capture into `thinking_lifecycle`.

## Code changes

- Added a distilled, content-specific fallback continuation path in:
  - `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_node.py`
- The new fallback:
  - derives inward-facing continuation from `distill_post_tool_context(...)` / `distill_visual_tool_context(...)`
  - stays specific to the retrieved or visualized content
  - avoids old authored-template behavior
  - only activates when model continuation is absent or answerish
- Tightened answerish suppression markers for tutor continuation:
  - `chào bạn`
  - `để mình giải thích`
  - similar outward-facing tutoring phrasing

## Regression coverage

Focused suite:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_tutor_agent_node.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_tutor_request_runtime.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_tutor_response.py`

Result:

- `57 passed`

## Live rerun

Full tutor session rerun:

- `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-05-233508.json`

Raw stream artifacts:

- `E:\Sach\Sua\AI_v1\.Codex\reports\golden-stream-tutor_rule15_visual-rule15_explain-2026-04-05-233508.txt`
- `E:\Sach\Sua\AI_v1\.Codex\reports\golden-stream-tutor_rule15_visual-rule15_visual-2026-04-05-233508.txt`

## Current truth

### `rule15_explain`

- `sync`: visible thinking restored
- `stream`: visible thinking restored with real `thinking_delta` events after tool result
- `provider/model`: `zhipu / glm-4.5-air`

### `rule15_visual`

- `stream`: visible thinking restored
- visible rail now contains:
  - pre-tool tutor thought
  - post-tool visual continuation
- `provider/model`: `zhipu / glm-4.5-air`

## Viewer updated

- HTML:
  - `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-review-latest.html`
- Screenshot:
  - `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-review-latest-tutor-2026-04-05.png`

## Remaining nuance

- The visual fallback thought is now alive and safe, but it is still more compact/metadata-shaped than the best selfhood/emotion thoughts.
- Next quality pass, if needed, should make tutor post-visual continuation less schema-flavored and more pedagogically inward without losing safety.
