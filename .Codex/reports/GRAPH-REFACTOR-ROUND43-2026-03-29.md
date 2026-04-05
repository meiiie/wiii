# Graph Refactor Round 43

Date: 2026-03-29

## Scope

This round targeted the last meaningful architectural cycle that still showed up when the codebase was analyzed at a broader package/layer level:

- `GraphRAG / corrective_rag / rag_tools / multi_agent.agents`

The key smell was that GraphRAG internals still depended directly on:

- `app.engine.multi_agent.agents.kg_builder_agent`

That is a backwards dependency from retrieval infrastructure into multi-agent adapters.

## Findings

Module-level SCC scans were already clean, but a broader package-style scan still found a cycle through:

- `app.engine.agentic_rag.graph_rag_retriever`
- `app.services.graph_rag_service`
- `app.engine.multi_agent.agents`
- `app.engine.tools.rag_tools`
- `app.engine.agentic_rag.corrective_rag*`

The worst edge was:

- `graph_rag_retriever -> multi_agent.agents.kg_builder_agent`
- `graph_rag_service -> multi_agent.agents.kg_builder_agent`

## Changes

### 1. Extract neutral KG builder service

Created:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\kg_builder_service.py`

Moved core KG extraction concerns into the neutral engine layer:

- `EntityItem`
- `RelationItem`
- `ExtractionOutput`
- `SYSTEM_PROMPT`
- `KGBuilderService`
- `get_kg_builder_service()`

This module contains extraction/runtime behavior only and does not depend on multi-agent adapters.

### 2. Convert the old multi-agent KG builder into an adapter

Updated:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\kg_builder_agent.py`

Now:

- reuses the neutral extraction service
- keeps the legacy multi-agent surface
- keeps `process(...)` for graph usage
- keeps `get_kg_builder_agent()` singleton for existing agent/tests

### 3. Rewire GraphRAG to the neutral service

Updated:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\agentic_rag\graph_rag_retriever.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\services\graph_rag_service.py`

They now depend on:

- `app.engine.kg_builder_service`

instead of:

- `app.engine.multi_agent.agents.kg_builder_agent`

### 4. Test patch-path updates

Updated:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_sprint182_graph_rag.py`

Patch target now points at:

- `app.engine.kg_builder_service.get_kg_builder_service`

instead of the old multi-agent path.

## Compatibility fix

After extraction, KG builder tests revealed that the service no longer matched the historical structured-output contract expected by existing tests.

Fixed in:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\kg_builder_service.py`

Behavior now:

- if `with_structured_output(...)` is available, the service builds and uses `_structured_llm`
- `extract(...)` prefers `_structured_llm.ainvoke(messages)` for compatibility
- otherwise it falls back to `StructuredInvokeService.ainvoke(...)`

This restored the old test contract while keeping the new architecture boundary.

## Validation

### Compile

Passed:

- `kg_builder_service.py`
- `kg_builder_agent.py`
- `graph_rag_retriever.py`
- `graph_rag_service.py`

### Tests

Passed:

- `tests/unit/test_kg_builder_agent_node.py`
- `tests/unit/test_sprint182_graph_rag.py`
- `tests/unit/test_sprint52_ingestion_service.py`

Result:

- `91 passed`

## Cycle measurements

### Custom package-style scan

After the KG builder extraction:

- `pkg3 SCC count: 0`

So the last real package-level cycle identified by the custom scan is gone.

### Sentrux

Latest gate:

- `Quality: 5944`
- `Coupling: 0.28`
- `Cycles: 1`
- `God files: 0`
- `Distance from Main Sequence: 0.31`
- Verdict: `No degradation detected`

Delta from original baseline:

- `Quality: 3581 -> 5944`
- `Coupling: 0.36 -> 0.28`
- `Cycles: 8 -> 1`
- `God files: 9 -> 0`

## Assessment

This round was not just line-splitting. It corrected a real architectural direction error:

- GraphRAG infrastructure no longer depends on multi-agent adapters for entity extraction.
- KG extraction now lives in the engine layer where both GraphRAG and the multi-agent adapter can depend on it.
- This is a materially cleaner dependency direction for future retrieval and thinking work.

At this point:

- module-level SCCs are clean
- package-level SCCs found by the custom scan are clean
- the remaining `Sentrux Cycles: 1` likely comes from a broader internal heuristic rather than a plain Python import/package cycle
