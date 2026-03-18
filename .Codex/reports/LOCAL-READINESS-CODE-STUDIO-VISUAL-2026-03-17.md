# Local Readiness — Code Studio + Visual Runtime

**Date:** 2026-03-17  
**Scope:** local-only verification before deploy  
**Status:** deploy-ready on local

## What was fixed

### 1. Vietnamese Code Studio follow-ups now reuse the active session
- Root cause:
  - `visual_intent_resolver._normalize()` was too weak for Vietnamese with diacritics, so prompts like `Giữ app hiện tại...` often collapsed into plain text intent.
  - `_build_visual_tool_runtime_metadata()` only reused `visual_context`, not active `code_studio_context`.
- Fix:
  - strengthened Unicode normalization in [visual_intent_resolver.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/visual_intent_resolver.py)
  - added app-followup patch classification for Vietnamese app/widget edits
  - added runtime metadata fallback from active `code_studio_context`
  - added support for `preferred_code_studio_session_id` in [visual_tools.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/tools/visual_tools.py)

### 2. Explicit `show code` flow now behaves correctly
- The frontend already pinned Code Studio to the `code` tab when the user explicitly asked to see code.
- The remaining proof gap was in end-to-end verification, so the Playwright suite was extended with the exact Vietnamese prompt chain:
  - initial pendulum app
  - add gravity + damping sliders
  - add angle + velocity display
  - show the code
- Result:
  - same session versions advance to `v1`, `v2`, `v3`
  - panel switches to code view when asked

### 3. Local readiness is now proven against the real prompts we want to ship
- Not just English smoke prompts
- Not just unit tests
- The exact Vietnamese prompts requested for local product validation now pass in browser E2E

## Files changed in this phase

### Backend
- [visual_intent_resolver.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/visual_intent_resolver.py)
- [graph.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py)
- [visual_tools.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/tools/visual_tools.py)
- [test_sprint154_tech_debt.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_sprint154_tech_debt.py)
- [test_visual_intent_resolver.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_visual_intent_resolver.py)
- [test_visual_tools.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_visual_tools.py)

### Frontend / E2E
- [code-studio-runtime.spec.ts](E:/Sach/Sua/AI_v1/wiii-desktop/playwright/code-studio-runtime.spec.ts)

## Verification

### Backend targeted tests
```powershell
cd E:\Sach\Sua\AI_v1\maritime-ai-service
python -m pytest tests/unit/test_sprint154_tech_debt.py tests/unit/test_visual_tools.py tests/unit/test_visual_intent_resolver.py -q
```

Result:
- `158 passed`

### Frontend targeted tests
Already green earlier in the same local readiness pass:
- `50 passed`

### Web build
```powershell
cd E:\Sach\Sua\AI_v1\wiii-desktop
npm run build:web
```

Result:
- pass

### Browser E2E
```powershell
cd E:\Sach\Sua\AI_v1\wiii-desktop
npm run test:e2e:visual
```

Result:
- `4 passed`

Covered:
- Code Studio English flow
- Code Studio Vietnamese flow
- Desktop inline visual/article flow
- Mobile visual/article flow

## Exact prompts now covered

### Visual / article flow
- `Explain Kimi linear attention in charts`

### Code Studio / app flow
- `Hãy mô phỏng vật lý con lắc bằng mini app HTML/CSS/JS có kéo thả chuột`
- `Giữ app hiện tại, thêm slider điều chỉnh trọng lực và ma sát`
- `Thêm hiển thị góc lệch và vận tốc theo thời gian`
- `Cho tôi xem code đang được sinh ra`

## Readiness assessment

### Ready
- balanced thinking remains inline and stable
- explanatory visual flow stays in article/editorial lane
- Code Studio app flow supports same-session follow-up patches in Vietnamese
- explicit code-view requests open the code surface instead of leaving the user stuck in preview
- build + browser E2E are green

### Still non-blocking polish
- visual art direction can still move closer to Claude in typography and whitespace
- Code Studio output quality can still be improved via chart runtime recipes and critic loop
- production has not received this phase yet

## Ship recommendation

This phase is **ready to deploy from local**.

Recommended next move:
1. deploy this patch set
2. smoke test on production with the same Vietnamese prompt chain
3. only after that continue with `quality gate + critic loop + chart runtime recipes`
