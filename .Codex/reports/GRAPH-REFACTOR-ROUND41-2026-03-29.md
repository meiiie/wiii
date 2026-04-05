# Graph Refactor Round 41

Date: 2026-03-29

## Scope

This round focused on two goals:

1. Lock the new `chat_orchestrator` fallback extraction with direct tests, even while the local environment still has the known SQLAlchemy `DeclarativeBase` drift.
2. Extract the oversized `InputProcessor.build_context()` runtime into a dedicated module so `input_processor.py` becomes a thin shell again.

## Changes

### 1. Chat orchestrator fallback runtime

Created:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\services\chat_orchestrator_fallback_runtime.py`

Extracted helpers:

- `persist_chat_message_impl()`
- `upsert_thread_view_impl()`
- `should_use_local_direct_llm_fallback_impl()`
- `process_with_direct_llm_impl()`
- `process_without_multi_agent_impl()`

Updated:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\services\chat_orchestrator.py`

Methods now delegate to the runtime module while preserving the existing shell and patch surface.

### 2. Input processor context runtime

Created:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\services\input_processor_context_runtime.py`

Extracted:

- `build_context_impl()`
- `_populate_semantic_memory_context()`
- `_populate_parallel_context()`
- `_populate_history_context()`
- `_apply_budgeted_history()`

Updated:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\services\input_processor.py`

Result:

- `input_processor.py`: `691 -> 311` lines
- `input_processor_context_runtime.py`: `469` lines

The shell now retains:

- dataclasses
- validation flow
- blocked-message logging
- singleton lifecycle
- thin delegation into the new context runtime

## Tests

### Chat orchestrator fallback extraction

Added:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_chat_orchestrator_fallback_runtime.py`

Result:

- `13 passed`

Coverage in the new test file:

- immediate/background persistence behavior
- thread-view upsert behavior
- local direct LLM fallback selection
- direct LLM result shaping
- fallback RAG path
- no-agent error path

### Input processor extraction

Result:

- `tests/unit/test_input_processor.py`: `31 passed`

### Mixed validation batch

Result:

- `120 passed`
- `8 failed`

The 8 failures are not from this refactor. They are still blocked by the local environment drift:

- `ImportError: cannot import name 'DeclarativeBase' from sqlalchemy.orm`

Affected collections/import paths:

- `test_chat_orchestrator.py`
- `test_chat_request_flow.py`
- `test_sprint210d_llm_sentiment.py`
- `test_sprint222_host_context.py`

## Compile checks

Passed:

- `chat_orchestrator.py`
- `chat_orchestrator_fallback_runtime.py`
- `input_processor.py`
- `input_processor_context_runtime.py`
- `test_chat_orchestrator_fallback_runtime.py`

## Sentrux

Latest gate:

- `Quality: 5478`
- `Coupling: 0.29`
- `Cycles: 2`
- `God files: 0`
- `Distance from Main Sequence: 0.31`
- Verdict: `No degradation detected`

Compared to the original baseline:

- `Quality: 3581 -> 5478`
- `Coupling: 0.36 -> 0.29`
- `Cycles: 8 -> 2`
- `God files: 9 -> 0`

## Assessment

This round improved structural separation in the service layer without reopening the old large-shell pattern:

- `ChatOrchestrator` now has a cleaner fallback/persistence seam.
- `InputProcessor` no longer hides a 400+ line context-assembly body in the shell.
- Both changes reduce future blast radius for any work around chat flow or thinking-related context preparation.

The remaining blocker for fuller validation is still the local SQLAlchemy environment mismatch, not this refactor round.
