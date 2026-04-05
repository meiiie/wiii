# VISION-OCR-LANE-FIT-HARDENING-2026-04-04

## Muc tieu
Lam ro su khac nhau giua lane `specialist` va `fallback` trong vision runtime, dac biet cho OCR, de route thuc te va admin/runtime UI cung noi cung mot su that.

## Thay doi chinh
- Them `lane_fit` + `lane_fit_label` vao `VisionProviderStatus` trong `app/engine/vision_runtime.py`.
- Dinh nghia fit theo capability:
  - `ocr_extract`:
    - `zhipu / glm-ocr` => `specialist`
    - cac VLM tong quat (`ollama/google/openai/openrouter`) => `fallback`
  - `visual_describe` / `grounded_visual_answer` => `general`
- `_resolve_provider_order(...)` gio sap xep chain theo lane fit khi khong co explicit override, roi moi ap demotion tam thoi.
- Dua `lane_fit` ra selectability snapshot, admin schema/API, desktop types, va runtime tab UI.
- Runtime tab hien badge cho tung capability: `OCR specialist`, `OCR fallback`, `General vision`.

## File chinh
- `maritime-ai-service/app/engine/vision_runtime.py`
- `maritime-ai-service/app/services/vision_selectability_service.py`
- `maritime-ai-service/app/api/v1/admin_schemas.py`
- `wiii-desktop/src/api/types.ts`
- `wiii-desktop/src/components/runtime/LlmRuntimePolicyEditor.tsx`

## Test
- Backend:
  - `tests/unit/test_vision_runtime.py` => `22 passed`
  - `tests/unit/test_vision_selectability_service.py` => `2 passed`
  - `tests/unit/test_admin_llm_runtime.py` => `6 passed`
- Frontend:
  - `src/__tests__/admin-runtime-tab.test.tsx` => `8 passed`

## Live verify
### Admin runtime snapshot
Sau khi refresh `POST /api/v1/admin/llm-runtime/vision-audit` voi `providers=['ollama','zhipu']`:
- `ollama / gemma3:4b`
  - `visual_describe` => `General vision`
  - `ocr_extract` => `OCR fallback`
  - `grounded_visual_answer` => `General vision`
- `zhipu`
  - `ocr_extract / glm-ocr` => `OCR specialist`
  - `visual_describe` + `grounded_visual_answer` van `model_unverified` theo contract hien tai

### Direct runtime probe
OCR live probe bang `run_vision_prompt(..., capability=OCR_EXTRACT)` tren screenshot LMS:
- success = `true`
- provider = `zhipu`
- model = `glm-ocr`
- attempted_providers[0].lane_fit = `specialist`
- tong thoi gian ~ `39.8s`

## Current truth
- Local general vision dang on dinh qua `ollama / gemma3:4b`.
- OCR specialist cua he thong van la `zhipu / glm-ocr`.
- Local `ollama / gemma3:4b` duoc giu dung vai tro OCR fallback, khong con bi nhin nhu ngang vai voi specialist.
- Admin/runtime UI gio phan biet ro lane theo capability thay vi chi bao `available` / `not available`.

## Buoc tiep theo hop ly
- Neu tiep tuc, buoc chuyen tiep dep nhat la ghi nhan `runtime observation` tu call that vao vision audit, de admin snapshot giam do tre so voi thuc te ma khong phai bam refresh thu cong qua nhieu.
