# Graph Refactor Round 30 — 2026-03-29

## Scope

Round 30 continued the clean-architecture pass on the runtime/admin seam.

This round focused on:

1. `app/api/v1/admin_llm_runtime.py`
2. stabilizing the post-Round-29 catalog/runtime shell split

---

## Changes

### `admin_llm_runtime.py` → shell + support split

Created:

- `app/api/v1/admin_llm_runtime_support.py`

Updated:

- `app/api/v1/admin_llm_runtime.py`

What changed:

- moved the heavy async runtime flows into support functions:
  - `build_model_catalog_response_runtime_impl(...)`
  - `update_llm_runtime_config_runtime_impl(...)`
- kept the public helper surface stable in `admin_llm_runtime.py`:
  - `build_model_catalog_response_impl(...)`
  - `update_llm_runtime_config_impl(...)`
  - all existing helper utilities still live in the original module
- preserved admin/router integration via `app/api/v1/admin.py`

Line count:

- `admin_llm_runtime.py`: `674 -> 361`
- `admin_llm_runtime_support.py`: `385`

### Ongoing consistency

Also validated that the prior round's shell splits remained intact:

- `chat_orchestrator.py`: `616`
- `reasoning_narrator.py`: `357`
- `model_catalog.py`: `453`

---

## Verification

### Compile

Passed:

- `app/api/v1/admin_llm_runtime.py`
- `app/api/v1/admin_llm_runtime_support.py`
- `app/engine/model_catalog.py`
- `app/engine/model_catalog_service_runtime.py`
- `app/services/chat_orchestrator.py`
- `app/services/chat_orchestrator_runtime.py`

### Tests

Passed:

- `tests/unit/test_model_catalog.py`
- `tests/unit/test_model_catalog_service.py`
- `30 passed`

Observed failures in broader admin/runtime smoke batch:

- `tests/unit/test_admin_llm_runtime.py`
- `tests/unit/test_runtime_endpoint_smoke.py`

Failure classes:

1. Local environment drift
   - `ImportError: cannot import name 'DeclarativeBase' from sqlalchemy.orm`
   - trigger path goes through `app.services.chat_service` patch/import
   - this is the same local SQLAlchemy mismatch already seen in other paths

2. Existing smoke/schema drift
   - one smoke helper expected fields that do not match the current `LlmRuntimeConfigResponse`
   - one chat sync smoke expected a specific metadata `model` value but received empty metadata in the mocked path

These failures do **not** indicate a direct compile/runtime break in the new `admin_llm_runtime` split itself.

---

## Structural Impact

Top remaining large files after Round 30:

1. `app/core/config/_settings.py` — `998`
2. `app/engine/multi_agent/graph.py` — `737`
3. `app/engine/agentic_rag/corrective_rag.py` — `734`
4. `app/engine/multi_agent/supervisor.py` — `683`
5. `app/services/input_processor.py` — `673`
6. `app/api/v1/course_generation_runtime.py` — `672`
7. `app/engine/living_agent/emotion_engine.py` — `670`

### Sentrux

Latest gate stayed stable:

- `Quality: 3581 -> 4408`
- `Coupling: 0.36 -> 0.30`
- `Cycles: 8 -> 8`
- `God files: 9 -> 3`
- `Distance from Main Sequence: 0.31`
- `No degradation detected`

---

## Assessment

Round 30 cleaned another thick runtime shell without opening the hot chat/thinking path.

This is the right kind of refactor for the current phase:

- low product-risk
- high architectural clarity
- better separation between router/admin shell and runtime mutation logic

The next meaningful step is **not** random file slicing. It should be a deliberate choice between:

1. `input_processor.py`
   - high value, but source-inspection constraints make it a careful extraction
2. `_settings.py`
   - biggest remaining shell, but highest blast radius
3. `chat_service.py`
   - worthwhile if we want to remove eager import chains and reduce patch-time import failures

---

## Recommendation

Best next round:

1. refactor `chat_service.py` imports/lifecycle lazily
2. then take `input_processor.py` with a guarded wrapper strategy
3. leave `_settings.py` for a separate, dedicated pass
