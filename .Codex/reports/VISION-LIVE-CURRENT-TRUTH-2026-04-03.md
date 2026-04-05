# Vision Live Current Truth - 2026-04-03

## What changed
- Chạy live probe thật cho `vision runtime` trên env hiện tại.
- Vá bug phân loại lỗi trong [vision_runtime_audit_service.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/services/vision_runtime_audit_service.py):
  - trước đó mọi lỗi probe có `timeout_seconds` đều bị gắn nhầm thành `timeout`
  - giờ chỉ exception timeout thật mới bị gắn `timeout`

## Verify
- Focused backend suite:
  - `4 passed`
  - [test_vision_runtime_audit_service.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_vision_runtime_audit_service.py)

## Live artifact
- [vision-live-probe-2026-04-03.json](/E:/Sach/Sua/AI_v1/.Codex/reports/vision-live-probe-2026-04-03.json)

## Current truth
- `google`
  - selectability: `available=true`
  - live probe: `degraded`
  - reason thật: `rate_limit / quota`
  - không phải timeout
- `openai`
  - blocked: `missing_api_key`
- `openrouter`
  - blocked: `missing_api_key`
- `ollama`
  - blocked: `model_unverified`
  - current local model không có dấu hiệu là vision model
- `zhipu`
  - blocked: `model_unverified`
  - contract vision production chưa đủ chắc để bật

## Interpretation
- Lớp `vision selectability` đang cho biết backend nào có thể được chọn về mặt config/runtime.
- Lớp `vision live probe audit` giờ cho biết backend nào đang thực sự usable ở thời điểm hiện tại.
- Với env này, Google vẫn là candidate mạnh nhất về mặt cấu hình, nhưng đang bị quota thực tế nên runtime tab sẽ hiện `degraded` với lý do đúng.

## Recommended next step
- Nếu muốn `vision runtime` thật sự sống đa provider, bước tiếp theo nên là:
  - chuẩn hóa `OpenAI-compatible vision` path khi có key
  - hoặc cài một local Ollama vision model có contract rõ
  - rồi benchmark lại `visual_describe / OCR / grounded answer`
