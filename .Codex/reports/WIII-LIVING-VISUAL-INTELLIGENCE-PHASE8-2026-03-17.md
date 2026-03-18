# Wiii Living Visual Intelligence Phase 8

Date: 2026-03-17
Owner: Codex
Scope: Backend-first implementation of SVG-first article figures/chart runtime, Canvas-first simulation, and living visual cognition.

## What changed

### 1. Visual cognition contract
- Extended `VisualIntentDecision` in `visual_intent_resolver.py` with:
  - `preferred_render_surface`
  - `planning_profile`
  - `thinking_floor`
  - `critic_policy`
  - `living_expression_mode`
- Updated routing defaults:
  - `article_figure` -> `svg` + `high`
  - `chart_runtime` -> `svg` + `high`
  - `simulation/code_studio_app` -> `canvas` + `max`
  - `artifact` -> `html` + `high`
- Upgraded `recommended_visual_thinking_effort()` so premium simulation now escalates to `max`.

### 2. Graph prompt injection
- Added `Visual Cognition Contract` prompt block in `graph.py`.
- Added `Living Visual Style` prompt block so Wiii can express pedagogy and scene choices without UI chrome changes.
- Runtime metadata now carries:
  - `preferred_render_surface`
  - `planning_profile`
  - `thinking_floor`
  - `critic_policy`
  - `living_expression_mode`

### 3. SVG-first structured runtime
- `visual_tools.py` now keeps `article_figure` and `chart_runtime` on structured/template lane by default.
- `code_html` no longer silently drags structured article/chart requests into inline HTML when runtime intent is structured.
- Structured payload scenes are enriched with shared scene grammar fields:
  - `render_surface`
  - `motion_profile`
  - `pedagogy_arc`
  - `state_model`
  - `narrative_voice`
  - `focus_states`

### 4. Canvas-first simulation critic
- Premium simulation validation now enforces Canvas-first expectations when the runtime asks for canvas.
- Existing premium simulation critic still requires:
  - state/update loop
  - controls
  - live readouts
  - feedback bridge
- Pendulum scaffold upgrade path remains intact.

### 5. Living-agent / prompt alignment
- Updated:
  - `code_studio.yaml`
  - `VISUAL_CODE_GEN.md`
  - `SKILL.md`
  - `character_card.py`
  - `wiii_identity.yaml`
  - `wiii_soul.yaml`
  - `.agents/skills/wiii-visual-runtime/references/scene-grammar.md`
- Net effect:
  - Wiii is nudged to think in scenes, motion, callouts, and takeaways.
  - Character-forward expression is framed as pedagogy and pacing, not extra chrome.

## Contract status

Preserved:
- `code_studio_context.active_session`
- SSE metadata:
  - `studio_lane`
  - `artifact_kind`
  - `quality_profile`
  - `renderer_contract`
- Existing widget feedback loop
- Existing patch/session reuse behavior

Additive only:
- visual cognition metadata
- scene grammar fields

## Test results

Verified:
- `test_visual_intent_resolver.py`
- `test_visual_tools.py`
- `test_graph_routing.py`
- `test_code_studio_streaming.py`

Result:
- `153 passed`

## Practical outcome

- Explanatory figures and charts now bias much harder toward structured SVG semantics.
- Premium simulations now bias harder toward deeper planning and Canvas-first quality.
- Wiii prompt assembly now carries a more explicit living visual pedagogy contract.
- The system is closer to:
  - LLM-first planning
  - host-governed runtime
  - character-forward expression
  - quality-first latency

## Remaining next step

Most valuable follow-up after this phase:
- add first-class SVG motion recipes
- add first-class canvas simulation recipes beyond pendulum
- add one more critic/repair layer before preview for non-recipe simulations
