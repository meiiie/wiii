# Wiii Current Flow And Truth

Date: 2026-03-29

## Scope

This note replaces several earlier partial conclusions that were polluted by:

- PowerShell Unicode corruption when probing Vietnamese prompts inline
- stream-vs-sync transport differences being mistaken for core thinking failures
- one real direct-lane bug where tool rounds could end with no final answer

The goal here is to capture the current backend/frontend truth before the next thinking-quality patches.

## Business Flow Today

### Sync path

User -> `POST /api/v1/chat`

1. `app/api/v1/chat.py`
2. `process_chat_completion_request(...)`
3. `ChatOrchestrator.prepare_turn()` / `process()`
4. `process_with_multi_agent(...)`
5. LangGraph shell
6. chosen lane (`direct`, `rag_agent`, `tutor_agent`, etc.)
7. final sync payload

Important sync truth:

- final answer authority is the final graph state / sync response payload
- final public thinking authority is currently resolved via `public_thinking`

### Stream path

User -> `POST /api/v1/chat/stream/v3`

1. `app/api/v1/chat_stream.py`
2. `ChatStreamCoordinator`
3. `process_with_multi_agent_streaming(...)`
4. LangGraph `astream(..., stream_mode="updates")`
5. merged SSE bus:
   - graph state updates
   - intra-node bus events
6. frontend SSE parser -> chat store -> UI blocks

Important stream truth:

- stream answer authority is the emitted `event: answer` sequence
- stream thinking authority is the emitted `thinking_start/thinking_delta/thinking_end` sequence
- final `metadata.thinking_content` should now agree with the same public thinking authority

## What We Re-Verified

### 1. Analytical thinking is real when the prompt arrives as clean Unicode

For prompts such as:

- `phân tích giá dầu`
- `Phân tích về toán học con lắc đơn`

the backend does produce analytical public thinking, not only relational fallback text.

Artifacts:

- `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-inproc-escaped-2026-03-29.json`
- `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-sync-httpx-escaped-2026-03-29.json`
- `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-stream-oil-raw-after-direct-fallback-2026-03-29.txt`

### 2. Earlier CLI conclusions were partially false due to encoding corruption

Raw inline PowerShell probes had turned prompts like:

- `Phân tích giá dầu`

into mojibake, which then changed routing, tool search queries, and narrator output.

This means some earlier “thinking is generic for analytical queries” conclusions were artifacts of broken prompt transport, not always backend truth.

### 3. One real direct-lane bug did exist

The direct lane could hit the tool-loop cap and stop with:

- multiple tool rounds completed
- `llm_response.content == ""`
- no final prose answer

This created the pattern:

- analytical thinking present
- tools fired
- final answer missing or `response_length = 0`

## Bug Fixed In This Round

### Root cause

In `app/engine/multi_agent/direct_tool_rounds_runtime.py`:

- after `max_rounds`, if the model still wanted more `tool_calls`, the helper returned the last empty tool-call response
- `extract_direct_response()` then saw no visible answer text
- result: direct lane finished with empty answer

This bug hit stream much more visibly, but it could also affect sync depending on nondeterministic model behavior.

### Fix

Added a direct-lane recovery step:

- if tool rounds end with remaining `tool_calls` or empty visible answer text
- force one final **no-tool synthesis** pass
- explicitly instruct the model to answer now using already-collected tool results

Files changed:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\direct_tool_rounds_runtime.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_sprint154_tech_debt.py`

Tests added/passed:

- `test_direct_tool_rounds_force_final_synthesis_when_tool_loop_hits_cap`

Focused test status:

- `4 passed` in `test_sprint154_tech_debt.py`
- `2 passed` in `test_graph_routing.py`

## Live Verification After Fix

### Sync

`/api/v1/chat` now returns a real answer for:

- `phân tích giá dầu`
- `Phân tích về toán học con lắc đơn`

Artifact:

- `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-answer-authority-live-retest-2026-03-29.json`

### Stream

Raw SSE now clearly emits:

- analytical `thinking_start/thinking_delta`
- tool events
- final `event: answer` chunks

Artifact:

- `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-stream-oil-raw-after-direct-fallback-2026-03-29.txt`

This confirms the backend stream answer hole is fixed.

### UI

On `http://localhost:1420`, with a clean Unicode prompt, the UI now shows:

- analytical thinking block
- final answer body

Artifacts:

- `E:\Sach\Sua\AI_v1\.Codex\reports\ui-localhost-1420-chat-oil-after-answer-fix-escaped-2026-03-29.txt`
- `E:\Sach\Sua\AI_v1\.Codex\reports\ui-localhost-1420-chat-oil-after-answer-fix-escaped-2026-03-29.png`

## Current Authority Model

### Answer authority

Recommended canon:

- final answer authority = final answer text that reaches the user
- sync canon = sync final payload
- stream canon = emitted `answer` events

Practical current rule:

- for stream, `event: answer` is now the real public answer surface
- for sync, `data.answer` is the real answer field

### Thinking authority

Current best rule:

- public thinking authority = emitted `thinking_delta` content
- `thinking_start.summary` is header/meta only
- final `thinking_content` is the resolved aggregate of public thinking, not a competing second narrator

## What Is Still Not Good Enough

The system now answers again, but the **quality bar** for analytical turns is still not where we want it.

Examples of remaining quality issues:

- answer often opens too relationally for analytical queries
- it apologizes for missing real-time data too early
- it sometimes falls back to broad explanatory scaffolding instead of sharper evidence distillation
- route choice can still wobble between slightly different structured intents for similar analytical prompts

So the next frontier is no longer “why is answer missing?”.

The next frontier is:

1. analytical routing stability
2. analytical tool policy
3. analytical answer framing
4. analytical thinking richness

## High-ROI Next Patches

### Patch 1: stabilize analytical routing hints

Target:

- `app/engine/multi_agent/supervisor.py`
- `app/engine/multi_agent/supervisor_structured_runtime.py`

Goal:

- make analytical market/math turns land on the intended lane more deterministically

### Patch 2: direct analytical answer frame

Target:

- `app/engine/multi_agent/direct_reasoning.py`
- `app/engine/reasoning/reasoning_narrator_support.py`
- direct prompt helpers

Goal:

- remove over-relational opening
- prefer claim -> forces -> evidence -> takeaway structure

### Patch 3: evidence distillation from tool results

Target:

- direct lane synthesis after tool rounds

Goal:

- use gathered search/news evidence more concretely
- reduce “I can’t access real-time data” boilerplate when enough contextual evidence already exists

## External Reference Notes

Anthropic’s official extended-thinking docs reinforce two design points we should keep following:

- thinking and final text are separate public surfaces
- tool use should support interleaved reasoning rather than collapsing everything into one opaque final blob

Sources:

- https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking
- https://docs.anthropic.com/en/docs/build-with-claude/streaming

Google’s current Gemini docs also matter for future tuning:

- Gemini 2.5-series uses `thinkingBudget`, not `thinkingLevel`

Source:

- https://ai.google.dev/gemini-api/docs/thinking

## Bottom Line

Current truth after re-check and patch:

- backend analytical thinking is working on clean Unicode prompts
- backend stream answer hole is fixed
- UI on `localhost:1420` can now show both analytical thinking and final answer for the same turn
- the remaining problem is primarily **quality**, not “thinking vanished” or “stream lost the answer”

That is a much better place to start the real thinking-quality work.
