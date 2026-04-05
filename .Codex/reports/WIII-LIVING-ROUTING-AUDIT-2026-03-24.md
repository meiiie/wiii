# Wiii Living Routing Audit — 2026-03-24

## Summary

This audit focused on why Wiii felt less alive, why visible thinking looked repetitive, and why short turns could still feel slow or misrouted.

Core conclusion:

- Wiii's `character card` is not being reloaded every turn.
- The bigger regression came from orchestration:
  - visible thinking for `supervisor` was emitted too late,
  - the visible thinking text was derived from a generic local fallback instead of the routing rationale,
  - routing/creative lanes were too exposed to per-request provider drift,
  - Google being degraded forced the house stack to fall back to Zhipu more often, which changed tone/consistency.

## What Was Confirmed

### 1. Character is not reloaded per turn

- `app/engine/character/character_card.py`
  - `get_wiii_character_card()` is cached with `@lru_cache(maxsize=1)`.
- `PromptLoader` is also not rebuilt aggressively anymore in the touched hot paths.

So the regression was not caused by reloading Wiii's identity file on every request.

### 2. Current stream flow before this audit

Observed flow:

1. frontend opens `/chat/stream/v3`
2. backend emits a quick `status`
3. graph starts
4. `guardian` completes
5. `supervisor` performs structured routing
6. only after supervisor finishes, visible `thinking_start` appears
7. next node runs (`direct`, `rag_agent`, `code_studio_agent`, ...)

This meant users could wait many seconds with almost no feeling that Wiii was "thinking", even when SSE itself had already connected.

### 3. Why thinking felt generic

- `graph_streaming.py` used `ReasoningNarrator.render_fast(...)` after the supervisor completed.
- The narrator received routing metadata, but local summary generation still leaned on fallback phrasing.
- Result: many turns collapsed toward the same meta-sentence instead of sounding like Wiii's inner voice.

### 4. Why tone drifted

Per-request provider selection previously reached deep into:

- supervisor routing
- reasoning narrator
- code studio generation

That made Wiii's conductor voice unstable when the selected provider changed.

### 5. Why the stack still sometimes feels "less Wiii"

Runtime truth on 2026-03-24:

- `google`: disabled/busy
- `zhipu`: selectable
- `ollama`: host_down

So even with house-model policy, the system may still fall back to Zhipu, which affects style and Vietnamese quality.

## Changes Applied

### A. Pre-route visible thinking now appears early

Updated:

- `app/engine/multi_agent/graph_streaming.py`

Behavior now:

- after the initial status, backend emits a lightweight `supervisor` pre-route thinking block immediately,
- later, when structured routing finishes, the same supervisor block continues with richer route-aware content and then closes.

This makes Wiii feel alive earlier, without waiting for the full routing pass to complete.

### B. Supervisor visible thinking now uses routing context better

Updated:

- `app/engine/reasoning/reasoning_narrator.py`

Changes:

- local summary now reads sanitized observations first,
- supervisor summaries are more context-aware,
- fallback is less likely to collapse into the same canned sentence,
- supervisor action text now maps node cues more cleanly.

### C. House-model policy restored for routing / creative identity

Updated:

- `app/engine/multi_agent/supervisor.py`
- `app/engine/reasoning/reasoning_narrator.py`
- `app/engine/multi_agent/graph.py`

Changes:

- `supervisor` now resolves from the house routing profile, not the user-selected generation provider,
- `reasoning_narrator` for `supervisor` and `code_studio_agent` also uses the house profile,
- `code_studio_agent` no longer follows the explicit per-request provider pin blindly.

This aligns better with the desired Wiii architecture:

- house routing / identity model
- stronger creative model for visual / code studio lanes
- user-selected provider should not fully replace Wiii's conductor soul

## Live Verification

### Stream behavior (`/chat/stream/v3`)

Post-patch `wow` sample:

- first visible `thinking_start`: around `0.27s - 0.53s`
- richer route-aware supervisor delta: around `7s - 9s`

Important distinction:

- stream is now alive quickly,
- total route time can still be several seconds because routing still depends on LLM inference.

### Sync behavior (`/chat`)

Post-patch `wow` sample:

- total: around `9.8s`

This is expected: sync waits for the entire turn, while streaming now shows progress much earlier.

## Remaining Risks

### 1. Google quota / busy state is still the biggest quality blocker

Because the intended house model is currently degraded, the system often falls back to Zhipu. That fallback is functional, but it weakens:

- tone consistency,
- Vietnamese smoothness,
- code-studio / creative feel.

### 2. Visible thinking is better, but still not "true streamed inner thought"

Current implementation is:

- immediate local prelude
- later route-aware local continuation

It is much better for UX, but it is still not the same as provider-native fine-grained thought/tool streaming.

### 3. Unicode / provider quality

Some no-diacritic or odd-Vietnamese behavior can still happen when fallback providers generate the final answer. That is now less about prompt loading and more about provider output quality plus current fallback conditions.

## Architecture Verdict

The right direction for Wiii is:

- keep `LLM-first` routing,
- keep only very narrow deterministic fast paths,
- keep a stable house routing/identity model,
- keep a stronger creative model for visual/code studio,
- use streaming to expose early, humane progress,
- do not let every user-selected provider replace Wiii's conductor voice.

This matches the broader 2026 pattern seen in:

- Anthropic/Claude streaming and fine-grained tool streaming,
- Anthropic guidance on reducing latency without flattening quality,
- AIRI's direction toward a stable "living" companion core rather than prompt-bloat per turn.
