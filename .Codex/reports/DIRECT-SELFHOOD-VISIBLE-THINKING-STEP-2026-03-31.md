# Direct Selfhood Visible Thinking Step

Date: 2026-03-31

## What changed

- Direct no-tool Google turns now prefer native LangChain `astream()` over the OpenAI-compatible stream path.
- Direct no-tool streaming no longer starts with `thinking_closed=True` when the opening phase did not emit a thinking block.
- Fixed a real runtime bug in `direct_execution.py` where `sanitize_visible_reasoning_text` was used without being imported.

## Files changed

- `maritime-ai-service/app/engine/multi_agent/direct_execution.py`
- `maritime-ai-service/tests/unit/test_direct_execution_streaming.py`

## Why this mattered

Before this patch:

- `sync` could contain native thinking in metadata.
- `stream` for direct selfhood/origin and hard-math often showed no visible thinking at all.

Root causes:

1. Google direct no-tool stream was taking the compat stream path first, and the live compat path was returning answer text without thought.
2. Even when native thought existed later in the direct native stream path, the code had already logically closed thinking before the first reasoning chunk arrived.

## Verification

Focused tests:

- `24 passed`

Probe:

- `live-origin-math-probe-2026-03-31-213655.json`
- `live-stream-wiii-origin-2026-03-31-213655.txt`
- `live-stream-hard-math-2026-03-31-213655.txt`
- `thinking-review-latest.html`

## Current truth

### Good

- Direct stream now surfaces visible thinking again.
- Hard-math stream thinking is back and on-topic.
- No fake narrator template was reintroduced.

### Still not done

- Selfhood/origin stream thinking is real but still English and generic.
- The origin stream answer is currently duplicated in the live stream.
- Hard-math visible thinking is more like expository reasoning than a clean inward monologue.

## Next likely step

Choose deliberately before proceeding:

1. Keep raw visible thinking and only fix duplication + obvious leaks.
2. Add a very thin live alignment layer for direct thinking language/style, while avoiding fake authored thought.
