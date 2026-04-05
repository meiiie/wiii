# Vision Live Probe Audit - 2026-04-03

## Summary
- Hoàn thiện `vision live probe / audit persistence` end-to-end cho Wiii.
- Admin runtime giờ nhìn được cả:
  - selectability tĩnh của vision providers/capabilities
  - live probe persisted state
  - degraded reasons theo provider/capability
- Desktop runtime tab đã refresh đồng thời:
  - `LLM runtime audit`
  - `Vision runtime audit`

## Backend
- Authority mới: [vision_runtime_audit_service.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/services/vision_runtime_audit_service.py)
- Contract admin đã mở rộng ở:
  - [admin_schemas.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/admin_schemas.py)
  - [admin_llm_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/admin_llm_runtime.py)
  - [admin.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/admin.py)
- Endpoint mới:
  - `POST /api/v1/admin/llm-runtime/vision-audit`

## Frontend
- API client:
  - [admin.ts](/E:/Sach/Sua/AI_v1/wiii-desktop/src/api/admin.ts)
  - [types.ts](/E:/Sach/Sua/AI_v1/wiii-desktop/src/api/types.ts)
- Admin runtime UI:
  - [LlmRuntimePolicyEditor.tsx](/E:/Sach/Sua/AI_v1/wiii-desktop/src/components/runtime/LlmRuntimePolicyEditor.tsx)
- Probe button giờ refresh cả catalog lẫn persisted vision runtime state.

## Tests
- Backend:
  - [test_vision_runtime_audit_service.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_vision_runtime_audit_service.py)
  - [test_admin_llm_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_admin_llm_runtime.py)
  - [test_runtime_endpoint_smoke.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_runtime_endpoint_smoke.py)
- Frontend:
  - [admin-runtime-tab.test.tsx](/E:/Sach/Sua/AI_v1/wiii-desktop/src/__tests__/admin-runtime-tab.test.tsx)

## Verify
- Backend focused suite: `20 passed`
- Frontend targeted suite: `7 passed`

## Current Truth
- Vision runtime audit đã có vòng đời đúng:
  - live probe
  - persist vào `admin_runtime_settings`
  - serialize vào runtime response
  - render ra admin tab
- Provider/capability rows giờ giữ được:
  - `last_probe_attempt_at`
  - `last_probe_success_at`
  - `last_probe_error`
  - `live_probe_note`
  - `degraded`
  - `degraded_reasons`

## Notes
- Mốc này chủ yếu khóa kiến trúc và operator visibility.
- Chưa chạy một live provider benchmark mới trong report này; phần probe thật sẽ phản ánh khi operator bấm `Probe capability` trên env có provider/config phù hợp.
