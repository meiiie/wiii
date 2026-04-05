# LLM Runtime Observation Audit - 2026-04-04

## Summary

Hoàn tất nhánh `LLM runtime observation audit` để `chat sync` và `chat stream` có mức trung thực vận hành tương đương `vision/OCR`:

- ghi nhận `runtime observation` thật từ các lượt chat thành công/thất bại
- phản ánh `failover route` theo từng provider, không chỉ provider cuối
- hiển thị `recovered` chỉ khi runtime success mới hơn probe lỗi
- đưa toàn bộ trạng thái này lên admin runtime tab

## Files Changed

### Backend runtime audit + admin surface

- `maritime-ai-service/app/services/llm_runtime_audit_service.py`
- `maritime-ai-service/app/api/v1/admin_schemas.py`
- `maritime-ai-service/app/api/v1/admin_llm_runtime.py`

### Sync + stream wiring

- `maritime-ai-service/app/api/v1/chat_endpoint_presenter.py`
- `maritime-ai-service/app/services/chat_stream_coordinator.py`
- `maritime-ai-service/app/engine/multi_agent/graph_stream_finalize_runtime.py`
- `maritime-ai-service/app/engine/multi_agent/graph_streaming.py`
- `maritime-ai-service/app/engine/multi_agent/graph_stream_runtime.py`

### Frontend runtime tab

- `wiii-desktop/src/api/types.ts`
- `wiii-desktop/src/components/runtime/LlmRuntimePolicyEditor.tsx`

### Tests

- `maritime-ai-service/tests/unit/test_llm_runtime_audit_service.py`
- `maritime-ai-service/tests/unit/test_admin_llm_runtime.py`
- `maritime-ai-service/tests/unit/test_chat_endpoint_presenter.py`
- `maritime-ai-service/tests/unit/test_sprint30_chat_api.py`
- `wiii-desktop/src/__tests__/admin-runtime-tab.test.tsx`

## What Changed

### 1. Persisted provider-level runtime observation

Mỗi provider trong audit giờ có thêm:

- `last_runtime_observation_at`
- `last_runtime_success_at`
- `last_runtime_error`
- `last_runtime_note`
- `last_runtime_source`

### 2. Failover is recorded as a route, not a single success

Nếu một lượt chat `google -> zhipu`, audit sẽ ghi:

- `google`: runtime fail với note failover/error
- `zhipu`: runtime success với note completion/recovery

### 3. Recovered badge now follows real runtime observation

`recovered=true` chỉ bật khi:

- provider vừa có probe lỗi trước đó
- runtime success mới hơn probe lỗi
- runtime success đó cũng là observation mới nhất

### 4. Sync and stream are both wired

- `sync /chat`:
  - explicit provider unavailable -> `503 PROVIDER_UNAVAILABLE`
  - audit ghi `chat_sync:error`
- `stream /chat/stream/v3`:
  - explicit provider unavailable -> SSE `error` event + `done`
  - auto failover -> audit ghi `chat_stream:failover` và `chat_stream`

## Verification

### Automated tests

- backend focused:
  - `13 passed`
- sync presenter regression:
  - `3 passed`
- frontend runtime tab:
  - `8 passed`

### Live health

- app health:
  - `http://127.0.0.1:8000/api/v1/health/live` -> `{"status":"alive"}`

## Live Smoke

### Case 1: stream with explicit `provider=google`

Raw artifact:

- `E:\Sach\Sua\AI_v1\.Codex\reports\llm-stream-smoke-google-explicit-2026-04-04-101355.txt`

Observed behavior:

- HTTP status from SSE endpoint: `200`
- SSE emits:
  - `status`
  - `status`
  - `status`
  - `error`
  - `done`
- no fake success answer is emitted

Important payload:

- SSE `error` carries:
  - `provider="google"`
  - `reason_code="busy"`
  - `model_switch_prompt.recommended_provider="zhipu"`

Admin runtime snapshot after this call:

- `google.last_runtime_note = "chat_stream:error: requested provider google unavailable (busy)."`
- `google.last_runtime_source = "chat_stream:error"`
- `google.recovered = false`

### Case 2: stream with `provider=auto`

Raw artifact:

- `E:\Sach\Sua\AI_v1\.Codex\reports\llm-stream-smoke-auto-failover-2026-04-04-101624.txt`

Observed behavior:

- HTTP status from SSE endpoint: `200`
- SSE emits:
  - normal status events
  - model-switch status:
    - `google -> zhipu`
  - answer events
  - metadata
  - done

Important metadata:

- `provider = "zhipu"`
- `model = "glm-4.5-air"`
- `runtime_authoritative = true`
- `failover.route[0].from_provider = "google"`
- `failover.route[0].to_provider = "zhipu"`
- `failover.route[0].reason_code = "timeout"`

Admin runtime snapshot after this call:

- `google.last_runtime_note = "chat_stream: failover google -> zhipu (Provider phan hoi qua lau va da bi timeout.)."`
- `google.last_runtime_source = "chat_stream:failover"`
- `zhipu.last_runtime_note = "chat_stream: completed via zhipu/glm-4.5-air after failover from google (Provider phan hoi qua lau va da bi timeout.)."`
- `zhipu.last_runtime_source = "chat_stream"`
- `zhipu.recovered = true`

## Current Truth

Nhánh `LLM runtime audit` hiện đã đạt được điều quan trọng nhất:

- sync và stream đều ghi trạng thái runtime thật
- failover không còn bị “nuốt” thành một success mơ hồ
- admin tab nhìn ra được provider nào đang đỏ vì probe, provider nào đã hồi thật nhờ runtime

## Follow-up Rerun

Artifact:

- `E:\Sach\Sua\AI_v1\.Codex\reports\llm-stream-smoke-auto-failover-rerun-2026-04-04-102400.txt`

Sau khi restart app và rerun lại cùng case `stream auto failover`, kết quả đã sạch hơn:

- vẫn có model-switch `google -> zhipu`
- metadata cuối vẫn authoritative ở `zhipu / glm-4.5-air`
- reasoning trace chuyển từ fallback sang:
  - `direct_response -> response_type = llm_generated`
- answer cuối là lời chào tự nhiên, không còn fallback generic

Current truth chính xác hơn là:

- `runtime audit` đang nói đúng về provider/failover
- `direct lane quality` ở case này không hỏng cố định; nó có vẻ intermittent
- mình đã thêm guard để nếu completion lần sau thực sự rơi vào fallback generic, runtime note có thể nói rõ `Completion degraded: ...`

## OpenRouter Transient Check

Artifact:

- `E:\Sach\Sua\AI_v1\.Codex\reports\openrouter-qwen-free-probe-2026-04-04-101802.json`

Verified transiently with the user-provided key:

- OpenRouter free Qwen models currently include:
  - `qwen/qwen3.6-plus:free`
  - `qwen/qwen3-next-80b-a3b-instruct:free`
  - `qwen/qwen3-coder:free`
- direct probe to `qwen/qwen3.6-plus:free` resolved live to:
  - `model = qwen/qwen3.6-plus-04-02:free`
  - `provider = Alibaba`
  - `duration ~ 13.2s`

Key safety note:

- OpenRouter key was used transiently for external verification only
- no runtime policy or persisted backend secret was changed in this step
