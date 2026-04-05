# Direct Thinking Native/Woven Step

Date: 2026-03-31

## Goal
- Stop fake/template direct emotional thinking.
- Keep Wiii's thought allowed to live inside the answer when it feels natural.
- Remove machine labels like `Visible Thinking:` / `Nghĩ thầm:` without going back to authored narrator prose.

## What Changed
- Updated [thinking_post_processor.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/services/thinking_post_processor.py)
  - strips label prefixes for `Nghĩ thầm`, `Suy nghĩ`, `Visible Thinking`
  - handles wrapped forms like `(Visible Thinking: *...*)`
  - keeps the natural body instead of surfacing the machine label
- Updated [direct_node_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_node_runtime.py)
  - suppresses separate direct visible thought when:
    - answer already carries a woven thought intro
    - the extracted block looks like English planner/meta thought
  - keeps direct social/emotional turns native-first instead of fallback-template-first
- Updated [render_thinking_probe_html.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/scripts/render_thinking_probe_html.py)
  - viewer can now show `Thinking (Woven Into Answer)` when there is no explicit thinking block but the answer opens with an italic/parenthetical thought-like intro

## Tests
- [test_sprint49_thinking_post_processor.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_sprint49_thinking_post_processor.py)
- [test_direct_identity_answer_policy.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_direct_identity_answer_policy.py)

Result:
- `34 passed`

## Live Probe
- JSON: [live-direct-thinking-probe-2026-03-31-165916.json](/E:/Sach/Sua/AI_v1/.Codex/reports/live-direct-thinking-probe-2026-03-31-165916.json)
- HTML viewer: [thinking-review-latest.html](/E:/Sach/Sua/AI_v1/.Codex/reports/thinking-review-latest.html)

## Current Truth
- `stream_buon` no longer emits a separate English planner `thinking` block.
- `stream_buon` no longer leaks `Visible Thinking:` in the visible answer.
- `stream_oke` no longer leaks `Suy nghĩ:` in the visible answer.
- direct emotional/social turns now prefer:
  - no fake separate thinking
  - answer-first delivery
  - optional woven inner tone only when it survives naturally

## Remaining Question
- Direct/social HTML thinking will now often be empty because the system prefers not to invent a separate block.
- This is more truthful than the old template rail, but it means review UX depends more on reading the answer itself.

## Suggested Next Step
- Decide whether direct/social should:
  1. stay answer-first with mostly empty explicit thinking
  2. or expose a very thin `woven thought` extraction into metadata for review only, without changing user-facing answer
