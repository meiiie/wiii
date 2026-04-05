# Leader Triage - Living Routing Regression

Date: 2026-03-25
Author: Codex LEADER

## Scope

This triage covers the user-facing regressions observed in local runtime on:

- short natural-language companion turns
- visible thinking / stream surface
- visual/chart intent preservation
- provider/model execution drift

## Live Symptoms Confirmed

### 1. Companion turns fall into knowledge behavior

Observed user symptom:

- `co the uong ruou thuong trang khong ?`
- output reported `Tim thay 0 tai lieu lien quan`
- then apologized with a knowledge-style fallback

Local reproduction on the current stack also showed a nearby failure mode:

- request returned through `direct`
- `tool_knowledge_search` was still used
- answer drifted semantically toward factual liquor content instead of a living, relational reply

Conclusion:

- the system can fail in two adjacent ways:
  - route or tool into CRAG and leak `0-doc` surface
  - stay in `direct` but still contaminate the turn with knowledge-search behavior

### 2. Visible thinking contract is still broken

From the user screenshots and prior wave validation:

- visible thinking still echoes or paraphrases the raw user request too closely
- supervisor heartbeats are appended repeatedly
- action/debug/tool evidence is mixed into the same rail as living thought
- visual/data requests can end in search snippets plus sources instead of a visual artifact

Conclusion:

- the issue is not only latency
- the issue is a broken event taxonomy and a broken separation of surfaces

### 3. Provider/model execution truth still drifts

Explorer audit found:

- auto-selection is healthy-first but still preference-ordered
- request-scoped provider/model is not honored consistently across all lanes
- metadata can fall back to configured runtime defaults rather than executed provider/model

Conclusion:

- the UI can still tell a slightly false story about which model/provider actually carried the turn

## Root Causes

### A. Short-turn routing is too brittle

Likely source:

- `supervisor.py`
- `_should_use_compact_routing_prompt()`
- `_looks_short_capability_probe()`

Problem:

- very short natural-language questions are treated as compact-routing candidates too aggressively
- this increases the chance of misclassification for relational or capability-adjacent turns

### B. Direct lane is over-tooled

Likely source:

- `graph.py`
- `_collect_direct_tools()`
- `_direct_required_tool_names()`

Problem:

- `tool_knowledge_search` is bound too broadly in `direct`
- even when supervisor correctly avoids `rag_agent`, `direct` can still call KB/CRAG

### C. CRAG leaks raw retrieval behavior to the user surface

Likely source:

- `corrective_rag.py`
- `rag_node.py`
- `rag_tools.py`

Problem:

- `Tim thay {len(documents)} tai lieu lien quan` leaks into visible thinking
- `0-doc` becomes a user-visible artifact
- fallback apology is hardcoded in a domain-style voice instead of being handed back cleanly

### D. Event taxonomy is still not clean

Likely source:

- supervisor stream beats
- graph stream orchestration
- frontend reasoning rail composition

Problem:

- living thought
- action preamble
- tool/debug evidence

are still not fully separated

## Guidance From Strong Systems

Current best-practice references reviewed in this project:

- Anthropic streaming and fine-grained tool streaming
- OpenAI background/stream separation
- AIRI companion-style runtime direction

Common pattern:

- keep user-facing live thought intentional and coherent
- keep operational traces typed and separated
- never leak raw retrieval/tool internals into the main conversational surface
- preserve one stable assistant identity across routing, thought, and answer

## Acceptance Criteria For The Next Fixes

### Fix Block 1 - Short-turn routing

- `co the uong ruou thuong trang khong ?` does not compact-route into domain/RAG behavior
- similar short relational turns remain LLM-first, but not through the brittle compact prompt

### Fix Block 2 - Direct KB gating

- `direct` does not bind `tool_knowledge_search` unless retrieval intent is explicit
- companion/social/off-topic turns cannot accidentally re-enter CRAG through direct tool use

### Fix Block 3 - CRAG surface hygiene

- user never sees `Tim thay 0 tai lieu lien quan`
- no-doc retrieval does not end with a robotic domain apology on the main surface
- `rag_node` no longer forwards raw CRAG retrieval traces directly into visible thinking

### Fix Block 4 - Runtime truth follow-up

- executed provider/model is stamped accurately in sync and streaming
- request-scoped provider is honored consistently in RAG/Tutor/Code Studio paths

## Current Execution Order

1. fix short-turn routing
2. fix direct KB gating
3. fix CRAG surface leakage
4. re-run live reproduction
5. only then proceed to provider/runtime truth alignment

## Notes

The most important principle for the next wave:

- do not optimize for speed first
- optimize for coherence of Wiii's living identity and visible thought contract first
