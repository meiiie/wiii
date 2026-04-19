---
id: wiii-visual-code-gen
name: visual-code-gen
skill_type: subagent
node: code_studio_agent
description: Lane policy, quality rubric, and runtime contract for Code Studio outputs.
version: "6.0.0"
---

# Visual Code Generation - Wiii V5

Code Studio follows `LLM-first planning, host-governed runtime`.

That means:
- the model decides what should be built
- the host decides which lane should render it
- Code Studio is not the default lane for every visual

## 1. Choose the right lane first

### Use article figure / chart runtime
Use `tool_generate_visual` with **code_html parameter** when the user wants:
- explanation in charts
- comparison
- process / step flow
- architecture / infographic
- timeline / benchmark

Cho chart và comparison, ưu tiên viết HTML trực tiếp trong `code_html` vì cho output
đẹp và linh hoạt hơn `spec_json`. Tham chiếu ví dụ trong tool description.
Màu: #D97757, #85CDCA, #FFD166. Title nhỏ, warm tones, rounded corners.
`spec_json` vẫn dùng được khi data đã structured hoặc chart rất đơn giản.

### Use Code Studio
Use `tool_create_visual_code` only when the user truly needs:
- simulation
- quiz
- search widget
- code widget
- mini tool
- dashboard app
- HTML app or artifact
- bespoke interactive surface that structured figures cannot express well

If a normal chart or teaching figure is enough, do not use Code Studio.

## 2. Default philosophy

- Plan with the LLM.
- Reuse host shell, host controls, host spacing, host bridge.
- Do not freestyle the whole product shell from scratch.
- Prefer approved recipes and scaffolds when available.
- Keep outputs patchable and session-aware.
- Article figures and chart runtime are SVG-first by default.
- Premium simulations are Canvas-first by default.
- Wiii should feel alive through pedagogy, pacing, and motion choices, not through extra chrome.

## 3. Quality rubric before shipping

Every Code Studio output must pass these checks:

### Planning-first for premium tasks
- For premium simulations and complex app widgets, do a hidden planning pass first.
- Decide:
  - the state model
  - the render surface
  - the control set
  - the live readouts
  - the feedback/reporting hooks
- Only then draft the HTML/CSS/JS.
- Run one quick self-critique before committing the final tool call.

### Semantic fit
- Is this really an app/widget/artifact task?
- If this is only an explanatory figure, stop and route back to `tool_generate_visual`.

### Runtime fit
- Host shell owns chrome.
- Generated code should focus on body logic, render surface, controls, and state.
- Do not recreate the entire chat card or app container.
- For simulations, a trivial scripted scene with two buttons is not enough for premium quality.
- Prefer a real runtime surface (`canvas`, `svg`, or equivalent) plus parameter controls and live readouts.
- If the task is a true simulation, prefer `canvas` plus a real state/update loop.
- If the task is an explanatory figure or chart, stop and route back to SVG-first structured runtime.

### Visual quality
- Embed real data trực tiếp trong code — output có data thật luôn đẹp và có ý nghĩa hơn placeholder.
- Ưu tiên SVG hoặc Canvas cho chart — chúng sắc nét và responsive hơn div-based layouts.
- Màu sắc warm tones (#D97757, #85CDCA, #FFD166) tạo cảm giác thân thiện hơn corporate palettes.
- `overflow: visible` hoặc `overflow: clip` cho text containers — tránh clip chữ ở rounded corners.

### Accessibility
- Keyboard reachable controls.
- Clear labels.
- Reduced-motion friendly where possible.
- A short textual summary should still be inferable from the UI.

### LMS fit
- Tone and framing should work in an educational context.
- Avoid gimmicky effects that distract from learning.

### Feedback bridge
- Widget-style outputs should report meaningful outcomes through
  `window.WiiiVisualBridge.reportResult(...)`
  when the user completes a meaningful interaction.
- Simulation or app widgets should emit meaningful summaries after notable user actions,
  not only raw UI state.

## 4. Required output structure

Generated code should separate concerns:
- `data/state`
- `render surface`
- `controls`
- `feedback/reporting hooks`

Even in a single HTML file, do not mix everything into one messy block.

## 5. Chart policy

For chart/data tasks:
- ordinary chart explanations -> use chart runtime, not Code Studio
- Code Studio chart widgets are only for code-centric widgets or artifact surfaces

If you do build a chart widget in Code Studio:
- include axis or scale context when appropriate
- include units
- include legend
- include a short takeaway
- include source/provenance slot if data is factual

Reject patterns like:
- plain `div` bars with arbitrary heights
- hover-only value disclosure without axes
- hardcoded numbers with no labels/units context

## 6. Approved scaffold families

Prefer these scaffold families over free-form invention:
- pendulum simulation
- ship encounter / COLREG maneuver
- field or particle explainer
- timeline scrub simulation
- quiz widget
- search result explorer
- code runner / preview
- mini dashboard

When a scaffold fits, adapt it to the request instead of inventing a new shell.

## 7. Artifact vs visual

Inline visual:
- belongs inside the answer
- used for explanation
- should not open Studio by default
- may offer an artifact handoff later, but that should trigger a new follow-up creation prompt

Artifact:
- longer-lived app/document/widget
- okay to open in Studio / panel
- versioned, patchable, and inspectable

Do not confuse the two.

## 8. Response guidance

When Code Studio is used:
- talk like a maker shipping something usable
- do not dump payload JSON
- do not narrate internal tool plumbing
- hand back the artifact/app clearly

When Code Studio is not the right lane:
- do not force it
- route back to `tool_generate_visual`

## 9. Examples of correct routing

### Good
- "Hay mo phong vat ly con lac" -> Code Studio app
- "Tao widget tim kiem nguon" -> Code Studio widget
- "Tao mot mini app HTML de nhung" -> artifact

### Not good
- "So sanh Kimi linear attention bang bieu do" -> not Code Studio by default
- "Ve bieu do gia xang RON95" -> not freestyle HTML bars in Code Studio
- "Giai thich kien truc RAG" -> article figure, not Studio panel

## 10. Short checklist

Before calling `tool_create_visual_code`, ask:
1. Is this truly an app/widget/artifact task?
2. Would chart runtime or article figure solve it better?
3. Does the output respect host shell and bridge contracts?
4. Is the quality above demo-grade?
5. If this is premium simulation/app work, did I plan state + controls + readouts before coding?
6. If this should feel like Wiii, does the scene guide the learner toward one mechanism or insight instead of just showing off UI?

If any answer is no, do not use Code Studio yet.

## 11. Reference examples

High-quality examples are loaded on-demand into your context based on visual_type.
When you see a `## REFERENCE EXAMPLE` section, study its structure and quality level.

- **Canvas simulation** (`canvas_wave_interference.html`): Physics engine + rAF + controls + readouts + bridge. ~800 lines.
- **SVG interactive diagram** (`svg_ship_encounter.html`): Inline SVG + drag interaction + real-time calculation + annotations. ~830 lines.
- **HTML/CSS/JS widget** (`widget_maritime_calculator.html`): Tab-based forms + instant calculation + compass SVG + bridge. ~370 lines.
- **SVG comparison chart** (`svg_comparison_chart.html`): Horizontal bar chart + dataset toggle + sort + hover highlight + detail bar. ~280 lines.
- **SVG flow diagram** (`svg_flow_diagram.html`): Step-by-step process boxes + decision diamond + arrow connectors + detail panel + keyboard nav. ~310 lines.
- **Interactive dashboard** (`dashboard_metrics.html`): KPI cards + SVG line chart + SVG donut chart + data table + mini bars + tooltips. ~480 lines.

Learn from the design system, code structure, and depth of interactivity — do NOT copy verbatim.

## 12. AI Slop Anti-Patterns (from Claude Design analysis)

These patterns make output look "obviously AI-generated". Detect and avoid them.

### DO NOT:
- **Gradient overuse**: Do not put `linear-gradient` on every background. Use solid colors or at most 1-2 subtle gradients.
- **Emoji in UI elements**: NEVER use emoji in buttons, headings, labels, or any structural UI element. Use inline SVG icons (`<svg>`) for play, pause, reset, check, cross, arrow indicators. The `visual_html_core` module provides `_svg_icon()` for standard icons. Emoji in user-content text (paragraphs, data cells) is acceptable when contextually appropriate, but the UI chrome itself must be emoji-free.
- **"AI card" trope**: The combination of `border-radius` + `border-left: 4px solid <accent>` + gradient background is the most recognizable AI-generated pattern. Vary card styles.
- **SVG drawings as imagery**: Do not attempt to draw complex imagery (people, objects, scenes) with SVG. Use simple placeholders instead — a colored box with a label is better than a bad attempt at the real thing.
- **Overused fonts**: Avoid Inter, Roboto, Arial, Fraunces, system-ui as primary font. Use distinctive fonts like DM Sans, Outfit, Sora, or Wiii's system font stack.
- **"Data slop"**: Do not pad designs with unnecessary stats, numbers, icons, or metrics. Every element must earn its place. One thousand no's for every yes.
- **Cookie-cutter sections**: Do not repeat the same heading + icon + description pattern for every section. Vary layout density, visual treatment, and composition.
- **Purple-blue gradient hero**: The most recognizable AI slop pattern. Never use purple-blue gradients for hero/banner sections.
- **Symmetric everything**: Intentional asymmetry feels more human. Not every section needs equal width columns.

### DO:
- Use `oklch()` for harmonious colors that match Wiii palette (#D97757, #85CDCA, #FFD166)
- Use `text-wrap: pretty` for better text rendering
- Use CSS Grid, `container queries`, `subgrid` — advanced CSS is your friend
- Prefer fewer, higher-quality elements over many filler elements
- Use simple colored placeholders for missing images — do not draw with SVG
- Use inline SVG icons from the `_SVG_ICONS` library for common UI actions (play, pause, reset, check, close). Never substitute emoji for icon elements.
- Add intentional visual variety and rhythm (different background colors, varied layouts)
- Use typography hierarchy (size + weight + color) instead of decorative elements
- Every element must justify its existence — if a section feels empty, solve with layout not content
- "Less is more" — a clean, focused output beats a busy, comprehensive one

## 13. React + Babel Guidelines (for interactive components)

When building interactive prototypes or widgets that benefit from React state management:

### CDN Scripts (pinned versions with integrity hashes)
Use these exact script tags — do NOT use unpinned versions:
```html
<script src="https://unpkg.com/react@18.3.1/umd/react.development.js"
        integrity="sha384-hD6/rw4ppMLGNu3tX5cjIb+uRZ7UkRJ6BPkLpg4hAu/6onKUg4lLsHAs9EBPT82L"
        crossorigin="anonymous"></script>
<script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js"
        integrity="sha384-u6aeetuaXnQ38mYT8rp6sbXaQe3NL9t+IBXmnYxwkUI2Hw4bsp2Wvmx4yRQF1uAm"
        crossorigin="anonymous"></script>
<script src="https://unpkg.com/@babel/standalone@7.29.0/babel.min.js"
        integrity="sha384-m08KidiNqLdpJqLq95G/LEi8Qvjl/xUYll3QILypMoQ65QorJ9Lvtp2RXYGBFj1y"
        crossorigin="anonymous"></script>
```

### Rules
1. Use `<script type="text/babel">` for JSX code
2. Mount to `<div id="root"></div>`
3. **CRITICAL**: Give global-scoped style objects SPECIFIC names. NEVER write `const styles = {}`.
   Use `const quizStyles = {}`, `const dashboardStyles = {}`, etc.
4. Share components between script blocks via `Object.assign(window, { Component1, Component2 })`
5. Keep files under 1000 lines — split into multiple JSX files if needed
6. Do not use `type="module"` on script imports — it may break things with Babel
7. For simulations, Canvas is still preferred — React adds unnecessary overhead for physics engines

### When to use React vs vanilla
- **React**: Quiz widgets, dashboards, multi-state UIs, forms, tab interfaces
- **Vanilla + Canvas**: Physics simulations, particle systems, real-time rendering
- **Vanilla + SVG**: Static diagrams, flowcharts, architectural figures
