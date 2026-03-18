# Wiii Visual System Shift — LLM-First Architecture

**Date:** 2026-03-18  
**Author:** Codex (LEADER)  
**Status:** Research + migration recommendation  

---

## 1. Executive Summary

Wiii should move to **LLM-first visual generation** for the primary render path:

- `article_figure` -> model generates inline SVG/HTML directly
- `chart_runtime` -> model generates SVG/Canvas/HTML directly
- `simulation` -> model generates Canvas/HTML/JS directly
- `artifact` -> model generates persistent HTML/JS artifacts directly

But "LLM-first" must be understood the way leading systems actually implement it in March 2026:

- **LLM-first at planning and code generation**
- **Host-governed at runtime, sandbox, theming, bridge, lifecycle, and safety**

Wiii should **not** keep a template library as the main render engine for visuals.  
Wiii **should** keep the sandboxed renderer layer, message bridge, theming injection, lifecycle rules, and quality gates.

---

## 2. Audit Of Current Wiii Renderer Infrastructure

### Current strengths

Wiii already has a strong renderer foundation that should be preserved:

- [InlineVisualFrame.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/common/InlineVisualFrame.tsx)
  - sandboxed iframe rendering
  - CSP injection
  - storage shim for sandboxed frames
  - postMessage bridge
  - ResizeObserver-based auto height sync
  - `reportResult(...)`, telemetry, focus/control hooks
- [EmbeddedAppFrame.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/common/EmbeddedAppFrame.tsx)
  - app-mode wrapper over the same host-owned sandbox
- [VisualBlock.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/chat/VisualBlock.tsx)
  - current split between `template`, `inline_html`, and `app`

### Current weakness

The current system is still **hybrid**:

- `template` visuals are host-rendered structured figures
- `inline_html` and `app` are model-generated
- `article_figure` and `chart_runtime` are still biased toward structured template rendering

This is the main place where Wiii diverges from the direction the user wants.

### P0 conclusion

The **renderer infrastructure is already mostly correct**.  
What needs to change is **what the backend asks that renderer to render**.

Practical translation:

- keep the iframe sandbox
- keep resize + bridge
- keep host shell injection
- stop treating templates as the primary visual runtime

---

## 3. What OpenGenerativeUI Actually Does

Source audited from:

- `README.md`
- `apps/agent/main.py`
- `apps/agent/skills/master-agent-playbook.txt`
- `apps/agent/skills/svg-diagram-skill.txt`
- `apps/app/src/hooks/use-generative-ui-examples.tsx`
- `apps/app/src/components/generative-ui/widget-renderer.tsx`

### Core findings

OpenGenerativeUI is **LLM-first**, but not "unbounded freestyle."

It uses:

1. **A generic LLM-driven component**
   - `widgetRenderer(title, description, html)`
   - This is the open-ended lane for HTML/SVG visuals

2. **A registered frontend contract**
   - `useComponent({ name: "widgetRenderer", parameters: WidgetRendererProps, render: WidgetRenderer })`
   - So the host still owns the component boundary and parameter schema

3. **A strong system prompt + skill pack**
   - the agent prompt explicitly says:
     - use `widgetRenderer` for visual explanations
     - HTML must be self-contained
     - theme via host CSS variables
     - use host-provided SVG classes and UI primitives
   - quality is driven by instructions, not template selection

4. **A sandboxed iframe runtime**
   - theme CSS injection
   - SVG utility classes
   - bridge helpers like `sendPrompt` and `openLink`
   - ResizeObserver postMessage auto-resize
   - iframe reload only when HTML changes

### Output schema

OpenGenerativeUI’s open-ended visual schema is intentionally simple:

```ts
{
  title: string;
  description: string;
  html: string;
}
```

### Error handling

OpenGenerativeUI has **light runtime handling**, not a deep repair pipeline:

- Zod parameter contract on the frontend component
- iframe `srcdoc` only updates when HTML changes
- auto-resize via postMessage
- loading placeholder and force-show fallback after timeout

It **does not** appear to implement a full compile/critic/repair loop for generated HTML before render.

### Key implication for Wiii

OpenGenerativeUI proves this:

- **drop templates as the primary output path** -> yes
- **drop host contracts, schema, iframe sandbox, and skill guidance** -> no

Wiii should copy the **LLM-first generation model**, but keep a stronger runtime contract than OpenGenerativeUI because Wiii is educational and production-connected to LMS/user memory.

---

## 4. External SOTA Direction (March 2026)

### Anthropic / Claude

Claude now creates **custom charts, diagrams, and interactive visuals inline** and distinguishes them from longer-lived artifacts.  
The important pattern is:

- inline visuals are conversational and ephemeral
- artifacts are longer-lived and treated differently

This strongly supports Wiii splitting:

- `visual` = inline, ephemeral, explanatory
- `artifact` = persistent, panel-based, shareable

### OpenAI Apps

OpenAI’s Apps direction also reinforces:

- host-owned app surfaces
- app contracts
- runtime separation between conversational output and richer tool UI

### SOTA takeaway

The leading pattern is **not**:

- template library selecting prebuilt visual blocks

The leading pattern **is**:

- model decides the medium
- model generates the payload
- host owns runtime contract and lifecycle

---

## 5. Recommended Wiii Architecture

### P0 — Renderer Infrastructure (keep)

Keep and standardize the current Wiii renderer layer as the permanent base:

- sandboxed iframe renderer
- CSP
- host theme injection
- bridge APIs
- resize sync
- result reporting

Recommendation:

- treat [InlineVisualFrame.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/common/InlineVisualFrame.tsx) as the canonical `SandboxedVisual`
- optionally rename later, but no urgent refactor needed

### P1 — LLM-First Code Generation

Replace template-first backend behavior with an LLM-first render contract.

#### New default rule

- `article_figure` -> generate inline SVG/HTML directly
- `chart_runtime` -> generate SVG/Canvas/HTML directly
- `simulation` -> generate Canvas/HTML directly
- `artifact` -> generate persistent HTML directly

#### New output contract

Recommended backend payload:

```json
{
  "title": "string",
  "summary": "string",
  "html": "string",
  "medium": "svg|canvas|html",
  "kind": "visual|artifact",
  "lifecycle": "ephemeral|persistent",
  "shell_variant": "editorial|immersive|artifact",
  "render_intent": "article_figure|chart_runtime|simulation|artifact"
}
```

Important:

- no template spec as primary path
- generated code is the primary render payload
- `html` can contain inline `<svg>` or `<canvas>`

#### Prompting strategy

Wiii should move from:

- "choose template and fill fields"

to:

- "choose the right medium"
- "generate the visual directly"
- "use host CSS variables and bridge helpers"
- "obey inline visual vs artifact lifecycle"

### P2 — Visual vs Artifact Split

This split must become explicit in backend contract and frontend behavior.

#### Visual

- inline in the conversation
- ephemeral
- supports explanation
- should merge into the message flow
- may disappear/recede as conversation moves on

#### Artifact

- persistent
- panel-based or dedicated surface
- versioned / shareable / downloadable
- survives conversation continuation

#### Rendering rule

- same sandbox runtime
- different lifecycle + shell behavior

This maps perfectly to the existing Wiii direction the user wants.

---

## 6. How Wiii Should Improve Beyond OpenGenerativeUI

OpenGenerativeUI is useful reference, but Wiii should go further in four ways:

### 1. Better critic loop

Before render, Wiii should score generated visuals for:

- runtime validity
- accessibility
- responsiveness
- educational clarity
- LMS fit
- bridge/result hook presence when needed

### 2. Better living pedagogy

Wiii should inject style/personality into:

- framing
- claim
- callout tone
- motion choice
- takeaway

not into UI chrome.

### 3. Stronger lifecycle separation

OpenGenerativeUI is mostly “generic generative widget.”

Wiii should be more explicit:

- `visual` vs `artifact`
- `ephemeral` vs `persistent`
- `inline` vs `panel`

### 4. Stronger simulation contract

For simulation, Wiii should require:

- state model
- controls
- readouts
- feedback bridge
- patchable session continuity

This is especially important for maritime simulation and LMS learning loops.

---

## 7. Concrete Migration Plan

### Phase A — Freeze renderer contract

- keep [InlineVisualFrame.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/common/InlineVisualFrame.tsx) as the renderer base
- add/lock Playwright tests for:
  - iframe render
  - resize sync
  - postMessage bridge
  - `reportResult(...)`

### Phase B — Switch article/chart generation to direct code

- stop preferring `template` for `article_figure` and `chart_runtime`
- make backend return generated `html` payload directly
- allow inline SVG as the dominant format for figures/charts

### Phase C — Introduce two explicit output kinds

- `kind=visual`
- `kind=artifact`

with separate lifecycle rules in chat/render/store

### Phase D — Add critic + repair

- first render attempt
- validate quality/runtime constraints
- one repair pass if needed
- only then commit preview

---

## 8. Final Recommendation

Yes, Wiii should shift toward **LLM-first**.

But the correct version is:

- **LLM-first generation**
- **host-governed runtime**
- **explicit visual vs artifact lifecycle**
- **critic pass before commit**

So the user decision should be interpreted as:

> "Bỏ template library as the main visual production path."

not:

> "Bỏ runtime contract, host shell, bridge, or evaluation."

That is the architecture most aligned with both:

- the user’s direction
- OpenGenerativeUI’s actual implementation
- Claude/OpenAI’s 2026 product direction

---

## 9. Source Links

- OpenGenerativeUI repo: https://github.com/CopilotKit/OpenGenerativeUI
- OpenGenerativeUI README: https://github.com/CopilotKit/OpenGenerativeUI/blob/main/README.md
- OpenGenerativeUI agent prompt: https://github.com/CopilotKit/OpenGenerativeUI/blob/main/apps/agent/main.py
- OpenGenerativeUI SVG skill: https://github.com/CopilotKit/OpenGenerativeUI/blob/main/apps/agent/skills/svg-diagram-skill.txt
- OpenGenerativeUI component registration: https://github.com/CopilotKit/OpenGenerativeUI/blob/main/apps/app/src/hooks/use-generative-ui-examples.tsx
- OpenGenerativeUI widget renderer: https://github.com/CopilotKit/OpenGenerativeUI/blob/main/apps/app/src/components/generative-ui/widget-renderer.tsx
- Claude builds visuals: https://claude.com/blog/claude-builds-visuals
- Interactive tools in Claude: https://claude.com/blog/interactive-tools-in-claude
- Apps in ChatGPT: https://openai.com/index/introducing-apps-in-chatgpt/
