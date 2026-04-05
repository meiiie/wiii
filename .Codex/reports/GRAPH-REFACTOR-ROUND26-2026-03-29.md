# Graph Refactor Round 26

Date: 2026-03-29

## Scope

Round 26 focused on the structured visual builder layer, specifically:

- `app/engine/tools/visual_html_builders.py`

This file had become a mixed bundle of:

- shared HTML/core helpers
- comparison/process/matrix/architecture/concept/infographic builders
- chart normalization + chart rendering
- dispatcher wiring

The goal was to split it into clearer modules without changing the public
surface that `visual_tools.py` and tests already depend on.

## Changes

### 1. Extracted visual HTML core helpers

Created:

- `app/engine/tools/visual_html_core.py`

Moved:

- `_DESIGN_CSS`
- `_esc`
- `_wrap_html`

Why:

- These are cross-cutting helpers used by multiple visual builder families.
- They should not live inside a catch-all builder file.

### 2. Extracted non-chart layout builders

Created:

- `app/engine/tools/visual_html_layout_builders.py`

Moved:

- `_build_comparison_html_impl`
- `_build_process_html`
- `_build_matrix_html`
- `_build_architecture_html`
- `_build_concept_html`
- `_build_infographic_html`
- `_build_timeline_html`
- `_build_map_lite_html`

Why:

- These are pure HTML builders with no tool/runtime policy logic.
- Grouping them together makes the builder family easier to navigate and extend.

### 3. Extracted chart normalization/rendering

Created:

- `app/engine/tools/visual_chart_builders.py`

Moved:

- `_normalize_chart_spec`
- `_build_chart_html_impl`

Why:

- Chart shaping/normalization is a distinct concern from layout builders.
- This file is now the single owner of chart payload coercion and SVG rendering.

### 4. Rebuilt `visual_html_builders.py` as a compatibility shell

Replaced:

- `app/engine/tools/visual_html_builders.py`

New shell responsibilities:

- re-export shared builder names used by `visual_tools.py`
- keep wrapper compatibility for:
  - `_build_comparison_html`
  - `_build_chart_html`
- preserve `_BUILDERS` dispatcher map

Compatibility strategy:

- `_build_comparison_html(...)`
  - keeps the legacy “row-data chart payload” fallback
- `_build_chart_html(...)`
  - keeps the legacy “left/right comparison payload” fallback

This avoids circular imports while keeping the old public API stable.

## Line-count impact

- `app/engine/tools/visual_html_builders.py`: `833 -> 60`
- `app/engine/tools/visual_html_core.py`: `88`
- `app/engine/tools/visual_html_layout_builders.py`: `559`
- `app/engine/tools/visual_chart_builders.py`: `245`

Net effect:

- the god-file-ish builder shell is now a thin compatibility layer
- concrete builder logic is grouped by responsibility

## Verification

### Compile

Passed:

- `python -m py_compile app/engine/tools/visual_html_core.py`
- `python -m py_compile app/engine/tools/visual_html_layout_builders.py`
- `python -m py_compile app/engine/tools/visual_chart_builders.py`
- `python -m py_compile app/engine/tools/visual_html_builders.py`
- `python -m py_compile app/engine/tools/visual_tools.py`

### Builder-focused tests

Passed:

- `tests/unit/test_visual_tools.py -k "ComparisonVisual or ProcessVisual or MatrixVisual or ArchitectureVisual or ConceptVisual or InfographicVisual or ChartVisual or TimelineVisual or MapLiteVisual or EnhancedBuilderFields or DesignSystem"`
- Result: `26 passed`

This is the most relevant batch for the extracted HTML builders themselves.

### Broader visual-tools integration

Observed failures in the full `tests/unit/test_visual_tools.py` run:

- `tool_generate_visual` expectations around:
  - `renderer_kind == "template"`
  - `patch_strategy == "spec_merge"`
  - auto-grouping count
- current runtime instead returns `inline_html` / `replace_html` /
  single-payload behavior in several cases

Interpretation:

- these failures point to current visual runtime policy / payload planning drift
  in `visual_tools.py`
- they are not directly tied to the extracted pure builder modules
- the builder-level tests above stayed green, which is the correct regression
  boundary for this refactor

## Sentrux

Latest gate after Round 26:

- `Quality: 4422`
- `Coupling: 0.30`
- `Cycles: 8`
- `God files: 3`
- `Distance from Main Sequence: 0.31`
- Verdict: `No degradation detected`

The headline metrics did not move in this round, but the local architecture is
meaningfully cleaner:

- shared HTML helpers have one home
- chart logic has one home
- layout builders have one home
- the compatibility shell is now small and easy to reason about

## Why this matters for future work

Even though this round does not touch `thinking`, it helps the project in a
real way:

- visual runtime behavior can now be debugged separately from raw HTML builder
  behavior
- future changes to chart or comparison rendering will touch a smaller file
- visual shell routing is now easier to inspect without scanning hundreds of
  lines of pure HTML builder code

## Recommended next cuts

Most promising next refactor seams after this round:

1. `app/engine/tools/visual_tools.py`
   - separate runtime policy/planning from payload construction
2. `app/core/config/_settings.py`
   - large blast radius, but still the biggest remaining shell
3. `app/engine/search_platforms/adapters/browser_base.py`
   - only with strict wrapper preservation for `_get_browser` and
     `_submit_to_pw_worker`
4. `app/services/chat_orchestrator.py`
   - smaller payoff, but good shell/service cleanup candidate

## Conclusion

Round 26 was successful.

`visual_html_builders.py` is no longer acting like a catch-all bucket for every
kind of structured visual HTML concern. The visual builder stack is now split
into:

- core helpers
- layout builders
- chart builders
- a thin compatibility shell

That is a real clean-architecture improvement, and it gives the visual runtime
layer a much better foundation for future fixes.
