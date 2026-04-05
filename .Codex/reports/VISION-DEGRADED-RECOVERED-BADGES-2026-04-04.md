# VISION-DEGRADED-RECOVERED-BADGES-2026-04-04

## Muc tieu
Lam cho badge `recovered` trong admin/runtime phan anh dung su that hien tai, khong phai chi vi tung co mot runtime success cu.

## Fix
- Them `recovered` + `recovered_reasons` o provider level.
- Them `recovered` + `recovered_label` o capability level.
- Logic moi chi danh dau `recovered=true` khi:
  - co `last_probe_error`
  - co `last_runtime_success_at`
  - va `last_runtime_success_at` khop voi observation runtime moi nhat (khong co runtime fail moi hon)
- Neu success cu nhung observation runtime moi nhat la fail, badge `recovered` se tat.

## File chinh
- `maritime-ai-service/app/services/vision_runtime_audit_service.py`
- `maritime-ai-service/app/api/v1/admin_schemas.py`
- `wiii-desktop/src/api/types.ts`
- `wiii-desktop/src/components/runtime/LlmRuntimePolicyEditor.tsx`

## Verify
- Backend: `9 passed`
- Frontend: `8 passed`

## Live current truth
Tu `/api/v1/admin/llm-runtime`:
- `zhipu / ocr_extract`
  - `degraded = true`
  - `recovered = false`
  - ly do: observation runtime moi nhat da fail sau lan success truoc do
- Nghia la dashboard gio khong con xanh gia khi provider vua roi lai.
