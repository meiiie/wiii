# Vision Runtime Audit Snapshot - 2026-04-03

## Summary
- Added a provider-agnostic `vision selectability` authority so admin/runtime no longer guesses image-capable backends from scattered config.
- Persisted `vision_provider`, `vision_failover_chain`, and `vision_timeout_seconds` inside the same durable runtime policy flow as LLM/embeddings.
- Exposed capability-level truth to operator UI for:
  - `visual_describe`
  - `ocr_extract`
  - `grounded_visual_answer`

## Backend
- New authority:
  - `E:\Sach\Sua\AI_v1\maritime-ai-service\app\services\vision_selectability_service.py`
- Admin/runtime contracts updated:
  - `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\admin_schemas.py`
  - `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\admin_llm_runtime.py`
  - `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\admin_llm_runtime_support.py`
  - `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\admin.py`
- Persisted policy extended:
  - `E:\Sach\Sua\AI_v1\maritime-ai-service\app\services\llm_runtime_policy_service.py`

## Frontend
- Runtime types extended:
  - `E:\Sach\Sua\AI_v1\wiii-desktop\src\api\types.ts`
- Admin runtime tab now shows a dedicated `Vision runtime` section:
  - provider mode
  - failover chain
  - timeout
  - per-provider capability cards
  - `E:\Sach\Sua\AI_v1\wiii-desktop\src\components\runtime\LlmRuntimePolicyEditor.tsx`

## Tests
- New:
  - `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_vision_selectability_service.py`
- Updated:
  - `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_admin_llm_runtime.py`
  - `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_llm_runtime_policy_service.py`
  - `E:\Sach\Sua\AI_v1\wiii-desktop\src\__tests__\admin-runtime-tab.test.tsx`

## Verify
- Backend focused:
  - `15 passed` for `test_vision_selectability_service.py`, `test_admin_llm_runtime.py`, `test_llm_runtime_policy_service.py`
- Backend smoke:
  - `10 passed` for `test_runtime_endpoint_smoke.py`
  - `5 passed` for `test_vision_runtime.py`
- Frontend:
  - `7 passed` for `admin-runtime-tab.test.tsx`

## Current Truth
- Vision runtime now has a single operator-facing truth source, similar to embeddings.
- Changing runtime policy invalidates:
  - LLM selectability cache
  - embedding selectability cache
  - vision selectability cache
  - vision runtime probe cache
- Operator can now see which provider is usable for each vision capability, instead of treating “vision” like one opaque on/off flag.
