# Wiii Thinking + Widget Feedback Phase 4

Date: 2026-03-16
Workspace: `E:\Sach\Sua\AI_v1`

## Scope

This phase closed the highest-priority issues left by the team handoff:

1. `P0` thinking interval finalization
2. `P0` duplicate text leaking from thinking into prose
3. `P1` pending widget streaming behavior
4. widget-to-Wiii feedback plumbing for interactive quiz/simulation widgets
5. stream pacing polish closer to large-model conversational products

## What Changed

### 1. Thinking lifecycle now finalizes correctly

File:
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\stores\chat-store.ts`

Change:
- `closeThinkingBlock()` now closes the latest open thinking block even if later non-thinking blocks already exist.
- closed intervals are marked `stepState = "completed"` instead of staying effectively live.

Result:
- inline thinking no longer stays visually half-open because the store failed to finalize the active interval.

### 2. No-tool answers no longer duplicate into thinking and prose

Files:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_node.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\product_search_node.py`

Change:
- pre-tool text is buffered and only emitted into thinking when the flow actually becomes a tool-using path.
- when no tool call happens, the text stays in the normal answer lane.

Result:
- fewer "I am about to answer..." style duplicates across thinking and final prose.

### 3. Pending widget fences now render safely while streaming

Files:
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\components\common\widget-segments.ts`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\components\common\MarkdownRenderer.tsx`

Change:
- widget parsing now handles open-but-not-yet-closed fences.
- a pending widget placeholder is rendered instead of leaking raw ````widget` fences into the chat body.

Result:
- inline widget streaming looks intentional during generation instead of visibly broken mid-stream.

### 4. Interactive widgets can now send semantic outcomes back to Wiii

Frontend files:
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\api\types.ts`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\stores\chat-store.ts`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\hooks\useSSEStream.ts`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\components\common\InlineVisualFrame.tsx`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\components\common\InlineHtmlWidget.tsx`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\VisualBlock.tsx`

Backend files:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\models\schemas.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\services\input_processor.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\state.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph_streaming.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\supervisor.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_node.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\product_search_node.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\memory_agent.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\rag_node.py`

Contract:
- widgets can call `window.WiiiVisualBridge.reportResult(kind, payload, summary, status)`
- frontend stores summarized widget outcomes on the active conversation
- the next turn includes `user_context.widget_feedback`
- backend converts that into `widget_feedback_prompt`
- downstream agents and synthesis can react naturally to outcomes

Current built-in emitters:
- simulation widgets
- quiz widgets

Examples of data now available next turn:
- score
- correct count
- answered count
- selected option
- current question index
- slider state and play/pause/reset state

This is the foundation needed for:
- personalized quiz follow-up
- memory note creation
- natural "you got 8/10" reactions without asking the user manually

### 5. Stream pacing tuned closer to polished chat products

File:
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\hooks\useSSEStream.ts`

Change:
- answer and thinking stream buffers now use gentler initial holds and smaller chunk sizes.

Effect:
- thinking appears sooner
- answer text feels less bursty
- pending visual/widget shells appear earlier while content is still arriving

## Verification

### Frontend

Commands:

```powershell
npm test -- --run src/__tests__/inline-html-widget.test.tsx src/__tests__/interleaved-block-sequence.test.tsx src/__tests__/thinking-lifecycle.test.ts
npm run build:web
npm run test:e2e:visual
```

Results:
- impacted Vitest suite: `40 passed`
- web production build: `pass`
- Playwright visual suite: `2 passed`

### Backend

Commands:

```powershell
python -m pytest maritime-ai-service/tests/unit/test_visual_tools.py -q
python -m pytest maritime-ai-service/tests/unit/test_tutor_agent_node.py -q
python -m pytest maritime-ai-service/tests/unit/test_product_search_tools.py -q
python -m pytest maritime-ai-service/tests/unit/test_visual_intent_resolver.py -q
```

Results:
- visual tools: `48 passed`
- tutor + product-search regressions: `53 passed`
- visual intent resolver: `13 passed`

## Remaining Gaps

These are no longer blockers, but they are the next places to improve:

1. Search/code widgets still need first-class semantic result reporting.
2. Legacy chart widgets outside the new bridge contract do not always send useful feedback back to the assistant.
3. Multi-figure routing can still be improved, but the highest-risk lifecycle bugs are now fixed.
4. Visual art direction can still move closer to Claude, but this phase focused on correctness, pacing, and feedback plumbing.

## Recommended Next Steps

### A. Search widget contract

Add a standard result payload for search widgets, for example:

```js
window.WiiiVisualBridge.reportResult(
  "search_result",
  {
    query,
    source_count,
    selected_source,
    expanded_source_ids,
    clicked_url,
  },
  "User reviewed 4 sources and opened the arXiv paper.",
  "completed"
);
```

### B. Code widget contract

Add a standard result payload for code-generation/code-run widgets, for example:

```js
window.WiiiVisualBridge.reportResult(
  "code_result",
  {
    language,
    file_count,
    run_status,
    test_status,
    error_summary,
  },
  "The generated app ran successfully but tests failed in one file.",
  "completed"
);
```

### C. Widget author guidance

Create a small internal guide so all widget/app generators use the same bridge:
- emit `ready`
- emit `in_progress`
- emit `completed`
- summarize outcomes in one human-readable sentence
- keep payload compact and semantic

## Bottom Line

This phase moved Wiii from "interactive widgets exist" to "interactive widgets can now inform the next turn."

That closes an important product loop:
- user acts inside widget
- Wiii sees the outcome
- next response can react naturally and personally

That loop is now in place for quiz and simulation widgets and ready to be extended to search/code widget lanes.
