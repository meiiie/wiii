# Thinking Summary-As-Header Patch - 2026-03-29

## Goal

Reduce gray-rail duplication by enforcing:
- `thinking_start.summary` = header/meta only
- visible thinking body = `thinking_delta` content only
- no automatic promotion of summary into body text on close/finalize

## What Changed

### Frontend store

File:
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\stores\chat-store.ts`

Change:
- stopped auto-filling thinking body from summary on block close
- summary-only thinking blocks now remain header/meta only unless real deltas arrive

### Reasoning interval surface

File:
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\ReasoningInterval.tsx`

Change:
- collapsed preview no longer falls back to `interval.summary`
- preview line now comes from real thinking body only

### Legacy thinking block surface

File:
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\ThinkingBlock.tsx`

Change:
- collapsed preview no longer prefers summary metadata
- preview comes from streamed body text only

## Result

This makes the UI closer to a Claude-like interval model:
- summary still exists as phase/header metadata
- but the gray rail stops treating summary as a second body paragraph

## Why This Matters

Before this patch, a turn could feel duplicated because:
- `thinking_start.summary` opened the block
- `thinking_delta` then streamed the real content
- frontend sometimes reused summary again as body/preview fallback

After this patch:
- the only prose body the user should read is the delta-backed content

## Verification

Targeted frontend test batches:
- `27 passed`
  - `reasoning-interval.test.tsx`
  - `thinking-block-dedup.test.tsx`
  - `thinking-delta.test.ts`
  - `message-list-streaming.test.ts`

Additional safety batch:
- `52 passed`
  - `sse.test.ts`
  - `interleaved-block-sequence.test.tsx`

## Remaining Work

This patch improves presentation, but does not yet fully solve thinking authority.

Still worth doing next:
- make backend explicitly tag summary as `header_only`
- make final sync `thinking_content` provably identical to aggregated streamed deltas
- keep `action_text` in a clearly separate progress lane
