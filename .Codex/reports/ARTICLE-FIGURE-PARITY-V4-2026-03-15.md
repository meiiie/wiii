# Wiii Article-Figure Parity V4

Date: 2026-03-15
Workspace: `E:\Sach\Sua\AI_v1`

## Goal

Move Wiii from `message + widget card` toward an `article shell + inline thinking intervals + figure runtime` model:

- `Claude-like`: prose serif rhythm, figures embedded as part of the article, multi-figure pedagogy
- `Z.ai-like`: public thinking visible inline throughout the stream
- `MCP Apps-like`: simulations and tools still run in a sandboxed lane, but the host shell absorbs them into the article flow

## What Changed

### Backend

- Extended `VisualPayloadV1` in `maritime-ai-service/app/engine/tools/visual_tools.py` with:
  - `figure_group_id`
  - `figure_index`
  - `figure_total`
  - `pedagogical_role`
  - `chrome_mode`
  - `claim`
- Added grouped figure parsing and normalization:
  - `parse_visual_payloads(...)`
  - `_build_multi_figure_payloads(...)`
- Upgraded `tool_generate_visual(...)` to return `1..N` structured payloads when `spec_json.figures[]` is provided.
- Upgraded graph streaming orchestration in `maritime-ai-service/app/engine/multi_agent/graph.py`:
  - grouped `visual_open` / `visual_patch`
  - grouped summary text
  - disposal of superseded sessions
  - figure-aware telemetry

### Frontend

- Promoted `wiii-desktop/src/components/chat/InterleavedBlockSequence.tsx` into an article composer.
- Added multi-figure grouping in the main answer flow:
  - prose split into article segments
  - figures inserted inline by `figure_group_id` / `figure_index`
  - grouped figures no longer re-render as standalone widget cards
- Kept thinking visible in the same reading column while removing the old per-interval `Trace` affordance from the main surface.
- Added a message-level inspector entry point instead of a main-flow reasoning box feel.
- Extended visual types in `wiii-desktop/src/api/types.ts` and normalized V4 figure metadata in `wiii-desktop/src/components/chat/VisualBlock.tsx`.
- Added styling support in `wiii-desktop/src/styles/globals.css` for:
  - bridge prose + claim chips
  - article figure segments
  - message-level inspector affordance

### Prompt / Skill Layer

- Updated `assistant.yaml`, `direct.yaml`, `rag.yaml`, and `tutor.yaml` to bias the model toward:
  - `2-3` explanatory figures by default
  - `problem -> mechanism -> result/benchmark/conclusion`
  - one claim per figure
  - bridge prose before each figure
  - inline editorial app figures for simulations
- Updated `.agents/skills/wiii-visual-runtime/SKILL.md` to describe:
  - article-first orchestration
  - multi-figure pedagogy
  - required V4 figure metadata
  - app lane guidance for simulations such as a pendulum

## Tests Run

### Backend

- `E:\Sach\Sua\AI_v1\maritime-ai-service\.venv\Scripts\python.exe -m pytest tests/unit/test_visual_tools.py tests/unit/test_visual_prompt.py -q`
  - `72 passed`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\.venv\Scripts\python.exe -m pytest tests/unit/test_visual_intent_resolver.py -q`
  - `13 passed`

### Frontend

- `npm test -- --run src/__tests__/interleaved-block-sequence.test.tsx src/__tests__/structured-visuals.test.tsx src/__tests__/sse.test.ts src/__tests__/use-sse-stream-concurrency.test.ts`
  - `62 passed`
- `npm run build:web`
  - pass
- `npm run test:e2e:visual`
  - `2 passed`
  - desktop: editorial inline visual flow preserved
  - mobile: editorial inline visual flow remains responsive

## Status

This phase is `deploy-ready` for the V4 target.

What is now true:

- thinking stays inline instead of collapsing into a default reasoning box
- grouped explanatory figures can be orchestrated as a sequence inside one answer
- prompt/skill guidance now matches the new UI contract
- browser acceptance still passes after the article-first refactor

## Remaining Gaps

These are polish or depth gaps, not blockers for V4:

- multi-figure follow-up patching is not yet as rich as initial grouped opening
- visual art direction can still move closer to Claude for chart/timeline/map families
- build warnings remain for large chunks (`vendor-mermaid`, `vendor-plotly`, `vendor-sandpack`)
- high-trust physics simulation still needs its own deterministic template lane if the goal is scientific accuracy, not just an inline app demo
