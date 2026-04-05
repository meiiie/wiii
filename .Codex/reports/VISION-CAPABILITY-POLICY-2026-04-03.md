# Vision Capability Policy Checkpoint — 2026-04-03

## Summary

Wiii now has a professional `vision-by-capability` policy surface instead of treating all vision work as one lane.

The system is now split across:

- `ocr_extract`
- `visual_describe`
- `grounded_visual_answer`

Policy is persisted through runtime admin config, surfaced in desktop admin UI, and backed by tests.

## Architecture Changes

Implemented capability-aware vision policy in:

- `maritime-ai-service/app/engine/vision_runtime.py`
- `maritime-ai-service/app/services/vision_runtime_audit_service.py`
- `maritime-ai-service/app/services/llm_runtime_policy_service.py`
- `maritime-ai-service/app/api/v1/admin_schemas.py`
- `maritime-ai-service/app/api/v1/admin_llm_runtime.py`
- `maritime-ai-service/app/api/v1/admin_llm_runtime_support.py`
- `maritime-ai-service/app/core/config/_settings_base_fields.py`
- `maritime-ai-service/app/core/config/_settings.py`

Desktop/admin updates:

- `wiii-desktop/src/components/runtime/LlmRuntimePolicyEditor.tsx`
- `wiii-desktop/src/api/types.ts`
- `wiii-desktop/src/__tests__/admin-runtime-tab.test.tsx`

## Current Policy Surface

New runtime fields:

- `vision_describe_provider`
- `vision_describe_model`
- `vision_ocr_provider`
- `vision_ocr_model`
- `vision_grounded_provider`
- `vision_grounded_model`

Default intent:

- OCR specialist lane defaults toward `glm-ocr`
- Describe / grounded lanes remain general-vision lanes
- Runtime stays fail-closed when a provider/model contract is unclear

## Current Truth

Local runtime sanity check after patch:

- OCR provider order: `zhipu -> google -> openai -> openrouter -> ollama`
- Describe provider order: `google -> openai -> openrouter -> ollama -> zhipu`
- Grounded provider order: `google -> openai -> openrouter -> ollama -> zhipu`

Provider status snapshots:

- `zhipu + ocr_extract`
  - `available=True`
  - `model_name=glm-ocr`
- `zhipu + grounded_visual_answer`
  - `available=False`
  - `reason_code=model_unverified`
  - this is intentional fail-closed behavior until a verified Zhipu VLM contract is configured
- `openrouter + visual_describe`
  - currently blocked by missing key in this runtime

## UI/Test Stability

The desktop runtime tab no longer depends on positional selectors for provider controls.

Stable field-level selectors were added for:

- vision provider
- vision failover chain
- vision timeout
- describe provider/model
- OCR provider/model
- grounded provider/model
- embedding provider/model/failover chain

This prevents future UI growth from breaking tests just because layout or field order changes.

## Verification

Backend:

- `pytest tests/unit/test_vision_runtime.py tests/unit/test_vision_runtime_audit_service.py tests/unit/test_vision_selectability_service.py tests/unit/test_admin_llm_runtime.py tests/unit/test_llm_runtime_policy_service.py -q -p no:capture`
- Result: `28 passed`

Frontend:

- `npx vitest run src/__tests__/admin-runtime-tab.test.tsx`
- Result: `8 passed`

- `npx vitest run src/__tests__/admin-panel.test.ts src/__tests__/admin-panel-complete.test.ts`
- Result: `101 passed`

## Recommendation

Professional production direction remains:

- `ocr_extract` -> OCR specialist lane (`GLM-OCR`)
- `visual_describe` -> general VLM lane
- `grounded_visual_answer` -> stronger general VLM lane

Next high-value step:

- add live verified contracts for `OpenRouter/Ollama` VLMs by capability
- then benchmark `Qwen2.5-VL` / `MiniCPM-V` against current Google path for describe vs grounded workloads
