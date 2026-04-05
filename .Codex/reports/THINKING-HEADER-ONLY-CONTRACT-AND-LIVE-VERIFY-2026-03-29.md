# Thinking Header-Only Contract And Live Verify

Date: 2026-03-29

## Goal

Make `thinking_start.summary` explicit header/meta only, so the visible gray-rail body comes from streamed `thinking_delta` instead of `summary` fallback.

This aligns Wiii more closely with interval-style public thinking seen in professional systems: phase/header is metadata, visible thought body is event-time reasoning text.

## Changes

Backend:
- `maritime-ai-service/app/engine/multi_agent/stream_utils.py`
  - `create_thinking_start_event()` now emits `summary_mode="header_only"` whenever a summary is present.
- `maritime-ai-service/app/engine/multi_agent/graph_stream_surface.py`
  - preserves `summary_mode` when converting bus events into stream events.
- `maritime-ai-service/tests/unit/test_chat_stream_presenter.py`
  - added coverage for `thinking_start` payload containing `summary_mode`.

Frontend:
- `wiii-desktop/src/api/types.ts`
  - added `ThinkingSummaryMode`
  - `SSEThinkingStartEvent.summary_mode`
  - `ThinkingBlockData.summaryMode`
  - `ThinkingPhase.summaryMode`
- `wiii-desktop/src/hooks/useSSEStream.ts`
  - forwards `summary_mode` into the store.
- `wiii-desktop/src/stores/chat-store.ts`
  - persists `summaryMode` on thinking blocks/phases.
- `wiii-desktop/src/components/chat/ReasoningInterval.tsx`
  - removed `summary` fallback from visible body/collapsed preview.
- `wiii-desktop/src/components/chat/ThinkingBlock.tsx`
  - collapsed preview now ignores summary when `summaryMode=header_only`.

## Verification

Backend tests:
- `python -m pytest maritime-ai-service/tests/unit/test_chat_stream_presenter.py -q`
- Result: `11 passed`

Frontend tests:
- `npx vitest run src/__tests__/reasoning-interval.test.tsx src/__tests__/thinking-block-dedup.test.tsx src/__tests__/thinking-delta.test.ts src/__tests__/message-list-streaming.test.ts`
- Result: `27 passed`

- `npx vitest run src/__tests__/sse.test.ts src/__tests__/interleaved-block-sequence.test.tsx`
- Result: `52 passed`

Total focused verification:
- `90 passed`

## Live Runtime Check

Environment:
- Backend health: `http://localhost:8000/api/v1/health/live`
- Frontend: `http://localhost:1420`

Artifacts:
- Sync response: `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-summary-mode-sync-2026-03-29.json`
- Stream raw SSE: `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-summary-mode-stream-2026-03-29.txt`

Confirmed raw stream now contains:

```text
event: thinking_start
data: {
  "summary": "...",
  "summary_mode": "header_only",
  ...
}
```

And visible body still arrives separately via:

```text
event: thinking_delta
data: { "content": "..." }
```

## Current Meaning

This patch does not yet make Wiii's thinking intrinsically better.

It does fix an important surface-contract problem:
- `summary` is no longer allowed to impersonate body text on the UI.
- stream payload now says that rule explicitly.
- sync/stream parity is healthier because the same deltas can now be treated as the public-thinking source of truth.

## Next Step

The next high-ROI step is not more UI cleanup.

It is backend public-thinking authority:
- treat streamed `thinking_delta` as canonical public thinking
- make final `thinking_content` a clean aggregate of those deltas
- keep `action_text` outside the gray-rail inner voice

