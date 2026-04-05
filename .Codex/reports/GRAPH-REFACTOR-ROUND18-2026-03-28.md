# Graph Refactor Round 18 — Corrective RAG + Chat Orchestrator

> Date: 2026-03-28
> Scope: Continue structural cleanup only. No thinking-quality changes in this round.
> Goal: Reduce shell responsibility, keep source-inspection tests stable, and preserve chat-side public wrappers.

---

## 1. Summary

This round focused on two safe, high-ROI refactors:

1. `corrective_rag.py`
2. `chat_orchestrator.py`

Both files were still carrying orchestration plus support-side responsibilities. The main pattern used here was:

- keep the public shell class intact
- extract support/runtime helpers into dedicated modules
- preserve source markers and public wrappers required by legacy tests

---

## 2. Files Added

1. `app/engine/agentic_rag/corrective_rag_runtime_support.py`
2. `app/services/chat_orchestrator_support.py`

---

## 3. Files Modified

1. `app/engine/agentic_rag/corrective_rag.py`
2. `app/services/chat_orchestrator.py`

---

## 4. Corrective RAG Refactor

### New support module

`app/engine/agentic_rag/corrective_rag_runtime_support.py`

Extracted responsibilities:

- cache-hit adaptation and result shaping
- thinking payload shaping
- evidence image collection
- final `CorrectiveRAGResult` assembly

### What stayed in `corrective_rag.py`

To avoid breaking source-inspection tests, the shell file still visibly owns:

- `aembed_query` calls
- `org_id=_org` / `org_id=_cache_org` cache parameter markers
- main orchestration flow inside `process()`

### Line count

- `corrective_rag.py`: `998 -> 914`

### Why this cut was careful

There are branch tests that inspect the source text of `corrective_rag.py` directly:

- require at least 3 `aembed_query` occurrences
- require `org_id=` keyword usage in the file

This round preserved those expectations while still reducing orchestration bloat.

---

## 5. Chat Orchestrator Refactor

### New support module

`app/services/chat_orchestrator_support.py`

Extracted responsibilities:

- `finalize_response_turn` side effects
- pronoun-style load/persist helpers
- previous-session auto-summary scheduling

### Public compatibility preserved

The `ChatOrchestrator` class still exposes:

- `finalize_response_turn()`
- `_load_pronoun_style_from_facts()`
- `_persist_pronoun_style()`
- `_maybe_summarize_previous_session()`

These methods now delegate to the support module, which keeps tests and downstream patch points stable.

### Compatibility fix applied

One regression appeared because older tests patch `chat_orchestrator.logger`, while the new helper initially logged from its own module.

Fix:

- `finalize_response_turn_impl()` now accepts `logger_obj`
- `chat_orchestrator.py` passes its module logger through

This restored legacy observable behavior without re-inlining the logic.

### Line count

- `chat_orchestrator.py`: `935 -> 824`

---

## 6. Verification

### Compile

Passed:

- `app/engine/agentic_rag/corrective_rag.py`
- `app/engine/agentic_rag/corrective_rag_runtime_support.py`
- `app/services/chat_orchestrator.py`
- `app/services/chat_orchestrator_support.py`

### Test batches that passed

1. Corrective RAG unit batch
   - `tests/unit/test_corrective_rag_unit.py`
   - Result: `19 passed`

2. Source-inspection compatibility batch
   - `tests/unit/test_sprint41_async_embeddings.py`
   - `tests/unit/test_sprint175b_isolation_hardening.py`
   - filtered to `corrective_rag`
   - Result: `6 passed, 65 deselected`

3. RAG integration-adjacent batch
   - `tests/unit/test_rag_agent_node.py`
   - `tests/unit/test_sprint179_visual_rag.py`
   - `tests/unit/test_sprint182_graph_rag.py`
   - `tests/unit/test_sprint189_rag_integrity.py`
   - Result: `158 passed`

4. Chat orchestrator compatibility batch
   - `tests/unit/test_chat_orchestrator.py`
   - `tests/unit/test_chat_request_flow.py`
   - `tests/unit/test_chat_stream_coordinator.py`
   - `tests/unit/test_sprint79_memory_hardening.py`
   - filtered to orchestrator/finalize/pronoun/summarize helpers
   - Result: `26 passed, 47 deselected`

### Broader chat batch status

This broader batch surfaced one existing branch-local issue not introduced by this refactor:

- `tests/unit/test_chat_request_flow.py::test_process_with_multi_agent_preserves_runtime_provider_metadata`
- observed: expected `glm-5`, got `glm-4.5-air`

This appears related to runtime provider/model metadata resolution, not to the support extraction done here.

---

## 7. Sentrux

Latest gate result:

- `Quality: 3581 -> 3598`
- `Coupling: 0.36 -> 0.33`
- `Cycles: 8 -> 8`
- `God files: 9 -> 4`
- `Distance from Main Sequence: 0.36`
- Verdict: `No degradation detected`

---

## 8. Architecture Effect

This round improved the codebase in two useful ways:

1. `CorrectiveRAG` now reads more like a pipeline owner instead of a mixed orchestration-plus-support blob.
2. `ChatOrchestrator` now better matches clean architecture boundaries:
   - shell owns request flow
   - support module owns post-response side effects and Sprint 79 persistence helpers

This does not directly fix Wiii thinking, but it reduces the structural friction that makes those fixes difficult.

---

## 9. Recommended Next Cuts

Best next structural targets:

1. `app/services/llm_runtime_audit_service.py`
2. `app/engine/multi_agent/graph.py`
3. `app/engine/multi_agent/graph_streaming.py`
4. `app/engine/multi_agent/direct_execution.py`

Avoid for now unless handled as a dedicated stabilization task:

1. `app/engine/tools/visual_tools.py`

That file still has branch-local test debt from an unfinished extraction and should be treated as its own refactor track.
