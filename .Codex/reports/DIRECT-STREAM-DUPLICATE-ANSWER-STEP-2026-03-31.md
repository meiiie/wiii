# Direct Stream Duplicate Answer Step

Date: 2026-03-31

## Symptom

In the direct `origin/selfhood` stream probe, the answer was emitted once as normal answer chunks and then emitted again as a full duplicate answer near the end of the turn.

Raw evidence before the patch:

- `live-stream-wiii-origin-2026-03-31-213655.txt`

Pattern observed:

1. `thinking_start`
2. `thinking_delta`
3. `thinking_end`
4. many `answer` chunks
5. one extra full-answer `answer` event

## Root cause hypothesis

`handle_direct_node_impl()` treated `answer_via_bus` as authoritative, but when the node used `_answer_streamed_via_bus=True` as the dedup signal, the handler did not always mark `answer_emitted=True`.

That left room for a later re-emission path to treat the turn as if no answer had been emitted yet.

## Code change

Updated:

- `maritime-ai-service/app/engine/multi_agent/graph_stream_agent_handlers.py`

Change:

- when either `answer_via_bus` **or** `_answer_streamed_via_bus` is true, direct handler now marks `answer_emitted=True`.

## Verification

Focused tests:

- `25 passed`

New regression test:

- `maritime-ai-service/tests/unit/test_graph_stream_agent_handlers.py`

## Current status

- Logic fix is in place.
- Focused tests are green.
- A clean live re-probe still needs a stable fresh backend process; local shell currently has process/startup friction on alternate ports, so the live HTML has not yet been refreshed with this specific dedup fix.
