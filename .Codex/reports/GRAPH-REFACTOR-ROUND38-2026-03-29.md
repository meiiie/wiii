# Graph Refactor Round 38 — Cycle Reduction Push

> Date: 2026-03-29
> Scope: structural cycle reduction across `services/`, `prompts/`, `living_agent/`, and `llm`

---

## Outcome

This round focused specifically on reducing import/dependency cycles after the
god-file campaign had already reached `God files: 0`.

### Sentrux result

- Quality: `3581 -> 5468`
- Coupling: `0.36 -> 0.30`
- Cycles: `8 -> 2`
- God files: `9 -> 0`
- Verdict: `No degradation detected`

### Local AST SCC result

- Nontrivial SCCs: `2`
- Remaining SCCs:
  - `app.engine.multi_agent` cluster (`32` modules)
  - `app.engine.llm_pool / llm_pool_support / llm_runtime_audit_service / llm_selectability_service` (`4` modules)

---

## Changes

### 1. Broke `living_continuity ↔ post_response` cycle

Created:

- `app/services/living_continuity_contracts.py`

Updated:

- `app/services/living_continuity.py`
- `app/services/lms_post_response.py`
- `app/services/routine_post_response.py`
- `app/services/sentiment_post_response.py`

What changed:

- moved `PostResponseContinuityContext` into a shared contract module
- post-response helpers no longer import `living_continuity` back, even via `TYPE_CHECKING`

Impact:

- eliminated the `living_continuity / lms_post_response / routine_post_response / sentiment_post_response` SCC

---

### 2. Broke `multimodal_ingestion_service ↔ vision_processor` cycle

Created:

- `app/services/multimodal_ingestion_contracts.py`

Updated:

- `app/services/multimodal_ingestion_service.py`
- `app/services/vision_processor.py`

What changed:

- moved `IngestionResult` and `PageResult` into a shared contracts module
- `vision_processor` now depends on contracts instead of importing back through the service shell

Impact:

- removed a tight 2-node cycle in multimodal ingestion flow

---

### 3. Broke `document_retriever ↔ rag_agent` cycle

Updated:

- `app/engine/agentic_rag/document_retriever.py`

What changed:

- switched `EvidenceImage` import to `rag_agent_contracts` instead of `rag_agent`

Impact:

- removed another 2-node `agentic_rag` cycle

---

### 4. Broke `prompt_loader ↔ prompt_loader_singleton` cycle

Updated:

- `app/prompts/prompt_loader.py`
- `app/prompts/prompt_loader_singleton.py`

What changed:

- `prompt_loader` now owns the singleton directly
- `prompt_loader_singleton` became a thin compatibility delegate
- restored prompt-context re-exports used by older tests/scripts:
  - `VALID_PRONOUN_PAIRS`
  - `INAPPROPRIATE_PRONOUNS`

Impact:

- removed the singleton loop without changing public `get_prompt_loader()` behavior

---

### 5. Broke `skill_builder ↔ skill_learner` cycle

Created:

- `app/engine/living_agent/skill_singleton_registry.py`

Updated:

- `app/engine/living_agent/skill_builder.py`
- `app/engine/living_agent/skill_learner.py`

What changed:

- introduced a shared singleton registry/factory module
- builder and learner no longer import each other just to fetch singleton accessors

Impact:

- removed the living-agent skill 2-node cycle

---

### 6. Broke `journal → heartbeat` edge inside living-agent SCC

Created:

- `app/engine/living_agent/heartbeat_runtime_state.py`

Updated:

- `app/engine/living_agent/heartbeat.py`
- `app/engine/living_agent/heartbeat_runtime_support.py`
- `app/engine/living_agent/journal.py`

What changed:

- introduced a lightweight runtime state module for `heartbeat_count`
- `journal.py` now reads `heartbeat_count` from shared runtime state instead of importing `heartbeat.py`

Impact:

- collapsed the old `heartbeat / heartbeat_action_runtime / journal / reflector` SCC

---

### 7. Shrunk the LLM SCC

Updated:

- `app/engine/llm_pool.py`
- `app/engine/llm_providers/vertex_provider.py`

What changed:

- inlined convenience wrappers into `llm_pool.py` to remove the `llm_pool ↔ llm_pool_public` loop
- `vertex_provider` now gets its circuit breaker from `app.core.resilience` directly instead of importing `llm_pool`

Impact:

- reduced the LLM SCC from `9` modules down to `4`
- helped pull total cycle count down to `2`

---

## Validation

### Compile

- `py_compile` passed for all files touched in this round

### Focused tests

- ingestion/vision/RAG batch: `33 passed`
- prompt/pronoun/living-identity batch: `34 passed`
- LLM/runtime/admin batch: `94 passed`

### Known pre-existing drift still visible

- `tests/unit/test_sprint87_wiii_identity.py::TestDirectNodeUsesIdentity::*`
  - failing because `direct_node_runtime` still hits
    `_collect_direct_tools() got an unexpected keyword argument 'state'`
  - this is a direct-lane regression debt, not caused by the cycle refactors here
- broader chat/session batches still hit local environment drift around:
  - `sqlalchemy.orm.DeclarativeBase`

---

## Why this matters for future thinking work

The system is now materially easier to reason about:

- post-response orchestration no longer depends on reverse helper imports
- prompt singleton access is no longer a cycle
- living-agent skill subsystems no longer fetch each other through module loops
- journal no longer drags the scheduler module back into the living-agent chain
- the LLM layer has fewer facade/runtime loops

That means future `thinking` work can target:

- public-thinking ownership
- stream surface contracts
- narrator/direct lane behavior

without having to push through as many structural import loops first.

---

## Recommended next refactor targets

Only two SCCs remain.

### Target A — multi-agent SCC (`32` modules)

This is still the biggest structural knot, but it is now isolated.
Best next cuts:

- runtime contracts around `graph / graph_streaming / supervisor`
- tool/runtime context seam reduction
- subagent/search isolation from main graph shell

### Target B — llm SCC (`4` modules)

Modules:

- `app.engine.llm_pool`
- `app.engine.llm_pool_support`
- `app.services.llm_runtime_audit_service`
- `app.services.llm_selectability_service`

Likely next low-risk seam:

- remove `llm_pool_support -> llm_selectability_service` direct dependency
- replace with snapshot/runtime contract or callback-based support

