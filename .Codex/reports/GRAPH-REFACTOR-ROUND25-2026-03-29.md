# Graph Refactor Round 25

Date: 2026-03-29

## Scope

Round 25 continued the clean-architecture refactor without touching `thinking`
logic directly. This pass focused on two seams that were still carrying too
much mixed responsibility:

1. `TutorAgentNode._react_loop()` tool-dispatch branches
2. `FactRepositoryMixin` read/write CRUD bulk

The goal was to keep public/tested contracts stable while moving concrete
runtime behavior into dedicated support modules.

## Changes

### 1. Tutor tool dispatch extracted

Created:

- `app/engine/multi_agent/agents/tutor_tool_dispatch_runtime.py`

Updated:

- `app/engine/multi_agent/agents/tutor_node.py`

What changed:

- Extracted the large per-tool execution branch logic from
  `TutorAgentNode._react_loop()` into `dispatch_tutor_tool_call(...)`.
- Preserved the inspect-based source contract inside `_react_loop()`:
  - `_CHUNK_SIZE = 40`
  - `_CHUNK_DELAY = 0.008`
  - `_BULK_SIZE = 200`
  - `_push_answer_deltas`
  - `_push_answer_bulk`
- Kept patch-sensitive symbols owned by `tutor_node.py` and passed them into the
  runtime helper:
  - `tool_knowledge_search`
  - `get_tool_by_name`
  - `invoke_tool_with_runtime`
  - `get_last_confidence`
  - `_iteration_beat`
  - `_tool_acknowledgment`

Line-count impact:

- `app/engine/multi_agent/agents/tutor_node.py`: `836 -> 552`
- `app/engine/multi_agent/agents/tutor_tool_dispatch_runtime.py`: `473`

Why this cut matters:

- `_react_loop()` remains the orchestration surface.
- Tool execution details now have a single owner.
- Future `thinking` work in tutor flow can change narration/interval behavior
  without being entangled with every tool branch.

### 2. Fact repository converted to facade + runtime mixins

Created:

- `app/repositories/fact_repository_query_runtime.py`
- `app/repositories/fact_repository_mutation_runtime.py`

Replaced:

- `app/repositories/fact_repository.py`

New structure:

- `FactRepositoryQueryRuntimeMixin`
  - `get_user_facts`
  - `_apply_importance_decay`
  - `search_relevant_facts`
  - `get_all_user_facts`
  - `find_fact_by_type`
  - `find_similar_fact_by_embedding`
- `FactRepositoryMutationRuntimeMixin`
  - `update_fact`
  - `update_metadata_only`
  - `delete_oldest_facts`
- `FactRepositoryTripleMixin`
  - unchanged existing triple operations
- `FactRepositoryMixin`
  - now only a compatibility shell composing the three mixins

Line-count impact:

- `app/repositories/fact_repository.py`: `843 -> 33`
- `app/repositories/fact_repository_query_runtime.py`: `429`
- `app/repositories/fact_repository_mutation_runtime.py`: `257`

Why this cut matters:

- The repository now mirrors the pattern already used by
  `SemanticMemoryRepository`.
- Query/search logic and mutation/eviction logic are no longer packed into one
  mixin file.
- This lowers maintenance friction around semantic memory work without changing
  the public repository interface.

## Verification

### Compile

Passed:

- `python -m py_compile app/engine/multi_agent/agents/tutor_node.py app/engine/multi_agent/agents/tutor_tool_dispatch_runtime.py`
- `python -m py_compile app/repositories/fact_repository.py app/repositories/fact_repository_query_runtime.py app/repositories/fact_repository_mutation_runtime.py`

### Tutor-focused tests

Passed:

- `tests/unit/test_tutor_agent_node.py` -> `22 passed`

Passed with unrelated pre-existing drift:

- `tests/unit/test_sprint74_streaming_quality.py -k "TutorAnswerDelta or TutorFinalGenerationAnswerDelta"`
  - `6 passed`
  - `1 failed`
  - unrelated existing drift: prompt-length expectation still looks for
    `"400 từ"` while current tutor prompt intentionally says
    `"Không giới hạn cứng"`

- `tests/unit/test_sprint75_latency.py -k "BulkAnswerPush or LatencyConstants"`
  - `11 passed`
  - `1 failed`
  - unrelated existing drift: `graph._guardian_instance` compatibility
    attribute no longer exposed as that test expects

### Fact repository tests

Passed:

- `tests/unit/test_sprint51_fact_repository.py` -> `36 passed`
- `tests/unit/test_sprint137_vector_facts.py` -> `16 passed`
- `tests/unit/test_sprint170c_tenant_hardening.py -k "FactRepositoryOrgFiltering"` -> `5 passed`

Observed unrelated drift in a broader combined run:

- `tests/unit/test_sprint170c_tenant_hardening.py` has 4 failing
  `TestChatHistoryOrgFiltering` tests because
  `app.repositories.chat_history_repository` is not exposed at the patch path
  those tests expect.
- Those failures are outside the `FactRepository` refactor surface.

## Sentrux

Latest gate after Round 25:

- `Quality: 4422`
- `Coupling: 0.30`
- `Cycles: 8`
- `God files: 3`
- `Distance from Main Sequence: 0.31`
- Verdict: `No degradation detected`

Interpretation:

- This round maintained the post-refactor structural gains.
- It did not further move the top-level Sentrux headline numbers, but it
  materially reduced local complexity in two important seams.

## Current hotspot snapshot

Top remaining large files after this round:

- `app/core/config/_settings.py` -> `1143`
- `app/engine/tools/visual_html_builders.py` -> `833`
- `app/engine/multi_agent/graph.py` -> `830`
- `app/engine/search_platforms/adapters/browser_base.py` -> `830`
- `app/services/chat_orchestrator.py` -> `825`
- `app/services/llm_runtime_audit_service.py` -> `813`
- `app/engine/tools/visual_tools.py` -> `802`

## Recommended next cuts

Most promising next refactor seams:

1. `visual_html_builders.py`
   - split chart/timeline/map builders from comparison/process/matrix/core
2. `visual_tools.py`
   - continue isolating payload/runtime orchestration from tool shell
3. `_settings.py`
   - only after choosing a careful strategy for Pydantic field-group extraction
4. `browser_base.py`
   - only if wrapper compatibility for `_submit_to_pw_worker` and `_get_browser`
     is preserved, because tests patch those symbols directly

## Conclusion

Round 25 was successful.

The project is now cleaner in two concrete places:

- tutor tool execution is no longer welded into one long orchestration method
- fact repository behavior is now organized by responsibility instead of by
  historical accumulation

This does not solve `thinking` yet, but it removes more structural friction
that previously made future fixes harder than they needed to be.
