# Wiii Local Readiness — Phase 11

Date: 2026-03-19
Scope: Conservative Evolution + Living Visual Cognition local verification

## Environment

- Frontend: `http://localhost:1420/`
- Backend: `http://127.0.0.1:8000/`
- Backend interpreter: `E:/Sach/Sua/AI_v1/maritime-ai-service/.venv/Scripts/python.exe`

## Enabled flags

- `ENABLE_LIVING_CORE_CONTRACT=true`
- `ENABLE_MEMORY_BLOCKS=true`
- `ENABLE_DELIBERATE_REASONING=true`
- `ENABLE_LIVING_VISUAL_COGNITION=true`
- `ENABLE_CONSERVATIVE_FAST_ROUTING=true`
- `ENABLE_CODE_STUDIO_STREAMING=true`
- `ENABLE_STRUCTURED_VISUALS=true`

## Key fixes validated

- Direct visual lane now narrows `article_figure/chart_runtime` turns to `tool_generate_visual`.
- Explicit inline visual turns can skip slow supervisor LLM routing through conservative fast path.
- Article/chart visual turns now force the visual tool more reliably.
- Code Studio session reuse and inline visual patch flow remain intact.

## Backend tests

- `python -m pytest maritime-ai-service/tests/unit/test_graph_routing.py maritime-ai-service/tests/unit/test_conservative_evolution.py -q -p no:capture`
  - Result: `31 passed`
- `python -m pytest maritime-ai-service/tests/unit/test_supervisor_routing.py maritime-ai-service/tests/unit/test_visual_intent_resolver.py -q -p no:capture`
  - Result: `60 passed`

## Frontend E2E tests

- `npx playwright test playwright/visual-runtime.spec.ts -c playwright.visual.config.ts --reporter=line`
  - Result: `2 passed`
- `npx playwright test playwright/code-studio-runtime.spec.ts -c playwright.visual.config.ts --reporter=line`
  - Result: `6 passed`

## Acceptance status

- `article_figure/chart_runtime`: pass on desktop and mobile
- `simulation/code_studio_app`: pass
- `artifact lane`: pass
- `follow-up patching`: pass
- `explicit code view`: pass

## Important note

This is local readiness for the current phase, not a full exhaustive rerun of the entire backend/frontend test corpus.
