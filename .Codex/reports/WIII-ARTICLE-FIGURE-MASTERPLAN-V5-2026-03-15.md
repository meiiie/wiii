# Wiii Article-Figure Master Plan V5

Date: 2026-03-15
Owner: Codex (LEADER)
Status: Ready for team implementation

## 1. Executive Summary

Wiii has moved beyond the old `reasoning box + widget card` phase, but it has not reached Claude-like parity yet.

Current status:

- Thinking is inline in the main column.
- Article shell exists in the DOM.
- Visuals can render inside `editorial-visual-flow`.
- Legacy explanatory fallback has been reduced.

Main remaining gaps:

1. Balanced thinking is still slightly too log-like.
2. Explanatory visuals still too often land as a single figure.
3. The outer shell is better, but some inline/app visuals still feel like embedded widgets instead of article figures.
4. Host-owned figure runtime is not strong enough yet.
5. Visual quality and pedagogy still trail Claude in multi-figure decomposition and art direction.

This plan is intentionally `policy-first`, not `hard-coded output-first`.

- Hard-force lane, shell, and UX boundaries.
- Let the model decide figure decomposition inside bounded rules.

## 2. Reference Baseline

Primary references:

- [CLAUDE-KIMI-HTML-UX-ANALYSIS-2026-03-15.md](E:/Sach/Sua/AI_v1/.Codex/reports/CLAUDE-KIMI-HTML-UX-ANALYSIS-2026-03-15.md)
- [WIII-HTML-AUDIT-2026-03-15-PM.md](E:/Sach/Sua/AI_v1/.Codex/reports/WIII-HTML-AUDIT-2026-03-15-PM.md)
- [WIII-POLICY-FIRST-FIGURE-PLANNER-2026-03-15.md](E:/Sach/Sua/AI_v1/.Codex/reports/WIII-POLICY-FIRST-FIGURE-PLANNER-2026-03-15.md)
- [Claude builds visuals](https://claude.com/blog/claude-builds-visuals)
- [Interactive tools in Claude](https://claude.com/blog/interactive-tools-in-claude)
- [MCP Apps blog](https://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/)
- [OpenGenerativeUI](https://github.com/CopilotKit/OpenGenerativeUI)

## 3. Product Goal

Move Wiii to:

- `article shell + inline thinking intervals + figure runtime`

instead of:

- `message + boxed widget`

Target experience:

- Users can see what Wiii is doing while it works.
- Explanatory answers read like a real article with figures.
- Simulations and tools still work inline, but feel absorbed by the host shell.
- Follow-up prompts update existing figures or app sessions rather than dumping new blocks unnecessarily.

## 4. Non-Negotiable UX Decisions

### 4.1 Thinking

- `thinking_level=balanced` is the production default.
- Balanced mode must show a public thinking rhythm, not internal logs.
- Thinking must remain in the main reading column.
- No default large reasoning box.
- No "visual is present, therefore hide reasoning" policy.

### 4.2 Figures

- Explanatory visuals are `article figures`, not app cards.
- Explanatory cases should usually produce `1..3 figures`, not one mega-widget.
- Each figure must prove one claim.
- Figure chrome must stay light and mostly host-owned.

### 4.3 App lane

- Simulation, quiz, mini-tool, dashboard go to `app`.
- But `app` still mounts as an `editorial app figure`, not as a raw boxed iframe.

### 4.4 LLM freedom

- The model should not be forced into exactly 3 figures every time.
- The system should force:
  - lane
  - shell
  - allowed figure budget
  - narrative rhythm
- The model should choose:
  - whether a case needs 1, 2, or 3 figures
  - which claims deserve separate figures
  - which renderer best fits each figure

## 5. High-Level Architecture

### 5.1 Three lanes

1. `Thinking lane`
   - inline intervals
   - balanced or detailed
2. `Figure lane`
   - explanatory figures
   - template or inline_html
3. `App lane`
   - simulation/tool
   - embedded app frame

### 5.2 Runtime policy

- `template`
  - comparison
  - process
  - matrix
  - architecture
  - concept
  - infographic
  - chart
  - timeline
  - map_lite

- `inline_html`
  - bespoke editorial figure
  - local interaction but not a full app

- `app`
  - simulation
  - quiz
  - interactive_table
  - mini tool
  - dashboard

## 6. Workstreams

## Workstream A: Balanced Thinking Rhythm

Goal:

- Make balanced mode read like public progress, not internal logs.

Files:

- [ReasoningInterval.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/chat/ReasoningInterval.tsx)
- [InterleavedBlockSequence.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/chat/InterleavedBlockSequence.tsx)
- [globals.css](E:/Sach/Sua/AI_v1/wiii-desktop/src/styles/globals.css)

Requirements:

- Keep:
  - interval headline
  - one useful opening thought or summary
  - one latest useful thought
  - one primary operation row
- Hide from balanced main flow:
  - duplicate self-talk
  - repeated progress rows
  - noisy tool/file churn
- Keep full trace available in detailed mode and/or inspector drawer.

Acceptance:

- Balanced mode should be scannable in under 3 seconds.
- A user should understand:
  - what Wiii is doing
  - what phase it is in
  - what changed most recently

## Workstream B: FigureShell Everywhere

Goal:

- No more `markdown answer + boxed iframe`.

Files:

- [VisualBlock.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/chat/VisualBlock.tsx)
- [InlineVisualFrame.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/common/InlineVisualFrame.tsx)
- [InlineHtmlWidget.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/common/InlineHtmlWidget.tsx)
- [EmbeddedAppFrame.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/common/EmbeddedAppFrame.tsx)
- [globals.css](E:/Sach/Sua/AI_v1/wiii-desktop/src/styles/globals.css)

Requirements:

- All explanatory visuals must pass through `FigureShell`.
- `FigureShell` must own:
  - spacing
  - width
  - chrome
  - hover actions
  - reduced motion
  - loading state
  - caption rhythm
- Editorial figures should not use heavy outer borders.
- App figures may retain a functional inner frame, but outer article shell must stay light.

Acceptance:

- In HTML export, explanatory figures must not appear as `answer-block > iframe`.
- Article figure ancestry must be preserved.
- App figures must no longer look like a second nested card inside the article.

## Workstream C: Multi-Figure Pedagogy

Goal:

- Stop trying to explain everything with one figure.

Files:

- [visual_tools.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/tools/visual_tools.py)
- [graph.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py)
- [visual_intent_resolver.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/visual_intent_resolver.py)
- [assistant.yaml](E:/Sach/Sua/AI_v1/maritime-ai-service/app/prompts/agents/assistant.yaml)
- [direct.yaml](E:/Sach/Sua/AI_v1/maritime-ai-service/app/prompts/agents/direct.yaml)
- [rag.yaml](E:/Sach/Sua/AI_v1/maritime-ai-service/app/prompts/agents/rag.yaml)
- [tutor.yaml](E:/Sach/Sua/AI_v1/maritime-ai-service/app/prompts/agents/tutor.yaml)

Requirements:

- Use bounded figure planning:
  - 1 figure for narrow/simple asks
  - 2 figures for moderate explanation
  - 3 figures for dense mechanism + results cases
- Each figure must include:
  - `claim`
  - `pedagogical_role`
  - `figure_group_id`
  - `figure_index`
  - `figure_total`
- Default explanatory sequence:
  - figure 1: problem or baseline
  - figure 2: mechanism or bridge
  - figure 3: result, benchmark, tradeoff, or conclusion

Acceptance:

- For `Explain Kimi linear attention in charts`, the DOM should usually show at least 2 figures.
- Follow-up patch turns should not explode into a brand new 3-figure article unless the user asks for a fresh reframing.

## Workstream D: Legacy Widget Retirement

Goal:

- Make `legacy-widget figure` transitional, not default.

Files:

- [InlineHtmlWidget.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/common/InlineHtmlWidget.tsx)
- [InlineVisualFrame.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/common/InlineVisualFrame.tsx)
- [EmbeddedAppFrame.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/common/EmbeddedAppFrame.tsx)
- [widget-segments.ts](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/common/widget-segments.ts)

Requirements:

- Legacy widget content must be host-wrapped and visually normalized.
- Legacy internals like `.widget-title` and `.sim-controls` should be progressively replaced by host shell tokens and styles.
- Explanatory requests should never default back to raw widget replay if structured figure path is available.

Acceptance:

- New HTML export should show reduced or zero `legacy_widget_figure` in explanatory cases.
- Inner iframe HTML should increasingly use host-owned shell classes rather than legacy standalone widget classes.

## Workstream E: App Figure Parity

Goal:

- Make simulations and tools feel embedded in the article, not bolted on.

Primary case:

- `Hay mo phong vat ly con lac`

Files:

- [EmbeddedAppFrame.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/common/EmbeddedAppFrame.tsx)
- [InlineVisualFrame.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/common/InlineVisualFrame.tsx)
- [visual_tools.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/tools/visual_tools.py)
- [visual_intent_resolver.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/visual_intent_resolver.py)

Requirements:

- Simulation requests must route to `app`.
- App frame must appear after a short bridge prose and inline thinking interval.
- Outer shell must look editorial.
- Local controls must be accessible and host-styled.

Later enhancement:

- Build deterministic physics templates for pendulum/spring/projectile if scientific correctness becomes a product requirement.

## Workstream F: Art Direction and Figure Quality

Goal:

- Close the final aesthetic gap with Claude.

Files:

- [VisualBlock.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/chat/VisualBlock.tsx)
- [visual-primitives.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/chat/visual-primitives.tsx)
- [globals.css](E:/Sach/Sua/AI_v1/wiii-desktop/src/styles/globals.css)

Requirements:

- Stronger article rhythm:
  - serif prose
  - lighter chrome
  - more whitespace
- Better figure primitives:
  - chart figure
  - stepper figure
  - benchmark figure
  - architecture figure
  - bridge/takeaway figure
- Better local interaction:
  - tabs
  - steppers
  - chips
  - focus toggles

Acceptance:

- Visuals should feel like editorial figures, not dashboards.
- Each figure should be readable in isolation and still fit the article.

## 7. Technical Guardrails

### Hard-force

- Explanatory visual lane cannot fall back to raw widget DOM path.
- App lane cannot auto-group like explanatory lane.
- Patch turns cannot auto-group by default.
- Balanced mode cannot render the old large thinking box.

### Flexible

- Figure count may vary from 1 to 3.
- The model may choose exact decomposition within that budget.
- The model may choose `template` or `inline_html` inside explanatory lane when policy allows.

## 8. What The Team Should Implement First

Priority order:

1. Workstream B
2. Workstream C
3. Workstream D
4. Workstream A
5. Workstream E
6. Workstream F

Reason:

- Outer shell and figure lane correctness must be locked before polishing thinking density or art direction.

## 9. Deliverables The Team Must Send Back

When the team reports back, require all of the following:

1. Changed file list
2. Short rationale per changed subsystem
3. Test commands run and exact results
4. Fresh HTML export for:
   - `Explain Kimi linear attention in charts`
   - `Hay mo phong vat ly con lac`
5. Screenshots for:
   - desktop
   - mobile
6. Known gaps not fixed yet

## 10. Review Checklist For Codex

When the team reports back, review in this order:

1. DOM/HTML reality
   - article shell present?
   - figure inside editorial flow?
   - no answer-block iframe regression?
2. Thinking rhythm
   - balanced compact enough?
   - not hidden?
   - not noisy?
3. Figure orchestration
   - explanatory case uses 2-3 figures when appropriate?
4. App shell
   - app figure feels editorial?
   - no double-card effect?
5. Browser tests
   - desktop pass
   - mobile pass
6. Art direction
   - better than previous export?

## 11. Success Criteria

We consider the next milestone successful when:

- HTML export proves `article-first` rather than `widget-first`
- balanced thinking reads like progress, not logs
- explanatory case defaults to `1..3` figures intelligently
- app case mounts inline without wide boxed widget feel
- browser tests stay green

## 12. Not In Scope For This Phase

- Full artifact parity
- Deep scientific simulation correctness
- Full replacement of all legacy widget paths
- Bundle-size perfection

These may come later, but they must not block the article-figure milestone.

## 13. Final Direction

The correct direction is:

- not hard-coded 3 figures every time
- not free-form LLM output with no constraints
- but a constrained article/figure system with bounded autonomy

That is the closest path to Claude-like quality without sacrificing reliability.
