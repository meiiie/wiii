# Graph Refactor Round 21 — 2026-03-29

## Scope

Vòng này tiếp tục refactor theo mục tiêu `clean architecture / clean code`, chưa quay lại sửa `thinking`.

Trọng tâm:
- giảm trách nhiệm của các shell lớn
- giữ compatibility import cũ
- khóa lại bằng `py_compile`, batch test focused, và `Sentrux gate`

## Refactors Completed

### 1. API shell cleanup

- Tạo [course_generation_schemas.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/course_generation_schemas.py)
- Tạo [course_generation_parsers.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/course_generation_parsers.py)
- Refactor [course_generation.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/course_generation.py)
  - tách schema và parser helpers ra khỏi router shell

- Mở rộng [admin_schemas.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/admin_schemas.py)
- Refactor [admin.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/admin.py)
  - tách `DomainSummary`, `DomainDetail`, `SkillDetail` ra khỏi router shell

### 2. Settings decomposition

- Tạo [\_settings_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/core/config/_settings_runtime.py)
- Tạo [\_settings_validation.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/core/config/_settings_validation.py)
- Refactor [\_settings.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/core/config/_settings.py)
  - tách runtime URL/neo4j/nested sync helpers
  - tách validator functions và cross-field validators
  - giữ shell `Settings` tương thích ngược

### 3. Model catalog support extraction

- Tạo [model_catalog_runtime_support.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/model_catalog_runtime_support.py)
- Refactor [model_catalog.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/model_catalog.py)
  - tách cache/discovery/hash/normalize/capability merge helpers
  - vá regression `import time`

### 4. OpenSandbox shell cleanup

- Tạo [opensandbox_runtime_support.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/sandbox/opensandbox_runtime_support.py)
- Refactor [opensandbox_executor.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/sandbox/opensandbox_executor.py)
  - tách execution-result normalization
  - tách file harvest/publish/search-entry/path/read helpers
  - tách sandbox cleanup helper

### 5. Schema decomposition

- Tạo [host_context_schemas.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/models/host_context_schemas.py)
- Refactor [schemas.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/models/schemas.py)
  - tách `UserRole`, `PageContext`, `StudentPageState`, `Host*`, `UserContext`, `ImageInput`
  - giữ `schemas.py` như compatibility aggregator

### 6. Corrective RAG retrieval extraction

- Tạo [corrective_rag_retrieval_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/agentic_rag/corrective_rag_retrieval_runtime.py)
- Refactor [corrective_rag.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/agentic_rag/corrective_rag.py)
  - tách `_retrieve()` ra khỏi class shell

### 7. Context budget extraction

- Tạo [context_budget_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/context_budget_runtime.py)
- Refactor [context_manager.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/context_manager.py)
  - tách `ContextBudget`
  - tách `TokenBudgetManager`
  - giữ `ConversationCompactor` ở shell cũ
  - vá compatibility method `compute_dynamic_window()`

### 8. RAG agent contract extraction

- Tạo [rag_agent_contracts.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/agentic_rag/rag_agent_contracts.py)
- Refactor [rag_agent.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/agentic_rag/rag_agent.py)
  - tách `EvidenceImage`
  - tách `RAGResponse`
  - tách `MaritimeDocumentParser`
  - restore alias `PromptLoader` để giữ legacy patch surface cho test

### 9. Supervisor helper extraction

- Tạo [supervisor_runtime_support.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/supervisor_runtime_support.py)
- Refactor [supervisor.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/supervisor.py)
  - tách provider-selection helper
  - tách domain keyword extraction
  - tách domain routing validation
  - tách complex-query heuristic
  - sửa drift rule-based priority để khớp contract test `social > personal > domain > learning > default`

## Line Count Highlights

- [course_generation.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/course_generation.py): `786`
- [admin.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/admin.py): `615`
- [schemas.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/models/schemas.py): `670`
- [opensandbox_executor.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/sandbox/opensandbox_executor.py): `786`
- [corrective_rag.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/agentic_rag/corrective_rag.py): `771`
- [context_manager.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/context_manager.py): `594`
- [rag_agent.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/agentic_rag/rag_agent.py): `766`
- [supervisor.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/supervisor.py): `790`

## Verification

### Compile

`py_compile` passed for all newly created / modified files in this round.

### Focused test batches

- `test_course_generation_flow.py`
- `test_course_generation_source_preparation.py`
- `test_admin_llm_runtime.py`
- `test_config_validators.py`
- `test_sprint32_config_asyncpg_url.py`
- `test_model_catalog.py`
- `test_model_catalog_service.py`
- `test_opensandbox_executor.py`
- `test_opensandbox_health.py`
- `test_sandbox_service.py`
- `test_code_execution_tools.py`
- `test_sprint221_page_context.py`
- `test_chat_identity_projection.py`
- `test_input_processor.py`
- `test_artifact_streaming.py`
- `test_corrective_rag_unit.py`
- `test_sprint78_context_manager.py`
- `test_sprint116_memory_flush.py`
- `test_sprint118_block_consolidation.py`
- `test_sprint125_isolation_sweep.py`
- `test_sprint54_rag_agent.py`
- `test_rag_agent_node.py`
- `test_supervisor_agent.py`
- `test_supervisor_routing.py`
- `test_supervisor_routing_reasoning.py`
- `test_graph_routing.py`

Representative green batches from this round:
- `33 passed` catalog/admin batch
- `53 passed` opensandbox batch
- `140 passed` schemas + CRAG + input/page-context batch
- `104 passed` context-manager batch
- `70 passed` RAG-agent batch
- `160 passed` supervisor/graph-routing batch

### Known unrelated drift

- [test_sprint179_vision_charts.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_sprint179_vision_charts.py) still exposes an older config/tool-gate drift around `enable_chart_tools`, not introduced by the schema/open-sandbox/context/rag/supervisor refactors above.
- [test_sprint210g_context_layers.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_sprint210g_context_layers.py) includes a source-code assertion around `PromptLoader` wording in an endpoint path; this did not block the context-budget extraction itself.

## Sentrux

Latest run:

- Quality: `3581 -> 3604`
- Coupling: `0.36 -> 0.32`
- Cycles: `8 -> 8`
- God files: `9 -> 4`
- Verdict: `No degradation detected`

## Assessment

The refactor direction remains correct:

- orchestration shells are thinner
- compatibility imports are preserved
- focused behavior is still green under test
- coupling remains improved vs baseline

Remaining structural hotspots likely driving `god files: 4` are now more about role density than raw line count. The next likely candidates are:

1. [\_settings.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/core/config/_settings.py)
2. [main.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/main.py)
3. [semantic_memory_repository.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/repositories/semantic_memory_repository.py)
4. [product_search_node.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/agents/product_search_node.py)

These should be the next cuts if the goal remains to keep pushing architecture quality before returning to `thinking`.
