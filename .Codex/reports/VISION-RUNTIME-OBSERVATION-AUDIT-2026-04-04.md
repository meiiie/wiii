# VISION-RUNTIME-OBSERVATION-AUDIT-2026-04-04

## Muc tieu
Lam cho admin/runtime snapshot bot tre so voi thuc te song bang cach ghi lai `runtime observation` tu cac vision call that, khong chi dua vao `live probe` thu cong.

## Thay doi chinh
- Them `runtime observation` vao persisted vision audit:
  - provider level
  - capability level
- Truong moi:
  - `last_runtime_observation_at`
  - `last_runtime_success_at`
  - `last_runtime_error`
  - `last_runtime_note`
  - `last_runtime_source`
- `run_vision_prompt(...)` gio se ghi observation moi khi:
  - provider thanh cong
  - timeout
  - exception
  - empty output
- Logic demotion doc persisted audit gio bo qua demotion neu da co `last_runtime_success_at >= last_probe_attempt_at`.
- Admin/runtime API + desktop runtime tab hien duoc `runtime success`, `runtime error`, `runtime note` rieng voi `live probe`.

## File chinh
- `maritime-ai-service/app/services/vision_runtime_audit_service.py`
- `maritime-ai-service/app/engine/vision_runtime.py`
- `maritime-ai-service/app/api/v1/admin_schemas.py`
- `wiii-desktop/src/api/types.ts`
- `wiii-desktop/src/components/runtime/LlmRuntimePolicyEditor.tsx`

## Test
- Backend focused:
  - `test_vision_runtime.py`
  - `test_vision_runtime_audit_service.py`
  - `test_vision_selectability_service.py`
  - `test_admin_llm_runtime.py`
  - Ket qua: `38 passed`
- Frontend:
  - `admin-runtime-tab.test.tsx`
  - Ket qua: `8 passed`

## Live verify
- OCR call that tren screenshot LMS da ghi vao persisted audit:
  - provider = `zhipu`
  - model = `glm-ocr`
  - lane fit = `OCR specialist`
  - `last_runtime_success_at` co gia tri moi trong audit/admin snapshot
- Sau restart app, endpoint `/api/v1/admin/llm-runtime` da tra ra cac field runtime observation moi.

## Current truth
- `live probe` van giu vai tro health check chu dong.
- `runtime observation` bo sung su that tu cac request that, giup operator thay duoc:
  - provider vua hoi phuc that
  - capability nao vua thanh cong that
  - loi runtime moi nhat tren lane nao
- OCR demotion hien tai sach hon vi success that co the trung hoa probe loi cu trong persisted audit.

## Note
- Mot OCR rerun sau do da timeout/fail do upstream provider bat on, nen `runtime note` compact chua duoc refresh de thay the note cu trong DB.
- App process da duoc restart sau patch cuoi de dong bo code live voi source tren dia.
