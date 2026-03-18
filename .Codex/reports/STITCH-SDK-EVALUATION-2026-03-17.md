# Stitch SDK Evaluation for Wiii

**Date:** 2026-03-17  
**Evaluator:** Codex LEADER  
**Status:** Recommend sandbox evaluation first, then limited artifact-lane integration if results are strong

---

## 1. Sources verified

- GitHub repo: `https://github.com/google-labs-code/stitch-sdk`
- Local clone reviewed at `C:\Users\Admin\AppData\Local\Temp\stitch-sdk`
- Key files inspected:
  - `README.md`
  - `packages/sdk/package.json`
  - `packages/sdk/src/client.ts`
  - `packages/sdk/src/constants.ts`
  - `packages/sdk/src/tools-adapter.ts`
  - `packages/sdk/generated/tools-manifest.json`
  - `packages/sdk/examples/*.ts`

## 2. What Stitch SDK actually is

Stitch SDK is not a drop-in replacement for Wiii's current visual runtime.

It is best understood as:

- a **remote UI screen generation service**
- exposed through an **MCP server**
- with a **TypeScript SDK**
- and optional **Vercel AI SDK tool adapters**

The package currently publishes as:

- `@google/stitch-sdk`
- version `0.0.3`
- license `Apache-2.0`
- node `>=18`

Default remote endpoint:

- `https://stitch.googleapis.com/mcp`

Authentication:

- API key via `X-Goog-Api-Key`
- or OAuth bearer token + Google Cloud project

## 3. What Stitch can do well

From the current SDK and tool manifest, Stitch is strong at:

- creating projects
- generating a UI screen from text
- editing screens by prompt
- generating design variants
- returning HTML download URLs
- returning screenshots
- exposing tools through MCP / AI SDK

This makes Stitch promising for:

- screen prototyping
- artifact ideation
- dashboard/login/settings-style UI generation
- rapid variant exploration for designers or internal experimentation

## 4. What Stitch is not a perfect fit for today

Stitch is not, by itself, a full answer for Wiii's current problems.

It does **not** naturally solve:

- article-first inline visual figures
- chart-runtime quality for factual data charts
- host-owned shell and Wiii design system parity
- `WidgetResultV1` feedback bridge
- Code Studio token streaming UX
- LMS-sensitive context governance by default
- semantic patch/session continuity in Wiii's current runtime model

Important output mismatch:

- Stitch returns HTML/image artifacts or URLs
- Wiii Code Studio currently centers around streamed code, preview, versioning, and host shell behavior

This means Stitch aligns better with **artifact generation** than with **inline article figures**.

## 5. Recommendation

### Do not

- do **not** wire Stitch directly into the main explanatory visual lane
- do **not** replace `tool_generate_visual`
- do **not** replace `chart_runtime`
- do **not** replace simulation or quiz apps immediately

### Do

- create a separate **internal evaluation page** first
- treat Stitch as an **experimental artifact/screen backend**
- compare it against Wiii Code Studio on real prompts
- only consider production integration after rubric-based wins

## 6. Best fit inside Wiii

### Good candidates

- `artifact` lane
- some `code_studio_app` scaffolding cases where the goal is screen/UI generation
- admin-only “design lab” usage
- previsualization of search/code widget shells

### Weak candidates

- `article_figure`
- `chart_runtime`
- scientific simulations
- LMS quiz/safety-critical educational flows

## 7. Best integration shape

The cleanest path is:

1. **Sandbox first**
   - Add a hidden/internal route like `stitch-lab`
   - Use it only for evaluation
   - Keep it behind a feature flag

2. **Artifact-only backend**
   - Add a new backend adapter or MCP-backed tool
   - Route only explicit artifact/prototype requests into Stitch

3. **No user-facing default routing yet**
   - Wiii should not silently choose Stitch for normal visuals

## 8. Why sandbox first is the right move

Because Wiii is already mid-transition to:

- `article_figure`
- `chart_runtime`
- `code_studio_app`
- `artifact`

If Stitch is inserted too early into the wrong lane, it will blur these boundaries again.

Sandboxing first lets the team answer:

- Does Stitch actually improve quality?
- Does it fit Wiii's design language?
- Can it preserve LMS-first requirements?
- Is the latency acceptable?
- Can outputs be patched conversationally enough for Wiii UX?

## 9. Concrete evaluation rubric

Use the same prompt set across:

- Wiii Code Studio
- Stitch
- current structured/article runtime

Score each on:

- visual quality
- Wiii brand/design fit
- responsiveness
- accessibility
- ability to follow Vietnamese prompts
- editability over follow-up turns
- host-shell fit
- LMS safety/context handling
- output consistency

## 10. Proposed next step

Build a small internal `Stitch Lab` page first, then test on:

- login page
- LMS lesson summary page
- teacher dashboard
- code widget shell
- search widget shell
- artifact app mockup

Do **not** use pendulum simulation or explanatory benchmark charts as primary Stitch benchmarks. Those belong to different lanes.

## 11. Final decision

**Recommended decision:** yes, evaluate Stitch, but only in a dedicated sandbox/internal page first.

If results are good, promote Stitch to:

- optional backend for `artifact` lane
- optional UI scaffold generator for some `code_studio_app` cases

Do **not** make it the main runtime for article visuals or chart runtime.
