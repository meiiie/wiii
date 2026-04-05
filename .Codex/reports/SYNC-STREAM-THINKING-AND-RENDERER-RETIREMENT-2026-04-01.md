# Sync/Stream Thinking + Renderer Retirement

Date: 2026-04-01  
Owner: Codex LEADER

## What changed

1. `public_thinking_renderer.py` was retired and deleted.
2. Surviving helper logic was split into:
   - `maritime-ai-service/app/engine/reasoning/memory_name_turns.py`
   - `maritime-ai-service/app/engine/reasoning/tutor_visible_thinking.py`
3. `maritime-ai-service/app/engine/reasoning/__init__.py` now exports only the still-useful helpers.
4. Stream bootstrap context was brought closer to sync by injecting:
   - `host_session_prompt`
   - `operator_context_prompt`
   - preserved `host_capabilities_prompt`
5. Desktop `finalizeStream()` now prefers richer `metadata.thinking_content` when the streamed rail is thinner, and can reconcile that into persisted thinking blocks.

## Why sync can look better than stream

There are two distinct causes:

### 1. Backend bootstrap parity gap

Before this patch, sync and stream were not building the same graph-level prompt surface.

Sync path already injected:
- host context
- host session
- operator context
- living context
- visual/widget/code-studio context

Stream bootstrap was missing:
- `host_session_prompt`
- `operator_context_prompt`
- explicit carry-through of `host_capabilities_prompt`

That means follow-up turns in stream could enter the graph with a thinner context floor than sync.

### 2. Frontend finalization gap

The desktop store used to persist stream turns with:
- `message.thinking = streamingThinking`

even when final metadata carried a better:
- `thinking_content`

So the live rail could be thinner than the final metadata, but the persisted message still kept the thinner version.

## Current probe truth

Fresh core probe:
- `.Codex/reports/wiii-golden-eval-2026-04-01-022908.json`
- `.Codex/reports/thinking-review-latest.html`

What it shows now:
- The old renderer file is gone cleanly.
- Sync/stream still do **not** fully converge in quality.
- Some of the remaining gap is now runtime/model variability, not only architecture.
- Memory stream can still feel more verbose than sync on later turns.
- Direct selfhood/origin thinking is still unstable across runs.

## Validation

Backend:
- `18 passed`
  - `test_public_thinking_renderer.py`
  - `test_public_thinking_renderer_sync_guardrails.py`
  - `test_public_thinking_renderer_visual.py`
  - `test_graph_stream_runtime.py`
- `20 passed`
  - `test_memory_agent_node.py`
  - `test_wiii_golden_eval_scripts.py`

Frontend:
- `26 passed`
  - `wiii-desktop/src/__tests__/chat-store.test.ts`

## Remaining gap

The biggest remaining quality issue is no longer the deleted renderer.

What remains:
- stream follow-up turns can still be thinner or noisier than sync
- memory lane stream is still too long/soft on some runs
- direct selfhood/hard-analytical thinking remains unstable between runs

## Recommended next step

Do not reintroduce a renderer.

Instead:
1. tighten memory narrator contract for 1-3 dense beats max
2. add transport-parity eval assertions specifically for follow-up turns
3. investigate provider/runtime differences that still make stream less stable than sync
