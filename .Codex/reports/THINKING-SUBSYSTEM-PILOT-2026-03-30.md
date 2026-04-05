# Thinking Subsystem Pilot - 2026-03-30

## Scope

This round moved Wiii one step away from lane-local thinking strings and one step closer to a centralized, extensible public-thinking subsystem.

## What Changed

### 1. Memory lane now consumes the centralized renderer

File:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\memory_agent.py`

Changes:
- Removed the half-migrated local memory helper functions.
- Rewired the node to consume `render_memory_public_plan(...)` for:
  - retrieve header
  - existing-memory beat
  - extract beat
  - new-fact decision beat
  - synthesis header + strategy beat
- Added a local `_emit_public_plan(...)` bridge so `ThinkingSurfacePlan` can drive SSE events and final `thinking_content` consistently.

Result:
- `memory_agent` is no longer in a split-brain state between old helper strings and the new renderer.
- Public thinking fragments are now emitted from a central plan shape rather than ad-hoc per-phase prose assembly inside the node.

### 2. Tutor public-thinking sanitization moved into the reasoning subsystem

Files:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\public_thinking_renderer.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\__init__.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_node.py`

Changes:
- Added `sanitize_public_tutor_thinking(...)` to the centralized renderer module.
- Exported it from `app.engine.reasoning`.
- Removed the duplicate tutor-only sanitizer implementation and marker tables from `tutor_node.py`.
- `tutor_node.py` now imports and uses the centralized sanitizer.

Result:
- The first tutor-related piece of public-thinking policy now lives in the shared subsystem rather than inside the tutor node shell.
- This reduces one more source of lane-specific drift.

### 3. Added contract tests for the subsystem

File:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_public_thinking_renderer.py`

Coverage added:
- lane-to-tone policy selection
- memory name-introduction detection
- memory plan emits header + self-correction beat
- tutor sanitizer keeps reasoning-like text and drops answer-like prose

## Verification

Compile:
- `py_compile` passed for:
  - `memory_agent.py`
  - `public_thinking_renderer.py`
  - `reasoning/__init__.py`
  - `tutor_node.py`
  - `test_public_thinking_renderer.py`

Tests:
- `test_memory_agent_node.py`: `15 passed`
- `test_public_thinking_renderer.py` + `test_memory_agent_node.py`: `19 passed`
- `test_tutor_agent_node.py -k "no_tool_calls_stream_answer_without_repeating_it_in_thinking or tool_call_stream_suppresses_pretool_answer_draft or process_propagates_thinking"`: `3 passed`

## Current Architectural Truth

The subsystem is now partially real, not just a design note:

- `memory` already consumes a centralized public-thinking plan.
- `tutor` already consumes a centralized public-thinking sanitizer.
- `rag` and `tutor` still generate most headers/beats locally.

This means Wiii is now past the purely tactical patch stage. The next steps can be framed as controlled migrations into the subsystem instead of more lane-local string surgery.

## What Is Still Missing

### Not done yet

- `tutor` still owns its own iteration beat/header generation.
- `rag` still has no shared public-thinking plan renderer.
- there is still no shared beat schema usage across all lanes beyond memory.

### Why that matters

Until tutor and rag also emit a shared plan shape, Wiii can still feel inconsistent:
- some lanes think in a highly curated way
- some lanes think in a more node-native prose style

## Best Next Step

Move `tutor` one layer deeper into the subsystem:

1. define a shared `render_tutor_public_plan(...)`
2. migrate `_iteration_beat` output into that plan shape
3. let tutor SSE thinking headers/deltas come from the plan, not tutor-local prose glue

That would be the first full lane after `memory` to run on the new architecture, and it would give the clearest path for later moving `rag` as well.
