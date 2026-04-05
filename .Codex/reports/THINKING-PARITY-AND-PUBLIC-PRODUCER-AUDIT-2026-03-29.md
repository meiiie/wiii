# Thinking Parity And Public Producer Audit

Date: 2026-03-29
Workspace: `E:\Sach\Sua\AI_v1`

## Scope

This audit answers the next question after the runtime secret fix:

- now that `/api/v1/chat` and `/api/v1/chat/stream/v3` both reach Gemini again,
- why do they still look different,
- and where does public `thinking` actually come from today?

Artifacts used:

- `E:\Sach\Sua\AI_v1\.Codex\reports\runtime-smoke-chat-2026-03-29-after-secret-fix.json`
- `E:\Sach\Sua\AI_v1\.Codex\reports\runtime-smoke-stream-pendulum-2026-03-29-after-secret-fix.json`
- `E:\Sach\Sua\AI_v1\.Codex\reports\THINKING-RUNTIME-PARITY-PATCH-2026-03-29.md`

Prompt used:

- `Phân tích về toán học con lắc đơn`

---

## Current Truth

After the secret-precedence patch:

- sync path works on `google`
- stream path works on `google`
- both use `routing_metadata.method = structured`
- both no longer degrade to `rule_based` because of invalid Google key

So the old catastrophic divergence is gone.

What remains is a second-layer divergence:

- sync and stream still do not surface the same user-visible answer/thinking shape

This is no longer mainly a provider/runtime-policy bug.
It is now a public-surface / transport-authority problem.

---

## `/api/v1/chat` vs `/api/v1/chat/stream/v3`

These two endpoints are not duplicates.

### `/api/v1/chat`

- one-shot sync JSON
- returns final shaped response + metadata
- best for LMS/server integrations and non-stream clients

### `/api/v1/chat/stream/v3`

- SSE transport
- emits status, thinking blocks, tool events, visuals, answer chunks, metadata, done
- best for desktop/web UX

Correct architecture is:

- one shared business pipeline
- two transports

So the target is not to remove one endpoint.
The target is:

- make both reflect one authoritative backend truth

---

## Sync Path Truth

Sync path returns final payload from:

- `app/engine/multi_agent/graph_process.py`

Important shaping behavior:

- `response` is built from `result["final_response"]`
- `thinking_content` is resolved by `resolve_public_thinking_content(...)`

This means sync path is fundamentally:

- final-state based
- aggregate based

It does not show the user the intermediate public-thinking phases directly.

---

## Streaming Path Truth

Streaming path orchestrates:

- graph state updates
- intra-node bus events

Key files:

- `app/engine/multi_agent/graph_streaming.py`
- `app/engine/multi_agent/graph_stream_merge_runtime.py`
- `app/engine/multi_agent/graph_stream_dispatch_runtime.py`
- `app/engine/multi_agent/graph_stream_agent_handlers.py`
- `app/engine/multi_agent/graph_stream_node_runtime.py`

Important behavior:

1. bus events are forwarded immediately
2. `thinking_start` / `thinking_delta` / `answer_delta` can appear while the node is still running
3. stream UI therefore sees phase-level public reasoning, not only final aggregate state
4. terminal metadata then includes `final_state.thinking_content`

So stream path is fundamentally:

- event-time based
- phase based

---

## Current Public Thinking Producers

Today public `thinking` is still not owned by one single producer.

### Producer A: bus `thinking_delta`

Examples:

- `direct_opening_runtime.py`
- `direct_tool_rounds_runtime.py`
- `tutor_node.py`
- `memory_agent.py`
- `product_search_runtime.py`

These emit:

- `thinking_start`
- `thinking_delta`
- `thinking_end`

in real time during node execution.

### Producer B: final aggregate `thinking_content`

Files:

- `app/engine/multi_agent/public_thinking.py`
- `app/engine/multi_agent/graph_process.py`

Important behavior:

- `capture_public_thinking_event(...)` records only `thinking_delta` fragments into `_public_thinking_fragments`
- `resolve_public_thinking_content(...)` later joins these fragments into final `thinking_content`

So sync `thinking_content` is often an aggregate of earlier deltas.

### Producer C: stream-time node surface fallback

File:

- `app/engine/multi_agent/graph_stream_node_runtime.py`

If node output has no already-streamed visible thinking, stream can still emit a node-level block from:

- `thinking_content`
- or fallback narration

This is another stream-side producer.

---

## Why Stream Looks Different From Sync

### 1. Stream shows phase beats, sync shows aggregate

For the pendulum prompt, stream showed two direct-lane public beats:

- first block: short attune beat
- second block: synthesize beat

Metadata at the end then carried the joined `thinking_content` across both.

Sync never showed those phase beats.
It only returned the final joined `thinking_content`.

### 2. Stream answer is emitted during lane execution

For direct lane:

- `handle_direct_node_impl(...)` emits answer from `node_output["final_response"]`
- then `synthesizer` later often emits only status + metadata because `answer_emitted` is already true

This means the streaming surface effectively prefers:

- lane answer timing

over:

- final post-synthesis canonical answer timing

This is a genuine parity seam.

### 3. Sync and stream are separate live LLM invocations

Even with the same prompt, these are two separate requests.
Current runtime still uses non-zero temperature (`0.5`) in provider creation.

So byte-identical answers are not guaranteed.

This explains why, even after provider parity is fixed, you can still see:

- sync answer length = 1597
- stream answer path = 868

That difference is partly due to:

- separate live generations
- not necessarily a pure bug by itself

But the stream-time suppression of post-synth answer is still an architectural parity risk.

---

## What This Means For Thinking

The main `thinking` issue now is no longer:

- broken Google key
- broken provider route

The real issue now is:

- public thinking authority is still split between event-time bus surface and final-state aggregate surface

This is exactly why the earlier diagnosis still stands:

> fix public-thinking authority before trying to polish the prose

If we only tune narrator/prompt wording now, we will still have:

- one truth for final sync `thinking_content`
- another truth for stream gray rail

---

## Cleanest Repair Direction

### Option 1: Stream authority wins

Meaning:

- bus/phase public thinking is the source of truth
- final `thinking_content` is derived from what was already shown

Pros:

- Claude-like interval thinking
- UI and metadata can converge on one timeline

Cons:

- requires careful dedup and final aggregation rules

### Option 2: Final aggregate authority wins

Meaning:

- stream should not invent extra phase-level public reasoning beyond what final state owns
- stream would mostly show status until final `thinking_content` is ready

Pros:

- simpler parity

Cons:

- loses much of the interleaved “live thinking” feel

### Recommended direction

For Wiii, the better long-term direction is Option 1:

- keep interval thinking
- but make it the single public authority

That means:

1. bus `thinking_delta` becomes canonical public stream content
2. final `thinking_content` is derived from captured public deltas only
3. stream should not create a second synthetic thinking block after the fact for the same node unless the node truly had no public deltas

---

## First Concrete Fix Targets

### 1. Make stream and final aggregate share one public-thinking source

Primary files:

- `app/engine/multi_agent/public_thinking.py`
- `app/engine/multi_agent/graph_stream_merge_runtime.py`
- `app/engine/multi_agent/graph_stream_node_runtime.py`

### 2. Prevent second-layer node thinking when bus already owns that node

Primary files:

- `app/engine/multi_agent/graph_stream_agent_handlers.py`
- `app/engine/multi_agent/graph_stream_node_runtime.py`

### 3. Revisit direct-lane answer ownership

If stream should match sync more closely, then answer authority should be clarified:

- either direct lane answer is canonical
- or synthesizer answer is canonical

Right now stream tends to surface direct answer immediately and suppress later answer emission.

Primary files:

- `app/engine/multi_agent/graph_stream_dispatch_runtime.py`
- `app/engine/multi_agent/graph_stream_agent_handlers.py`
- `app/engine/multi_agent/graph_process.py`

---

## Working Diagnosis

As of now, the cleanest statement is:

> runtime-provider parity is mostly restored, but public-thinking parity is still split because sync consumes final aggregate `thinking_content` while stream consumes event-time thinking beats plus terminal metadata.

That is the real starting point for the next thinking repair phase.

---

## Recommended Immediate Next Step

Before rewriting any narrator prompt again:

1. choose public-thinking authority
2. make stream and final metadata both follow it
3. only then tune the content quality of Wiii’s thinking

This should be the next repair phase.
