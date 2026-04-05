# Graph Refactor Round 27

Date: 2026-03-29

## Scope

This round stayed focused on low-blast-radius refactors that reduce large utility/runtime shells without changing public import paths:

1. `visual_tools.py` facade split
2. `browser_base.py` fetch/interception runtime split
3. `visual_intent_resolver.py` heuristic/support split

## Changes

### 1. Visual tool facade cleanup

Created:

- `app/engine/tools/visual_payload_models.py`
- `app/engine/tools/visual_surface_support.py`

Modified:

- `app/engine/tools/visual_tools.py`

What moved:

- `VisualPayloadV1` model moved to `visual_payload_models.py`
- visual summary/title/claim/telemetry/renderer inference helpers moved to `visual_surface_support.py`
- `visual_tools.py` now keeps the legacy public surface and delegates to support modules

Line counts:

- `visual_tools.py`: `676 -> 534`
- `visual_surface_support.py`: `231`
- `visual_payload_models.py`: `52`

Verification:

- `py_compile` pass for all 3 files
- `pytest tests/unit/test_visual_tools.py -q -p no:capture --tb=short`
  - `78 passed`
  - `7 failed`

Notes:

- An initial mojibake regression in visual summary strings was fixed during this round.
- The remaining 7 failures match the pre-existing `visual_tools.py` runtime-policy drift already observed before this cut:
  - `renderer_kind` expected `template` vs current `inline_html`
  - `patch_strategy` expected `spec_merge` vs current `replace_html`
  - auto-grouping expectations (`1` payload vs expected `2/3`)

### 2. Browser adapter runtime split

Created:

- `app/engine/search_platforms/adapters/browser_fetch_runtime.py`

Modified:

- `app/engine/search_platforms/adapters/browser_base.py`

What moved:

- page fetch flow
- scroll-and-extract flow
- GraphQL interception flow
- worker-submitted fetch helpers
- LLM extraction helper

Preserved in `browser_base.py`:

- module-level patch points:
  - `_get_browser`
  - `_submit_to_pw_worker`
  - `_pw_worker_loop`
- class API:
  - `PlaywrightLLMAdapter._fetch_page_text`
  - `PlaywrightLLMAdapter._fetch_page_text_with_scroll`
  - `PlaywrightLLMAdapter._fetch_page_with_interception`
  - `PlaywrightLLMAdapter._run_fetch*`

Line counts:

- `browser_base.py`: `716 -> 495`
- `browser_fetch_runtime.py`: `346`

Verification:

- `py_compile` pass
- Browser-focused suite:
  - `pytest tests/unit/test_sprint152_browser_scraping.py tests/unit/test_sprint154_thumbnail_cookie.py tests/unit/test_sprint155_facebook_group.py tests/unit/test_sprint156_network_interception.py -q -p no:capture --tb=short`
  - Result: `191 passed`

Notes:

- `test_sprint153_browser_screenshots.py` is still blocked by an unrelated collection error:
  - `graph_streaming -> graph` import drift for `_build_turn_local_state_defaults`
- `test_sprint153_hardening.py` still has an unrelated old drift:
  - `ImportError: cannot import name '_TRACERS' from app.engine.multi_agent.graph`

### 3. Visual intent heuristic split

Created:

- `app/engine/multi_agent/visual_intent_support.py`

Modified:

- `app/engine/multi_agent/visual_intent_resolver.py`

What moved:

- keyword banks
- normalization helper
- metadata helper
- quality/thinking merge helpers
- quiz/simulation/app-followup detection helpers
- figure-budget heuristic

Preserved in `visual_intent_resolver.py`:

- `VisualIntentDecision`
- `resolve_visual_intent`
- `detect_visual_patch_request`
- `required_visual_tool_names`
- `filter_tools_for_visual_intent`
- `recommended_visual_thinking_effort`

Line counts:

- `visual_intent_resolver.py`: `691 -> 450`
- `visual_intent_support.py`: `325`

Verification:

- `py_compile` pass
- `pytest tests/unit/test_visual_intent_resolver.py tests/unit/test_graph_routing.py -q -p no:capture --tb=short`
  - Result: `102 passed`

## Sentrux

Ran:

```powershell
E:\Sach\Sua\AI_v1\tools\sentrux.exe gate .
```

Result:

- Quality: `4419`
- Coupling: `0.30`
- Cycles: `8`
- God files: `3`
- Distance from Main Sequence: `0.31`
- Verdict: `No degradation detected`

## Current top large files

After this round:

1. `app/core/config/_settings.py` — `998`
2. `app/engine/multi_agent/graph.py` — `737`
3. `app/services/chat_orchestrator.py` — `735`
4. `app/engine/agentic_rag/corrective_rag.py` — `734`
5. `app/sandbox/opensandbox_executor.py` — `706`
6. `app/engine/model_catalog.py` — `704`
7. `app/services/llm_runtime_audit_service.py` — `696`
8. `app/engine/reasoning/reasoning_narrator.py` — `693`

## Recommendation for next round

Best next safe targets:

1. `app/sandbox/opensandbox_executor.py`
2. `app/services/llm_runtime_audit_service.py`
3. `app/services/input_processor.py`

Defer for now:

- `app/core/config/_settings.py`
  - large blast radius
- `app/engine/model_catalog.py`
  - contains path-guarded legacy model strings that are intentionally whitelisted in tests
- `app/services/chat_orchestrator.py`
  - many patch + source-inspection tests make it more sensitive than it looks
