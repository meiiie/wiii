# Graph Refactor Round 29 — 2026-03-29

## Scope

Round 29 continued the clean-architecture refactor without touching thinking behavior directly.

This round focused on three shells that were still carrying too much runtime logic:

1. `app/services/chat_orchestrator.py`
2. `app/engine/reasoning/reasoning_narrator.py`
3. `app/engine/model_catalog.py`

The goal was to keep public contracts stable while moving heavy implementations into support/runtime modules.

---

## Changes

### 1. `chat_orchestrator.py` → thinner orchestration shell

Created:

- `app/services/chat_orchestrator_runtime.py`

Updated:

- `app/services/chat_orchestrator.py`

What changed:

- `prepare_turn()` now delegates to `prepare_turn_impl(...)`
- `_process_with_multi_agent()` now delegates to `process_with_multi_agent_impl(...)`
- `process()` source/ordering was intentionally left intact for source-inspection tests and flow readability
- request/turn preparation logic moved out of the shell while preserving:
  - `PreparedTurn`
  - `RequestScope`
  - `ChatOrchestrator.process()`
  - `ChatOrchestrator.process_without_multi_agent()`

Line count:

- `chat_orchestrator.py`: `824 -> 616`
- `chat_orchestrator_runtime.py`: `178`

### 2. `reasoning_narrator.py` → shell + support split

Created:

- `app/engine/reasoning/reasoning_narrator_support.py`

Updated:

- `app/engine/reasoning/reasoning_narrator.py`

What changed:

- pure helper logic moved out of narrator shell
- public sanitizer functions and narrator class remained in place
- this is especially valuable for future `thinking` work because the narrator shell is now much easier to reason about

Line count:

- `reasoning_narrator.py`: `793 -> 357`
- `reasoning_narrator_support.py`: `344`

### 3. `model_catalog.py` → service facade + runtime support

Created:

- `app/engine/model_catalog_service_runtime.py`

Updated:

- `app/engine/model_catalog.py`

What changed:

- runtime discovery methods now delegate to service-runtime helpers:
  - Google discovery
  - OpenAI-compatible discovery
  - Ollama discovery
  - full catalog assembly
  - cache reset
- `ModelCatalogService` remains the public, patchable facade used by admin/runtime tests
- static catalog definitions stay in `model_catalog.py`

Line count:

- `model_catalog.py`: `704 -> 453`
- `model_catalog_service_runtime.py`: `414`

---

## Verification

### Compile

Passed:

- `app/services/chat_orchestrator.py`
- `app/services/chat_orchestrator_runtime.py`
- `app/engine/reasoning/reasoning_narrator.py`
- `app/engine/reasoning/reasoning_narrator_support.py`
- `app/engine/model_catalog.py`
- `app/engine/model_catalog_service_runtime.py`

### Tests

Passed:

- `tests/unit/test_reasoning_narrator_runtime.py`
- `tests/unit/test_graph_routing.py`
- `84 passed`

Passed:

- `tests/unit/test_model_catalog.py`
- `tests/unit/test_model_catalog_service.py`
- `tests/unit/test_llm_runtime_audit_service.py`
- `35 passed`

Blocked by local environment drift, not by this refactor:

- `tests/unit/test_chat_orchestrator.py`
- `tests/unit/test_chat_request_flow.py`

Observed blocker:

- `ImportError: cannot import name 'DeclarativeBase' from sqlalchemy.orm`

Import chain:

- `chat_orchestrator -> session_manager -> chat_history_repository -> app.models.database`

This same local SQLAlchemy mismatch has already appeared in other unrelated test paths, so it should not be counted as a regression from Round 29.

---

## Structural Impact

Current measured line counts of the newly touched files:

- `app/services/chat_orchestrator.py`: `616`
- `app/services/chat_orchestrator_runtime.py`: `178`
- `app/engine/reasoning/reasoning_narrator.py`: `357`
- `app/engine/reasoning/reasoning_narrator_support.py`: `344`
- `app/engine/model_catalog.py`: `453`
- `app/engine/model_catalog_service_runtime.py`: `414`

Top remaining large files in `app/` after this round:

1. `app/core/config/_settings.py` — `998`
2. `app/engine/multi_agent/graph.py` — `737`
3. `app/engine/agentic_rag/corrective_rag.py` — `734`
4. `app/engine/multi_agent/supervisor.py` — `683`
5. `app/api/v1/admin_llm_runtime.py` — `674`
6. `app/services/input_processor.py` — `673`
7. `app/api/v1/course_generation_runtime.py` — `672`

### Sentrux

Latest gate:

- `Quality: 3581 -> 4408`
- `Coupling: 0.36 -> 0.30`
- `Cycles: 8 -> 8`
- `God files: 9 -> 3`
- `Distance from Main Sequence: 0.31`
- `No degradation detected`

---

## Assessment

Round 29 improved architecture in the exact area that has been slowing future thinking work:

- narrator shell is now small enough to refactor behavior intentionally later
- chat orchestrator is more clearly a pipeline shell instead of a mixed shell/runtime blob
- model catalog runtime discovery is no longer inflating the static catalog module

This round did **not** attempt to change visible thinking quality. It reduced structural friction around the modules that future thinking work will depend on.

---

## Next Recommended Cuts

Highest-ROI next targets:

1. `app/services/input_processor.py`
   - careful split only if source-inspection constraints are preserved
2. `app/api/v1/admin_llm_runtime.py`
   - extract update/build helpers into runtime support
3. `app/core/config/_settings.py`
   - highest blast radius, but still the biggest remaining god-file candidate

Conservative recommendation:

- do `admin_llm_runtime.py` before `_settings.py`
- treat `input_processor.build_context()` as a guarded extraction because tests inspect its source
