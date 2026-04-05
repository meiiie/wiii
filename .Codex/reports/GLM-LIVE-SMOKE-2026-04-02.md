# GLM Live Smoke - 2026-04-02

## What was tested
- Targeted ASGI smoke with `provider="zhipu"` pinned in chat payloads.
- Sessions covered:
  - `direct_origin_bong`
  - `emotion_direct`
  - `tutor_rule15_visual`

Artifacts:
- [glm-targeted-live-smoke-2026-04-02-042119.json](E:/Sach/Sua/AI_v1/.Codex/reports/glm-targeted-live-smoke-2026-04-02-042119.json)
- [thinking-review-latest.html](E:/Sach/Sua/AI_v1/.Codex/reports/thinking-review-latest.html)

## Result
- All targeted API turns failed user-facing checks.
- Sync responses returned `503 PROVIDER_UNAVAILABLE`.
- Stream responses emitted:
  - `status`
  - `error`
  - `done`
  with no visible thinking and no answer.

Representative raw files:
- [glm-sync-direct_origin_bong-origin-2026-04-02-042119.json](E:/Sach/Sua/AI_v1/.Codex/reports/glm-sync-direct_origin_bong-origin-2026-04-02-042119.json)
- [glm-stream-direct_origin_bong-origin-2026-04-02-042119.txt](E:/Sach/Sua/AI_v1/.Codex/reports/glm-stream-direct_origin_bong-origin-2026-04-02-042119.txt)

Observed error:
- `provider="zhipu"`
- `reason_code="verifying"`
- message: `He thong dang xac minh trang thai runtime.`

## Important diagnosis
This is **not** the same as “GLM is dead”.

Low-level provider smoke using [llm_pool_public.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/llm_pool_public.py) succeeded in creating a pinned Zhipu LLM and receiving an `AIMessage`.

So the current failure is:
- **chat/runtime gate problem**
- not a confirmed **Zhipu provider execution problem**

## Supporting evidence
`get_llm_selectability_snapshot()` currently reports all providers as hidden / unavailable in this environment, including `zhipu`.

At the same time, a direct lower-level pinned call to Zhipu did return successfully before console encoding failed while printing the content.

## Conclusion
- The updated HTML is valid, but it currently reflects a **runtime selectability gating failure**, not Wiii’s true GLM thinking quality.
- Next meaningful step is to fix the `zhipu` selectability/configuration gate so chat endpoints can actually route into the live provider.
