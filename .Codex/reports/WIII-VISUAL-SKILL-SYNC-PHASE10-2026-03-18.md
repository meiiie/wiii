# Wiii Visual Skill Sync + Artifact Handoff Cleanup — 2026-03-18

## Scope
- Sync Wiii-only SKILL docs with the new direction:
  - `article_figure` / `chart_runtime` => SVG-first
  - `simulation` => Canvas-first
  - artifact promotion => follow-up prompt handoff, not silent conversion
- Remove safe legacy residue that could confuse future maintainers.
- Lock the new inline-visual artifact handoff contract with tests.

## Changes
- Updated Wiii skills in `.agents/skills/` so they no longer describe a template-first visual strategy.
- Added new Wiii skills:
  - `wiii-svg-motion-explainer`
  - `wiii-canvas-simulation`
  - `wiii-scene-grammar`
  - `wiii-visual-critic`
- Updated backend/internal skill guidance:
  - `code_studio.yaml`
  - `code_studio_agent/SKILL.md`
  - `code_studio_agent/VISUAL_CODE_GEN.md`
  - `scene-grammar.md`
- Added artifact-handoff fields to the visual contract so inline visuals can advertise a Claude-like “open as artifact” follow-up action:
  - `artifact_handoff_available`
  - `artifact_handoff_mode`
  - `artifact_handoff_label`
  - `artifact_handoff_prompt`
- Clarified `VisualBlock.tsx` comments so the file no longer falsely claims every visual goes through an iframe.
- Removed temporary local probe files:
  - `wiii-desktop/tmp_probe.cjs`
  - `wiii-desktop/tmp_probe.js`
- Cleaned a leftover legacy callsite in `visual_intent_resolver.py` after simplifying `required_visual_tool_names()`.

## Important Behavior
- Inline visuals and inline Code Studio apps can now carry a handoff prompt that asks Wiii to create a true artifact on the next turn.
- True artifact lane payloads explicitly disable that handoff.
- Structured template fallback still exists as a safety path; it was not deleted in this slice.

## Verification
- `python -m pytest maritime-ai-service/tests/unit/test_visual_tools.py -q` -> `85 passed`
- `python -m pytest maritime-ai-service/tests/unit/test_visual_intent_resolver.py -q` -> `24 passed`
- `python -m pytest maritime-ai-service/tests/unit/test_graph_routing.py -q` -> `32 passed`
- `npm run build:web` -> pass

## Follow-up
- Frontend still needs an explicit UI affordance if we want users to click “Artifact” directly from inline visuals.
- That UI should send a new prompt using `artifact_handoff_prompt`, not mutate the current visual in place.
