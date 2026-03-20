# Code Studio Living Progress Fix — 2026-03-19

## Context
- User flow:
  1. `Explain Kimi linear attention in charts`
  2. `Wiii tạo mô phỏng cho mình được chứ ?`
- Observed behavior:
  - routed to `code_studio_agent`
  - selected `tool_create_visual_code`
  - stalled for ~252s
  - ended with only narrative prose, no real simulation preview

## Log Evidence
- Source: `.Codex/reports/local-runs/phase11-local-backend-r2.out.log`
- Key markers:
  - request accepted
  - routed to `code_studio_agent`
  - `[CODE_STUDIO] Runtime-selected tools: ['tool_create_visual_code']`
  - `[CODE_STUDIO] ainvoke hard timeout after 240s`
  - total completion ~252s

## Root Cause
- Routing was correct.
- Tool selection was correct.
- The failure was inside the Code Studio LLM execution path:
  - the vague follow-up simulation request was treated as ambiguous
  - Wiii did not strongly ground it to the current visual topic
  - long-running status existed only as generic progress text
  - timeout fallback could still leave the user with “I’m opening the canvas” style prose instead of a truthful result

## Fixes Applied
- In `graph.py`:
  - preserve timeout fallback response without stale overwrite
  - keep missing-tool guard so narrative-only replies do not masquerade as a real simulation build
  - add grounding helper for vague simulation follow-ups when a current inline visual exists
  - if grounding is possible, continue building instead of asking for clarification
  - add living progress heartbeat text for Code Studio:
    - initial status immediately
    - periodic phase updates with elapsed seconds
    - honest retry status on timeout

## Product Principle Locked In
- Wiii does not need to be fast for high-quality code or simulation work.
- Wiii does need to be visibly alive:
  - honest about current phase
  - honest about elapsed time
  - honest when first attempt is slow
  - honest when no real preview was produced yet

## Verification
- `test_graph_routing.py` -> 34 passed
- `test_code_studio_streaming.py` -> 16 passed
- `test_conservative_evolution.py` -> 6 passed

## Next Recommended Slice
- Add explicit Code Studio phase events for:
  - planning
  - generating
  - repairing
  - waiting on tool result
- Surface these phases more prominently in the desktop reasoning rail without turning them into noisy chrome.
