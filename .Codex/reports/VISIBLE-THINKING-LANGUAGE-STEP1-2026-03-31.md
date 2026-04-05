# Visible Thinking Language Step 1 - 2026-03-31

## Goal

Move tutor `stream` visible thinking closer to the turn language without reintroducing authored/public-thinking prose.

## Architecture Chosen

- Keep `native-thinking-first`
- Keep raw tool/research trace visible
- Add only a thin language-alignment layer on tutor visible thought
- Default to `vi` if tutor live context does not explicitly carry `response_language`

## External Guidance Considered

- Anthropic extended thinking: keep model-owned thinking and avoid over-authoring the reasoning surface
  - https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking
- Google Gemini thinking: thinking is model-native, and thought context in multi-turn/tool flows needs careful handling
  - https://ai.google.dev/gemini-api/docs/thinking
  - https://ai.google.dev/gemini-api/docs/thought-signatures

## Code Changes

- Tutor visible thought now calls `align_visible_thinking_language(...)`
  - [tutor_node.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/agents/tutor_node.py)
- Tutor visible thought defaults to `response_language="vi"` when live context does not provide a language
  - [tutor_node.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/agents/tutor_node.py)
- Alignment helper now:
  - tries the provided LLM first
  - falls back to light LLM translation when needed
  - strips translator-native `<thinking>` output before language judgment
  - [public_thinking_language.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/public_thinking_language.py)

## Verification

- Focused unit suite: `53 passed`
  - [test_public_thinking_language.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_public_thinking_language.py)
  - [test_tutor_agent_node.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_tutor_agent_node.py)
  - [test_response_language_policy.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_response_language_policy.py)

## Live Probe Artifacts

- Latest probe JSON:
  - [stream-thinking-align-probe-lite-2026-03-31-040527.json](E:/Sach/Sua/AI_v1/.Codex/reports/stream-thinking-align-probe-lite-2026-03-31-040527.json)
- Latest raw stream:
  - [stream-thinking-align-rule15-2026-03-31-040527.txt](E:/Sach/Sua/AI_v1/.Codex/reports/stream-thinking-align-rule15-2026-03-31-040527.txt)
  - [stream-thinking-align-visual-2026-03-31-040527.txt](E:/Sach/Sua/AI_v1/.Codex/reports/stream-thinking-align-visual-2026-03-31-040527.txt)
- Latest HTML review:
  - [thinking-review-latest.html](E:/Sach/Sua/AI_v1/.Codex/reports/thinking-review-latest.html)

## Current Truth

- `stream_rule15`
  - visible thinking is now Vietnamese and much closer to Wiii
  - answer still arrives after synthesizer
- `stream_visual_followup`
  - visible thinking improved from fully-English to mixed-language
  - first and last blocks are now Vietnamese
  - the middle block still leaks English planning prose

## What This Means

The thin alignment layer is now definitely hitting the real tutor stream path, but it is not yet strong enough to fully normalize every visual-planning thought block. The remaining issue is narrower than before:

- not answer authority
- not tool trace visibility
- not general tutor thinking transport
- specifically mixed-language visible thought in visual-planning turns

## Next Narrow Step

Keep the same architecture and target only the remaining mixed-language visual-planning block:

- inspect why one middle paragraph still survives in English
- strengthen paragraph-level alignment on mixed-language tutor visual thoughts
- preserve raw structure and tool trace
