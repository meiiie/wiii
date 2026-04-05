# Wave 1: Visible Reasoning + Identity Guardrails Audit

Date: 2026-03-25
Scope: Wiii visible thinking contract, selfhood consistency, visual supersession on chat surface

## Why this wave exists

The main problem was not raw latency. The bigger issue was contract drift:

- visible thinking leaked raw user turns and transcript-like content
- Wiii could answer in a way that sounded like it did not know who Wiii was
- operational traces and superseded visual sessions were showing up on the main chat surface

This made Wiii feel less alive, less coherent, and less professional even when the underlying routing still worked.

## Root causes confirmed

1. `reasoning_narrator.py` could surface raw user-goal echoes and transcript-like fragments.
2. `graph.py::_build_recent_conversation_context()` passed recent turns as `User:` / `Wiii:` text into narrator-facing context.
3. direct/code-studio system prompts did not explicitly guard against the selfhood mistake where `Wiii` is treated like the user's name.
4. the frontend still rendered visual blocks whose sessions had already been marked `disposed`.

## Wave 1 changes

### Backend

- Added visible-reasoning sanitization in:
  - `maritime-ai-service/app/engine/reasoning/reasoning_narrator.py`
- Sanitization now strips:
  - transcript markers like `User:` / `Wiii:`
  - raw goal echo when the exact user turn is repeated
  - self-vocative drift like `Wiii ơi` inside Wiii's own visible thought
  - known operational leak phrases from intermediate tool/planning traces
- Tightened narrator prompt instructions so visible reasoning:
  - must not copy transcript
  - must not self-address as `Wiii ơi`
  - must treat `Wiii` as the assistant when the user says `Wiii...`
- If LLM narrator output collapses to trace-only content after sanitization, the system now falls back instead of keeping the original label/result shell.

### Graph / runtime context

- `maritime-ai-service/app/engine/multi_agent/graph.py`
  - `_build_recent_conversation_context()` now returns only compact conversation summary instead of raw recent `User:` / `Wiii:` turns
  - added direct identity guardrails so direct/code-studio lanes preserve Wiii's selfhood more reliably

### Frontend

- `wiii-desktop/src/components/chat/InterleavedBlockSequence.tsx`
  - disposed visual sessions are now hidden from the main chat surface
  - editorial visual composition also ignores disposed sessions

## Focused verification

### Backend

- `pytest tests/unit/test_reasoning_narrator_runtime.py -q -p no:capture`
- Result: `11 passed`

Added/covered:

- narrator no longer leaks transcript markers
- narrator no longer echoes raw goal text into visible thought
- narrator no longer keeps self-vocative `Wiii ơi` in visible thought
- trace-only structured narrator output now degrades cleanly to fallback

### Frontend

- `npx vitest run src/__tests__/interleaved-block-sequence.test.tsx -t "hides superseded visual sessions that were already disposed"`
- Result: `1 passed`

- `npx tsc --noEmit`
- Result: pass

Note:

- the full `interleaved-block-sequence.test.tsx` suite currently has older unrelated failures in balanced reasoning interval expectations
- the new disposed-visual regression itself passes

## Golden sample check

Using `ReasoningNarrator.render_fast()` after Wave 1:

- social:
  - `Mình đang nghe kỹ điều này trước đã...`
- visual:
  - `Mình đang cân xem yêu cầu trực quan này...`
- simulation:
  - `Mình đang dựng lại ý kỹ thuật cho điều này...`

These samples no longer contain:

- raw quoted user turns
- `User:` / `Wiii:` transcript fragments
- `Wiii ơi` self-vocative drift

## Runtime note from live environment

At the time of this audit, `/api/v1/llm/status` showed:

- `google`: disabled / busy
- `ollama`: disabled / host_down
- `zhipu`: disabled / capability_missing

So live browser chat smoke is currently constrained by provider readiness, not only by UI contract.
This is important: a failed live turn right now does not necessarily mean Wave 1 logic is wrong.

## What Wave 1 fixes

- removes the most obvious visible-thinking contamination
- restores a basic selfhood guardrail for Wiii
- prevents superseded visual sessions from piling up on the main chat surface

## What Wave 1 does not solve yet

- action/debug/tool traces still need a cleaner event taxonomy split on the main rail
- chart vs code-studio intent preservation still needs a deeper routing/planner pass
- code-studio session reuse/upsert for retries still needs a dedicated follow-up wave
- provider health / capability policy still affects what can be tested live in UI

## Recommended next wave

1. Split user-facing stream taxonomy into:
   - living_thought
   - action_preamble
   - evidence_or_debug
2. Enforce visual intent preservation:
   - chart/data visual stays chart
   - simulation/app stays code studio
3. Upsert/persist one active visual session per creative turn unless explicit versioning is requested
4. Re-run browser smoke once at least one provider is `selectable` for this chat mode
