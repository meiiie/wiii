# Wiii SVG + Canvas Focus Memo
**Date:** 2026-03-17  
**Status:** Strategic recommendation

## Conclusion
Wiii should focus deeply on **two first-class visual runtimes**:

1. **SVG Motion Explainer**
2. **Canvas Simulation**

This matches both:
- what Wiii is trying to become: an AI that explains, visualizes, and simulates for learning
- how leading platforms are evolving in 2025-2026: inline visuals for explanation, interactive app surfaces for richer manipulation, and strong host-owned runtime contracts

## Why this is the right direction

### 1. Anthropic is moving toward inline explanatory visuals
Anthropic states on **March 12, 2026** that Claude can create **custom charts, diagrams, and other visualizations inline** and then **tweak and modify them as the conversation develops**.

They also explicitly distinguish these visuals from artifacts:
- artifacts are more permanent and shareable
- inline visuals are temporary and exist to **aid understanding during the conversation**

This aligns extremely well with Wiii's intended `article_figure` lane.

### 2. Anthropic also recommends deeper planning for complex interactive tools
In Anthropic's use case **Build interactive diagram tools**, they advise:
- treating the prompt like a **design brief**
- specifying **interaction model**, **data/source constraints**, and **aesthetic standards**
- turning on **Extended Thinking** for complex multi-component apps so Claude can **plan architecture before building**

This strongly supports a Wiii policy of:
- raising reasoning depth for premium simulation / motion / multi-part codegen
- not letting high-quality simulation code return instantly with shallow planning

### 3. OpenAI and MCP Apps point to host-owned interactive surfaces
OpenAI's Apps SDK says developers should define both the **logic and interface** of an app inside ChatGPT, and that the SDK extends **MCP** so apps can run anywhere that adopts the standard.

The MCP Apps announcement adds the important architectural piece:
- the model stays in the loop
- the UI handles **live updates, persistent state, direct manipulation**
- apps run in **sandboxed iframes**
- communication is **auditable**

That is exactly the right pattern for Wiii's `code_studio_app` / widget / simulation lane.

### 4. SVG and Canvas each have a clearly different technical sweet spot
MDN and Observable/D3 reinforce the split:

- **SVG**
  - text-based, DOM-friendly, scalable at any size
  - works cleanly with CSS, DOM, JavaScript, and animation
  - ideal for labels, callouts, structure, and explanatory diagrams

- **Canvas**
  - controlled by JavaScript drawing commands
  - ideal for repeated redraw, frame-by-frame animation, dense particle systems, and interactive simulations
  - natural fit for physics, motion fields, and richer dynamic scenes

Observable/D3 also highlights an important practical bridge:
- some geometry/path logic can be shared across **Canvas** and **SVG**
- use Canvas when performance matters more
- use SVG when convenience and semantics matter more

## Implications for Wiii

### Make SVG Motion Explainer a first-class lane
Use for:
- mechanism diagrams
- process flows
- timelines
- concept maps
- architecture views
- benchmark visuals with labels and takeaways
- motion explainers with restrained animation

This should become the main lane for Claude-like inline educational visuals.

### Make Canvas Simulation a first-class lane
Use for:
- pendulum
- ship movement
- wave/field behavior
- particles
- system dynamics
- kinetic demonstrations

This should become the main lane for simulations and interactive physics.

### Keep video as an export lane, not the primary runtime
Video is useful when Wiii needs:
- replay
- sharing
- embedding in LMS/slides
- packaging a finalized motion explanation

But video should not replace:
- SVG for explanation
- Canvas for live simulation

## Recommended architecture

### Lane policy
- `article_figure` -> **SVG-first**
- `chart_runtime` -> **SVG-first**
- `code_studio_app` for simulation -> **Canvas-first**
- `artifact/export` -> **WebM/MP4** when the result is finalized

### Reasoning policy
- premium SVG/canvas requests should automatically increase thinking depth
- multi-component simulation requests should not run on low-effort generation
- add a critic pass before preview/publish for simulation outputs

### Runtime policy
- host owns chrome, shell, controls, and feedback contracts
- model owns scene plan, claim structure, and interaction design within the contract
- avoid free-form HTML/CSS/JS for tasks that fit SVG or Canvas runtimes better

## What not to do
- do not route normal explanatory visuals into freestyle Code Studio HTML
- do not force Canvas for diagrams that need labels and structured reading
- do not force SVG for heavy simulation loops
- do not use video as the default lane for learning interactions

## Suggested next build focus
1. SVG Motion Explainer runtime
2. Canvas Simulation runtime
3. Shared scene grammar and geometry primitives
4. Premium reasoning + critic loop for visual codegen
5. Export pipeline for WebM/MP4 only after the live experience is strong

## Sources
- Claude blog: https://claude.com/blog/claude-builds-visuals
- Claude use case: https://claude.com/resources/use-cases/build-interactive-diagram-tools
- Claude blog: https://claude.com/blog/interactive-tools-in-claude
- MCP Apps blog: https://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/
- OpenAI Apps SDK: https://help.openai.com/pt-pt/articles/12515353-build-with-the-apps-sdk
- WebMCP draft: https://webmachinelearning.github.io/webmcp
- MDN SVG: https://developer.mozilla.org/en-US/docs/Web/SVG
- MDN Canvas basic animations: https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API/Tutorial/Basic_animations
- D3 path: https://d3js.org/d3-path
- D3 zoom: https://d3js.org/d3-zoom
