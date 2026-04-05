# Graph Refactor Round 22 — Main + Product Search Runtime Split

> Date: 2026-03-29
> Scope: Continue structural refactor only. No thinking changes in this round.

---

## 1. Summary

This round targeted two high-ROI seams that were still concentrating too much orchestration logic:

- `app/main.py`
- `app/engine/multi_agent/agents/product_search_node.py`

Both files are now thin compatibility shells. Heavy startup/shutdown orchestration and product-search ReAct runtime were extracted into dedicated support modules.

Result:

- `main.py`: `850 -> 213` lines
- `product_search_node.py`: `853 -> 269` lines
- Sentrux:
  - `Quality: 3581 -> 4424`
  - `Coupling: 0.36 -> 0.31`
  - `Cycles: 8 -> 8`
  - `God files: 9 -> 3`
  - Verdict: `No degradation detected`

This is the largest structural improvement of the refactor campaign so far.

---

## 2. Files Added

- `app/main_runtime_support.py`
- `app/main_app_factory_support.py`
- `app/engine/multi_agent/agents/product_search_runtime.py`

---

## 3. Files Modified

- `app/main.py`
- `app/engine/multi_agent/agents/product_search_node.py`

---

## 4. Main.py Refactor

### 4.1 New module: `app/main_runtime_support.py`

Extracted startup/shutdown orchestration into dedicated helpers:

- startup banner + observability init
- DB / Neo4j / pgvector validation
- prompt loader validation
- domain discovery
- optional migrations
- persisted runtime policy restore
- LMS connector bootstrap
- LLM pool / agent registry / audit scheduling
- unified client init
- embedding dimension validation
- RAG / CorrectiveRAG / graph prewarm
- startup health check
- course generation recovery
- MCP client init
- scheduler start
- living agent start
- soul bridge start
- shutdown cleanup for all corresponding resources

### 4.2 New module: `app/main_app_factory_support.py`

Extracted app factory helpers:

- CORS config builder
- Session middleware wiring
- core middleware wiring
- exception handler registration
- API router inclusion
- agent card endpoint registration
- MCP server mount
- embed/web static mount logic

### 4.3 Result

`app/main.py` now acts as:

- entrypoint shell
- lifespan wrapper
- app factory shell
- exception handlers
- root + health endpoints

This makes future startup policy changes much safer and easier to test in isolation.

---

## 5. Product Search Node Refactor

### 5.1 New module: `app/engine/multi_agent/agents/product_search_runtime.py`

Extracted:

- `init_llm_impl(...)`
- `react_loop_impl(...)`

Moved heavy responsibilities out of the node shell:

- tool-aware LLM initialization
- runtime tool selection
- query planner pre-step
- multimodal image prompt injection
- streamed thinking / answer event fan-out
- tool execution loop
- preview emission
- post-loop curation
- final synthesis

### 5.2 Compatibility preserved

`product_search_node.py` still re-exports legacy constants/helpers relied on by tests and import sites:

- `_SYSTEM_PROMPT`
- `_DEEP_SEARCH_PROMPT`
- `_iteration_label`
- `_PRODUCT_RESULT_TOOLS`
- `_emit_product_previews`

`ProductSearchAgentNode._init_llm()` and `ProductSearchAgentNode._react_loop()` remain public methods, but now delegate into runtime helpers.

### 5.3 Result

`product_search_node.py` is now mostly:

- constants / compatibility surface
- `process(...)`
- thin wrapper methods
- extract helpers
- singleton access

This is a much healthier ownership boundary for a multi-step tool node.

---

## 6. Validation

### 6.1 Compile

Passed:

```bash
python -m py_compile app/main.py app/main_runtime_support.py app/main_app_factory_support.py \
  app/engine/multi_agent/agents/product_search_node.py \
  app/engine/multi_agent/agents/product_search_runtime.py
```

### 6.2 Focused pytest batches

Passed:

- `tests/unit/test_product_search_tools.py`
- `tests/unit/test_sprint150_deep_search.py`
- `tests/unit/test_sprint200_visual_search.py`
- `tests/unit/test_alembic_startup.py`
- `tests/unit/test_sprint175_web_deployment.py`

Counts:

- product-search batch: `121 passed`
- startup/web-deployment batch: `61 passed`

### 6.3 Known unrelated local-environment drift

Observed but not treated as regressions from this round:

1. `tests/unit/test_sprint197_query_planner.py`
   - local runtime currently reports no selectable provider for some planner paths
   - failures are quota/runtime-availability related, not caused by the extraction itself

2. `tests/unit/test_living_agent_integration.py`
3. `tests/unit/test_sprint178_admin_compliance.py`
   - local environment has `sqlalchemy.orm.DeclarativeBase` import mismatch
   - this is an environment/package issue already present in this machine state

---

## 7. Sentrux

Command:

```powershell
E:\Sach\Sua\AI_v1\tools\sentrux.exe gate .
```

Workdir:

```text
E:\Sach\Sua\AI_v1\maritime-ai-service\app
```

Result:

- `Quality: 4424`
- `Coupling: 0.31`
- `Cycles: 8`
- `God files: 3`
- `Distance from Main Sequence: 0.32`
- `No degradation detected`

Interpretation:

- coupling improved materially
- god-file concentration dropped again
- the codebase is moving toward a far more maintainable orchestration shape

---

## 8. Highest Remaining Hotspots

Top large files now:

- `app/core/config/_settings.py` — `1143`
- `app/repositories/semantic_memory_repository.py` — `874`
- `app/repositories/fact_repository.py` — `843`
- `app/engine/multi_agent/subagents/search/workers.py` — `840`
- `app/api/v1/living_agent.py` — `837`
- `app/engine/multi_agent/agents/tutor_node.py` — `836`
- `app/engine/search_platforms/adapters/browser_base.py` — `830`
- `app/engine/multi_agent/graph.py` — `830`

Most likely remaining Sentrux god-file candidates are now driven by structural density, not just raw LOC.

---

## 9. Recommended Next Cuts

Best next ROI for structural cleanup:

1. `app/core/config/_settings.py`
   - split field groups / validation / runtime helpers further

2. `app/repositories/semantic_memory_repository.py`
   - split summary / cleanup / search helpers into support modules

3. `app/engine/multi_agent/subagents/search/workers.py`
   - isolate worker runtime loops and result merging

4. `app/api/v1/living_agent.py`
   - split response models / endpoint support / orchestration shell

5. `app/engine/multi_agent/agents/tutor_node.py`
   - same playbook used successfully on `product_search_node.py`

---

## 10. Verdict

This round is a strong structural win.

- the application entrypoint is no longer a massive startup monolith
- the product-search node no longer owns its full ReAct engine inline
- Sentrux shows a real architecture improvement, not just cosmetic file splitting

This directly supports the long-term goal: making future `thinking` fixes easier because orchestration, runtime loops, and public surface logic are becoming separable again.
