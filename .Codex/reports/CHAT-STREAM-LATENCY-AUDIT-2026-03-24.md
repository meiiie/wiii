# Chat Stream Latency Audit - 2026-03-24

## Scope

- Audit why trivial social turns such as `he he`, `he he`, and `xin chao hao han`
  were sometimes perceived as `15s`, `24s`, or even `112s+` in the Wiii web UI.
- Focus area:
  - `/api/v1/chat/stream/v3`
  - social fast path routing
  - frontend metadata correlation
  - UI timing display
  - explicit `GLM-5` selection

## Official Reference Direction

As of March 2026, the direction from major teams is still:

- optimize time-to-first-visible-progress and time-to-first-token
- emit useful stream events early
- keep deterministic fast paths only for obvious turns
- do not put a second LLM narration step on the critical path

Official references:

- [Claude streaming](https://platform.claude.com/docs/en/build-with-claude/streaming)
- [Claude fine-grained tool streaming](https://platform.claude.com/docs/en/agents-and-tools/tool-use/fine-grained-tool-streaming)
- [Claude reduce latency](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-latency)
- [Vercel provider timeouts](https://vercel.com/docs/ai-gateway/models-and-providers/provider-timeouts)

## Findings

### 1. The small `15s` near the user bubble is not assistant processing time

- That number is the relative timestamp for the user message.
- The real assistant runtime number is the footer that renders from
  `metadata.processing_time`, for example `Tong 112.1s`.

### 2. The old large-latency symptom was a mix of real and visual issues

There were two distinct causes:

- real heavy-path latency when a trivial social turn missed the obvious-social fast path
- stale metadata overwrite on the frontend when late metadata from an older request
  patched the newest assistant message

### 3. Request correlation on the main graph-stream metadata path was incomplete

- Fallback metadata already carried `request_id`.
- Main graph metadata could still arrive without a usable `request_id`.
- That made it easier for old metadata to poison the latest assistant message.

### 4. UI timing display had a smaller inflation bug

- Some short reasoning intervals were rounded too aggressively.
- That did not explain `112s`, but it did make short phases look longer than they were.

### 5. Current backend behavior for true Unicode social turns is fast

Direct API smoke with a true Unicode `he he` equivalent (`hẹ hẹ`) and `provider=zhipu`
now shows:

- `routing_metadata.method = "always_on_social_fast_path"`
- first visible stream activity in about `0.58s`
- total completion around `0.97s`
- `metadata.processing_time` around `0.35s`

This proves the backend is currently capable of handling the exact social turn quickly
even when `GLM-5` is selected.

### 6. Current browser behavior for explicit `GLM-5` is also fast after a clean load

Headless browser verification on `http://localhost:1420` with explicit `GLM-5` selection
and a fresh chat produced:

- request body with `provider = "zhipu"`
- final assistant response already present by the `2s` checkpoint
- stable footer `Tong 0.4s`
- no drift to `24s`, `43s`, or `112s` even after waiting to `30s`

Artifacts:

- screenshot: `.Codex/tmp/ui-glm5-hh.png`
- capture: `.Codex/tmp/ui-glm5-hh.json`

### 7. There was still a real inconsistency for other tiny chatter turns

Further audit on March 24 showed that the earlier "everything is fixed" verdict
was still incomplete.

Before the latest patch:

- `he he` / `hẹ hẹ` hit the obvious social fast path and returned quickly
- `wow` still missed the fast path, went through structured routing, then paid the
  full DIRECT LLM cost with a very large prompt and many bound tools
- `gì đó` also missed the fast path, went through structured routing, then paid the
  full DIRECT LLM cost

This explains the user's observed non-uniform behavior:

- one trivial turn could finish in about `0.5s`
- another equally trivial turn could take `17s`, `25s`, or `35s`
- a failure on the heavy DIRECT path could still surface a fallback error after
  a long wait

The issue was not that "keyword lists exist". The issue was that the ultra-short
fast path was too narrow and did not cover low-information interjections and vague
banter turns.

### 8. The correct fix is a narrow shape-based chatter fast path, not a big keyword expansion

Based on the current official guidance from Anthropic and Vercel:

- deterministic fast paths should stay narrow
- they should be reserved for obviously low-information turns
- they should optimize time-to-first-visible-progress by skipping heavyweight
  routing and generation

So the latest patch added a narrow chatter classifier for:

- `reaction` turns such as `wow`
- `vague_banter` turns such as `gì đó`
- existing obvious-social turns such as greetings / thanks / laughter

This is intentionally shape-based and low-entropy. It is not meant to become a
wide keyword router for substantive requests.

## Root Cause Verdict

The final verdict is:

- the old `15s` near the user bubble was a UI timestamp misunderstanding
- the old stale-footer issue was real and has been fixed
- but there was also a genuine backend inconsistency:
  - `hẹ hẹ` was fast
  - `wow` and `gì đó` were still falling into the heavyweight structured + DIRECT LLM path

So the user's report of non-uniform latency was valid.

## Code Changes In This Audit Slice

Backend:

- `app/services/chat_orchestrator.py`
  - thread `request_id` into graph execution input
- `app/services/chat_stream_coordinator.py`
  - pass `request_id` into execution builders
- `app/engine/multi_agent/graph_streaming.py`
  - include `request_id` and `routing_metadata` on main metadata events
- `app/engine/multi_agent/supervisor.py`
  - add narrow `reaction` / `vague_banter` chatter classification
  - fast-route those turns before structured routing
- `app/engine/multi_agent/graph.py`
  - return immediate local responses for chatter fast-path turns
  - mark chatter fast-path separately from the classic social fast-path

Frontend:

- `src/stores/chat-store.ts`
  - reject stale metadata patching when `request_id` does not match
- `src/components/chat/MessageBubble.tsx`
  - hide misleading model/reasoning decorations on local social fast-path turns
- `src/components/chat/ReasoningInterval.tsx`
  - format sub-second durations correctly
- `src/components/chat/InterleavedBlockSequence.tsx`
  - avoid inflating short interval totals
- `src/components/chat/MessageBubble.tsx`
  - also suppress misleading model/reasoning decorations on chatter fast-path turns

## Verification

Automated checks completed:

- `npx tsc --noEmit` -> pass
- `npx vitest run src/__tests__/message-bubble-fast-path.test.tsx` -> `2 passed`
- `pytest tests/unit/test_chat_request_flow.py tests/unit/test_chat_stream_coordinator.py -q -p no:capture` -> `19 passed`
- direct Unicode API stream smoke with `provider=zhipu` -> fast-path confirmed
- browser smoke with explicit `GLM-5` -> stable `Tong 0.4s`
- direct `/api/v1/chat` smoke after chatter fast-path patch:
  - `wow` -> about `0.30s`, `method=always_on_chatter_fast_path`
  - `gì đó` -> about `0.30s`, `method=always_on_chatter_fast_path`
  - `hẹ hẹ` -> about `0.48s`, `method=always_on_social_fast_path`

## Practical Conclusion

- The backend social fast path is correct.
- The backend low-information chatter path is now also correct for `wow` and `gì đó`.
- The explicit `GLM-5` browser path is correct on a clean load.
- The `15s` shown near the user bubble is not the processing metric.
- The old `112s` symptom was partly stale client-state confusion, but the user's
  broader complaint about inconsistent latency was also backed by a real routing gap
  that is now patched.

## Recommended Retest Procedure

1. Open `http://localhost:1420`
2. Press `Ctrl+F5`
3. Create a new conversation
4. Select `GLM-5`
5. Send `hẹ hẹ`

Expected result:

- visible activity within about `1s`
- final answer in about `1s`
- footer around `Tong 0.4s`

If a new run still shows `50s+`, capture:

- browser hard-refresh status
- the new `X-Request-ID`
- the final metadata payload
- the full thread screenshot including the footer
