# Primary Agent Architecture Review

Date: 2026-03-19
Status: Needs changes before implementation

## Summary

The proposed migration is directionally aligned with 2025-2026 guidance from Anthropic, OpenAI, Google, and xAI: start simple, keep one primary tool-using agent for the common path, and reserve orchestration for ambiguous or decomposition-heavy work.

However, the current plan overstates the baseline cost of Wiii's existing pipeline, underestimates how much behavior lives inside the current Memory agent, and proposes a Guardian fast path that is more destructive than necessary.

The best next step is not "Direct absorbs RAG + Memory" in one move. The safer and more SOTA-consistent move is:

1. Make Direct the primary lookup agent first.
2. Keep Memory as a specialized agent until equivalent background extraction exists elsewhere.
3. Extend Guardian's existing regex/content-filter fast path instead of replacing nuanced validation with regex-only allow/block.
4. Add a lightweight router only for trivially obvious cases and make it reuse existing Wiii helper logic.

## External Research

Primary sources reviewed:

- Anthropic, "Building effective agents" / architecture patterns PDF
- Anthropic Engineering, "How we built our multi-agent research system"
- OpenAI, "A practical guide to building agents"
- Google Cloud, "Single-agent AI system architecture with ADK and Cloud Run"
- Google Research, "Towards a science of scaling agent systems: when and why agent systems work"
- xAI Docs, "Multi-agent" capability page

Consensus from those sources:

- Start with a single agent or the simplest possible system.
- Use multi-agent only when you need real decomposition, specialization, or parallelism.
- Multi-agent systems can help on the right workloads, but they add latency, cost, routing complexity, and context-fragmentation risk.
- "Single-primary-agent + tools + harness" is the mainstream default pattern, but not every specialized subsystem should be collapsed immediately.

## Findings

### 1. The current baseline is already lower than the plan assumes

In the checked-out working tree, `synthesizer` already returns the single agent output directly when there is only one output. That means the common DIRECT / RAG / MEMORY path does not necessarily incur another synthesis LLM call.

Also, the working tree currently removes the Grader node from the graph entirely.

Implication:

- The plan's "3-4 minimum LLM calls" baseline is stale for this workspace.
- The migration can still be worthwhile, but the claimed savings should be recalculated from the actual branch behavior.

Relevant code:

- `maritime-ai-service/app/engine/multi_agent/supervisor.py`
- `maritime-ai-service/app/engine/multi_agent/graph.py`

### 2. RAG -> Direct is plausible, but Memory -> Direct is not equivalent yet

`Direct` already binds `tool_knowledge_search`, so using it as a primary lookup agent is a real routing simplification.

But the current `MemoryAgentNode` is not just a tool caller. It performs a 4-phase pipeline:

- retrieve existing facts
- extract new facts from the current turn
- classify ADD / UPDATE / DELETE / NOOP
- generate a natural response grounded in those changes

Simply attaching `tool_save_user_info`, `tool_get_user_info`, `tool_remember`, `tool_forget`, and `tool_list_memories` to Direct does not replace that behavior.

Implication:

- "Primary agent for lookup" is strong.
- "Primary agent for memory" is incomplete unless you also migrate implicit extraction / update behavior into a post-response hook or background memory pipeline.

Relevant code:

- `maritime-ai-service/app/engine/multi_agent/graph.py`
- `maritime-ai-service/app/engine/multi_agent/agents/memory_agent.py`
- `maritime-ai-service/app/engine/tools/memory_tools.py`

### 3. CRAG metadata harvesting is absolutely required if RAG runs as a tool

`rag_tools.py` already stores per-request context in `contextvars`:

- retrieved sources
- native thinking
- reasoning trace
- confidence

Those values are currently not harvested by the Direct path. So if Direct becomes the primary lookup agent, metadata parity will break unless the plan's Step 1.3 is implemented.

Implication:

- This is the strongest part of the plan.
- Without it, API responses will lose source fidelity and confidence traceability.

Relevant code:

- `maritime-ai-service/app/engine/tools/rag_tools.py`
- `maritime-ai-service/app/engine/multi_agent/graph.py`

### 4. The biggest hidden issue: `tool_knowledge_search` is not a retrieval-only tool

This is the most important mismatch in the plan.

`tool_knowledge_search()` does not simply return retrieved documents. It calls `CorrectiveRAG.process()`, produces a full answer, captures confidence and reasoning trace, and appends sources.

That means routing lookup queries through Direct does **not** automatically collapse the stack into "Supervisor + Primary Agent". In the current implementation, it more likely becomes:

- Supervisor LLM
- Direct LLM loop
- nested CRAG / RAG generation inside the tool

So the plan's statement that this is "largely a routing change, not a code rewrite" is not true if the goal is to reduce model calls and latency.

Implication:

- If you want Direct to become the true primary lookup agent, `tool_knowledge_search` should be redesigned into a retrieval / evidence tool, not a full answer-generation sub-agent.
- Otherwise, routing lookup to Direct may increase orchestration overhead rather than reduce it.

Relevant code:

- `maritime-ai-service/app/engine/tools/rag_tools.py`
- `maritime-ai-service/app/engine/multi_agent/agents/rag_node.py`

### 5. The Guardian phase is already partly optimized; Phase 2 is too blunt

The current Guardian already skips the LLM for:

- exact/short greetings
- very short messages
- all messages under 200 chars when `ContentFilter` severity is ALLOW or FLAG

That means Wiii already has a regex/content-filter fast path for many common requests.

The proposed "regex-only Guardian for all messages" would remove useful nuance:

- pronoun request handling
- ambiguous borderline safety cases
- nuanced FLAG reasoning

Implication:

- Phase 2 should not replace Guardian with pure regex allow/block.
- It should extend the existing skip logic, not flatten it.

Relevant code:

- `maritime-ai-service/app/engine/guardian_agent.py`
- `maritime-ai-service/app/engine/content_filter.py`
- `maritime-ai-service/app/engine/multi_agent/graph.py`

### 6. Lightweight routing should reuse Wiii's current helper logic, not generic keyword maps

The current Supervisor already contains policy beyond simple intent keywords:

- visual lane override
- code studio capability override
- product search gate
- colleague gate
- domain validation
- org knowledge bypass

A naive `_lightweight_route()` will regress these unless it reuses the current helpers and only short-circuits truly obvious cases.

Implication:

- Good idea in principle.
- Dangerous if implemented as a fresh keyword router divorced from current policy.

Relevant code:

- `maritime-ai-service/app/engine/multi_agent/supervisor.py`

### 7. Direct prompt quality needs an explicit lookup/citation upgrade

`direct.yaml` is conversational and tool-aware, but it does not carry the stronger "always search first / always cite sources" contract that `rag.yaml` has.

If Direct becomes the primary lookup path, prompt behavior must be upgraded alongside routing.

Implication:

- This is not only a routing migration.
- It is also a prompt-and-observability migration.

Relevant code:

- `maritime-ai-service/app/prompts/agents/direct.yaml`
- `maritime-ai-service/app/prompts/agents/rag.yaml`

## Recommendation

### Keep

- Feature-gated rollout
- CRAG metadata harvest
- Ambiguous fallback to LLM supervisor

### Change

- Re-scope Phase 1 before implementation:
  - either make Direct a true primary lookup agent by introducing retrieval-only evidence tools
  - or keep the current RAG agent and target Phase 3 routing reductions first
- Recalculate latency/token claims from the current branch, not the old graph
- Update Direct prompt and tests for citation/source parity
- Implement lightweight routing only for safe obvious cases and reuse current helpers

### Drop or postpone

- Memory -> Direct in the first cut
- Regex-only Guardian replacement
- Any claim that exact Grok / Claude / ChatGPT traffic percentages are verified unless primary sources are added

## Safer Revised Migration

### Phase 1A — Primary Lookup Agent

- Add `enable_primary_agent`
- Do **not** route lookup intents to Direct until lookup tools are retrieval-first rather than full-answer CRAG wrappers
- Keep Memory agent unchanged
- Harvest CRAG metadata after `tool_knowledge_search`
- Upgrade Direct prompt for retrieval/citations

### Phase 1B — Measurement

- Compare current vs flag-on:
  - latency
  - token usage
  - source parity
  - routing accuracy
  - answer quality

### Phase 2 — Guardian Extension

- Add `enable_regex_guardian`
- Only skip LLM for clearly safe messages using current `ContentFilter` path
- Preserve LLM path for pronoun requests and nuanced WARN / FLAG cases

### Phase 3 — Lightweight Router

- Add `enable_lightweight_routing`
- Fast-path only:
  - greetings / thanks
  - explicit web/news/legal
  - explicit product search
  - explicit code studio / simulation
  - explicit lookup with strong domain signal
- Fall through to structured LLM routing for everything else

### Phase 4 — Memory Migration (optional, later)

- Only if Wiii adds a replacement for:
  - background extraction
  - semantic update classification
  - natural acknowledgment behavior

## Final Verdict

The plan is good in direction but not yet ready as written.

Best decision:

- Approve the architectural direction.
- Approve RAG absorption into Direct with CRAG metadata harvest.
- Reject the Memory absorption part for Phase 1.
- Rewrite Guardian Phase 2 to extend current fast-path logic instead of replacing it.
- Narrow lightweight routing to obvious cases only and reuse existing Wiii policy helpers.
