# Refactor Round 17 — Tutor / Prompt / LLM Pool Cleanup

> Date: 2026-03-28  
> Scope: structural refactor only, no thinking-specific behavior changes intended

---

## 1. Summary

This round focused on three medium-risk, high-ROI files that still concentrated too much orchestration logic:

- `app/engine/multi_agent/agents/tutor_node.py`
- `app/prompts/prompt_loader.py`
- `app/engine/llm_pool.py`

The refactor goal was to keep each file as an orchestration shell while moving pure or semi-pure helpers into dedicated support modules.

Result:

- `tutor_node.py`: `993 -> 836` lines
- `prompt_loader.py`: `997 -> 832` lines
- `llm_pool.py`: `997 -> 976` lines
- Sentrux: `Quality 3599`, `Coupling 0.33`, `God files 4`

---

## 2. Files Added

### Tutor runtime seam

- `app/engine/multi_agent/agents/tutor_request_runtime.py`

Extracted:

- `PreparedTutorRequest`
- `build_tutor_tools()`
- `_merge_tutor_context()`
- `prepare_tutor_request()`

Purpose:

- move tool bootstrap out of `TutorAgentNode.__init__`
- move request-specific provider/tool/runtime-context setup out of `TutorAgentNode.process()`

### Prompt section builders

- `app/prompts/prompt_section_builders.py`

Extracted:

- `append_identity_fallback_sections()`
- `append_style_sections()`

Purpose:

- move pure prompt assembly blocks out of `PromptLoader.build_system_prompt()`
- isolate persona/identity prose composition from loader lifecycle code

### LLM pool monitoring seam

- `app/engine/llm_pool_monitoring.py`

Extracted:

- `get_request_selectable_providers_impl()`
- `get_stats_impl()`
- `is_available_impl()`
- `record_provider_success_impl()`
- `record_provider_failure_impl()`
- `get_circuit_breaker_for_provider_impl()`
- `reset_pool_state_impl()`

Purpose:

- keep `LLMPool` focused on lifecycle/provider creation/failover
- move monitoring/circuit-breaker bookkeeping to a dedicated support module

---

## 3. Files Modified

### `app/engine/multi_agent/agents/tutor_node.py`

Changes:

- replaced inline tool-extension logic with `build_tutor_tools()`
- replaced large request-preparation block inside `process()` with `prepare_tutor_request()`
- kept `TutorAgentNode` as orchestration shell + `_react_loop()` authority

Impact:

- lower local complexity
- clearer future seam for tutor-lane thinking/runtime cleanup

### `app/prompts/prompt_loader.py`

Changes:

- identity fallback section now delegates to `append_identity_fallback_sections()`
- style/thought-process/deep-reasoning section now delegates to `append_style_sections()`

Impact:

- `PromptLoader` now owns loading and composition flow, not all section details
- prompt assembly becomes easier to test and evolve in slices

### `app/engine/llm_pool.py`

Changes:

- request-selectable provider surface moved to helper
- monitoring/stats/circuit-breaker bookkeeping moved to helper
- reset path moved to helper

Impact:

- `LLMPool` now leans more toward routing/lifecycle
- operational introspection is separated from provider creation logic

---

## 4. Verification

### Compile

- `python -m py_compile app/engine/multi_agent/agents/tutor_node.py app/engine/multi_agent/agents/tutor_request_runtime.py`
- `python -m py_compile app/prompts/prompt_loader.py app/prompts/prompt_section_builders.py`
- `python -m py_compile app/engine/llm_pool.py app/engine/llm_pool_monitoring.py`

All passed.

### Tests

#### Tutor lane

Command:

```powershell
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe -m pytest `
  tests\unit\test_tutor_agent_node.py `
  tests\unit\test_tutor_agent.py `
  tests\unit\test_sprint54_tutor_agent.py `
  tests\unit\test_sprint148_thinking_chain.py `
  -q -p no:capture --tb=short
```

Result:

- `99 passed`

#### Prompt-specific spot checks

Commands:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_sprint100_unified_prompt.py -q -p no:capture --tb=short -k "tutor_agent_unchanged or unified_prompt_still_works_for_other_roles or uses_new_tools_context_parameter"
.\.venv\Scripts\python.exe -m pytest tests\unit\test_sprint87_wiii_identity.py -q -p no:capture --tb=short -k "build_system_prompt_contains_identity_section or build_system_prompt_contains_personality_summary or build_system_prompt_contains_avoid_rules"
```

Result:

- prompt subset: `1 passed`
- identity subset: `3 passed`

Note:

- a broader prompt batch still contains existing branch-local failures in direct-node/provider and a legacy synthesis prompt assertion. These did not appear tied to this extraction and were not expanded in this round.

#### LLM runtime / failover

Command:

```powershell
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe -m pytest `
  tests\unit\test_llm_failover.py `
  tests\unit\test_llm_providers.py `
  tests\unit\test_model_catalog_service.py `
  tests\unit\test_admin_llm_runtime.py `
  -q -p no:capture --tb=short
```

Result:

- `98 passed`

### Sentrux

Command:

```powershell
$env:PYTHONIOENCODING='utf-8'
E:\Sach\Sua\AI_v1\tools\sentrux.exe gate .
```

Workdir:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app`

Result:

- `Quality: 3581 -> 3599`
- `Coupling: 0.36 -> 0.33`
- `Cycles: 8 -> 8`
- `God files: 9 -> 4`
- `No degradation detected`

---

## 5. Current Large Files

Post-round line counts:

- `app/engine/tools/visual_tools.py` — `2757`
- `app/core/config/_settings.py` — `1689`
- `app/engine/agentic_rag/corrective_rag.py` — `998`
- `app/engine/llm_pool.py` — `976`
- `app/engine/multi_agent/graph.py` — `991`
- `app/engine/multi_agent/graph_streaming.py` — `984`

Files pushed below the 900-line threshold in this round:

- `app/engine/multi_agent/agents/tutor_node.py`
- `app/prompts/prompt_loader.py`

---

## 6. Risks / Notes

### Visual tooling remains unstable

`app/engine/tools/visual_tools.py` still has a separate experimental extraction in progress (`visual_runtime_metadata.py`) and an existing red test cluster:

- renderer kind drift (`template -> inline_html`)
- patch strategy drift (`spec_merge -> replace_html`)
- auto-grouping counts collapsing (`2/3 -> 1`)
- article figure intent drifting to `chart_runtime`

This round deliberately avoided pushing deeper there until the seam is stabilized or reverted cleanly.

### Prompt batch caveat

The broad prompt suite currently mixes:

- prompt-loader behavior
- direct-node/provider availability
- one unrelated legacy natural-conversation prompt assertion

That makes it noisy as a pure refactor gate. Future rounds should keep using tighter prompt subsets plus a separate direct-lane gate.

---

## 7. Recommended Next Cuts

Highest ROI next targets:

1. `app/engine/agentic_rag/corrective_rag.py`
2. `app/engine/llm_pool.py` (second cut if we want it under 900)
3. `app/engine/multi_agent/graph.py`
4. `app/engine/multi_agent/graph_streaming.py`

Recommended caution target:

- `app/engine/tools/visual_tools.py`

Approach for visual tools:

- either revert the unstable extraction first
- or continue only with preserved wrapper seams + a dedicated test gate

---

## 8. Verdict

This round is a net structural win:

- more orchestration shells
- less mixed responsibility in core files
- better seams for future thinking work
- improved Sentrux score without behavioral regression in validated areas

The codebase is measurably easier to extend than at the start of the round.
