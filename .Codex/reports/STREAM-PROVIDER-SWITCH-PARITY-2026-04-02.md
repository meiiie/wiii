# Stream Provider Switch Parity — 2026-04-02

## Summary
- Fixed the last stream-layer bug where `ProviderUnavailableError` was flattened into a generic `"Graph processing error"`.
- `stream` explicit provider failure now surfaces:
  - `provider`
  - `reason_code`
  - `model_switch_prompt`
- `sync` explicit provider failure now returns honest `503 PROVIDER_UNAVAILABLE` with the same switch prompt payload.

## Code Changes
- Preserved provider errors at graph merge layer:
  - `maritime-ai-service/app/engine/multi_agent/graph_stream_merge_runtime.py`
- Re-raised provider errors through the streaming generator instead of converting them into internal/generic SSE error text:
  - `maritime-ai-service/app/engine/multi_agent/graph_streaming.py`
- Added tests:
  - `maritime-ai-service/tests/unit/test_graph_stream_merge_runtime.py`
  - `maritime-ai-service/tests/unit/test_sprint54_graph_streaming.py`

## Test Results
- Focused unit suite:
  - `47 passed`

## Live Smoke Results

### Stream
Artifact:
- `.Codex/reports/live-provider-switch-stream-postfix-2026-04-02-071328.json`

Observed result:
- SSE ends with `event: error`
- payload includes:
  - `message = "Provider duoc chon hien khong san sang de xu ly yeu cau nay."`
  - `provider = "google"`
  - `reason_code = "rate_limit"`
  - `model_switch_prompt.recommended_provider = "zhipu"`

### Sync
Artifact:
- `.Codex/reports/live-provider-switch-sync-postfix-2026-04-02-071328.json`

Observed result:
- HTTP `503`
- body includes:
  - `error_code = "PROVIDER_UNAVAILABLE"`
  - `provider = "google"`
  - `reason_code = "rate_limit"`
  - `model_switch_prompt.recommended_provider = "zhipu"`

## Current Truth
- The old generic `Graph processing error` failure mode is no longer the authoritative stream outcome for explicit provider failure.
- The user-facing `model switch` UX is now parity-clean across `stream` and `sync` for explicit provider failure.
- Remaining issue seen during probing is a Windows console logging encoding warning (`cp1252`) when verbose Vietnamese logs print to stdout. This did **not** affect API payload correctness.
