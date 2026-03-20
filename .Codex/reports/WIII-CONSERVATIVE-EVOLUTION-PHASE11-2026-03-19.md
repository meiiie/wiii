# Wiii Conservative Evolution - Phase 11

Date: 2026-03-19
Owner: Codex

## Goal

Implement the first deployable slice of the Conservative Evolution plan:

- living core contract without rewriting the graph
- memory taxonomy for prompt-time living memory
- deliberate reasoning floors for hard turns
- conservative fast routing for only the safest obvious cases
- subtle, consistent Wiii voice across agent lanes

## What changed

### 1. Living context compiler

Added `LivingContextBlockV1`, `MemoryBlockV1`, `ReasoningPolicyV1`, and `LivingExpressionPolicyV1` in:

- `maritime-ai-service/app/engine/character/living_context.py`

This compiler now produces:

- `core_card`
- `narrative_state`
- `relationship_memory`
- `task_mode`
- `reasoning_policy`
- `visual_cognition`
- `memory_blocks`
- `living_expression_policy`

### 2. Additive runtime flags

Added new feature flags in:

- `maritime-ai-service/app/core/config/_settings.py`

Flags:

- `enable_living_core_contract`
- `enable_memory_blocks`
- `enable_deliberate_reasoning`
- `enable_living_visual_cognition`
- `enable_conservative_fast_routing`

All default to `False`.

### 3. Graph integration

Integrated living context into sync and streaming graph setup:

- `maritime-ai-service/app/engine/multi_agent/graph.py`
- `maritime-ai-service/app/engine/multi_agent/graph_streaming.py`

New runtime state:

- `living_context_prompt`
- `memory_block_context`
- `reasoning_policy`

`thinking_effort` now merges with `reasoning_policy.deliberation_level` when deliberate reasoning is enabled.

### 4. Prompt-stack cleanup

PromptLoader now avoids duplicating narrative/identity injections when the living core contract is enabled:

- `maritime-ai-service/app/prompts/prompt_loader.py`

### 5. Cross-agent subtle continuity

Living context is now appended in the main agent lanes:

- direct/code studio via `graph.py`
- tutor via `tutor_node.py`
- memory via `memory_agent.py`
- product search via `product_search_node.py`
- rag context threading via `rag_node.py`
- synthesis via `supervisor.py`

### 6. Conservative fast routing

Added a narrow fast-path in:

- `maritime-ai-service/app/engine/multi_agent/supervisor.py`

It only skips the supervisor LLM for:

- obvious social turns
- obvious web/news/legal lookup turns
- obvious product search turns
- obvious code/simulation/artifact turns

Pedagogical, memory-sensitive, domain-ambiguous, and mixed-intent turns still fall through to the supervisor LLM.

### 7. Wiii skill-pack expansion

Added new Wiii-only skills:

- `.agents/skills/wiii-living-core/SKILL.md`
- `.agents/skills/wiii-memory-blocks/SKILL.md`
- `.agents/skills/wiii-deliberate-reasoning/SKILL.md`
- `.agents/skills/teaching-by-seeing/SKILL.md`
- `.agents/skills/simulation-as-understanding/SKILL.md`

### 8. Character card refinement

Updated:

- `maritime-ai-service/app/engine/character/character_card.py`

This reinforces:

- subtle living visibility
- continuity over roleplay
- visual/simulation craft identity

## Test coverage

Passed:

- `maritime-ai-service/tests/unit/test_conservative_evolution.py`
- `maritime-ai-service/tests/unit/test_supervisor_agent.py`
- `maritime-ai-service/tests/unit/test_supervisor_routing.py`
- `maritime-ai-service/tests/unit/test_sprint100_unified_prompt.py`
- `maritime-ai-service/tests/unit/test_graph_routing.py`
- `maritime-ai-service/tests/unit/test_code_studio_streaming.py`
- `maritime-ai-service/tests/unit/test_visual_prompt.py`
- `maritime-ai-service/tests/unit/test_sprint97_living_character.py`

Results:

- 132 passed
- 64 passed
- total verified in this phase: 196 passed

## Not done on purpose

- no primary-agent migration
- no memory-agent collapse into direct
- no regex-only guardian
- no frontend chrome expansion
- no long-running sleep-time scheduler rewrite

Those remain future phases.

## Notes

- The workspace already contains separate dirty changes removing the grader node from the graph. This phase did not revert or rework those changes.
- The new living contract is additive and feature-gated, so rollout can stay local/staging-first.
