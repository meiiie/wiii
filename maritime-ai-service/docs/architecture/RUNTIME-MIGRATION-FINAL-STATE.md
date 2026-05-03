# Runtime Migration Epic #207 — Final state report

> **As of**: 2026-05-03 (updated after Phase 9 worker session)
> **Status**: All langchain runtime surface eliminated. `langchain-core` + `langchain-mcp-adapters` dropped from manifest; `langsmith` SDK dropped (stub keeps public surface). Remaining work is operational gates (Phase 5b harness wake/replay, canary rollout) — none of which still depend on LangChain code.

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

### Phase 9 langchain removal — DONE (2026-05-03)

The Phase 9 worker session shipped the gating rewrites in three branches:

- ``codex/runtime-phase-9a-wiii-chat-model`` — ``WiiiChatModel`` rewritten without ``BaseChatModel`` inheritance. Returns native ``Message`` and ``StreamChunk`` types. Streaming compat preserved via Option A (``StreamChunk.message`` self-pointing shim + ``__add__`` accumulator).
- ``codex/runtime-phase-9b-receive-coupled`` — 9 RECEIVE-coupled history paths migrated to native ``Message`` / ``ToolCall``: ``conversation_window``, ``context_manager``, ``context_budget_runtime``, ``tutor_node:1318`` placeholder, ``tutor_tool_dispatch_runtime``, ``product_search_runtime``, ``code_studio_tool_rounds``, ``direct_tool_rounds_runtime``, ``widget_surface``. ``Message.type`` LC-compat alias added so legacy introspectors keep working.
- ``codex/runtime-phase-9c-drop-langchain-core`` — ``app/mcp/client.py`` rewritten against the raw ``mcp`` SDK (``ClientSession`` + ``AsyncExitStack``); ``langchain-core`` removed from ``pyproject.toml``; ``langchain-mcp-adapters`` and ``langsmith`` removed from ``requirements.txt``; the no-op stub at ``app/core/langsmith.py`` is left in place so the two consumer call sites do not need to branch.

After 9c, ``grep -rE "from langchain|import langchain" app/`` returns 0 lines.

### Phase 8 follow-ups shipped (2026-05-03 evening)

After the initial 7-PR series merged, a follow-up branch (``codex/runtime-phase-8-finish-langchain-removal``) chipped at the deferred list:

- ``app/core/langsmith.py`` — dropped the ``langchain_core.tracers`` import. ``get_langsmith_callback`` now returns ``None``. The ``langsmith`` SDK stays a top-level dep so a future direct integration can wire observability without re-introducing langchain-core.
- ``app/engine/runtime/adapters/anthropic_compat.py`` — third edge protocol adapter joining ``wiii_native`` + ``openai_compat``. Anthropic ``tool_use`` blocks round-trip into native ``ToolCall``; ``tool_result`` blocks split into standalone role=``tool`` Messages.
- ``ChatOrchestrator.process(record=True)`` wiring — per-call opt-in eval recording, gated by ``settings.enable_eval_recording``. Fail-soft on recorder I/O errors so production traffic is never blocked.

What was still open after Phase 8 — the ``WiiiChatModel(BaseChatModel)`` rewrite, the 9 RECEIVE-coupled history files, and the dependency-manifest cleanup — was all addressed in the Phase 9 worker session above.

### `langchain-core` package — REMOVED Phase 9c (2026-05-03)

Zero ``from langchain*`` imports remain in ``app/``. ``pyproject.toml`` no longer declares ``langchain-core``; ``requirements.txt`` no longer declares ``langchain-mcp-adapters`` or ``langsmith``. The ``app/core/langsmith.py`` stub kept the public surface (``configure_langsmith`` / ``is_langsmith_enabled`` / ``get_langsmith_callback``) so call sites stay untouched; a future direct LangSmith integration can re-add the SDK in its own PR.

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

| Surface | Before | After Phase 9 |
|---|---|---|
| `langchain_core.messages` import | 22+ files (all paths) | 0 |
| `langchain_core.tools` import | 30 files | 0 in `app/`; 1 in `tests/integration/test_manual_react.py` (legacy fallback only) |
| `langchain_core.language_models` import | 13 files | 0 |
| `BaseChatModel` type-hint / inheritance usage | ~70 references | 0 |
| `langchain_mcp_adapters` import | 1 file (`app/mcp/client.py`) | 0 (rewritten against raw `mcp` SDK) |
| `langchain` meta package | declared in `pyproject.toml` | removed in Phase 0 |
| `langchain-openai` / `-google-genai` / `-ollama` | declared in `pyproject.toml` | removed in Phase 0 |
| `langchain-core` package | declared in `pyproject.toml` + `requirements.txt` | removed in Phase 9c |
| `langchain-mcp-adapters` package | declared in `requirements.txt` | removed in Phase 9c |
| `langsmith` package | declared in `requirements.txt` | removed in Phase 9c (stub kept; future direct integration can re-add) |

## What this means for follow-up work

The runtime migration's goal is reached. Every SEND-side path, every tool definition, every provider seam, and every RECEIVE-coupled history rebuild are native Wiii code. ``WiiiChatModel`` is a plain Pydantic ``BaseModel`` returning native ``Message`` / ``StreamChunk``. The MCP client uses the raw ``mcp`` SDK directly. The dependency manifest has zero ``langchain*`` packages.

The eval recorder (Phase 6a) is the regression net for any future runtime change. With it shipped — even as a foundation only — every future change can be replayed against the prior production trace.

## Atomic commits index

Each phase landed as a single squash commit with a Vietnamese title and an English/Vietnamese mixed body. `git log --oneline main` shows the linear history. Per-commit detail (foundation/migration/test fixes) lives on the original branches before squash.
