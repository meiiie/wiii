# Claude Code Thinking/Stream Learning For Wiii

Date: 2026-04-01  
Author: Codex LEADER  
Scope: Learn from local `claude-code` source and extract patterns useful for Wiii's stream/thinking architecture.

## Executive Summary

`claude-code` does **not** win by having prettier thinking text. It wins because it treats thinking as a **first-class streamed block with a lifecycle**, then preserves that lifecycle across:

1. provider stream events  
2. query/tool loop state  
3. UI rendering  

That is the key lesson for Wiii.

Wiii has already moved in the right direction:

- removed the old authored public renderer
- shifted to native-thinking-first
- added thin cleanup/alignment instead of prose generation
- improved stream/sync parity

But Wiii still has one core architectural weakness compared to `claude-code`:

**Wiii still often treats visible thinking as text that needs cleanup/recovery, while Claude Code treats thinking as structured trajectory state that should be preserved.**

That single difference explains many of the issues we have been fighting:

- stream thinner than sync
- thought disappearing on some lanes
- direct/selfhood requiring backfill
- final metadata overriding live thought
- answer/thinking contamination

## Sources Studied

### Local Claude Code Source

- [thinking_capture.ts](E:/Sach/Sua/test/claude_lo/claude-code/thinking_capture.ts)
- [src/query.ts](E:/Sach/Sua/test/claude_lo/claude-code/src/query.ts)
- [src/QueryEngine.ts](E:/Sach/Sua/test/claude_lo/claude-code/src/QueryEngine.ts)
- [src/utils/thinking.ts](E:/Sach/Sua/test/claude_lo/claude-code/src/utils/thinking.ts)
- [src/utils/messages.ts](E:/Sach/Sua/test/claude_lo/claude-code/src/utils/messages.ts)
- [src/components/Messages.tsx](E:/Sach/Sua/test/claude_lo/claude-code/src/components/Messages.tsx)
- [src/services/api/claude.ts](E:/Sach/Sua/test/claude_lo/claude-code/src/services/api/claude.ts)
- [src/cli/transports/ccrClient.ts](E:/Sach/Sua/test/claude_lo/claude-code/src/cli/transports/ccrClient.ts)

### Current Wiii Flow Compared

- [direct_execution.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_execution.py)
- [graph_stream_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_stream_runtime.py)
- [chat_stream_coordinator.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/services/chat_stream_coordinator.py)
- [thinking_post_processor.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/services/thinking_post_processor.py)
- [chat-store.ts](E:/Sach/Sua/AI_v1/wiii-desktop/src/stores/chat-store.ts)

## What Claude Code Is Doing Right

## 1. Thinking Is A Real Stream Primitive

In [src/query.ts](E:/Sach/Sua/test/claude_lo/claude-code/src/query.ts), they write down the rules explicitly:

- a thinking block belongs to a query with thinking enabled
- a thinking block cannot be an orphan tail
- thinking must be preserved for the whole assistant trajectory, including tool continuation

This is the deepest lesson.

They are not thinking in terms of:

- "generate a public summary"
- "repair the rail later"
- "if rail is weak, rewrite it"

They are thinking in terms of:

- **this thought block exists**
- **this block is attached to a trajectory**
- **this trajectory must survive tools and continuation**

## 2. Provider Config Is Separate From Rendering

In [src/utils/thinking.ts](E:/Sach/Sua/test/claude_lo/claude-code/src/utils/thinking.ts), thinking support is treated as:

- provider/model capability
- request-level config
- adaptive or budgeted mode

This means:

- model choice is one decision
- thinking policy is another decision
- UI is a third decision

This separation is very healthy.

## 3. Stream Transport Coalesces Deltas Into Stable Snapshots

In [src/cli/transports/ccrClient.ts](E:/Sach/Sua/test/claude_lo/claude-code/src/cli/transports/ccrClient.ts), they do something Wiii should learn from immediately:

- buffer stream events briefly
- coalesce `text_delta` into full-so-far block snapshots
- keep state by `{message_id, block_index}`

That gives them a much stronger stream substrate.

They do not simply trust every tiny delta as final UI truth.

They also do not regenerate prose.

They accumulate block state.

## 4. Query Engine Owns Turn Lifecycle

In [src/QueryEngine.ts](E:/Sach/Sua/test/claude_lo/claude-code/src/QueryEngine.ts), there is a clear separation:

- `query.ts`: loop/tool/thinking mechanics
- `QueryEngine.ts`: turn/session lifecycle
- `Messages.tsx`: rendering

This is important because it prevents UI heuristics from becoming authority.

## 5. UI Renders Live Thinking As A Temporary Overlay, Not A Replacement Truth

In [src/components/Messages.tsx](E:/Sach/Sua/test/claude_lo/claude-code/src/components/Messages.tsx), `streamingThinking` is:

- visible while streaming
- briefly retained
- clearly separate from finalized assistant message history

This is subtle but important.

They do not confuse:

- live streaming thought
- finalized stored message

Wiii currently does some reconciliation well, but still sometimes needs to promote metadata snapshots back into the final message because the live path was incomplete.

## What Wiii Is Already Doing Well

Wiii today is **much healthier** than before.

We have already done these important repairs:

- retired the old `public_thinking_renderer.py`
- moved toward native-thinking-first
- cleaned selfhood/direct thought with thin cleanup instead of fake narration
- improved stream/sync parity on core cases
- made the desktop store prefer stronger final metadata when live stream was thinner

These were correct moves.

So this is **not** a story of "Wiii is wrong, Claude Code is right."

It is a story of:

- Wiii has repaired many surface-level mistakes
- now Wiii needs one deeper architectural upgrade

## The Remaining Architectural Gap In Wiii

## 1. Wiii Still Recovers Thought As Text Too Often

Look at [direct_execution.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_execution.py):

- `_extract_stream_chunk_parts(...)`
- `_normalize_direct_visible_thinking(...)`
- `_preserve_ai_message_metadata(...)`
- `_should_prefer_invoke_backfilled_stream(...)`

These functions are smart and necessary.

But they reveal the current architectural truth:

**Wiii still has to recover, align, sanitize, and backfill visible thought from text-form artifacts because the underlying stream is not yet authoritative enough by itself.**

That is why we keep seeing:

- direct selfhood/emotion needing backfilled stream
- some lanes stronger in sync than stream
- final metadata rescuing stream

## 2. Wiii Has Great Final Metadata Recovery, But That Is Still Recovery

In [chat-store.ts](E:/Sach/Sua/AI_v1/wiii-desktop/src/stores/chat-store.ts), the frontend now does something good:

- compare `streamingThinking`
- compare `metadata.thinking_content`
- pick preferred final thinking
- reconcile into final blocks

This is a good repair.

But Claude Code's strength is that it needs less of this kind of rescue because the stream path itself is closer to block-authoritative.

## 3. Wiii Still Mixes "Live Thought" And "Final Thought Rescue"

In [chat_stream_coordinator.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/services/chat_stream_coordinator.py) and [graph_stream_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_stream_runtime.py), Wiii still depends on:

- live SSE events
- fallback metadata
- finalization metadata event

This works, but it means visible thinking can still depend on:

- how a provider streams
- whether a lane used tool rounds
- whether the final merged message kept metadata

That is more fragile than Claude Code's "trajectory first" model.

## What Wiii Should Learn Next

## 1. Introduce A Backend Thinking Trajectory Accumulator

Wiii should add a provider-neutral backend concept like:

- `ThinkingTrajectory`
- keyed by `turn_id / step_id / block_index`
- tracking:
  - pre-tool thought
  - post-tool continuation
  - end-of-turn final thought snapshot
  - source provenance: live delta vs final metadata rescue

This should sit **before** UI and **before** cleanup.

Not in frontend store.
Not as prose.
Not as renderer.

This is the single most valuable lesson from Claude Code.

## 2. Preserve Thought Across Tool Trajectory As A Rule

Claude Code is very explicit: thought belongs to the assistant trajectory, including tool continuation.

Wiii should formalize the same rule:

- if a turn has thought before tool call
- and then tool result
- and then continuation thought
- those are one thought trajectory with phases, not unrelated text scraps

That would help:

- tutor explain
- tutor visual follow-up
- direct search
- code studio

## 3. Keep Cleanup Thin, Not Creative

Current Wiii direction here is good.

Keep:

- turn analysis
- human-style reflective/log-like thought
- mild humor or cute touches when natural

Strip only:

- answer drafts
- "I will say..."
- explicit response choreography
- prompt-internal scaffolding
- obvious meta-host lines

This matches the user's stated preference and is also closer to Claude Code's spirit.

## 4. Separate Three Authorities Clearly

Wiii should explicitly distinguish:

1. **provider-native thinking**
2. **backend thought trajectory state**
3. **frontend display blocks**

Right now Wiii is better than before, but these still blur together in some lanes.

## 5. Treat Final Metadata As Reconciliation, Not Primary Design

Current Wiii metadata rescue is good and should remain.

But the target architecture should be:

- stream path already produces a strong thought trajectory
- metadata mostly confirms and reconciles
- metadata does not need to save the entire visible-thought experience

## What Wiii Should NOT Copy From Claude Code

Not everything in `claude-code` is worth copying.

Do not blindly import:

- Anthropic-specific block semantics like `signature_delta`
- CLI-specific buffering assumptions
- their exact UI visibility timeout rules
- their provider-specific capability gates as-is

Wiii is multi-provider and multi-surface:

- Gemini
- GLM
- future OpenRouter/Ollama
- desktop/web/LMS/embed

So the lesson to borrow is:

- **shape of architecture**

not:

- exact Anthropic implementation details

## Recommended Next Technical Roadmap For Wiii

### Phase A: Architecture

1. Add backend `ThinkingTrajectory` object for streamed turns.
2. Feed it from:
   - live delta
   - tool continuation
   - final merged metadata
3. Mark each segment with provenance:
   - `live_native`
   - `final_snapshot`
   - `aligned_cleanup`

### Phase B: Lane Upgrades

1. `memory`
   - keep human continuity
   - reduce over-literary narration
2. `direct emotion`
   - keep warmth
   - keep non-template authenticity
3. `tutor`
   - maintain depth through tool/visual steps

### Phase C: Eval

Extend golden eval so each turn captures:

- stream live thought length
- final metadata thought length
- provenance mix
- tool trajectory presence
- whether final thought is richer than live

This will let Wiii detect real regressions instead of relying on intuition alone.

## Bottom Line

The core lesson from `claude-code` is:

**Do not fix thinking by writing better fake thinking. Fix it by giving real thinking a stronger lifecycle.**

Wiii has already escaped the worst old anti-patterns.

The next jump is not another prompt patch.

It is to make stream thinking in Wiii behave more like a preserved trajectory and less like text that must be rescued after the fact.

