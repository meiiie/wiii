# Wiii Article-Figure Host Shell Phase 2

Date: 2026-03-15

## Scope
- Compact `balanced` reasoning so main flow reads like public reasoning intervals, not agent log rows.
- Force host-owned shell for `inline_html` and `app` full-document payloads so exported HTML stops looking like `outer article card + inner legacy widget card`.
- Add backend auto-grouping for explanatory template visuals so article requests can promote from one oversized visual into a figure group at runtime.

## Key Changes
- Frontend reasoning:
  - `ReasoningInterval` now compacts `balanced` mode to public reasoning plus one primary operation row.
  - `InterleavedBlockSequence` dedupes adjacent repeated interval/tool rows.
  - Trace launcher is no longer shown in balanced mode.
- Frontend figure/app shell:
  - `InlineVisualFrame` now supports `hostShellMode="force"` and wraps full-document HTML into a host shell when needed.
  - Added legacy widget shim CSS so old `.widget-*` and `.sim-*` internals lose the double-card effect inside editorial figures.
  - `EmbeddedAppFrame` and inline HTML visuals now opt into forced host shell mode.
- Backend visual orchestration:
  - `graph.py` now passes visual intent metadata into tool runtime context, not just patch metadata.
  - `tool_generate_visual` now auto-groups explanatory template visuals into:
    - primary figure
    - takeaway infographic figure
  - Auto-grouping is disabled for:
    - app runtime
    - patch turns
    - explicit `figures`
    - explicit single-figure opt-out

## Validation
- Backend:
  - `python -m pytest tests/unit/test_visual_tools.py -q`
  - Result: `45 passed`
- Frontend unit:
  - `npm test -- --run src/__tests__/interleaved-block-sequence.test.tsx src/__tests__/structured-visuals.test.tsx src/__tests__/inline-visual-frame.test.ts`
  - Result: `32 passed`
- Web build:
  - `npm run build:web`
  - Result: pass
- Playwright:
  - `npm run test:e2e:visual`
  - Result: `2 passed`

## Notes
- The earlier desktop Playwright failure was not a UX regression; the suite was still asserting old `.editorial-visual-flow__lead/.tail` selectors after the article composer moved to `.editorial-visual-flow__prose--lead/.tail`.
- Current gaps are now higher-level quality work, not correctness blockers:
  - richer multi-figure pedagogy than `primary + takeaway`
  - stronger chart/timeline/map art direction
  - scientific-grade physics templates for simulations like the pendulum
