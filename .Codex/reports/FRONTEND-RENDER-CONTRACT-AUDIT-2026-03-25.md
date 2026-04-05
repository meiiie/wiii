# Frontend Render Contract Audit

Date: 2026-03-25
Role: TESTER / RESEARCHER support for LEADER
Scope: chat UI render contract for `thinking`, `action`, `debug/tool trace`, and `visual` session handling.

## Summary

The chat UI is not inventing the bad content on its own. The main failure is contract drift across layers:

1. backend emits multiple user-facing event types into the same response turn,
2. frontend stores them as adjacent narrative blocks,
3. `InterleavedBlockSequence` merges them into a single reasoning interval,
4. `ReasoningInterval` then renders them as one coherent-looking rail.

That is why users still see:

- repeated thinking,
- tool/search snippets leaking into the main chat surface,
- visual cards stacking when multiple visual sessions are opened in one turn.

Wave 1 reduced some leakage, but the core event taxonomy is still wrong for the chat surface.

## Root Causes

### 1. Full-paragraph thinking is appended into the same block with only weak dedupe

- [useSSEStream.ts](E:\Sach\Sua\AI_v1\wiii-desktop\src\hooks\useSSEStream.ts):552-560
  - `onThinking` forwards full paragraph reasoning directly to `setStreamingThinking()`.
- [chat-store.ts](E:\Sach\Sua\AI_v1\wiii-desktop\src\stores\chat-store.ts):829-863
  - `setStreamingThinking()` appends paragraph text to the current `thinking` block.
  - Dedupe only checks whether the normalized new paragraph equals the last narrative line of the flat field and last block.
  - Slightly different heartbeat/planner paragraphs are therefore accumulated instead of collapsed.

Why this matches the screenshots:
- repeated prose like `Mình vẫn đang cân xem...`, `Điểm mình đang giữ ở...`, `Nhịp này...` can accumulate inside one visible thinking block even if they are semantically the same.

### 2. Token deltas can reopen or continue prior thinking blocks instead of enforcing a clean phase boundary

- [chat-store.ts](E:\Sach\Sua\AI_v1\wiii-desktop\src\stores\chat-store.ts):899-937
  - `appendThinkingDelta()` first tries to append into the last open thinking block.
  - If none exists, it reuses the previous block when `stepId` matches.
  - Otherwise it creates a new block with inherited label/summary.

Impact:
- if backend sends multiple supervisor deltas / route summaries / follow-up deltas under the same or ambiguous `stepId`, the UI stitches them into one long thinking rail.
- this amplifies repetition instead of segmenting thought into clean phases.

### 3. The UI hides technical trace only in `balanced`; in `detailed` it intentionally surfaces action/tool/status inside the same reasoning rail

- [InterleavedBlockSequence.tsx](E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\InterleavedBlockSequence.tsx):470-492
  - `action_text` and `tool_execution` are considered technical trace.
- [InterleavedBlockSequence.tsx](E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\InterleavedBlockSequence.tsx):474-482
  - `shouldHideTechnicalTraceBlock()` hides `action_text` and `tool_execution` only when reasoning rail is on and `thinkingLevel !== "detailed"`.
- [InterleavedBlockSequence.tsx](E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\InterleavedBlockSequence.tsx):484-492
  - interval candidates include technical trace when `thinkingLevel === "detailed"`.
- [InterleavedBlockSequence.tsx](E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\InterleavedBlockSequence.tsx):825-833
  - visible blocks are filtered only by the above rule.
- [ReasoningInterval.tsx](E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\ReasoningInterval.tsx):207-245
  - `status`, `action`, and `tool` operation items are rendered inline inside the same reasoning component.

Impact:
- if the user is in `detailed` mode, tool/web snippets are not leaking accidentally; the UI is explicitly rendering them into the same rail.
- this is incompatible with the desired product contract where main chat should show living thought, while tool/debug evidence belongs in a separate inspector surface.

### 4. Search tool results are converted into user-visible rich widgets on the main rail

- [ToolExecutionStrip.tsx](E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\ToolExecutionStrip.tsx):32-39
  - search tools are explicitly classified via `SEARCH_TOOL_NAMES`.
- [ToolExecutionStrip.tsx](E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\ToolExecutionStrip.tsx):371-375
  - `parseSearchResults()` is run for search tools.
- [ToolExecutionStrip.tsx](E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\ToolExecutionStrip.tsx):395-402
  - if search items exist, a `SearchResultWidget` is rendered in chat.
- [ReasoningInterval.tsx](E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\ReasoningInterval.tsx):231-246
  - tool items become visible operation rows / strips inside reasoning intervals.

Impact:
- snippets like Brent/WTI headlines are shown because the UI treats search output as user-facing inline evidence, not hidden debug.
- for the desired Wiii experience, that belongs in a secondary evidence surface, not in the same visible-thought stream.

### 5. Consecutive intervals are merged aggressively, which collapses multiple phases into one visible reasoning object

- [InterleavedBlockSequence.tsx](E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\InterleavedBlockSequence.tsx):661-672
  - compatible interval blocks are grouped into one interval.
- [InterleavedBlockSequence.tsx](E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\InterleavedBlockSequence.tsx):865-916
  - consecutive intervals are merged into a single rendered `ReasoningInterval`.

Impact:
- multiple supervisor/direct/tool phases can visually collapse into one long “Wiii đang nghĩ...” section.
- this hides the actual phase boundaries and makes repeated content look like one chaotic monologue.

### 6. `MessageList` passes the full streaming block list into the same surface; only a coarse filter exists

- [MessageList.tsx](E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\MessageList.tsx):21-31
  - `getVisibleStreamingBlocks()` only removes `thinking`, `action_text`, `tool_execution` when reasoning rail is disabled.
- [MessageList.tsx](E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\MessageList.tsx):157-176
  - `InterleavedBlockSequence` receives the live streaming block list directly.

Impact:
- once a block enters `streamingBlocks`, there is no stronger UI-side separation between:
  - living thought,
  - operational preamble,
  - tool evidence,
  - visual artifacts.

### 7. Visual session dedupe is only session-local; there is no per-turn “single active visual” policy

- [chat-store.ts](E:\Sach\Sua\AI_v1\wiii-desktop\src\stores\chat-store.ts):335-336
  - `getVisualSessionId()` keys by `visual_session_id || id`.
- [chat-store.ts](E:\Sach\Sua\AI_v1\wiii-desktop\src\stores\chat-store.ts):395-434
  - `upsertVisualBlockDraft()` dedupes only against the same `sessionId` or `visual.id`.
- [chat-store.ts](E:\Sach\Sua\AI_v1\wiii-desktop\src\stores\chat-store.ts):1195-1252
  - `openVisualSession()` and `patchVisualSession()` update one session correctly, but only if backend keeps the same `visual_session_id`.
- [chat-store.ts](E:\Sach\Sua\AI_v1\wiii-desktop\src\stores\chat-store.ts):504-539
  - status changes (`committed`, `disposed`) are propagated correctly, but only for the targeted session.

Impact:
- if backend opens multiple distinct `visual_session_id` values in the same turn, frontend will keep all of them.
- previous Wave 1 only hid blocks explicitly marked `disposed`; it did not enforce “one active visual session per turn”.

### 8. Render layer only suppresses disposed visuals, not superseded-but-still-open visuals

- [InterleavedBlockSequence.tsx](E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\InterleavedBlockSequence.tsx):147-149
  - `isDisposedVisualBlock()` only treats `status === "disposed"` as removable.
- [InterleavedBlockSequence.tsx](E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\InterleavedBlockSequence.tsx):733-738
  - editorial flow keeps all non-disposed visuals.
- [InterleavedBlockSequence.tsx](E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\InterleavedBlockSequence.tsx):827-833
  - visible blocks filter removes only disposed visuals.
- [InterleavedBlockSequence.tsx](E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\InterleavedBlockSequence.tsx):959-975
  - standalone visuals are still rendered unless they belong to a Code Studio session already mapped in `codeStudioVisualIds`.

Impact:
- if a previous visual was superseded logically but never disposed at protocol level, the UI will continue to show it.
- this is the direct frontend reason visual cards can appear stacked.

### 9. Backend still emits rich supervisor reasoning directly into `thinking_delta`; frontend is rendering it faithfully

This is the main cross-layer cause and explains why frontend symptoms persist even after some Wave 1 sanitization.

- [graph_streaming.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph_streaming.py):1049-1089
  - supervisor narration opens a thinking block, streams `delta_chunks` into `thinking_delta`, emits a route status, closes thinking, then emits `action_text`.
- [supervisor.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\supervisor.py):744-760
  - heartbeat text generator still produces long planner-style prose.
- [supervisor.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\supervisor.py):912-935
  - heartbeat is emitted as `status_only`, which frontend hides from steps, but the richer supervisor narration sent through `thinking_delta` remains visible.

Impact:
- frontend cannot fully solve the problem alone, because the “living thought” rail is still receiving planner/debug-adjacent prose as normal thinking content.

## Why the user sees the specific failures

### A. Repeated thinking

Direct cause:
- full paragraph append in [chat-store.ts](E:\Sach\Sua\AI_v1\wiii-desktop\src\stores\chat-store.ts):829-863
- delta reuse in [chat-store.ts](E:\Sach\Sua\AI_v1\wiii-desktop\src\stores\chat-store.ts):899-937
- interval merge in [InterleavedBlockSequence.tsx](E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\InterleavedBlockSequence.tsx):865-916

Upstream cause:
- supervisor narration streamed as visible `thinking_delta` in [graph_streaming.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph_streaming.py):1061-1068

### B. Tool/web snippets leak into main chat

Direct cause:
- `detailed` mode includes technical trace via [InterleavedBlockSequence.tsx](E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\InterleavedBlockSequence.tsx):474-492
- tool results are rendered as operations via [ReasoningInterval.tsx](E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\ReasoningInterval.tsx):231-246
- search results are expanded into `SearchResultWidget` via [ToolExecutionStrip.tsx](E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\ToolExecutionStrip.tsx):371-402

### C. Visual/session stacking

Direct cause:
- visual dedupe is only by exact session or visual id in [chat-store.ts](E:\Sach\Sua\AI_v1\wiii-desktop\src\stores\chat-store.ts):395-434
- render layer hides only `disposed` visuals in [InterleavedBlockSequence.tsx](E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\InterleavedBlockSequence.tsx):147-149, 827-833
- no per-turn supersede policy exists.

## Acceptance Criteria

### Wave 2: Surface Separation

1. Main chat in `balanced` mode shows only:
   - living thought,
   - final answer,
   - user-facing visual/artifact blocks.

2. `action_text`, `tool_execution`, and search evidence are not rendered on the main reasoning rail in `balanced`.

3. `thinking` content never includes:
   - raw query echo,
   - raw transcript,
   - tool names such as `tool_web_search`,
   - search snippets,
   - route/planner prose like `mình chốt lane...`.

4. If backend emits repeated heartbeat-like thinking paragraphs with minor wording variation, UI collapses them into a single visible thought update rather than appending all variants.

5. `ReasoningInterval` in `balanced` mode must not expose search result widgets or tool result strips inline.

6. If detailed diagnostics are still needed, they must move to a separate trace inspector, not the primary visible-thought body.

### Wave 3: Visual / Session Ownership

1. One user turn can expose at most one active inline visual surface in main chat unless the product explicitly supports multi-figure output for that lane.

2. A new visual session in the same turn must either:
   - patch the prior session,
   - or mark the previous session as superseded/hidden before rendering the new one.

3. Visual blocks with status `superseded` or equivalent must be filtered out exactly like `disposed`.

4. Visual rendering must be keyed by turn ownership plus session identity, not session identity alone.

5. Code Studio linked visuals must not appear both:
   - as standalone inline visual blocks,
   - and as Code Studio session cards,
   for the same turn/session.

6. `visual_open` followed by `visual_patch` within one turn must update the same visible card when the logical artifact is the same, even if backend revision count increases.

## Recommended test prompts for Wave 2/3 validation

1. `Visual cho mình xem thống kê dữ liệu hiện tại giá dầu mấy ngày gần đây`
   - expected: living thought + final chart or clear chart clarification
   - not expected: search snippets inline, repeated route prose

2. `mô phỏng cảnh Thúy Kiều ở lầu Ngưng Bích cho mình được chứ ?`
   - expected: one active visual/app card
   - not expected: stacked superseded visual cards

3. `Wiii có thể uống rượu thưởng trăng không ?`
   - expected: living thought without raw route/debug language

4. `hehe`
   - expected: no tool trace, no search, no robotic planner prose

