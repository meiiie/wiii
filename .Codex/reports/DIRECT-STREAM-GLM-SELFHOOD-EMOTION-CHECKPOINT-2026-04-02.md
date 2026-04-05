## Direct Stream GLM Checkpoint

- Date: `2026-04-02`
- Scope: `direct_origin_bong.origin`, `direct_origin_bong.bong_followup`, `emotion_direct.sadness`
- Runtime: `zhipu / glm-5` with Google quota exhausted

### Changes completed

- Added best-effort salvage in [direct_node_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_node_runtime.py) so post-processing failures do not automatically destroy a valid `llm_response`.
- Stopped pinning direct turns to `state["provider"]` when the user did not explicitly choose a provider; only `explicit_user_provider` now pins failover behavior.
- Added tests in [test_direct_node_provider_errors.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_direct_node_provider_errors.py) to lock:
  - salvage after post-processing failure
  - no implicit provider pin
  - provider-unavailable propagation

### Focused tests

- `30 passed`

### Latest artifacts

- HTML viewer: [thinking-review-latest.html](E:/Sach/Sua/AI_v1/.Codex/reports/thinking-review-latest.html)
- Latest mixed composite: [glm-direct-emotion-mixed-latest-2026-04-02-composite-2026-04-02-155529.json](E:/Sach/Sua/AI_v1/.Codex/reports/glm-direct-emotion-mixed-latest-2026-04-02-composite-2026-04-02-155529.json)
- Latest parity markdown: [glm-direct-emotion-mixed-latest-2026-04-02-2026-04-02-155529.md](E:/Sach/Sua/AI_v1/.Codex/reports/glm-direct-emotion-mixed-latest-2026-04-02-2026-04-02-155529.md)
- Latest direct-origin report: [wiii-golden-eval-2026-04-02-154620.json](E:/Sach/Sua/AI_v1/.Codex/reports/wiii-golden-eval-2026-04-02-154620.json)

### Current truth

- `sync` on GLM is currently strong for `origin` and acceptable for `bong_followup` and `sadness`.
- `stream` is still the weak lane for these direct turns:
  - `origin`: stream falls back to generic answer and loses visible thinking
  - `bong_followup`: stream returns fallback-ish answer and loses visible thinking
  - `sadness`: last clean stream artifact still ends in provider/model-switch error instead of answer

### Important nuance

- The latest `sadness` rerun was blocked by a probe-side `MemoryError` while importing optional heavy dependencies in a fresh ASGI process. That rerun is not a valid Wiii behavior signal.
- The current HTML therefore mixes:
  - latest clean `origin/Bong` run from `15:46`
  - latest clean `sadness` run from `15:29`

### Most likely remaining fault domain

- The remaining hole is no longer the `direct_node_runtime` post-processing salvage itself.
- The likely problem is earlier in the direct stream path, before a valid `llm_response` reaches the node:
  - `execute_direct_tool_rounds`
  - `_stream_answer_with_fallback`
  - `_ainvoke_with_fallback`
- In these failing GLM runs, `direct_response` ends quickly as `Fallback (LLM generation error)` with no `thinking_lifecycle`, which strongly suggests the failure happens before final response extraction/salvage.

### Recommended next step

- Instrument and harden the direct stream execution path so provider/runtime failures in backfilled selfhood/emotion turns surface as structured provider errors or retryable outcomes, not generic fallback answers.
