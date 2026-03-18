# Wiii Code Studio Local Readiness Phase 7

**Date:** 2026-03-17
**Owner:** Codex
**Scope:** Backend capability hardening for Code Studio simulation flow, local readiness verification

## Summary

This phase stayed focused on system capability, not chat chrome.

Key outcomes:

- Pendulum simulation requests now route faster and more deterministically in the `code_studio_app` lane.
- Premium pendulum scaffolds no longer over-fulfill gravity/damping controls on v1 unless the query asks for them.
- Follow-up prompts like "add gravity and damping sliders" now have meaningful room to become `v2`.
- Premium simulation outputs still require feedback bridge hooks before preview.
- Local Playwright visual/code-studio suite is fully green again.

## Backend Changes

### 1. Exact tool forcing for single-tool Code Studio cases

File:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph.py`

Change:
- `_bind_direct_tools(..., force=True)` now uses the exact tool name when only one tool is bound.
- This reduces dithering before the first Code Studio tool call.

### 2. Premium simulation critic tightened

File:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\tools\visual_tools.py`

Change:
- Premium simulations now require feedback bridge hooks such as `window.WiiiVisualBridge.reportResult(...)`.
- Rich-but-silent simulations get upgraded instead of passing preview as-is.

### 3. Query-aware pendulum scaffold

File:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\tools\visual_tools.py`

Change:
- Pendulum scaffold now reads the runtime user query.
- Default scaffold includes `length` control only.
- `gravity` and `damping` controls appear only when the query explicitly asks for them.

Why:
- Keeps `v1` lighter and less over-specified.
- Makes follow-up patch prompts semantically meaningful.

### 4. Pendulum Code Studio fast path

File:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph.py`

Change:
- Added a narrow fast path for clear pendulum simulation requests in the `code_studio_app` lane.
- The fast path invokes `tool_create_visual_code` directly with a minimal placeholder that upgrades into the approved scaffold.
- This avoids long pre-tool LLM latency for recipe-backed pendulum tasks.

Constraints:
- Only applies to pendulum-style simulation requests.
- Does not apply to explicit code-view requests.
- Does not replace the normal LLM loop for custom or broader Code Studio tasks.

### 5. Playwright local backend parity

File:
- `E:\Sach\Sua\AI_v1\wiii-desktop\scripts\start-visual-backend.mjs`

Change:
- Ensures `ENABLE_CODE_STUDIO_STREAMING=true` during Playwright visual/code-studio runs.

## Contract Clarification For Frontend

### `tool_create_visual_code`

Current backend contract:

- `studio_lane=app|widget` -> `renderer_kind="app"`
- `studio_lane=artifact` -> `renderer_kind="inline_html"`

It does **not** intentionally emit `renderer_kind="template"` for Code Studio output.

So if frontend sees:

- `renderer_kind="template"`
- article shell header
- empty structured body

that issue is more likely coming from the structured `tool_generate_visual` path, not from `tool_create_visual_code`.

### `fallback_html`

For `tool_create_visual_code`, `fallback_html` is populated with the full HTML document that gets streamed through:

- `code_open`
- `code_delta`
- `code_complete`

with metadata:

- `studio_lane`
- `artifact_kind`
- `quality_profile`
- `renderer_contract`

## Validation

### Backend tests

- `test_visual_tools.py`
- `test_graph_routing.py`
- `test_visual_intent_resolver.py`
- `test_code_studio_streaming.py`
- `test_chat_request_flow.py`

Result:
- `152 passed`
- `14 passed`

### Frontend / E2E

Command:
- `cmd /c npm run test:e2e:visual`

Result:
- `4 passed`

Covered:
- English Code Studio pendulum prompt
- Vietnamese Code Studio follow-up patch flow
- Desktop editorial visual flow
- Mobile editorial visual flow

### Build

Command:
- `cmd /c npm run build:web`

Result:
- pass

## Readiness

Local status for this phase:

- Backend targeted tests: green
- Code Studio visual e2e: green
- Web build: green

This phase is now local-ready for deploy handoff.
