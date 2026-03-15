# Claude Kimi HTML UX Analysis

Date: 2026-03-15
Analyst: Codex (LEADER)

## Sources

- `C:\Users\Admin\Downloads\Kimi linear attention visualization - Claude.html`
- `C:\Users\Admin\Downloads\Kimi linear attention visualization - Claude_files\`

## Executive Summary

Claude's Kimi response is not a single "better chart". It is a layered response system:

1. A serif-first article shell for prose.
2. Thin inline thinking intervals that stay in the reading column.
3. Multiple small interactive figures, each scoped to one teaching claim.
4. A host-controlled design system that styles the figures for the model.
5. Lightweight iframe embedding that feels like a figure, not a widget.

Wiii currently has the right primitives for streaming, inline reasoning, and structured visuals, but still behaves more like `tool-first/widget-first` than `article-first/figure-first`.

## What The Saved HTML Proves

### 1. Claude splits article shell and figure runtime

The top-level page sets:

- `--font-user-message: var(--font-sans-serif)`
- `--font-claude-response: var(--font-serif)`

This confirms a deliberate typography split: user message sans, assistant prose serif.

The page also allows frame sources such as:

- `https://www.claudeusercontent.com`
- `https://www.claudemcpclient.com`
- `*.claudemcpcontent.com`
- `*.livepreview.claude.ai`

So Claude is architected for embedded app/figure runtimes.

### 2. Thinking is inline interval UI, not a big reasoning card

In the response HTML, status rows appear as compact blocks like:

- `Researching Kimi's linear attention mechanism details`
- `Orchestrated visual explanation of Kimi linear attention`

Each one is rendered as:

- a compact label row
- a small chevron
- an `aria-live` status span
- a collapsed details region

The key point is that these intervals live inside the same prose column, immediately before the prose they introduce.

### 3. Claude interleaves prose and figures in a strict pedagogy sequence

The response structure is:

1. short thinking interval
2. short prose bridge
3. figure 1
4. short explanatory prose
5. heading
6. bridge prose
7. figure 2
8. prose insight
9. figure 3
10. prose conclusion

This sequence repeats. Claude does not dump one oversized interactive block and then explain around it.

### 4. Figures are embedded as transparent iframes

The main HTML injects many inline MCP app containers such as:

- `mcp_apps.html`
- `mcp_apps(1).html`
- `mcp_apps(4).html`
- `mcp_apps(5).html`
- `mcp_apps(7).html`
- `mcp_apps(8).html`
- `mcp_apps(9).html`

Each iframe is:

- `sandbox="allow-scripts allow-same-origin allow-forms"`
- `border: none`
- `background-color: transparent`
- individually height-sized (`364px`, `539px`, `324px`, etc.)

This is important: Claude is not afraid to use iframe/app runtime inline. The trick is that the iframe is visually absorbed into the article shell.

### 5. Claude uses many small figures, not one giant visual artifact

The saved figures map cleanly to claims:

- compute cost chart
- stepper for vanilla -> GDN -> KDA
- ratio/perplexity chart
- architecture stack
- throughput/memory chart
- benchmark chart
- RL convergence chart

This is one of the strongest UX differences vs Wiii.

### 6. The figure runtime has a built-in host design system

Inside `saved_resource(1).html`, the iframe provides host tokens and default element styling:

- serif and sans font tokens
- semantic color tokens
- border radius tokens
- shadow tokens
- automatic styling for bare `button`, `input`, `textarea`, `range`

Examples from the HTML:

- bare buttons automatically get border, radius, hover, active states
- range sliders are styled centrally
- headings are auto-colored
- SVG utility classes (`.th`, `.ts`, `.arr`, color groups) are predeclared

This means the model is not hand-crafting every visual system detail from scratch. Claude gives the model a strong figure shell and primitive set.

### 7. Figure chrome is minimal and mostly hover-only

Inside the figure runtime:

- `#vis-container` is width 100%, relative, overflow hidden
- hover-only action buttons appear in the top-right
- popover is lightweight
- main content itself is transparent and unframed

This matters a lot. Claude's inline figures do have tool affordances, but they are not visually dominant.

### 8. Stepper interaction is local, simple, and pedagogical

The stepper figure uses simple local buttons:

- `Step 1`
- `Step 2`
- `Step 3`

The logic is tiny:

- toggle `.panel.active`
- toggle `.step-btn.active`

The real sophistication is not the JS. It is the teaching structure:

- one local interaction
- one conceptual ladder
- one visual scene per step

### 9. Claude writes the prose to hand off into the figure

Examples from the response:

- `Let me break it down visually.`
- `Let me show you how Kimi Linear solves this step by step.`
- `Here's the evolution:`

This handoff matters. The prose prepares the reader for the figure.

### 10. Claude keeps each figure semantically narrow

The stepper figure only teaches one concept evolution.
The line chart only proves a scaling claim.
The ratio chart only argues why 3:1 is the sweet spot.

The figures are not overloaded.

## Wiii vs Claude: Concrete Gaps

### Gap A: Wiii is still too widget-first

Wiii currently inserts a visual block that still reads as an object with its own shell, instead of a figure in the article.

Main places involved:

- `wiii-desktop/src/components/chat/VisualBlock.tsx`
- `wiii-desktop/src/components/chat/visual-primitives.tsx`
- `wiii-desktop/src/styles/globals.css`

### Gap B: Wiii often tries to explain too much with one figure

Claude uses multiple small figures.
Wiii often tries to carry several teaching claims in one block.

### Gap C: Wiii thinking is improved, but still more "UI component" than "article interval"

The current `ReasoningInterval` is much better than the old box, but it still has more explicit UI metadata than Claude's very thin interval rhythm.

Main places:

- `wiii-desktop/src/components/chat/ReasoningInterval.tsx`
- `wiii-desktop/src/components/chat/InterleavedBlockSequence.tsx`
- `wiii-desktop/src/styles/globals.css`

### Gap D: Wiii does not yet have a figure-shell design system as strong as Claude's host runtime

Claude's saved figure runtime proves they provide:

- default button styles
- default form styles
- color primitive classes
- SVG helpers
- figure action chrome
- script-loading state

Wiii has partial equivalents, but not yet a unified inline figure shell that all inline HTML/app figures inherit from automatically.

### Gap E: Wiii prose-to-figure handoff is not yet disciplined enough

Claude's prose introduces each figure with intent.
Wiii still sometimes shows the figure as a visually separate event.

## Architectural Conclusion

Claude's system is best described as:

- `article shell`
- `thinking interval lane`
- `inline figure runtime`
- `host-owned figure design system`
- `many small claim-specific figures`

This is not "just use React" or "just use HTML".
It is an orchestration problem.

## Recommended Direction For Wiii

### 1. Treat inline visuals as figures, not cards

Inline explanatory visuals should become article-width figures with:

- no heavy outer card
- low chrome
- transparent figure surface where possible
- caption and takeaway tied to prose

### 2. Introduce a host-owned figure shell

Wiii should provide a reusable shell for inline HTML/app visuals with:

- default button styles
- default range/input styles
- semantic color tokens
- SVG helper classes
- hover-only action controls
- transparent background by default

### 3. Move from one-big-visual to many-small-figures

For explanatory requests, the model/tooling should prefer:

- figure 1: define the problem
- figure 2: show the mechanism
- figure 3: show the tradeoff or result

instead of one block doing everything.

### 4. Thin the visible reasoning lane further

Wiii should keep the new inline reasoning intervals, but reduce visible chrome and make them read more like narrative timestamps than mini components.

### 5. Add local pedagogical interactions

The highest-value interactive pattern to copy from Claude is not a large app.
It is local figure interactions:

- step tabs
- local toggles
- comparison switches
- narrow scoped reveals

### 6. Keep app/runtime for deep interaction, but not for every explanation

Simulation tools like pendulum should still use app/runtime.
But explanatory visuals should look like article figures, not embedded tools.

## Suggested Next Build Phase

1. Build `FigureShell` for inline HTML/app visuals.
2. Refactor `VisualBlock` to render `editorial figure` by default.
3. Add `multi-figure response orchestration` to structured visuals.
4. Thin `ReasoningInterval` further to Claude-like interval rhythm.
5. Add first-class `stepper`, `comparison chart`, and `claim figure` templates.

## Bottom Line

Claude wins here because it combines:

- better article rhythm
- better figure granularity
- better host-owned visual shell
- thinner public reasoning intervals

Wiii already has enough streaming and runtime infrastructure to move in this direction. The next gains are mostly orchestration, figure shell design, and multi-figure pedagogy.
