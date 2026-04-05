# Graph / Prompt Refactor Round 8

> Date: 2026-03-28  
> Scope: continue structural cleanup for backend orchestration and prompt-loading seams  
> Goal: reduce god-file pressure, lower cross-cutting ownership, keep behavior stable

## 1. What Changed

### 1.1 `graph_streaming.py`
- Extracted merged-bus handling into [graph_stream_merge_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_stream_merge_runtime.py)
- Added:
  - `handle_bus_message_impl(...)`
  - `drain_pending_bus_events_impl(...)`
- Removed one unreachable supervisor branch that lived after `continue`
- Result: [graph_streaming.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_streaming.py) now keeps the main loop but delegates queue/soul-buffer/drain details

### 1.2 `prompt_loader.py`
- Extracted page-context formatting into [prompt_page_context.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/prompts/prompt_page_context.py)
- Extracted persona loading/template helpers into [prompt_persona_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/prompts/prompt_persona_runtime.py)
- Kept public API stable:
  - `format_page_context_for_prompt(...)`
  - `PromptLoader._load_personas()`
  - `PromptLoader._load_identity()`
  - `PromptLoader._load_shared_config()`
  - `PromptLoader._load_domain_shared_config()`
  - `PromptLoader._get_default_persona()`
  - `PromptLoader.get_persona()`
  - `PromptLoader._replace_template_variables()`
- Result: [prompt_loader.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/prompts/prompt_loader.py) is now more of a shell around prompt assembly instead of also owning file IO and page-context formatting

### 1.3 `supervisor.py`
- Extracted prompt/routing contract data into [supervisor_contract.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/supervisor_contract.py)
- Moved out:
  - routing prompt templates
  - synthesis prompt templates
  - keyword lists and fast-turn markers
  - routing thresholds / heartbeat interval / mixed-intent pairs
- Result: [supervisor.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/supervisor.py) now focuses more on routing behavior and agent orchestration

### 1.4 Small regression fix
- Restored missing `re` import in [agent_nodes.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/agent_nodes.py) so greeting-strip behavior keeps working after earlier extraction

## 2. Line Count Snapshot

- [graph.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py): `1394`
- [graph_streaming.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_streaming.py): `1356`
- [supervisor.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/supervisor.py): `1032`
- [prompt_loader.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/prompts/prompt_loader.py): `1078`
- [llm_pool.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/llm_pool.py): `1304`

## 3. Verification

### Compile
- `python -m py_compile ...graph_streaming.py ...graph_stream_merge_runtime.py`
- `python -m py_compile ...prompt_loader.py ...prompt_page_context.py ...prompt_persona_runtime.py ...agent_nodes.py`
- `python -m py_compile ...supervisor.py ...supervisor_contract.py`

### Tests
- [test_sprint54_graph_streaming.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_sprint54_graph_streaming.py): `40 passed`
- [test_graph_routing.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_graph_routing.py) + [test_supervisor_agent.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_supervisor_agent.py): `119 passed`
- [test_sprint221_page_context.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_sprint221_page_context.py): `15 passed`
- [test_sprint87_wiii_identity.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_sprint87_wiii_identity.py) subset (`WiiiIdentityLoading or GetIdentity or BugC1Fix`): `18 passed`
- [test_sprint203_natural_conversation.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_sprint203_natural_conversation.py) subset (`GreetingStripBypass or strip_greeting_prefix_unchanged`): `5 passed`

### Notes on broader prompt suite
- A wider prompt-oriented batch still contains existing repo drift unrelated to this extraction:
  - runtime/provider availability assumptions in some direct-node tests
  - older expectation mismatches around prompt wording/content
  - a few visual example assertions tied to current YAML content
- Those were not introduced by this round; the targeted seam tests above stayed green

## 4. Sentrux

Latest gate:

- `Quality: 3581 -> 3584`
- `Coupling: 0.36 -> 0.34`
- `Cycles: 8 -> 8`
- `God files: 9 -> 7`
- `Distance from Main Sequence: 0.36`
- Verdict: `No degradation detected`

## 5. Architectural Impact

This round improved the project in 3 useful ways:

1. `graph_streaming` now owns less queue choreography detail in its main loop.
2. `prompt_loader` no longer mixes prompt assembly with persona repository concerns and page-context formatting.
3. `supervisor` no longer embeds a large prompt/keyword contract blob inline.

Taken together, these changes make the next cuts safer:
- [llm_pool.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/llm_pool.py)
- [visual_tools.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/tools/visual_tools.py)
- [app/api/v1/admin.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/admin.py)

## 6. Recommended Next Cuts

### Priority 1
- Extract provider-selection / route-resolution helpers from [llm_pool.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/llm_pool.py)

### Priority 2
- Split artifact/chart/widget builders out of [visual_tools.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/tools/visual_tools.py)

### Priority 3
- Separate admin route handlers from analytics/compliance helpers inside [app/api/v1/admin.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/admin.py)
