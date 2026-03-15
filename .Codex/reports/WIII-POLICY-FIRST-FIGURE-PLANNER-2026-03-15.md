# Wiii Policy-First Figure Planner

Date: 2026-03-15

## Summary

- Replaced rigid explanatory auto-grouping with a policy-first figure budget planner.
- Balanced thinking now compacts to a thinner public rhythm instead of exposing every intermediate beat in the main flow.
- Verified that article flow and visual browser acceptance still pass after the change.

## Backend

Updated [visual_tools.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/tools/visual_tools.py):

- Added query-aware figure planning:
  - `_normalize_visual_query_text()`
  - `_estimate_query_figure_pressure()`
  - `_estimate_spec_figure_pressure()`
  - `_plan_auto_group_figure_budget()`
- Auto-grouping now returns `1..3` figures depending on:
  - explanatory template intent
  - query wording
  - spec density
- Added `_build_bridge_infographic_spec()` for the middle figure when the planner selects 3 figures.
- Preserved hard constraints:
  - no auto-group for app lane
  - no auto-group for patch turns
  - no auto-group when `allow_single_figure` or `disable_auto_group` is set

## Frontend

Updated [ReasoningInterval.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/chat/ReasoningInterval.tsx):

- Balanced mode now compacts multiple thinking beats into:
  - one opening or summary beat
  - one latest beat
  - one primary operation row
- Detailed mode remains unchanged.

## Tests

Backend:

- `python -m pytest maritime-ai-service/tests/unit/test_visual_tools.py -q` -> `48 passed`
- `python -m pytest maritime-ai-service/tests/unit/test_visual_intent_resolver.py -q` -> `13 passed`

Frontend:

- `npm test -- --run src/__tests__/interleaved-block-sequence.test.tsx` -> `19 passed`

Web:

- `npm run test:e2e:visual` -> `2 passed`
- `npm run build:web` -> pass

## Notes

- The planner is intentionally constrained, not fully free-form:
  - lane selection remains hard-controlled by the resolver/runtime policy
  - figure count is flexible inside a bounded `1..3` range
- Remaining gap after this phase is still visual quality and host-owned figure runtime depth, not stream correctness.
