# Graph Refactor Round 31 — 2026-03-29

## Scope

Round 31 focused on two service-layer seams:

1. `app/services/chat_service.py`
2. `app/services/input_processor.py`

This round stayed aligned with the current strategy:

- keep product behavior stable
- reduce eager import chains
- make future thinking work easier by shrinking service shells

---

## Changes

### 1. `chat_service.py` → lazy shell

Created:

- `app/services/chat_service_runtime.py`

Updated:

- `app/services/chat_service.py`

What changed:

- moved heavy runtime initialization into `initialize_chat_service_runtime_impl(...)`
- `chat_service.py` no longer eagerly imports:
  - chat orchestrator
  - session manager
  - input/output processors
  - background runner
  - graph/repositories/guardrails setup
- added module-level lazy export resolution for:
  - `AgentType`
  - `ProcessingResult`
  - `SessionState`
  - `SessionContext`

Why this matters:

- importing `app.services.chat_service` is now much lighter
- patch paths like `app.services.chat_service.reset_chat_service` no longer drag the full chat/runtime stack in at import time
- this directly reduces one of the import-chain pain points seen in admin/runtime smoke tests

Line count:

- `chat_service.py`: `303 -> 119`
- `chat_service_runtime.py`: `141`

### 2. `input_processor.py` → helper extraction without touching `build_context()`

Created:

- `app/services/input_processor_support.py`

Updated:

- `app/services/input_processor.py`

What changed:

- extracted `extract_user_name()` logic into `extract_user_name_impl(...)`
- extracted `validate_pronoun_request()` logic into `validate_pronoun_request_impl(...)`
- preserved `build_context()` body shape to avoid breaking structural/source-inspection tests
- fixed the default blocked guardian message to proper Unicode:
  - `"Nội dung không phù hợp"`

Why this matters:

- service shell is smaller without destabilizing the memory/context path
- Vietnamese name extraction and pronoun validation are now isolated and easier to evolve/test

Line count:

- `input_processor.py`: `673 -> 624`
- `input_processor_support.py`: `62`

---

## Verification

### Compile

Passed:

- `app/services/chat_service.py`
- `app/services/chat_service_runtime.py`
- `app/services/input_processor.py`
- `app/services/input_processor_support.py`

### Tests

Passed:

- `tests/unit/test_sprint30_chat_service.py`
- `tests/unit/test_chat_completion_endpoint_support.py`
- `14 passed`

Passed:

- `tests/unit/test_admin_llm_runtime.py`
- `tests/unit/test_runtime_endpoint_smoke.py`
- `10 passed`

Passed:

- `tests/unit/test_input_processor.py`
- `31 passed`

Passed:

- `tests/unit/test_model_catalog.py`
- `tests/unit/test_model_catalog_service.py`
- `44 passed`

Observed unrelated pre-existing structural drift:

- `tests/unit/test_sprint122_memory_foundation.py::test_core_memory_section_empty_in_tutor_node`

This failure is about the current tutor-node source text:

- expected `core_memory_section = ""`
- actual source no longer contains that exact legacy literal

This is not a regression introduced by Round 31’s `input_processor`/`chat_service` refactor.

---

## Structural Impact

Current line counts after Round 31:

- `app/services/chat_service.py`: `119`
- `app/services/chat_service_runtime.py`: `141`
- `app/services/input_processor.py`: `624`
- `app/services/input_processor_support.py`: `62`

Top remaining large files:

1. `app/core/config/_settings.py` — `998`
2. `app/engine/multi_agent/graph.py` — `737`
3. `app/engine/agentic_rag/corrective_rag.py` — `734`
4. `app/engine/multi_agent/supervisor.py` — `683`
5. `app/api/v1/course_generation_runtime.py` — `672`
6. `app/engine/living_agent/emotion_engine.py` — `670`
7. `app/engine/tools/visual_payload_runtime.py` — `667`

### Sentrux

Latest gate:

- `Quality: 3581 -> 4408`
- `Coupling: 0.36 -> 0.30`
- `Cycles: 8 -> 8`
- `God files: 9 -> 2`
- `Distance from Main Sequence: 0.31`
- `No degradation detected`

This is the most important structural milestone of this round:

- `God files` dropped from `3` to `2`

---

## Assessment

Round 31 produced a meaningful architectural gain:

- `chat_service` is no longer a heavy import-time trap
- `input_processor` is slimmer without risking the chat-context contract
- the project now has only **2** remaining Sentrux god files

This is exactly the kind of refactor that improves future extensibility without forcing early thinking changes.

---

## Next Recommended Cuts

Best next targets:

1. `app/core/config/_settings.py`
   - biggest remaining shell
   - highest blast radius, so should be a dedicated round

2. `app/engine/agentic_rag/corrective_rag.py`
   - still large
   - good candidate for more runtime/support extraction

3. `app/engine/multi_agent/graph.py`
   - still critical to future thinking work
   - now much safer to revisit after the service-layer cleanup
