# GLM Lane-SLA Targeted Benchmark

- Date: `2026-04-02`
- Scope: `direct_origin_bong`, `emotion_direct`, `hard_math_direct`
- Provider reality: `google` exhausted, runtime fell back to `zhipu/glm-5`
- Viewer: [thinking-review-latest.html](E:/Sach/Sua/AI_v1/.Codex/reports/thinking-review-latest.html)

## Artifacts
- Base targeted report: [wiii-golden-eval-2026-04-02-082132.json](E:/Sach/Sua/AI_v1/.Codex/reports/wiii-golden-eval-2026-04-02-082132.json)
- Emotion targeted report: [wiii-golden-eval-2026-04-02-082935.json](E:/Sach/Sua/AI_v1/.Codex/reports/wiii-golden-eval-2026-04-02-082935.json)
- Hard-math targeted report: [wiii-golden-eval-2026-04-02-083207.json](E:/Sach/Sua/AI_v1/.Codex/reports/wiii-golden-eval-2026-04-02-083207.json)
- Composite parity report: [glm-targeted-parity-composite-2026-04-02-083641.json](E:/Sach/Sua/AI_v1/.Codex/reports/glm-targeted-parity-composite-2026-04-02-083641.json)
- Parity summary: [glm-targeted-parity-2026-04-02-083641.md](E:/Sach/Sua/AI_v1/.Codex/reports/glm-targeted-parity-2026-04-02-083641.md)

## What changed
- Golden eval summary now retains:
  - `transport_avg_processing_time`
  - `transport_max_processing_time`
  - `provider_counts`
  - `model_counts`
  - `failover_switch_transports`
  - `failover_reason_counts`
  - `failover_route_counts`
- Parity analyzer now carries runtime fields per turn:
  - `provider`
  - `model`
  - `processing_time`
  - `failover_reason_code`
  - `failover_route`
- HTML viewer now shows runtime details in each transport card:
  - status
  - provider
  - model
  - failover reason / route
  - lifecycle lengths / provenance

## Benchmark truth
- `origin`
  - sync: `84.091s`, `zhipu/glm-5`, thinking present (`199 chars`)
  - stream: `25.005s`, `zhipu`, answer present, visible thinking missing
- `bong_followup`
  - sync: `87.366s`, `zhipu/glm-5`, visible thinking missing
  - stream: `112.255s`, `zhipu/glm-5`, visible thinking missing
- `sadness`
  - sync: `83.322s`, `zhipu/glm-5`, thinking present (`190 chars`)
  - stream: failed user-facing expectations, no visible thinking, provider metadata absent on final stream result
- `hilbert_operator`
  - sync: `71.175s`, `zhipu/glm-5`, visible thinking missing
  - stream: `145.348s`, `zhipu/glm-5`, thinking present (`834 chars`)

## Interpretation
- Lane-SLA instrumentation is working: runtime latency and failover are now visible and attributable.
- Current bottleneck is no longer the harness.
- The remaining problem is lane/runtime capture quality on stream:
  - `origin` and `sadness` can still lose visible thinking on stream even when sync keeps it.
  - `hard_math` shows the opposite: stream captures thought better than sync.
- This pattern strongly suggests a lane-specific stream capture / finalization issue, not a generic GLM incapability.

## Current recommendation
- Next highest-value fix is `direct` stream capture for:
  - `selfhood/origin`
  - `emotion`
- Only after that should we tune more timeout values, because right now quality loss is coming from thought capture/finalization, not just latency.
