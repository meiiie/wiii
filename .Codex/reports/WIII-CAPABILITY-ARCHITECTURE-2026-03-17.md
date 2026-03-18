# Wiii Capability Architecture Review

**Date:** 2026-03-17  
**Author:** Codex LEADER  
**Goal:** Improve Wiii's actual visual/app generation capability, not keep tweaking chat chrome

---

## Executive decision

Wiii should **stop spending cycles on UI chrome changes** for now and focus on **generation architecture quality**.

The core problem is not that Wiii lacks a sandbox or a panel.

The core problem is:

- wrong lane chosen too often
- a weak final generator is being trusted too much
- too little domain/runtime structure is given to the model
- not enough recipe/eval/critic loops exist before publishing output

In short:

**Wiii currently overuses open-ended codegen where a stronger runtime contract should exist.**

---

## What leading organizations are doing

### Anthropic / Claude

Official sources show Claude's strongest visual/app outputs are **not raw freestyle alone**.

They combine:

- rich design briefs
- concrete source assets
- known implementation constraints
- extended reasoning for complex apps
- artifact or inline visual surfaces chosen for the right task

Key evidence:

- [Claude builds visuals](https://claude.com/blog/claude-builds-visuals)
- [Build interactive diagram tools](https://claude.com/resources/use-cases/build-interactive-diagram-tools)

Important pattern:

- For complex learning tools, Anthropic explicitly recommends **providing assets, exact constraints, and a design brief**
- They also recommend **Extended Thinking** for complex multi-component apps
- Their example says *do not generate diagrams yourself* when trustworthy domain SVG assets already exist

This is not "pure freestyle". It is **LLM-led composition on top of strong structure**.

### OpenAI

OpenAI's Apps direction also reinforces the same pattern:

- apps appear naturally in conversation
- interfaces and logic are both supported
- but they are built on a standard app/tool contract, not arbitrary HTML dumps

Official sources:

- [Introducing apps in ChatGPT](https://openai.com/index/introducing-apps-in-chatgpt/)
- [Build with the Apps SDK](https://help.openai.com/pt-pt/articles/12515353-build-with-the-apps-sdk)

Key lines:

- apps fit naturally into conversation
- the Apps SDK extends MCP so developers can design both logic and interface
- apps that meet higher design and functionality standards may be featured more prominently

Again: **host contract + quality bar**, not unlimited freestyle.

### MCP Apps / WebMCP

The MCP ecosystem is converging on the same architecture:

- tools declare UI resources
- hosts render them in sandboxed iframes
- bidirectional messaging is logged and auditable
- hosts can review templates/resources before rendering

Official sources:

- [MCP Apps](https://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/)
- [WebMCP draft](https://webmachinelearning.github.io/webmcp/)

This strongly supports Wiii's existing direction:

- host-owned shell
- tool/app/widget bridge
- semantic result reporting
- auditable feedback back into the assistant

### Vercel / v0

v0 is also not simply "LLM writes raw HTML and hope for the best."

Official docs position it as:

- end-to-end development
- real-time preview
- rich visual feedback
- works with a modern stack
- extensible with your APIs and components

Source:

- [v0 docs](https://v0.app/docs)

That means even the strongest UI-first products still rely on:

- an opinionated stack
- a preview loop
- reusable components
- runtime scaffolding

---

## What this means for Wiii

Wiii is **not** primarily a general UI builder.

Wiii is trying to excel at:

- explanatory visuals
- charts
- maritime or LMS-specific simulations
- tool widgets
- mini apps that teach or explore
- later: motion/video explainers

That means Wiii should optimize for:

- **educational correctness**
- **interactive reasoning**
- **patchable follow-up editing**
- **host context + LMS context**
- **feedback loop into the assistant**

and **not** for generic one-shot UI screen generation.

---

## Diagnosis of the current Wiii failure mode

The example code the user showed is weak because the system still allows too much of this pattern:

- low-context prompt
- weak or mid-tier model
- free-form HTML/CSS/JS
- no strong domain recipe
- no critic gate
- immediate render

That produces:

- simplistic DOM/CSS widgets
- shallow animation
- no formal simulation model
- weak educational fidelity
- weak reuse across turns

The current result is often:

- "it runs"
- but it does not feel flagship

---

## Strategic architecture for Wiii

### 1. Freeze cosmetic UI work unless it supports capability

Do not spend the next sprint changing chat chrome again.

Only touch UI when it improves:

- lane clarity
- preview quality
- feedback surfaces
- versioning
- diagnostics

### 2. Keep the 4-lane split

Wiii should continue with these lanes:

- `article_figure`
- `chart_runtime`
- `code_studio_app`
- `artifact`

But the key now is to make each lane **actually specialized**.

### 3. Article figure lane

Use for:

- mechanism explanation
- comparisons
- architectures
- timelines
- process diagrams

This lane should remain:

- inline
- article-first
- lightweight
- not studio-first

This lane should **not** try to solve simulation-heavy tasks.

### 4. Chart runtime lane

This lane is where Wiii needs a real upgrade.

It should own:

- bar/line/benchmark/trend charts
- ratios/perplexity charts
- comparisons
- structured annotations
- provenance/takeaway/accessibility

This lane should prevent junk like:

- `div` bars with arbitrary heights
- no axes
- no units
- no source slot

### 5. Code Studio app lane

This lane should become:

- simulation runtime
- search widget runtime
- code widget runtime
- quiz/tool runtime

Not:

- a fallback for every chart or figure

Code Studio should be reserved for cases where the user genuinely needs:

- state
- controls
- iterative patching
- app logic
- meaningful interaction

### 6. Artifact lane

This is where tools like Stitch may become useful later.

Use artifact lane for:

- long-lived HTML apps
- downloadable prototypes
- UI shells
- reusable outputs

Do not confuse artifact lane with inline teaching visual lane.

---

## The most important capability upgrades

### A. Domain recipes

Wiii needs **recipe families**, not just prompts.

Examples:

- COLREG rule crossing/overtaking/head-on simulation recipes
- pendulum and classical mechanics recipes
- search result explorer recipe
- teacher dashboard recipe
- benchmark chart recipe
- timeline explainer recipe

The model should adapt recipes, not invent from blank space each time.

### B. Domain assets and trusted primitives

For strong outputs, the model needs trusted starting points:

- SVG ship silhouettes
- nautical coordinate overlays
- maritime color system
- standard motion primitives
- chart grammars
- LMS component shells

Anthropic's best examples also rely on trustworthy source assets instead of inventing everything from scratch.

### C. Model tiering

Do not use a light model as the final generator for premium simulation/app code.

Recommended split:

- light: summaries, tiny patches, low-risk text transforms
- moderate: ordinary figures, chart spec generation, small code patches
- deep/premium: simulation architecture, repair pass, critic pass, high-value app generation

### D. Critic loop

Before publishing a Code Studio result, run a critic pass with a rubric:

- semantic fit
- domain correctness
- interaction quality
- accessibility
- host shell fit
- feedback bridge fit
- LMS fit

If it fails:

- repair once
- or reroute to a better lane

### E. Structured feedback contract

Wiii already started this with widget feedback.

Now it should be universal for:

- simulation
- quiz
- code widget
- search widget

Every meaningful interaction should emit semantic result summaries.

### F. Motion/video should be a separate lane later

Do not force "video motion" into current Code Studio HTML lane.

Later Wiii likely needs a distinct motion pipeline:

- storyboard spec
- timeline spec
- scene transitions
- render backend

This is adjacent to, but not the same as, app runtime.

---

## What Wiii should not do next

- do not keep redesigning the chat shell
- do not broaden Code Studio again into the default for everything
- do not trust low-end model output as a final premium result
- do not benchmark success only by "something rendered"
- do not mix article figures and artifact apps again

---

## What Wiii should do next

### Priority 1

Professionalize `chart_runtime`

### Priority 2

Professionalize `code_studio_app` for simulation/widget lanes with:

- recipe scaffolds
- better model routing
- critic loop
- result contract

### Priority 3

Create skill packs for code agents:

- `wiii-simulation-recipes`
- `wiii-maritime-simulation`
- `wiii-chart-runtime`
- `wiii-code-studio-critic`
- `wiii-motion-storyboard` later

### Priority 4

Build a benchmark set and score outputs against it

---

## Final decision

Wiii should **not** chase generic UI generation as its center of gravity.

Its advantage should come from:

- domain-rich interactive teaching tools
- trustworthy runtime contracts
- assistant-visible widget outcomes
- strong patchability over conversation
- specialist skills and recipes

That is a stronger long-term position than trying to imitate generic screen generators.

In one sentence:

**Wiii should become a high-quality educational visual/runtime system, not a general-purpose screen mockup machine.**
