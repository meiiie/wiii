# Thinking Interval + Inline Surface

Date: 2026-03-15
Owner: Codex (LEADER)

## Outcome

Wiii now keeps public thinking inline in the main reading column instead of collapsing it into the old boxed `ThinkingBlock` surface. The visual runtime also holds up under real web acceptance on desktop and mobile with editorial inline visuals and inline reasoning intervals visible together.

## What Changed

- Frontend main flow now renders `ReasoningInterval` as the public thinking surface.
- `ThinkingBlock` remains available only inside the trace inspector drawer.
- Main flow no longer hides reasoning when visuals are present.
- Tutor lane now binds structured visual tools and filters legacy chart/widget tools for explicit visual intents.
- Visual intent resolver now catches `charts` prompts more reliably and routes Vietnamese simulation prompts like `mo phong vat ly con lac` to the app/runtime lane.
- Playwright acceptance was hardened to wait for a stable visual state before comparing counts and to assert inline reasoning intervals directly.

## Key Files

- `E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\ReasoningInterval.tsx`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\InterleavedBlockSequence.tsx`
- `E:\Sach\Sua\AI_v1\wiii-desktop\playwright\visual-runtime.spec.ts`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\visual_intent_resolver.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_node.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph.py`

## Verification

- Backend:
  - `python -m pytest tests\unit\test_visual_intent_resolver.py -q -p no:capture`
  - `python -m pytest tests\unit\test_tutor_agent_node.py -q -p no:capture`
  - `python -m pytest tests\unit\test_visual_tools.py -q -p no:capture`
  - `python -m pytest tests\unit\test_visual_prompt.py -q -p no:capture`
  - `python -m pytest tests\unit\test_chat_stream_presenter.py -q -p no:capture`
- Frontend:
  - `npm test -- --run src/__tests__/interleaved-block-sequence.test.tsx src/__tests__/structured-visuals.test.tsx src/__tests__/use-sse-stream-concurrency.test.ts`
  - `npm run build:web`
  - `npm run test:e2e:visual`

## Current Status

- Correctness: pass
- Inline thinking intervals: pass
- Editorial inline visual flow: pass
- Desktop web acceptance: pass
- Mobile web acceptance: pass

## Remaining Non-Blocking Work

- Richer art direction for charts/timeline/map visuals
- Optional physics-grade simulation templates for pendulum-style requests
- Chunk-size follow-up for `vendor-mermaid`, `vendor-plotly`, and `vendor-sandpack`
