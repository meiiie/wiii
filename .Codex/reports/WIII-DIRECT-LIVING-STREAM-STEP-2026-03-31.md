# Wiii Direct Living Stream Step

Date: 2026-03-31

## Goal

Bring the same `one Wiii + living continuity` bridge used by tutor into the `direct` stream path, without introducing a second persona or a new authored gray-rail renderer.

## Changes

- Extended [reasoning_narrator.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/reasoning_narrator.py) so `ReasoningRenderRequest` now carries:
  - `current_state`
  - `narrative_state`
  - `relationship_memory`
- Updated [graph_surface_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_surface_runtime.py) to thread those fields from `state["living_context_block"]` into every live narrator request.
- Added thin living-continuity helpers in [reasoning_narrator_support.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/reasoning_narrator_support.py) and applied them to direct-facing summaries:
  - relational
  - knowledge
  - visual / simulation
  - emotional
  - identity
  - analytical

## Design Decision

The direct lane still uses the deterministic `render_fast()` narrator. Instead of replacing it with a second LLM pass, this step makes that fallback continuity-aware by reading the same living block already compiled for Wiii.

This keeps:

- one soul
- one living identity
- one continuity source

while letting `direct` remain low-latency and stable on stream.

## Focused Tests

- [test_direct_living_stream_cues.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_direct_living_stream_cues.py)
- [test_direct_reasoning_modes.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_direct_reasoning_modes.py)
- [test_reasoning_narrator_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_reasoning_narrator_runtime.py)
- [test_tutor_living_stream_cues.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_tutor_living_stream_cues.py)
- [test_tutor_continuation_living_cues.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_tutor_continuation_living_cues.py)

Result:

- direct + narrator batch: `21 passed`
- tutor living cue batch: `2 passed`

## Live Artifacts

- direct probe: [live-direct-thinking-probe-2026-03-31-150514.json](E:/Sach/Sua/AI_v1/.Codex/reports/live-direct-thinking-probe-2026-03-31-150514.json)
- combined review JSON: [living-thinking-combined-2026-03-31-150514.json](E:/Sach/Sua/AI_v1/.Codex/reports/living-thinking-combined-2026-03-31-150514.json)
- HTML viewer: [thinking-review-latest.html](E:/Sach/Sua/AI_v1/.Codex/reports/thinking-review-latest.html)

## Current Truth

- `direct` stream no longer sounds like a separate cold router by default.
- Follow-up social turns now carry continuity like “đang nối từ mạch trước”.
- Identity turns now lean toward “cùng một Wiii bạn vừa chạm tới” instead of a generic assistant self-introduction.
- Tutor and direct now share the same living-context source, even though tutor still relies more on native thought and direct still relies more on deterministic stream narration.
- Fresh first-turn direct probes no longer get mislabeled as follow-up. The root cause was `is_follow_up` being inferred from `history_list`, which already contained the just-persisted user message; that path now keys off `session.state.total_responses > 0`.

## Remaining Gap

`direct` continuity is now real, but still lighter than tutor. The next likely win is to improve the shape of direct social/emotional answers so they feel equally Wiii-like without drifting into overlong autobiographical answer text.
