# Living Routing Hotfix - 2026-03-25

## Goal

Stop the most harmful regressions where:

- short companion turns fell into knowledge/RAG behavior
- direct lane could still pull `tool_knowledge_search`
- CRAG leaked `0-doc` retrieval surface and robotic fallback text to users

## Implemented

### 1. Short natural questions no longer auto-use compact routing

Files:

- `maritime-ai-service/app/engine/multi_agent/supervisor.py`
- `maritime-ai-service/tests/unit/test_supervisor_agent.py`

Change:

- added `_looks_like_short_natural_question()`
- `_should_use_compact_routing_prompt()` no longer enables compact routing just because a turn is short
- compact prompt remains for fast chatter, short capability probes, and truly tiny fragments

Effect:

- turns like `co the uong ruou thuong trang khong ?` no longer get squeezed through the brittle short-turn compact prompt

### 2. Direct lane no longer binds KB search by default

Files:

- `maritime-ai-service/app/engine/multi_agent/graph.py`
- `maritime-ai-service/tests/unit/test_graph_routing.py`
- `maritime-ai-service/tests/unit/test_sprint214_org_knowledge_retrieval.py`

Change:

- `tool_knowledge_search` is now gated by explicit retrieval intent
- `_needs_direct_knowledge_search()` only enables KB search for clear internal-doc / KB / file lookup turns
- `_direct_required_tool_names()` follows the same gate

Effect:

- companion/social/off-topic/visual turns in `direct` stop dragging CRAG back into the surface

### 3. CRAG surface is sanitized

Files:

- `maritime-ai-service/app/engine/agentic_rag/corrective_rag.py`
- `maritime-ai-service/app/engine/multi_agent/agents/rag_node.py`
- `maritime-ai-service/app/engine/tools/rag_tools.py`
- `maritime-ai-service/tests/unit/test_corrective_rag_unit.py`
- `maritime-ai-service/tests/unit/test_rag_agent_node.py`
- `maritime-ai-service/tests/unit/test_sprint52_rag_tools.py`

Change:

- suppress raw retrieval wording like `Tim thay 0 tai lieu lien quan`
- replace hard fallback surface with a neutral house-friendly transition
- sanitize `rag_node` thinking before it reaches UI
- sanitize direct-lane KB tool answers so domain fallback/apology text does not leak raw

Effect:

- even if retrieval finds no matching docs, user-facing surfaces do not show the old `0-doc` CRAG trace

## Verification

### Targeted regression suite

Command group result:

- `164 passed`

Covered files:

- `test_graph_routing.py`
- `test_supervisor_agent.py`
- `test_corrective_rag_unit.py`
- `test_rag_agent_node.py`
- `test_sprint52_rag_tools.py`
- `test_sprint214_org_knowledge_retrieval.py`

### Live runtime checks

`GET /api/v1/llm/status`

- `google = disabled/busy`
- `zhipu = selectable`
- `ollama = disabled/host_down`

`POST /api/v1/chat` with `co the uong ruou thuong trang khong ?`

- no `tool_knowledge_search`
- `agent_type = direct`
- `model = glm-4.5-air`
- old `0-doc` surface no longer reproduced

## What Is Fixed

- the worst regression path (`short turn -> KB/CRAG surface leak`) is blocked
- auto no longer needs to bounce through busy Gemini for this case; healthy runtime truth can stay on Zhipu
- `0-doc` retrieval text is cleaned off the main surface

## What Is Still Not Finished

### 1. Provider/runtime drift

Still pending:

- request-scoped provider/model truth is not yet fully aligned across RAG/Tutor/Code Studio
- metadata can still drift from actual execution in some lanes

### 2. House-voice and semantic fit

Current live result for `co the uong ruou thuong trang khong ?` is cleaner, but still not ideal:

- it no longer goes into CRAG
- but the answer can still misread the relational tone or semantic intent

This is now a higher-level `house voice / semantic fit / living identity` problem, not a retrieval leak problem.

## Recommended Next Step

Do **not** reopen the old KB/RAG behavior.

Next fix should focus on:

1. house-voice semantic fit for short relational turns
2. provider/runtime truth alignment
3. stricter event taxonomy separation on the UI rail
