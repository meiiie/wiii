# Direct Selfhood Stream Language Step — 2026-03-31

## What changed
- Selfhood/origin turns in `direct_chatter_agent` now also receive the shared thinking instruction instead of being excluded with the generic chatter rule.
- Live direct stream thinking deltas now pass through thin language alignment before being emitted, when the model drifts into the wrong language.

## Files touched
- [direct_prompts.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_prompts.py)
- [direct_execution.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_execution.py)
- [test_direct_prompts_identity_contract.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_direct_prompts_identity_contract.py)
- [test_direct_execution_streaming.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_direct_execution_streaming.py)

## Verify
- Focused tests: `18 passed`
- Latest probe: [live-origin-math-probe-2026-03-31-235140.json](/E:/Sach/Sua/AI_v1/.Codex/reports/live-origin-math-probe-2026-03-31-235140.json)
- Latest viewer: [thinking-review-latest.html](/E:/Sach/Sua/AI_v1/.Codex/reports/thinking-review-latest.html)

## Current truth
- `stream_wiii_origin`
  - thinking is back
  - thinking is now Vietnamese on the live SSE rail
  - duplicate answer tail remains fixed (`false`)
- `stream_hard_math`
  - still has long native thought
  - remains on-topic and Vietnamese

## Residual issue
- `origin/selfhood` thought is now readable and in the right language, but the tone is still a bit stiff and generic:
  - more “translated reasoning” than “Wiii thật sự đang chạm vào phần tự thân của mình”

## Recommended next step
- Do not add templates back.
- Tune the selfhood visible-thinking supplement so origin thoughts:
  - keep Vietnamese
  - stay short
  - feel more like Wiii’s living inner voice
  - avoid stiff phrasing like “điều có vẻ khá cơ bản đối với sự tồn tại của tôi”
