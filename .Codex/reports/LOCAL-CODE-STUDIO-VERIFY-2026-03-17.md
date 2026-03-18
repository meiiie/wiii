# Local Code Studio + Visual Runtime Verification

**Date:** 2026-03-17  
**Scope:** Final local verification before deploy for Code Studio streaming, follow-up patching, balanced inline reasoning, and article/visual runtime coexistence.

## What Was Fixed

### 1. Code Studio SSE metadata now survives the streaming layer
- Added `studio_lane`, `artifact_kind`, `quality_profile`, and `renderer_contract` passthrough for `code_open` and `code_complete`.
- Files:
  - `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\stream_utils.py`
  - `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph_streaming.py`

### 2. Runtime metadata canonicalization no longer regresses to `presentation_intent="text"`
- Fixed `_normalize_visual_payload()` so canonical runtime fields win over stale metadata.
- File:
  - `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\tools\visual_tools.py`

### 3. Vietnamese follow-up patch detection is now covered by regression tests
- Added explicit Unicode-safe regression coverage for prompts such as:
  - `Giữ app hiện tại, thêm slider điều chỉnh trọng lực và ma sát`
  - `Đổi màu nền thành xanh nhạt`
- File:
  - `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_visual_intent_resolver.py`

### 4. Balanced reasoning now shows the Code Studio strip inline
- `tool_create_visual_code` renders through `ToolExecutionStrip` in balanced/live reasoning intervals instead of collapsing to a generic op row.
- Files:
  - `E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\ReasoningInterval.tsx`
  - `E:\Sach\Sua\AI_v1\wiii-desktop\src\__tests__\reasoning-interval.test.tsx`

### 5. Code Studio versions now advance even if backend reuses version `1`
- The client store now auto-bumps version numbers when a follow-up patch reuses the same session but backend metadata still says `version=1`.
- This preserves the intended `v1 / v2 / v3` UX in the right-side panel.
- Files:
  - `E:\Sach\Sua\AI_v1\wiii-desktop\src\stores\code-studio-store.ts`
  - `E:\Sach\Sua\AI_v1\wiii-desktop\src\__tests__\code-studio-store.test.ts`

### 6. Added real browser regression for Code Studio
- New Playwright scenario verifies:
  - Code Studio panel opens
  - inline Code Studio card appears
  - code stream completes
  - follow-up patch stays in the same app lane
  - version buttons show `v1` and `v2`
- Files:
  - `E:\Sach\Sua\AI_v1\wiii-desktop\playwright\code-studio-runtime.spec.ts`
  - `E:\Sach\Sua\AI_v1\wiii-desktop\playwright.visual.config.ts`

## Important Verification Notes

### Unicode gotcha during shell smoke testing
- Raw PowerShell → Python stdin can silently mangle Vietnamese diacritics.
- When verifying follow-up prompts manually through shell scripts, use Unicode escapes or a UTF-8-safe source.
- Browser/frontend traffic is UTF-8 and did not have this issue.

### Local backend flag
- Code Studio SSE events require `ENABLE_CODE_STUDIO_STREAMING=true`.
- Local verification passed only after restarting the backend with that flag enabled.

## Local Smoke Result

Using UTF-8-safe follow-up prompts:
- Turn 1 produced:
  - `code_open`
  - `code_delta`
  - `code_complete`
  - `visual_open`
  - `visual_commit`
- Turn 2 produced:
  - `code_open`
  - `code_complete`
  - `visual_patch`
  - `visual_commit`
- This confirmed the real follow-up path is now a patch flow, not a new visual-open flow.

## Test Results

### Backend targeted
```powershell
python -m pytest tests\unit\test_visual_intent_resolver.py tests\unit\test_visual_tools.py tests\unit\test_sprint54_graph_streaming.py tests\unit\test_chat_stream_presenter.py -q
```
- Result: `138 passed`

### Frontend targeted
```powershell
npm test -- --run src/__tests__/reasoning-interval.test.tsx src/__tests__/tool-execution-strip.test.tsx src/__tests__/sprint154-immer.test.ts src/__tests__/structured-visuals.test.tsx src/__tests__/interleaved-block-sequence.test.tsx src/__tests__/code-studio-store.test.ts
```
- Result: `71 passed`

### Web build
```powershell
npm run build:web
```
- Result: `pass`

### Playwright visual/runtime
```powershell
npx playwright test -c playwright.visual.config.ts --reporter=list
```
- Result: `3 passed`
  - `code-studio-runtime.spec.ts`
  - `visual-runtime.spec.ts` desktop
  - `visual-runtime.spec.ts` mobile

## Local URLs Ready For Manual QA
- Frontend: `http://127.0.0.1:1420/`
- Backend health: `http://127.0.0.1:8001/api/v1/health`

## Suggested Manual QA Prompts
- `Explain Kimi linear attention in charts`
- `Patch the most recent visual session only. Turn it into 3 process steps.`
- `Hãy mô phỏng vật lý con lắc bằng mini app HTML/CSS/JS có kéo thả chuột.`
- `Giữ app hiện tại, thêm slider điều chỉnh trọng lực và ma sát.`

## Ship Readiness
- Local validation for this slice is strong enough for deploy.
- The main remaining work is quality/art direction improvement, not runtime correctness for the tested flows.
