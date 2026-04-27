# Wiii-Native Orchestration Runtime RFC

Status: Accepted / active migration plan
Date: 2026-04-27
Tracking issue: #130
Owner: Wiii maintainers

## Executive Decision

Wiii should remove LangGraph as an architectural assumption, but it should not
delete remaining graph-shaped files in one broad PR.

The correct direction is a controlled migration to a Wiii-owned runtime:

```text
API edge
-> turn preparation
-> WiiiRunner orchestration
-> agent/tool/provider lanes
-> synthesis
-> persistence and memory
-> streaming events
```

This is already partly true in production code. `WiiiRunner` is the active
orchestration path, while most remaining LangGraph residue is naming, test
mocks, compatibility shells, historical documentation, and old mental models.

The risk is not whether the final direction is right. It is right. The risk is
deleting too broadly before Wiii has golden tests for chat, streaming, memory,
tool calls, provider failover, and FE-visible event semantics.

## Non-Goals

- Do not remove multiple runtime layers in the same PR as dependency upgrades or
  secret rotation.
- Do not change public chat API, SSE event names, auth behavior, memory
  semantics, or thread persistence in the RFC PR.
- Do not delete `graph_rag_*` modules just because their names contain `graph`;
  knowledge-graph and GraphRAG concepts are separate from LangGraph.
- Do not remove LangChain Core while Wiii still uses it as a model/tool
  compatibility surface.

## Evidence Snapshot

Checked on 2026-04-27 from the repository working tree.

| Signal | Current result | Meaning |
|---|---:|---|
| Active `import langgraph` statements | 0 | LangGraph is no longer actively imported by normal app code. |
| Exact `from langgraph` hits | 4 textual hits | The hits are commented-out historical imports in deprecated subgraph compatibility files. |
| `MemorySaver` hits | 0 | The old LangGraph memory checkpointer is no longer present. |
| `CompiledStateGraph` hits | 0 | No compiled LangGraph graph type remains. |
| `get_multi_agent_graph` / `build_multi_agent_graph` hits | 5 | Remaining tracked hits are only in `test_graph_thread_id.py`, where they assert retired public APIs are absent. |
| Graph-named tracked Python files | 21 | Many are runner-backed streaming/helper shells or GraphRAG, not active LangGraph. |

Representative current files:

- `maritime-ai-service/app/engine/multi_agent/runner.py`: active `WiiiRunner`.
- `maritime-ai-service/app/engine/multi_agent/graph_process.py`: sync entrypoint that calls `get_wiii_runner().run(...)`.
- `maritime-ai-service/app/engine/multi_agent/graph_streaming.py`: runner-backed SSE shell with legacy graph naming.
- `maritime-ai-service/app/engine/multi_agent/state.py`: flat `AgentState` plus typed overlays.
- `maritime-ai-service/app/engine/multi_agent/stream_events.py`: typed event constructors but still uses graph-shaped event names.
- `maritime-ai-service/app/engine/llm_provider_registry.py`: provider registry for `google`, `vertex`, `openai`, `openrouter`, `nvidia`, `ollama`, and `zhipu`.
- `maritime-ai-service/app/engine/llm_route_runtime.py`: request-scoped provider route and failover resolution.
- `maritime-ai-service/app/engine/llm_runtime_profiles.py`: provider presets and default failover chains.

Issue state update after initial drafting:

- #93 Phase 1 runtime-shell purge has been verified and closed.
- #97 Phase 2 graph/checkpointer shim removal has been verified and closed.
- #101 Phase 3 deprecated graph mock cleanup has been verified and closed after
  PR #142 merged.
- #128 remains open because GitHub secret-scanning alerts #1 and #2 still need
  external OpenRouter revocation/rotation before they can be resolved.
- #129 dependency triage is down to the upstream-blocked `glib` Tauri/GTK
  alert. The residual `rand` build-dependency alert was dismissed as
  `tolerable_risk` after verification.

Next implementation focus:

- Rename or retire runner-backed `graph_*` compatibility shells only after
  adding parity tests for chat, streaming, memory, tool calls, and FE-visible
  event semantics.
- Keep `graph_rag_*`, knowledge graph, learning graph, and semantic graph code
  out of the LangGraph purge unless a file imports or depends on LangGraph
  directly.
- Treat `.claude/` LangGraph references as legacy local notes, not canonical
  architecture truth.

## Verification commands

Re-run these checks before each destructive LangGraph-removal PR so the
inventory above stays reproducible.

```bash
rg -n "^(import langgraph|from langgraph)" maritime-ai-service
rg -n "\b(MemorySaver|CompiledStateGraph|StateGraph)\b" maritime-ai-service
rg -n "\b(get_multi_agent_graph|build_multi_agent_graph)\b" maritime-ai-service
```

Windows PowerShell equivalent:

```powershell
Get-ChildItem maritime-ai-service -Recurse -File |
  Select-String -Pattern '^(import langgraph|from langgraph)'
Get-ChildItem maritime-ai-service -Recurse -File |
  Select-String -Pattern '\b(MemorySaver|CompiledStateGraph|StateGraph)\b'
Get-ChildItem maritime-ai-service -Recurse -File |
  Select-String -Pattern '\b(get_multi_agent_graph|build_multi_agent_graph)\b'
```

## Current Runtime Truth

The active chat path is:

```text
wiii-desktop
-> useSSEStream
-> POST /api/v1/chat/stream/v3
-> auth and request validation
-> ChatOrchestrator.prepare_turn
-> InputProcessor.build_context
-> process_with_multi_agent_streaming
-> WiiiRunner.run_streaming
-> guardian
-> supervisor
-> selected agent or parallel dispatch
-> synthesizer
-> SSE finalization
-> finalize_response_turn
-> thread_views, chat history, memory/background tasks
```

The sync path is similar:

```text
ChatOrchestrator.process
-> process_with_multi_agent_impl
-> WiiiRunner.run
-> response payload shaping
-> finalize_response_turn
```

Important distinction:

- `WiiiRunner` is active orchestration.
- `graph_*` names now mostly mean "legacy shell around runner-backed runtime".
- Some docs and tests still speak as if LangGraph is central. They should be
  treated as migration debt.

## Target Architecture

Wiii should converge on these runtime layers.

| Layer | Responsibility | Must not know |
|---|---|---|
| API edge | HTTP, SSE, WebSocket, LMS/embed adapters, auth, request validation | Agent internals |
| Turn preparation | user/session/thread identity, context, domain, host context, memory input | Provider implementation |
| Runtime core | deterministic step loop, handoff, retries, guardrails, error policy | FastAPI details |
| Agent lanes | direct, memory, tutor, RAG, product search, code studio, host action, colleague | Provider secrets |
| Tool runtime | tool selection, validation, execution, metrics, MCP/host bridges | UI rendering details |
| Provider runtime | canonical model route, capabilities, failover, circuit breaker | Agent prompt details |
| Streaming runtime | normalized Wiii stream events and SSE conversion | LangGraph event vocabulary |
| Persistence runtime | turn ledger, messages, thread view, memory writes, checkpoints | Provider classes |
| Observability | trace, audit, metrics, provider observations, reviewable failure reasons | Business logic |

## Core Contracts To Add Before Deletion

### `WiiiTurnRequest`

The normalized request accepted by the runtime after API/auth parsing.

Required fields:

- `query`
- `user_id`
- `session_id`
- `thread_id`
- `organization_id`
- `domain_id`
- `messages`
- `host_context`
- `provider_hint`
- `model_hint`
- `thinking_effort`

### `WiiiTurnState`

The runtime state object that replaces the implicit graph-shaped flat dict over
time. Initially it can wrap `AgentState` to avoid a breaking rewrite.

Required groups:

- input context
- routing state
- agent outputs
- tool state
- provider route
- memory state
- streaming state
- persistence state
- error state

### `WiiiRuntimeStep`

Every runtime step should expose the same callable contract:

```python
async def run_step(state: WiiiTurnState, ctx: WiiiRunContext) -> WiiiStepResult:
    ...
```

The result should declare:

- `state_delta`
- `next_step`
- `events`
- `tool_calls`
- `provider_observations`
- `persistence_actions`
- `error`

### `WiiiStreamEvent`

The wire format can remain backward-compatible while internals stop using
graph wording.

Canonical internal event categories:

- `runtime.step.started`
- `runtime.step.completed`
- `runtime.step.failed`
- `thinking.started`
- `thinking.delta`
- `thinking.completed`
- `answer.delta`
- `tool.call`
- `tool.result`
- `preview`
- `artifact`
- `host.action`
- `memory.write`
- `provider.failover`
- `done`
- `error`

SSE conversion can map these to the current FE event names until the frontend is
ready for a versioned stream contract.

### `WiiiCheckpointStore`

Do not reintroduce a framework checkpointer. Wiii needs an explicit persistence
contract:

- turn started
- user message persisted
- assistant response pending
- assistant response completed
- stream interrupted
- provider/tool failed
- memory write queued
- memory write completed

This store should protect FE chat continuity and prevent user-only dangling
turns after stream interruption.

## Provider Runtime Direction

Wiii should keep provider support first-class, but the abstraction should be
model-and-capability aware rather than only provider-name aware.

Current supported provider names:

- `google`
- `vertex`
- `openai`
- `openrouter`
- `nvidia`
- `ollama`
- `zhipu`

Target provider contract:

```text
ProviderAdapter
-> list_models()
-> resolve_model(request)
-> capabilities(model)
-> create_chat_client(route)
-> stream_chat(route, messages, tools, response_format)
-> health()
```

Capabilities should include:

- streaming support
- tool calling support
- structured output support
- reasoning controls
- vision input
- image/file input
- max context window
- latency tier
- cost tier
- reliability score
- supports OpenAI-compatible request shape
- requires provider-specific extra body

Provider-management pattern to keep from the earlier Unsloth-style runtime
comparison requested by maintainers. This is a design reference only; Wiii
should not import Unsloth code or couple orchestration to that project:

- Resolve a canonical model/runtime object before routing.
- Keep protocol compatibility at the API edge.
- Treat different execution lanes honestly instead of pretending all providers
  behave the same.
- Isolate incompatible runtime lanes behind workers if needed.

Recommended Wiii objects:

- `RuntimeModelSpec`
- `ResolvedProviderRoute`
- `ExecutionPlan`
- `ProviderCapabilityProfile`
- `RuntimeLane`

## Phased Migration Plan

### Phase 0: Safety Baseline

Goal: do not begin destructive runtime deletion until security and governance
gates are stable.

Inputs:

- #127 high dependency remediation complete.
- #128 secret rotation tracked separately.
- CodeRabbit and Codex review required for security-sensitive/runtime PRs.

Allowed changes:

- Documentation.
- Inventory scripts.
- Test planning.

Blocked changes:

- Runtime deletion.
- Provider behavior changes.
- Stream event changes.

Verification:

- GitHub Gate Summary green.
- No high Dependabot alerts open.
- Secret alerts not falsely resolved before provider revocation.

Rollback:

- Revert documentation-only PR if the plan is incorrect.

### Phase 1: Runtime Inventory and Naming Boundary

Goal: separate true LangGraph residue from graph-named Wiii runtime helpers.

Work:

- Produce a tracked inventory of all `graph_*`, `get_multi_agent_graph*`,
  `build_multi_agent_graph`, `StateGraph`, and `from langgraph` references.
- Classify each hit as active runtime, compatibility shell, test debt,
  documentation drift, GraphRAG, or safe historical comment.
- Rename only documentation and comments first.
- Create issues for code renames that can be done safely.

Exit criteria:

- Maintainers can see which files are safe to rename and which are not.
- No production behavior changed.

Rollback:

- Revert docs/inventory commit.

### Phase 2: Golden Chat and Stream Tests

Goal: make FE chat stability measurable before deleting compatibility shells.

Golden scenarios:

- direct social chat
- memory recall and memory write
- RAG fallback with zero documents
- tutor response
- tool call with result
- provider failover
- stream interruption
- provider unavailable
- host context injection
- visual/artifact event pass-through

Each scenario needs:

- sync API assertion
- streaming SSE assertion
- final persisted thread/message assertion
- no raw internal graph event leak

Exit criteria:

- CI has a small required smoke suite that proves Wiii can still chat after
  every migration PR.

Rollback:

- Revert only the failing test or fixture PR if tests are inaccurate.

### Phase 3: State and Event Contract

Goal: introduce Wiii-native names without breaking existing API responses.

Work:

- Add `WiiiTurnRequest` and `WiiiRunContext`.
- Wrap current `AgentState` in `WiiiTurnState` accessors.
- Add internal `WiiiStreamEvent` categories.
- Keep SSE compatibility mapping unchanged.
- Mark `GraphNodeEvent` and `GraphDoneEvent` names as compatibility aliases.

Exit criteria:

- New runtime code uses Wiii-native event names.
- Existing FE stream still works.

Rollback:

- Keep compatibility aliases and switch internal producers back to current
  event constructors.

### Phase 4: Provider Route Contract

Goal: move provider selection from scattered provider-name logic to a canonical
model route.

Work:

- Add `RuntimeModelSpec`.
- Add `ProviderCapabilityProfile`.
- Add `ResolvedProviderRoute`.
- Move provider health, model, failover, and extra-body decisions behind a
  single route resolver.
- Keep current provider classes as adapters.

Exit criteria:

- Google, OpenRouter, Zhipu, Ollama, OpenAI, NVIDIA, and Vertex are all
  represented by the same route contract.
- Provider-specific behavior is expressed as capabilities, not ad hoc checks in
  agents.

Rollback:

- Fallback to existing `llm_route_runtime.py` route resolution while preserving
  the new types behind a feature flag.

### Phase 5: Turn Ledger and Checkpoint Replacement

Goal: replace any remaining implicit graph/checkpoint mental model with Wiii's
own turn ledger.

Work:

- Add explicit turn status transitions.
- Persist stream lifecycle state.
- Ensure interrupted streams are visible and recoverable.
- Block long-term memory writes for service identities.

Exit criteria:

- No user-only turns after stream interruption.
- Memory writes are tied to completed assistant turns or explicit queued state.

Rollback:

- Disable new turn ledger writes with a feature flag and keep old persistence.

### Phase 6: Tool Runtime Boundary

Goal: make tool routing independent of agent framework history.

Work:

- Normalize tool definitions across direct, tutor, visual, LMS, MCP, host
  action, and Code Studio paths.
- Record tool call/result events through one runtime surface.
- Add per-agent tool capability matrix.

Exit criteria:

- Tool calls have one event schema and one audit surface.
- Agents do not manually format tool event payloads differently.

Rollback:

- Keep per-agent adapters while disabling the unified tool runtime path.

### Phase 7: Complex Lane Migration

Goal: migrate high-risk lanes one at a time.

Order:

1. Direct lane.
2. Memory lane.
3. Tutor lane.
4. RAG lane.
5. Product search lane.
6. Code Studio and visual lanes.
7. Host action/MCP lanes.
8. Parallel dispatch and aggregator.

Per-lane PR requirements:

- owned path list
- golden tests touched
- exact verification commands
- FE chat smoke result
- rollback switch

Rollback:

- Re-enable previous lane adapter for that lane only.

### Phase 8: Delete Compatibility Shells

Goal: remove old names only after behavior is already covered.

Deletion candidates:

- deprecated `get_multi_agent_graph*` test mocks
- deprecated `build_multi_agent_graph` references
- graph-named streaming aliases after FE contract versioning
- subagent graph builder shells that only raise deprecation errors
- docs that say LangGraph is primary

Do not delete:

- GraphRAG modules that are about knowledge graph retrieval.
- `langchain-core` if it is still the model/tool interface.

Exit criteria:

- `import langgraph`, `from langgraph`, `StateGraph`, `MemorySaver`,
  `CompiledStateGraph`, `get_multi_agent_graph`, and `build_multi_agent_graph`
  are absent from active app and non-deprecated tests.

Rollback:

- Revert the deletion PR. No database rollback should be required.

## Multi-Agent Ownership Model

Use narrow ownership to avoid agent conflicts:

| Workstream | Owner type | Owned paths |
|---|---|---|
| Runtime contract | Architect/Developer | `app/engine/multi_agent/runner.py`, new runtime contract modules |
| Streaming contract | Developer/Tester | `graph_streaming.py`, stream helper modules, FE stream tests |
| Provider route | Architect/Developer | `llm_*runtime*.py`, `llm_providers/**`, model catalog |
| Memory/checkpoint | Developer/Tester | `chat_orchestrator*`, repositories, semantic memory |
| Tool runtime | Developer/Reviewer | `engine/tools/**`, MCP, host action, visual tools |
| Test migration | Tester | affected `tests/unit/test_sprint*.py` files |
| Docs/governance | Leader/Reviewer | `docs/**`, issue/PR templates |

Rules:

- One agent owns one path slice per PR.
- No PR should rename and change behavior in the same path unless unavoidable.
- All runtime PRs must include rollback notes.
- All stream PRs must include FE chat smoke verification.

## Required Follow-Up Issues

Create or update focused issues for:

1. Inventory remaining graph-shaped references and classify them.
2. Add golden chat/stream smoke tests.
3. Introduce Wiii-native runtime contracts.
4. Introduce canonical provider route and capability profiles.
5. Add turn ledger/checkpoint replacement.
6. Unify tool runtime events.
7. Close #101 by merging the test-mock cleanup PR and keeping retired API names
   only in negative public-surface assertions.
8. Delete compatibility shells after parity.

## Merge Readiness Checklist

Before any destructive LangGraph removal PR:

- #127 remains closed with no high dependency alerts.
- #128 is either resolved or explicitly acknowledged as a separate external
  provider operation.
- Current branch has no unrelated dependency or secret changes.
- Golden smoke tests exist for sync and streaming chat.
- PR body lists in-scope and out-of-scope runtime lanes.
- PR body lists rollback command or feature flag.
- CodeRabbit review is green.
- Codex review has run for security/runtime regressions.
- `wiiiii123` or another maintainer has approved.

## Bottom Line

Clearing LangGraph completely is reasonable and probably the right strategic
move for Wiii. The safest path is not to delete more today; it is to formalize
the Wiii-native contracts, lock down golden behavior, then remove one
compatibility surface at a time.
