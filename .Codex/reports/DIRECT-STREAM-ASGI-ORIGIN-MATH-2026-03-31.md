# Direct Stream ASGI Check — 2026-03-31

## Scope
- Re-probe `origin/selfhood` and `hard math` against the in-process FastAPI app via ASGI.
- Eliminate Windows localhost/process noise from evaluation.
- Verify the direct-stream duplicate-answer fix.
- Verify whether direct stream preserves or surfaces native thinking.

## Files touched
- [probe_live_origin_math.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/scripts/probe_live_origin_math.py)
- [direct_execution.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_execution.py)
- [test_direct_execution_streaming.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_direct_execution_streaming.py)
- [test_graph_stream_agent_handlers.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_graph_stream_agent_handlers.py)

## What changed
- Added an ASGI probe mode so origin/math review now runs against `app.main:app` directly.
- Fixed direct stream metadata loss when a merged final AIMessage had richer metadata than the visible streamed text.
- Preserved `response_metadata` / `additional_kwargs` when stream had to trim visible content to `emitted_text`.
- Added thin language alignment for preserved final metadata thought, but only when that thought actually exists.
- Kept duplicate-answer fix in the direct stream handler.

## Verification
- Focused tests:
  - `17 passed`
- Latest artifacts:
  - [live-origin-math-probe-2026-03-31-230806.json](/E:/Sach/Sua/AI_v1/.Codex/reports/live-origin-math-probe-2026-03-31-230806.json)
  - [thinking-review-latest.html](/E:/Sach/Sua/AI_v1/.Codex/reports/thinking-review-latest.html)
  - [live-stream-wiii-origin-2026-03-31-230806.txt](/E:/Sach/Sua/AI_v1/.Codex/reports/live-stream-wiii-origin-2026-03-31-230806.txt)
  - [live-stream-hard-math-2026-03-31-230806.txt](/E:/Sach/Sua/AI_v1/.Codex/reports/live-stream-hard-math-2026-03-31-230806.txt)

## Current truth
- `origin/selfhood`
  - routes to `direct`
  - uses `google / gemini-3.1-pro-preview`
  - stream duplicate-answer bug is gone
  - visible thinking is unstable:
    - some runs surface a short thought
    - the latest ASGI run surfaced no thought at all
- `hard math`
  - routes to `direct`
  - uses `google / gemini-3.1-pro-preview`
  - stream now preserves strong native thought again
  - latest stream thought is Vietnamese and on-topic

## Interpretation
- The duplicate-answer issue was a stream authority bug and appears fixed.
- The hard-math case proves the stream can now preserve model-authored thought when the provider returns it.
- The origin/selfhood case is different: the model often chooses not to emit thought at all for that turn.
- This means the remaining problem for `origin` is no longer a simple transport bug. It is now a **thought-generation consistency** problem.

## Recommended next step
- Do not reintroduce fake direct templates.
- Improve selfhood/origin direct prompting so the model is more likely to emit a short, native, living inner thought on those turns.
- Keep the instruction soft:
  - same Wiii
  - same living continuity
  - same language as user
  - no planner/editor scaffold
  - no schema or renderer prose
