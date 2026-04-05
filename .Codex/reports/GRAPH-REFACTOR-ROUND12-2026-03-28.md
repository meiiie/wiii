# Graph Refactor Round 12 — 2026-03-28

> Scope: continue backend structural cleanup without changing thinking behavior
> Focus: `corrective_rag.py` and `fact_repository.py`

---

## 1. Summary

This round removed two more files from god-file territory by extracting clearly bounded responsibilities:

- `app/engine/agentic_rag/corrective_rag.py`
- `app/repositories/fact_repository.py`

The strategy remained the same:

1. keep public class/module contracts stable
2. move cohesive sub-responsibilities into helper modules
3. verify with focused tests and Sentrux

---

## 2. Changes

### 2.1 `CorrectiveRAG` generation helpers extracted

Created:

- `app/engine/agentic_rag/corrective_rag_generation.py`

Moved generation responsibilities out of `CorrectiveRAG`:

- `generate_fallback_impl()`
- `generate_answer_impl()`

`CorrectiveRAG` now delegates:

- `_generate_fallback()` → helper module
- `_generate()` → helper module

This keeps `corrective_rag.py` focused more on pipeline orchestration and less on prompt/model interaction details.

### 2.2 `fact_repository.py` semantic triple operations extracted

Created:

- `app/repositories/fact_repository_triples.py`

Added:

- `FactRepositoryTripleMixin`

Moved semantic triple responsibilities out of `FactRepositoryMixin`:

- `save_triple()`
- `find_by_predicate()`
- `update_memory_content()`
- `upsert_triple()`

`FactRepositoryMixin` now inherits from `FactRepositoryTripleMixin`.

This makes the repository boundary cleaner:

- `fact_repository.py` now focuses on fact CRUD / fact search
- `fact_repository_triples.py` owns semantic triple behavior

---

## 3. Size Impact

### `corrective_rag.py`

- before: `1089`
- after: `998`

New helper:

- `corrective_rag_generation.py`: `118`

### `fact_repository.py`

- before: `1122`
- after: `843`

New helper:

- `fact_repository_triples.py`: `226`

---

## 4. Verification

### Compile

Passed:

- `python -m py_compile app/engine/agentic_rag/corrective_rag.py`
- `python -m py_compile app/engine/agentic_rag/corrective_rag_generation.py`
- `python -m py_compile app/repositories/fact_repository.py`
- `python -m py_compile app/repositories/fact_repository_triples.py`

### Tests

Passed:

- `tests/unit/test_corrective_rag_unit.py` → `19 passed`
- `tests/unit/test_sprint51_fact_repository.py` + `tests/unit/test_sprint137_vector_facts.py` → `52 passed`
- `tests/unit/test_sprint170c_tenant_hardening.py -k FactRepositoryOrgFiltering` → `5 passed`

Note:

- A wider tenant-hardening batch surfaced 4 failures in `chat_history_repository` patch setup.
- Those failures are unrelated to this refactor and were reproduced outside the fact-repository scope.

### Sentrux

Latest gate:

- `Quality: 3581 -> 3593`
- `Coupling: 0.36 -> 0.34`
- `Cycles: 8 -> 8`
- `God files: 9 -> 7`
- Verdict: `No degradation detected`

---

## 5. Why This Matters

These two cuts reduce future change cost in important hot areas:

- `CorrectiveRAG` is closer to an orchestration shell, which will matter when we later revisit response/thinking integration.
- `FactRepository` now has a clearer boundary between fact retrieval and semantic-triple persistence logic.

That means:

- easier test targeting
- lower cognitive load per file
- cleaner future seams for memory and response work

---

## 6. Recommended Next Targets

Best next structural cuts:

1. `app/engine/search_platforms/adapters/browser_base.py`
2. `app/engine/multi_agent/agents/product_search_node.py`
3. `app/engine/multi_agent/agents/tutor_node.py`
4. `app/services/chat_orchestrator.py`

Lower-priority but still large:

- `app/core/config/_settings.py`
- `app/api/v1/admin.py`
- `app/api/v1/course_generation.py`

I recommend continuing with runtime-heavy but bounded modules before touching large API/config files.
