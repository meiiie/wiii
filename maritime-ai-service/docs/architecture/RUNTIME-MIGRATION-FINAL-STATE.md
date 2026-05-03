# Runtime Migration Epic #207 — Final state report

> **As of**: 2026-05-03
> **Status**: Phases 0–6 shipped + Phase 7 partial (this PR). LangChain dependency reduced to a small deferred surface; full removal pending the wake/replay path (5b) and `WiiiChatModel` rewrite.

## What shipped

| Phase | PR | Squash | Scope |
|---|---|---|---|
| 0 | #209 | `48a6000` | Drift fix + scaffold (`runtime/lane.py`, `runtime/spec.py`, `enable_native_runtime` flag) |
| 1 | #211 | `e4be88d` | Native `Message`/`ToolCall` + 3 provider dict adapters; 22 SEND-side migrations |
| 2 | #212 | `e9dc89e` | Native `Tool`/`StructuredTool` + `@tool` decorator; 30 import migrations |
| 3 | #213 | `090576f` | Reverse adapters (`from_openai_response`/`from_anthropic_response`) + 11 file `BaseChatModel` → `Any` |
| 4 | #214 | (squash on main) | `TurnRequest` + `RuntimeIntent` + `lane_resolver` + 2 edge protocol adapters (Wiii native, OpenAI compat) |
| 5a | #215 | (squash on main) | Append-only `SessionEventLog` Protocol + `InMemorySessionEventLog` + `session_events` Alembic table |
| 6a | #216 | (squash on main) | `EvalRecord` + `EvalRecorder` + `scripts/eval_summary.py` + `enable_eval_recording` flag |
| 7 | this PR | — | Final cleanup + honest closure documentation |

## What's deferred (and why)

### Phase 8 follow-ups shipped (2026-05-03 evening)

After the initial 7-PR series merged, a follow-up branch (``codex/runtime-phase-8-finish-langchain-removal``) chipped at the deferred list:

- ``app/core/langsmith.py`` — dropped the ``langchain_core.tracers`` import. ``get_langsmith_callback`` now returns ``None``. The ``langsmith`` SDK stays a top-level dep so a future direct integration can wire observability without re-introducing langchain-core.
- ``app/engine/runtime/adapters/anthropic_compat.py`` — third edge protocol adapter joining ``wiii_native`` + ``openai_compat``. Anthropic ``tool_use`` blocks round-trip into native ``ToolCall``; ``tool_result`` blocks split into standalone role=``tool`` Messages.
- ``ChatOrchestrator.process(record=True)`` wiring — per-call opt-in eval recording, gated by ``settings.enable_eval_recording``. Fail-soft on recorder I/O errors so production traffic is never blocked.

What's still open after Phase 8: ``WiiiChatModel(BaseChatModel)`` rewrite (the gating step for actually removing ``langchain-core`` from the dependency manifest) and the 9 RECEIVE-coupled history files. Both depend on the BaseChatModel rewrite first.

### `langchain-core` package — kept in `pyproject.toml`

22 references remain in `app/` across 11 files. All of them sit in two deferred buckets:

**RECEIVE-coupled** (Phase 1 left them; need Phase 5b harness wake/replay first):
- `app/engine/context_budget_runtime.py`
- `app/engine/context_manager.py`
- `app/engine/conversation_window.py`
- `app/engine/multi_agent/agents/tutor_node.py:1319` — lazy `AIMessage` placeholder
- `app/engine/multi_agent/agents/tutor_tool_dispatch_runtime.py`
- `app/engine/multi_agent/agents/product_search_runtime.py`
- `app/engine/multi_agent/code_studio_tool_rounds.py`
- `app/engine/multi_agent/direct_tool_rounds_runtime.py`
- `app/engine/multi_agent/widget_surface.py`

**Provider implementation**:
- `app/engine/llm_providers/wiii_chat_model.py` — `class WiiiChatModel(BaseChatModel)`. Removing the inheritance requires re-implementing `_generate` / `_agenerate` / `_astream` / `bind_tools` / `with_structured_output` to satisfy ~50 consumer call sites. Lane-first dispatcher (Phase 4) provides the prerequisite, but the actual rewrite is its own PR.

**Observability**:
- `app/core/langsmith.py` — LangSmith tracer integration. Independent product decision; not in scope for the runtime migration.

### Operational gates from Phase 5–7 brief

| Item | Status |
|---|---|
| `PostgresSessionEventLog` + `wake(session_id)` | Deferred to Phase 5b (DB schema is shipped; wiring pending) |
| Subagent context isolation (RAG/Tutor/Memory emit summary, not raw chunks) | Deferred — needs careful Sprint 189b 73/73 source-flow re-verification |
| p50 TTFT 30% reduction benchmark | Deferred — needs phase-4 baseline replay first |
| `ChatOrchestrator.process(record=True)` integration | Deferred — touches production code path; ship in fresh PR with deeper testing |
| `scripts/replay_eval.py` HTML report | Deferred — depends on `record=True` integration |
| `.github/workflows/nightly-eval-replay.yml` cron | Deferred — needs real recording traffic first |
| Per-org canary rollout of `enable_native_runtime=True` | Operational, not single-PR work |
| Pointy V1 GA on LMS `holilihu.online` | Operational + needs browser test infra |
| 30-day post-mortem | Time-based, fill at +30d |

### Anthropic edge protocol adapter

`app/engine/runtime/adapters/anthropic_compat.py` was deferred from Phase 4. Content-block typing pays off after the harness session/sandbox split. Add when there is a concrete consumer.

## Surface reduction summary

| Surface | Before | After this epic |
|---|---|---|
| `langchain_core.messages` import | 22+ files (all paths) | 9 files (RECEIVE-coupled only) |
| `langchain_core.tools` import | 30 files | 0 in `app/`; 1 in `tests/integration/test_manual_react.py` (legacy fallback only) |
| `langchain_core.language_models` import | 13 files | 1 file (`wiii_chat_model.py` class definition) |
| `BaseChatModel` type-hint usage | ~70 references | ~7 (only inside `wiii_chat_model.py`) |
| `langchain` meta package | declared in `pyproject.toml` | removed in Phase 0 |
| `langchain-openai` / `-google-genai` / `-ollama` | declared in `pyproject.toml` | removed in Phase 0 |

## What this means for follow-up work

The migration's *runtime* goal is reached: every SEND-side path, every tool definition, and every pure-type-hint provider seam is native Wiii code. The remaining `langchain_core` surface is:

- 1 class implementation (`WiiiChatModel`) — easy single-PR rewrite once consumers are confirmed to need only the duck-typed methods we already mirror.
- 9 RECEIVE-coupled history-rebuild paths — refactor candidates once `SessionEventLog` becomes the source of truth (Phase 5b wiring).
- 1 observability integration (`langsmith.py`) — separate concern.

The eval recorder (Phase 6a) is the regression net for that follow-up work. With it shipped — even as a foundation only — every future change can be replayed against the prior production trace.

## Atomic commits index

Each phase landed as a single squash commit with a Vietnamese title and an English/Vietnamese mixed body. `git log --oneline main` shows the linear history. Per-commit detail (foundation/migration/test fixes) lives on the original branches before squash.
