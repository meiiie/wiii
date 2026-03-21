---
id: wiii-visual-code-gen
name: visual-code-gen
skill_type: subagent
node: code_studio_agent
description: Lane policy, quality rubric, and runtime contract for Code Studio outputs.
version: "5.0.0"
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
- No placeholder UI. No "No data provided" fallbacks — ALWAYS embed real data directly in the code.
- No generic "AI slop" card stacks.
- No purple-for-the-sake-of-purple.
- No low-effort `div bar chart` for real chart requests.
- If building a chart-like widget, use `SVG`, `Canvas`, or a chart library such as `Chart.js`.
- Never use `overflow: hidden` with `border-radius` on text containers — text at corners will be clipped. Use `overflow: clip` or `overflow: visible` instead.

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
