# Thinking Runtime Parity Patch

Date: 2026-03-29
Workspace: `E:\Sach\Sua\AI_v1`

## What Was Fixed

Patched startup runtime policy restore so persisted DB secrets no longer overwrite an already-present env secret during startup restore.

Files changed:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\services\llm_runtime_policy_service.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_llm_runtime_policy_service.py`

Behavior now:

- explicit runtime/admin updates can still set keys normally
- startup restore keeps the current in-memory secret if one already exists
- non-secret runtime policy fields still restore from DB as before

## Why This Matters

Before this patch:

- direct core invocation could use the env Gemini key and succeed
- live HTTP server restored a different persisted `google_api_key` from DB
- `/api/v1/chat` and `/api/v1/chat/stream/v3` degraded into fallback behavior

After this patch and server restart:

- live HTTP path now uses Gemini successfully again
- server path no longer shows the old `API key not valid` failure on this prompt path

## Verification

Unit tests:

- `tests/unit/test_llm_runtime_policy_service.py`: `6 passed`

Artifacts:

- `E:\Sach\Sua\AI_v1\.Codex\reports\runtime-smoke-chat-2026-03-29-after-secret-fix.json`
- `E:\Sach\Sua\AI_v1\.Codex\reports\runtime-smoke-stream-pendulum-2026-03-29-after-secret-fix.json`

Prompt used:

- `Phân tích về toán học con lắc đơn`

Observed after patch:

- `/api/v1/chat`
  - `provider = google`
  - `model = gemini-3.1-flash-lite-preview`
  - `routing_metadata.method = structured`
  - `routing_metadata.intent = off_topic`
- `/api/v1/chat/stream/v3`
  - `provider = google`
  - `model = gemini-3.1-flash-lite-preview`
  - `routing_metadata.method = structured`
  - no `API key not valid`
  - no `rule_based`

## Current Truth After Fix

The catastrophic engine/API divergence caused by secret mismatch is now resolved enough that `thinking` work can proceed on a cleaner backend truth.

However, there is still an important remaining parity issue:

- sync and streaming are no longer catastrophically divergent
- but they still do not produce identical final content

Observed on the same prompt:

- sync answer length: `1597`
- streaming answer path: `868`

This is no longer a provider-secret failure.
It is now a higher-level execution/presentation parity issue.

## `/api/v1/chat` vs `/api/v1/chat/stream/v3`

These two endpoints should both stay.

They are not redundant:

- `/api/v1/chat`
  - final JSON response
  - best for LMS/server-to-server clients, simple integrations, tests, non-stream consumers
- `/api/v1/chat/stream/v3`
  - progressive SSE transport
  - needed for desktop/web UX, visible thinking, status updates, tool events, visuals

Correct architecture:

- one shared business pipeline
- two transports
- same authoritative routing/runtime truth

So the goal is not to delete one of them.
The goal is:

- keep both
- make them share the same backend truth
- minimize parity drift between final sync result and streamed result

## Recommended Next Step

Now that the provider-secret split is fixed, the next work item should move to:

1. sync vs stream parity audit on the same prompt set
2. unify public thinking producer/authority
3. then improve `thinking` quality itself
