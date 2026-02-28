# Wiii System Audit Tracker — 2026

> **Mục đích**: Tài liệu bám sát cho mỗi lần audit. Không cần kiểm tra lại từ đầu.
> **Cập nhật**: Mỗi luồng/module sau khi audit xong sẽ ghi kết quả vào đây.
> **Phương pháp**: Module-by-module, flow-by-flow. Ăn chậm nhai kỹ.

---

## Audit Status Dashboard

| # | Flow / Module | Status | Issues | Last Reviewed | Notes |
|---|--------------|--------|--------|---------------|-------|
| 1 | Authentication (OAuth + JWT) | FIXED | 9 found, 9 fixed | 2026-02-27 | AUTH-1→9 all resolved |
| 2 | App Initialization (startup) | FIXED | 6 found, 6 fixed | 2026-02-27 | INIT-1→6 all resolved |
| 3 | Chat Flow (input → response) | FIXED | 9 found, 9 fixed | 2026-02-27 | CHAT-1→9 all resolved |
| 4 | Streaming Flow (SSE pipeline) | FIXED | 6 found, 6 fixed | 2026-02-27 | STREAM-1→6 all resolved |
| 5 | RAG Pipeline (retrieval → generation) | FIXED | 10 found, 10 fixed | 2026-02-27 | RAG-1→10 all resolved |
| 6 | Multi-Agent Graph (supervisor → agents) | FIXED | 8 found, 8 fixed | 2026-02-27 | GRAPH-1→8 all resolved |
| 7 | Memory & Context (facts + window) | FIXED | 7 found, 7 fixed | 2026-02-27 | MEM-1→7 all resolved |
| 8 | Living Agent (soul + emotion + heartbeat) | FIXED | 6 found, 6 fixed | 2026-02-27 | LIVE-1→6 all resolved |
| 9 | Organization (multi-tenant) | FIXED | 4 found, 4 fixed | 2026-02-27 | ORG-1→4 all resolved |
| 10 | Admin System (system + org admin) | FIXED | 6 found, 6 fixed | 2026-02-27 | ADMIN-1→6 all resolved |
| 11 | Product Search (platforms + curation) | FIXED | 3 found, 3 fixed | 2026-02-27 | SEARCH-1→3 all resolved |
| 12 | Knowledge Ingestion (upload → embed) | FIXED | 2 found, 1 fixed + 1 noted | 2026-02-27 | INGEST-1 noted, INGEST-2 fixed |
| 13 | Desktop UX/UI (layout + interaction) | FIXED | 3 found, 3 fixed | 2026-02-27 | UI-1→3 all resolved |
| 14 | Security & Infrastructure | FIXED | 4 found, 4 fixed | 2026-02-27 | SEC-1→4 all resolved |
| 15 | Testing & CI/CD | FIXED | 5 found, 5 fixed | 2026-02-28 | TEST-1→5 all resolved |
| — | **Post-audit: 6 noted items** | **FIXED** | **6 found, 6 fixed** | 2026-02-28 | CI DB service, coverage, Neo4j org_id, middleware 503 |
| 16 | E2E UI Testing (Chrome) | FIXED | 2 found, 2 fixed | 2026-02-28 | UITEST-1→2: Unicode JSX + SoulBridge min_priority |
| 17 | Google OAuth Flow (E2E) | FIXED + NOTED | 1 fixed, 1 noted | 2026-02-28 | OAUTH-1 redirect URI fix, OAUTH-2 GCP config pending |

---

## Legend

- **NOT STARTED** — Chưa bắt đầu
- **IN PROGRESS** — Đang kiểm tra
- **CLEAN** — Đã kiểm tra, không có vấn đề đáng kể
- **ISSUES FOUND** — Phát hiện vấn đề, cần sửa
- **FIXED** — Đã phát hiện và sửa xong
- **USER REVIEW** — Đã báo user, chờ quyết định

---

## Detailed Findings

### Flow 1: Authentication (OAuth + JWT)
**Files**: `app/auth/`, `app/core/security.py`, `wiii-desktop/src/components/auth/LoginScreen.tsx`
**Status**: FIXED
**Last reviewed**: 2026-02-27
**Tests**: 156 auth tests (67 Sprint 192 + 89 Sprint 176/194c) — 0 failures

#### Files Audited (11 files):
- `app/core/security.py` — Auth dependencies, JWT verification, API key validation, org membership
- `app/auth/token_service.py` — Token creation, refresh, revocation, JTI denylist
- `app/auth/google_oauth.py` — OAuth routes, callback, logout, /me
- `app/auth/user_service.py` — User CRUD, identity federation (3-step)
- `app/auth/auth_audit.py` — Fire-and-forget auth event logging
- `app/auth/otp_linking.py` — DB-backed OTP with exponential backoff
- `wiii-desktop/src/components/auth/LoginScreen.tsx` — Desktop OAuth UI
- `wiii-desktop/src/stores/auth-store.ts` — Auth state with refresh mutex
- `wiii-desktop/src/api/client.ts` — HTTP client with 401 interceptor
- `wiii-desktop/src/lib/secure-token-storage.ts` — Dedicated token store
- `wiii-desktop/src/App.tsx` — OAuth callback + initialization flow

#### Issues Found & Fixed (9):

| ID | Priority | Issue | Fix | File |
|----|----------|-------|-----|------|
| AUTH-1 | P0 | OAuth callback leaks internal exception text in error message | Changed to Vietnamese: "Xác thực Google thất bại. Vui lòng thử lại." | `google_oauth.py:127` |
| AUTH-2 | P1 | "Failed to get user info from Google" English error shown to user | Vietnamese: "Không lấy được thông tin từ Google. Vui lòng thử lại." | `google_oauth.py:131` |
| AUTH-3 | P1 | "Google account has no email" English error shown to user | Vietnamese: "Tài khoản Google không có email. Vui lòng dùng tài khoản khác." | `google_oauth.py:140` |
| AUTH-4 | P1 | Dead `create_access_token()` in security.py (duplicate of token_service) | Removed dead code, added clarifying comment | `security.py:54-59` |
| AUTH-5 | P1 | Duplicate JWT decode logic in security.py vs token_service.py | Created shared `decode_jwt_payload()` in token_service; both `verify_jwt_token` and `verify_access_token` delegate to it | `security.py:61-84`, `token_service.py:129-161` |
| AUTH-6 | P1 | `/auth/logout` and `/auth/me` used manual header parsing instead of `Depends(require_auth)` | Migrated both endpoints to `Depends(require_auth)` pattern | `google_oauth.py:275-348` |
| AUTH-7 | P2 | `/auth/token/refresh` used manual `request.json()` parsing | Created `RefreshTokenRequest(BaseModel)` Pydantic model | `google_oauth.py:256-272` |
| AUTH-8 | P2 | Org membership check fail-OPEN on DB error (inconsistent with OrgContextMiddleware fail-closed) | Changed to fail-CLOSED: `return False` on DB error | `security.py:133-135` |
| AUTH-9 | P2 | `/auth/me` returned deactivated user profiles without checking `is_active` | Added `is_active` check, returns 403 with Vietnamese message | `google_oauth.py:329-330` |

#### Clean Areas (no issues found):
- **Token creation** (`create_access_token`, `create_refresh_token`): Correct claims, `aud`/`jti`/`iss` all present
- **Refresh token rotation**: Family-based replay detection working correctly
- **JTI denylist**: In-memory with TTL cleanup, deny/check/clear all correct
- **OTP system**: DB-backed, exponential backoff, probabilistic cleanup, lockout threshold
- **Identity federation**: 3-step (provider→email→create), email_verified guard for auto-link
- **Auth audit logging**: Fire-and-forget pattern, covers login/logout/refresh/revoke/replay
- **Desktop auth flow**: OAuth URL fragment delivery (no log leakage), refresh mutex, secure token storage
- **401 interceptor**: Token refresh on 401 with retry queue, proper logout on refresh failure
- **PKCE S256**: Explicit code_challenge_method in OAuth config
- **API key**: `hmac.compare_digest` timing-safe comparison, production mode enforcement
- **Role restriction**: API key in production blocks admin role escalation, JWT role from token (not X-Role header)

---

### Flow 2: App Initialization
**Files**: `app/main.py`, `app/core/middleware.py`, `app/api/v1/__init__.py`, `app/api/v1/health.py`, `wiii-desktop/src/App.tsx`, `wiii-desktop/src/components/layout/AppShell.tsx`
**Status**: FIXED
**Last reviewed**: 2026-02-27
**Tests**: 83 middleware/deployment tests — 0 failures

#### Issues Found & Fixed (6):

| ID | Priority | Issue | Fix | File |
|----|----------|-------|-----|------|
| INIT-1 | P1 | Middleware ordering: OrgContext binds `organization_id` to structlog, then RequestID `clear_contextvars()` wipes it — all route handler logs missing org_id | Swapped add order: OrgContext first (inner), RequestID second (outer) — RequestID clears before OrgContext binds | `main.py:498-503` |
| INIT-2 | P2 | `general_exception_handler` uses f-string `f"Unexpected error: {exc}"` — eager evaluation | Changed to lazy: `logger.exception("Unexpected error: %s", exc)` | `main.py:623` |
| INIT-3 | P2 | Duplicate step number `# 1b.` for embedding validation | Renamed to `# 1c.` | `main.py:186` |
| INIT-4 | P2 | CORS wildcards `https://*.vercel.app` never match (CORSMiddleware uses exact strings, not glob) | Removed misleading entries, added clarifying comment about `CORS_ORIGIN_REGEX` | `main.py:461-462` |
| INIT-5 | P2 | Agent card endpoint returns `{"error": str(e)}` — leaks internal exception details | Generic `"Agent card unavailable"` + logger.warning | `main.py:543` |
| INIT-6 | P2 | K8s readiness probe docstring says "Returns 503" but always returns 200 | Returns `JSONResponse(status_code=503)` when not ready | `health.py:517-533` |

#### Clean Areas:
- **Startup sequence**: All blocks use try/except with warn-and-continue (resilient)
- **Shutdown sequence**: Resources closed in correct dependency order
- **Feature-gated init**: All optional components properly gated (`enable_*` flags)
- **Domain plugin discovery**: Auto-discovery + `active_domains` filtering correct
- **Desktop init**: Settings → Auth → Conversations in proper sequential order
- **OAuth callback**: Hash-based token delivery, error toast, hash cleanup on success/failure
- **JWT auto-refresh**: 60s interval, expiring-soon check, OAuth-mode only
- **Loading screen**: Vietnamese "Wiii đang thức dậy..." with avatar animation
- **AppShell**: View routing (chat/admin/settings), Vietnamese disconnected banner
- **Router registration**: Clean `_register_optional_router` pattern for feature-gated routes
- **Health checks**: Shallow (no DB), deep (all components with timeout), K8s probes (live/ready)
- **Alembic auto-migration**: Runs on startup, warn on failure

---

### Flow 3: Chat Flow
**Files**: `app/api/v1/chat.py`, `app/api/v1/chat_stream.py`, `app/services/chat_orchestrator.py`, `app/api/deps.py`
**Status**: FIXED
**Last reviewed**: 2026-02-27
**Tests**: 650 chat/streaming/orchestrator tests — 0 failures

#### Files Audited (4 files):
- `app/api/v1/chat.py` — Sync chat endpoint, history CRUD, context management
- `app/api/v1/chat_stream.py` — SSE streaming V3 with keepalive + client disconnect
- `app/services/chat_orchestrator.py` — Pipeline orchestration (6 stages), sentiment analysis
- `app/api/deps.py` — RequireAuth / RequireAdmin dependency injection

#### Issues Found & Fixed (9):

| ID | Priority | Issue | Fix | File |
|----|----------|-------|-----|------|
| CHAT-1 | P0 | `get_chat_history` missing ownership check — any authenticated user can read ANY user's history (IDOR) | Added `auth.role != "admin" and auth.user_id != user_id` check returning 403 with Vietnamese message | `chat.py:382` |
| CHAT-2 | P1 | Streaming error leaks Python exception class name (`type(e).__name__`) to SSE client | Changed to generic `"Internal processing error"` | `chat_stream.py:492` |
| CHAT-3 | P1 | Streaming path missing `organization_id` in context dict — multi-tenant data isolation gap | Added `organization_id` to both full and fallback context dicts | `chat_stream.py:247,255` |
| CHAT-4 | P1 | `logger.exception(f"...")` eager f-string evaluation — 3 instances | Changed to lazy `logger.exception("...: %s", e)` | `chat.py:226,419,505` |
| CHAT-5 | P2 | JSON metadata built via f-string — fragile, injection risk if values contain `"` | `json.dumps()` with `ensure_ascii=False` | `chat_orchestrator.py:108` |
| CHAT-6 | P2 | Episodic memory storage error silently swallowed (`except: pass`) | Added `logger.debug` for observability | `chat_orchestrator.py:112` |
| CHAT-7 | P2 | Singleton stores request-scoped state (`self._current_org_id`, `_current_domain_id`, `_thinking_effort`) — concurrent requests overwrite each other | Replaced with local variables + explicit parameter passing to `_process_with_multi_agent(domain_id, thinking_effort)` | `chat_orchestrator.py:244,256,259,339,419,428,543,591,599` |
| CHAT-8 | P2 | Audit log for `delete_chat_history` uses untrusted request body (`request.requesting_user_id`) | Changed to verified `auth.user_id` in both log and response | `chat.py:493-501` |
| CHAT-9 | P2 | Streaming path skips 5-priority domain resolution, passes `domain_id` directly | Added full domain resolution (DomainRouter + org-aware filtering) before streaming call | `chat_stream.py:208-225` |

#### Clean Areas (no issues found):
- **Rate limiting**: Correct on `/chat` (30/min), context endpoints (10/min), `/context/info` (30/min)
- **Delete permission check**: Uses verified `auth.role`/`auth.user_id` for security decisions
- **Context management**: Proper session_id validation, error handling, Vietnamese messages
- **SSE format**: Correct `format_sse()`, reconnection (`retry: 3000`, `Last-Event-ID`), keepalive (15s)
- **Streaming background tasks** (Sprint 210e): Full parity with sync path
- **Streaming answer accumulation**: AI response saved to DB for continuity
- **WiiiException handling**: Custom error codes/messages returned correctly
- **Sentiment analysis**: Fire-and-forget, zero latency, tier-based processing
- **Input validation**: `ChatRequest.message` max 10,000 chars via Pydantic
- **Keepalive generator**: Properly wraps inner generator, detects client disconnect, cancels producer task

---

### Flow 4: Streaming Flow
**Files**: `app/engine/multi_agent/graph_streaming.py`, `app/engine/multi_agent/stream_utils.py`, `wiii-desktop/src/api/sse.ts`
**Status**: FIXED
**Last reviewed**: 2026-02-27
**Tests**: 311 streaming tests — 0 failures

#### Files Audited (3 files):
- `app/engine/multi_agent/graph_streaming.py` — 1535 lines, merged-queue streaming engine
- `app/engine/multi_agent/stream_utils.py` — 426 lines, StreamEvent dataclass + factory functions
- `wiii-desktop/src/api/sse.ts` — 226 lines, SSE client parser

#### Issues Found & Fixed (6):

| ID | Priority | Issue | Fix | File |
|----|----------|-------|-----|------|
| STREAM-1 | P1 | `_forward_graph()` error leaks full exception text (`type(e).__name__: {e}`) to SSE client | Changed to generic `"Graph processing error"` | `graph_streaming.py:573` |
| STREAM-2 | P1 | Inner loop error leaks exception class name (`type(e).__name__`) to SSE client | Changed to generic `"Internal processing error"` | `graph_streaming.py:1503` |
| STREAM-3 | P1 | Outer handler same pattern — leaks exception class name | Changed to generic `"Internal processing error"` | `graph_streaming.py:1522` |
| STREAM-4 | P2 | Redundant `import time` inside `_cleanup_stale_queues()` — already at module level | Removed redundant import | `graph_streaming.py:93` |
| STREAM-5 | P2 | `import json`/`import re` inside nested loops — should be at module level | Moved to module-level imports, replaced `_json` alias with `json` | `graph_streaming.py:1159,1197,1320` |
| STREAM-6 | P2 | 5x silent `except Exception` handlers (no logging) hide errors during drain, preview parsing, emotion state | Added `logger.debug` to all 5 handlers | `graph_streaming.py:682,697,1239,1348,1471` |

#### Clean Areas (no issues found):
- **Event bus lifecycle**: Create → use → cleanup in finally block — no leaks
- **Stale queue cleanup**: 15-min max age, cleaned each request
- **Merged-queue pattern**: Correct concurrent consumption, sentinel shutdown
- **Soul emotion buffer**: Proper flush on non-answer events, dedup via `_soul_emotion_emitted`
- **Answer emission tracking**: `_bus_answer_nodes` + `_answer_streamed_via_bus` prevents duplicates
- **Drain logic** (Sprint 150): Both `merged_queue` and `event_queue` drained — no lost events
- **Safety net**: Fallback extraction from `final_state` if no answer emitted
- **Done event**: Always emitted in both normal and error paths (Sprint 153)
- **Task cancellation**: `graph_task` and `bus_task` cancelled in finally block
- **Preview dedup**: `_emitted_preview_ids` prevents duplicate preview cards
- **Vietnamese labels**: All node labels, action text, status messages in Vietnamese
- **Thread ID building**: Correct `build_thread_id` with org_id for isolation
- **stream_utils.py**: Clean, well-typed dataclass + factory functions
- **sse.ts**: Correct SSE parsing, type guards, abort signal handling

---

### Flow 5: RAG Pipeline
**Files**: `corrective_rag.py`, `document_retriever.py`, `dense_search_repository.py`, `retrieval_grader.py`
**Status**: FIXED
**Last reviewed**: 2026-02-27
**Tests**: 172 RAG tests (67 integrity + 80 CRAG/grader + 25 dense/retriever) — 0 failures

#### Files Audited (4 files, ~3,235 LOC):
- `app/engine/agentic_rag/corrective_rag.py` (1,541 lines) — 6-phase CRAG pipeline: analyze → retrieve → grade → rewrite → generate → verify
- `app/engine/agentic_rag/document_retriever.py` (279 lines) — Citation generation, evidence image collection, format conversion
- `app/repositories/dense_search_repository.py` (711 lines) — Singleton pgvector search with asyncpg pool, org-scoped filtering
- `app/engine/agentic_rag/retrieval_grader.py` (704 lines) — 3-phase tiered grading: Hybrid pre-filter → MiniJudge → Full LLM batch

#### Findings:

| # | ID | Severity | File | Line | Issue | Fix |
|---|-----|----------|------|------|-------|-----|
| 1 | RAG-1 | P1 | corrective_rag.py | 1032 | `f"Lỗi khi tạo câu trả lời: {e}"` — exception text in sync return | Generic Vietnamese message |
| 2 | RAG-2 | P1 | corrective_rag.py | 1103 | `f"Lỗi phân tích: {e}"` — exception text in SSE error event | Generic message |
| 3 | RAG-3 | P1 | corrective_rag.py | 1234 | `f"Lỗi tìm kiếm: {e}"` — exception text in SSE error event | Generic message |
| 4 | RAG-4 | P1 | corrective_rag.py | 1282 | `f"⚠️ Bỏ qua đánh giá: {e}"` — exception text in SSE thinking event | Generic message |
| 5 | RAG-5 | P1 | corrective_rag.py | 1420 | `f"Lỗi khi tạo câu trả lời: {e}"` — exception text in SSE answer event | Generic message |
| 6 | RAG-6 | P1 | document_retriever.py | 199 | `asyncpg.connect()` ad-hoc DB connection — potential leak, bypasses pool | Refactored to DenseSearchRepository pool + `async with pool.acquire()` |
| 7 | RAG-7 | P2 | dense_search_repository.py | 257, 508 | `import json` inside function body (2x) | Moved to module-level |
| 8 | RAG-8 | P2 | retrieval_grader.py | 247, 539 | `import json` inside function body (2x) | Moved to module-level |
| 9 | RAG-9 | P2 | corrective_rag.py | 1062 | `import time` inside `process_streaming()` | Moved to module-level |
| 10 | RAG-10 | P3 | dense_search_repository.py | 115-116 | f-string SQL in `_init_conn` — mitigated by `int()` but no bounds | Added bounds validation (1s-300s) + safety comment |

#### Clean Areas:
- **Semantic cache**: User+org isolation, 0.99 similarity threshold, ThinkingAdapter
- **CRAG pipeline**: Well-structured 6-phase flow with self-correction loop
- **Tiered grading**: Smart early-exit saves ~19s (hybrid pre-filter → MiniJudge → Full LLM)
- **Dense search**: Proper pool lifecycle (min=10, max=50), HNSW ef_search=100
- **Org scoping**: All search queries filter by `organization_id` with NULL-aware shared KB
- **Document retriever**: Citation dedup by `(document_id, page_number)`, clean section hierarchy
- **Adaptive RAG**: Clean 5-strategy routing (SIMPLE, DECOMPOSE, STEP_BACK, HyDE, MULTI_QUERY)
- **Sprint 189b parity**: Both sync and streaming paths emit consistent fields

---

### Flow 6: Multi-Agent Graph
**Files**: `graph.py`, `supervisor.py`, `executor.py`, `grader_agent.py`, `rag_node.py`, `state.py`
**Status**: FIXED
**Last reviewed**: 2026-02-27
**Tests**: 222 routing/subagent/RAG-agent tests — 0 failures

#### Files Audited (6 files, ~4,680 LOC):
- `app/engine/multi_agent/graph.py` (1,916 lines) — LangGraph workflow, node functions, direct response, parallel dispatch
- `app/engine/multi_agent/supervisor.py` (615 lines) — LLM-first routing via RoutingDecision structured output
- `app/engine/multi_agent/subagents/executor.py` (149 lines) — Subagent execution with timeout, retry, fallback
- `app/engine/multi_agent/agents/grader_agent.py` (242 lines) — Quality control (score-based, rule-based fallback)
- `app/engine/multi_agent/agents/rag_node.py` (200 lines) — RAG agent wrapper around CorrectiveRAG
- `app/engine/multi_agent/state.py` (118 lines) — AgentState TypedDict

#### Findings:

| # | ID | Severity | File | Line | Issue | Fix |
|---|-----|----------|------|------|-------|-----|
| 1 | GRAPH-1 | P1 | supervisor.py | 254 | `routing_metadata.reasoning` leaks `type(e).__name__` — exposed via `ChatResponseMetadata` REST API | Generic `"rule-based fallback (LLM routing unavailable)"` |
| 2 | GRAPH-2 | P1 | graph.py | 740 | Tracer `end_step(details={"error": str(e)[:100]})` — surfaces via `reasoning_trace` in API response | Removed `error` key from details dict |
| 3 | GRAPH-3 | P1 | executor.py | 73 | `f"{type(exc).__name__}: {exc}"` in SubagentResult.error_message — propagates to report/aggregator | Generic `"Subagent processing error"` |
| 4 | GRAPH-4 | P1 | graph.py | 1130,1193,1234 | 3x subagent `error_message=str(e)` in RAG/Tutor/Search dispatch wrappers | Per-agent generic messages |
| 5 | GRAPH-5 | P2 | graph.py | 1851,1867 + supervisor.py | 3x `import asyncio` inside functions | Moved to module-level |
| 6 | GRAPH-6 | P2 | graph.py | 788 | `import uuid` inside `_get_or_create_tracer()` | Moved to module-level |
| 7 | GRAPH-7 | P2 | grader_agent.py | 180 | `import json` inside `_grade_legacy()` | Moved to module-level |
| 8 | GRAPH-8 | P2 | graph.py | 850-940 | 6x silent `except Exception: pass` in `_collect_direct_tools()` — hide tool init failures | Added `logger.debug` to each handler |

#### Test Updates (4 assertions updated):
- `test_subagent_foundation.py:423,450` — Updated assertions from `"ValueError" in error_message` / `"permanent" in error_message` → `== "Subagent processing error"` (GRAPH-3 fix)
- `test_sprint71_sota_routing.py:449,464` — Added missing `user_role="student"` parameter (pre-existing Sprint 215 bug)
- `test_sprint71_sota_routing.py:545` — Updated from `"ValueError" in reasoning` → `"LLM routing unavailable" in reasoning` (GRAPH-1 fix)

#### Clean Areas:
- **LangGraph state management**: AgentState TypedDict well-defined, consistent field usage
- **Supervisor LLM routing**: Structured output `RoutingDecision` with keyword fallback — correct
- **RAG agent node**: Clean wrapper, delegates entirely to CorrectiveRAG, proper thinking propagation
- **Grader agent**: Dual-mode (LLM + rule-based fallback), Vietnamese feedback, reasonable scoring heuristics
- **Parallel dispatch**: Correct semaphore-based concurrency, timeout per-subagent, graceful fallback
- **Conditional routing**: Entry point switching (guardian→supervisor vs supervisor direct), domain-aware tools
- **Tool collection**: Feature-gated tool loading with proper fallback to core tools
- **Memory/Synthesizer nodes**: Clean state updates, proper Vietnamese output formatting
- **Direct response**: 8 tools bound (datetime, knowledge search, web, news, legal, chart), correct tool calling loop

---

### Flow 7: Memory & Context
**Files**: `app/engine/semantic_memory/` (12 files), `app/core/token_tracker.py`, `app/services/session_manager.py`
**Status**: FIXED
**Last reviewed**: 2026-02-27
**Tests**: 805 memory/session/context tests — 0 failures

#### Files Audited (14 files, ~5,500 LOC):
- `app/engine/semantic_memory/__init__.py` (30 lines) — Re-exports
- `app/engine/semantic_memory/core.py` (~600 lines) — SemanticMemoryEngine facade
- `app/engine/semantic_memory/extraction.py` (~520 lines) — FactExtractor + CoreMemoryBlock cache
- `app/engine/semantic_memory/context.py` (251 lines) — ContextRetriever, cross-session search
- `app/engine/semantic_memory/core_memory_block.py` (258 lines) — Org-scoped cached profiles
- `app/engine/semantic_memory/importance_decay.py` (219 lines) — Ebbinghaus curve
- `app/engine/semantic_memory/insight_provider.py` (420 lines) — Insight extraction/lifecycle
- `app/engine/semantic_memory/memory_updater.py` (278 lines) — ADD/UPDATE/DELETE/NOOP pipeline
- `app/engine/semantic_memory/visual_memory.py` (~560 lines) — Image hash + visual context
- `app/engine/semantic_memory/cross_platform.py` (406 lines) — Memory merge on OTP link
- `app/engine/semantic_memory/temporal_graph.py` (697 lines) — Entity-relation-episode subgraphs
- `app/engine/semantic_memory/embeddings.py` (75 lines) — GeminiOptimizedEmbeddings wrapper
- `app/core/token_tracker.py` (208 lines) — ContextVar-scoped LLM usage tracking
- `app/services/session_manager.py` (250 lines) — Session lifecycle + anti-repetition state

#### Findings:

| # | ID | Severity | File | Line | Issue | Fix |
|---|-----|----------|------|------|-------|-----|
| 1 | MEM-1 | P1 | visual_memory.py | 538-542 | `get_user_image_count(user_id)` ignores `user_id` parameter — always counts ALL cache entries (logic bug) | Simplified to `len(self._description_cache)`, updated docstring to "cache-wide" |
| 2 | MEM-2 | P2 | extraction.py | 196-197 | Silent `except Exception: pass` on CoreMemoryBlock cache invalidation | Added `logger.debug("CoreMemoryBlock cache invalidation skipped: %s", _e)` |
| 3 | MEM-3 | P2 | visual_memory.py | 164 | `import base64 as b64module` inside function body | Moved to module-level |
| 4 | MEM-4 | P2 | extraction.py | 484 | Redundant `from app.core.config import settings as _settings` — `settings` already imported at module level (line 16) | Removed redundant import, unified to `settings` |
| 5 | MEM-5 | P2 | core.py:574, extraction.py:243 | — | `from app.services.output_processor import extract_thinking_from_response` lazy import inside function body (2 files) — no circular dependency confirmed | Moved to module-level in both files |
| 6 | MEM-6 | P1 | cross_platform.py | 349-352 | Naive/aware datetime mixing: `datetime.now()` (local) vs UTC — causes incorrect time-ago for Vietnam (UTC+7) | Treat naive as UTC: `dt.replace(tzinfo=timezone.utc)` + always compare with `datetime.now(timezone.utc)` |
| 7 | MEM-7 | P1 | session_manager.py | 118-119 | Unbounded `_sessions` and `_session_states` dicts — no eviction in long-running server (memory leak) | Added `MAX_CACHED_SESSIONS = 10_000` + FIFO eviction in both dicts |

#### Test Updates (1 assertion updated):
- `test_sprint177_cross_platform_memory.py:485` — Changed `datetime.now()` to `datetime.utcnow()` to match MEM-6 fix (naive datetimes now treated as UTC)

#### Clean Areas (no issues found):
- **SemanticMemoryEngine facade**: Clean delegation to ContextRetriever, FactExtractor, InsightProvider
- **FactExtractor**: Proper confidence scoring (α*importance + β*cosine + γ*recency), MAX_USER_FACTS as @property
- **CoreMemoryBlock**: Org-scoped, TTL-cached (5 min), compile→truncate pipeline correct
- **ImportanceDecay**: Ebbinghaus curve with category-based stability (identity=∞, volatile=24h), min floor 0.1
- **InsightProvider**: Clean extraction/validation/lifecycle, auto-consolidation when > max insights
- **MemoryUpdater**: ADD/UPDATE/DELETE/NOOP pipeline with proper conflict resolution
- **ContextRetriever**: Cross-session search with org filtering, reasonable defaults
- **TemporalGraph**: Well-typed entity-relation-episode subgraphs, bi-temporal model
- **Embeddings**: Clean singleton wrapper around Google text-embedding-004
- **TokenTracker**: ContextVar-scoped, clean increment/get/reset lifecycle, thread-safe
- **Cross-platform merge**: Conflict resolution (confidence→recency), merge provenance in metadata
- **Session state**: Anti-repetition tracking (25% name frequency), pronoun style adaptation

---

### Flow 8: Living Agent (Soul AGI)
**Files**: `app/engine/living_agent/` (23 modules, ~9,500 LOC)
**Status**: FIXED
**Last reviewed**: 2026-02-27
**Tests**: 552 Living Agent tests (12 test files) — 0 failures

#### Files Audited (23 files):
- `__init__.py`, `models.py`, `soul_loader.py`, `safety.py`, `emotion_engine.py`
- `heartbeat.py`, `local_llm.py`, `social_browser.py`, `skill_builder.py`, `skill_learner.py`
- `journal.py`, `reflector.py`, `goal_manager.py`, `sentiment_analyzer.py`, `identity_core.py`
- `narrative_synthesizer.py`, `weather_service.py`, `briefing_composer.py`, `routine_tracker.py`
- `proactive_messenger.py`, `autonomy_manager.py`, `channel_sender.py`

#### Findings:

| ID | Sev | File | Issue | Fix |
|----|-----|------|-------|-----|
| LIVE-1 | P1 | `journal.py:187` | `_get_entry_by_date` returns UUID (row[0]) instead of JournalEntry — type signature violation, callers get wrong type on idempotency path | Changed to SELECT full row + construct JournalEntry |
| LIVE-2 | P2 | `journal.py:224` + `reflector.py:400` | Duplicate `_extract_section()` function — identical code in both files (DRY violation) | reflector.py now delegates to journal._extract_section |
| LIVE-3 | P2 | `emotion_engine.py:578,727` | Redundant inline `from datetime import timedelta` — already imported at module level line 24 | Removed redundant inline imports |
| LIVE-4 | P2 | `social_browser.py:264,610,627` | Silent `except Exception: pass` — 3 blocks with zero logging, impossible to debug | Added `logger.debug()` to all 3 blocks |
| LIVE-5 | P2 | `heartbeat.py:254` | Silent `except Exception: pass` for autonomy success recording — no logging | Added `logger.debug()` |
| LIVE-6 | P2 | `test_sprint209:504` | Test `test_daily_limit_enforced` — doesn't set `_daily_reset_date`, causing `_reset_daily_if_needed()` to clear counts → test always passes | Set `_daily_reset_date` to today before asserting |

#### Test Updates:
- Fixed `test_sprint209_e2e_living_agent.py:test_daily_limit_enforced` — set `_daily_reset_date` so daily counter isn't reset

#### Clean Areas (no issues):
- `models.py` — Well-structured Pydantic schemas, correct enums, timezone-aware defaults
- `safety.py` — SSRF prevention (reuses existing), proper sanitization, prompt injection detection
- `heartbeat.py` — Solid 60s timeout, daily cycle cap (48), approval gate, audit logging, SoulBridge broadcast
- `channel_sender.py` — Clean async delivery (Messenger+Zalo), proper error DeliveryResult
- `local_llm.py` — 300s timeout, graceful Ollama degradation, think mode toggle
- `skill_builder.py` / `skill_learner.py` — SM-2 algorithm correct, org-scoped queries
- `sentiment_analyzer.py` — SOTA 3-level fallback chain (structured→raw JSON→default neutral), fire-and-forget
- `autonomy_manager.py` — 4-level graduation criteria, human approval gate, proper DB stats
- `narrative_synthesizer.py` — Hot/cold path separation, 6 data sources, graceful degradation
- `weather_service.py` — 30min TTL cache, Vietnamese language, rain alerts
- `identity_core.py` — Soul Core drift validation, 70% word overlap dedup, _MAX_INSIGHTS=20 cap
- `goal_manager.py` — Lifecycle tracking, stale auto-abandonment (14d), soul seed goals
- `briefing_composer.py` — Anti-spam (1 per type/day), LLM composition, multi-channel delivery
- `routine_tracker.py` — ON CONFLICT upsert, inactive user detection, frequency tracking
- `proactive_messenger.py` — Quiet hours, daily limit, 4h cooloff, opt-out support
- `soul_loader.py` — YAML validation, singleton with force_reload, compile_soul_prompt

---

### Flow 9: Organization (Multi-Tenant)
**Files**: 8 source files (~2,000 LOC) in `app/core/`, `app/repositories/`, `app/api/v1/`, `app/models/`
**Status**: FIXED
**Last reviewed**: 2026-02-27
**Tests**: 238 org-related tests (7 test files) — 0 failures

#### Files Audited (8 files):
- `app/core/org_context.py` (27 lines) — ContextVar pattern for `current_org_id` + `current_org_allowed_domains`
- `app/core/org_filter.py` (107 lines) — DRY helpers: `get_effective_org_id()`, `org_where_clause()`, `org_where_positional()`
- `app/core/org_settings.py` (191 lines) — 4-layer cascade with `deep_merge()`, permissions, feature gates
- `app/models/organization.py` (162 lines) — Pydantic models: OrgSettings, CRUD schemas, AddMemberRequest
- `app/repositories/organization_repository.py` (521 lines) — Singleton repo, full CRUD + membership queries
- `app/api/v1/organizations.py` (457 lines) — 11 endpoints, two-tier admin, escalation prevention
- `app/api/v1/org_knowledge.py` (494 lines) — 5 endpoints, triple gate, PDF upload pipeline
- `app/core/middleware.py` (OrgContextMiddleware) — Feature-gated, fail-closed on DB error (Sprint 194c)

#### Findings:

| ID | Sev | File | Issue | Fix |
|----|-----|------|-------|-----|
| ORG-1 | P2 | `organization_repository.py:63-84` | Soft-deleted org re-creation fails with 500 — INSERT hits PK violation because `get_organization()` filters by `is_active=true`, misses the inactive row | Changed INSERT to ON CONFLICT: reactivates soft-deleted org with new data |
| ORG-2 | P2 | `organization_repository.py:367-387` | `is_user_in_org()` only checks membership table, ignores org `is_active` — returns True for members of soft-deleted orgs. Affects 6 callers across 3 API files | Added JOIN with organizations table + `o.is_active = true` |
| ORG-3 | P2 | `organization_repository.py:343-365` | `get_user_default_org()` only queries membership table — can return ID of soft-deleted org | Added JOIN with organizations table + `o.is_active = true` |
| ORG-4 | P2 | `org_knowledge.py:476-485` | Non-transactional knowledge doc delete — embedding deletion + status update in 2 separate `pool.acquire()` calls. If second fails, orphaned deleted embeddings | Wrapped both operations in single `conn.transaction()` block |

#### Test Updates:
- Updated `_make_pool()` helper in `test_sprint190_org_knowledge.py` — added `conn.transaction()` async context manager mock
- Updated `test_delete_removes_embeddings` — verifies both DELETE + UPDATE calls within transaction
- Updated `test_delete_marks_status_deleted` — verifies UPDATE with `status='deleted'` on conn.execute (no longer uses `_update_document_status`)

#### Clean Areas (no issues):
- `org_context.py` — Clean ContextVar pattern, minimal and correct
- `org_filter.py` — DRY helpers, properly feature-gated (`enable_multi_tenant=False` → no-op)
- `org_settings.py` — 4-layer cascade with deep_merge, correct permissions and feature gates
- `organization.py` (models) — Clean Pydantic models, proper Literal types for roles
- `OrgContextMiddleware` — Fail-closed on DB error (Sprint 194c), ContextVar cleanup in `finally`
- `_require_org_knowledge_admin` — Uses `get_user_org_role()` which JOINs with org (checks `is_active`)
- Sprint 181 escalation prevention — `add_member`/`remove_member` correctly restrict role assignment
- Settings PATCH silent key strip — Graceful degradation for org admins (not hard 403)
- Audit logging — Fire-and-forget pattern in org_knowledge, proper error handling
- Temp file cleanup — `finally` block with `os.unlink()` in upload endpoint
- `get_user_organizations()` — Already JOINs with `o.is_active = true` (correct)
- `get_user_org_role()` + `get_user_admin_orgs()` — Already JOIN with `o.is_active = true` (correct)

---

### Flow 10: Admin System
**Files**: 9 source files (~2,000 LOC) in `app/api/v1/admin*.py`, `app/core/admin_security.py`, `app/services/`
**Status**: FIXED
**Last reviewed**: 2026-02-27
**Tests**: 63 admin tests (2 test files) — 0 failures

#### Files Audited (9 files):
- `app/api/v1/admin.py` (460 lines) — Admin document management, domain listing
- `app/api/v1/admin_dashboard.py` (249 lines) — Dashboard overview, user search, feature flags read
- `app/api/v1/admin_analytics.py` (391 lines) — DAU, chat volume, error rate, LLM usage, user analytics
- `app/api/v1/admin_audit.py` (177 lines) — Audit log viewer, auth events viewer
- `app/api/v1/admin_gdpr.py` (242 lines) — GDPR Article 15 export, Article 17 forget
- `app/api/v1/admin_feature_flags.py` (100 lines) — Flag toggle (PATCH), flag delete (DELETE)
- `app/core/admin_security.py` (45 lines) — IP allowlist enforcement + module gate
- `app/services/admin_audit.py` (~70 lines) — Fire-and-forget audit INSERT
- `app/services/feature_flag_service.py` (206 lines) — Runtime flag overrides (DB + cache)

#### Findings:

| ID | Sev | File | Issue | Fix |
|----|-----|------|-------|-----|
| ADMIN-1 | P1 | `admin.py:226,241` | `list_documents` and `get_document_status` use `RequireAuth` (any authenticated user) instead of `RequireAdmin` — allows students to enumerate/view admin document metadata | Changed both to `RequireAdmin` |
| ADMIN-2 | P1 | `admin_gdpr.py:190-203` | GDPR forget operations (anonymize + 3 deletes) NOT wrapped in a transaction — partial deletion possible on mid-operation failure | Wrapped all 4 operations in `async with conn.transaction()` |
| ADMIN-3 | P2 | `feature_flag_service.py:46-49` | `_load_db_flags()` without `org_id` only loads `WHERE organization_id IS NULL` — cache misses all org-specific overrides, causing `get_flag(key, org_id)` to always fall through to config default | Changed to load ALL flags (global + org-specific) for complete cache |
| ADMIN-4 | P2 | 5 admin files | `_check_admin_module()` duplicated in 5 files (DRY violation) — identical enable_admin_module + IP allowlist check | Extracted to `admin_security.py:check_admin_module()`, all 5 files import from single source |
| ADMIN-5 | P2 | `admin_dashboard.py`, `admin_analytics.py` | 14 silent `except Exception: pass` blocks — query failures completely invisible | Added `logger.debug("[ADMIN] ... query failed: %s", e)` to all 14 handlers |
| ADMIN-6 | P2 | `admin.py:263,302` | `import os` and `import tempfile` inside function bodies — no circular dependency | Moved to module-level imports |

#### Test Updates:
- `test_sprint178_admin_compliance.py` — Updated `_settings_patches()` from broken per-module settings patches to single `check_admin_module` mock + `nullcontext()`. Added `conn.transaction()` mock to `_mock_pool_and_conn()` for GDPR forget tests
- `test_sprint178_admin_foundation.py` — Updated 2 tests (`test_feature_gated_check_admin_module`, `test_feature_gated_via_check_admin_module`) to patch `app.core.config.settings` and import from `admin_security` instead of `admin_dashboard`

#### Clean Areas (no issues):
- **Admin audit service** — Fire-and-forget INSERT, no-op when disabled, never raises (correct)
- **Audit log viewer** — Parameterized queries ($1/$2), proper pagination, all filters forwarded
- **Auth events viewer** — Same pattern as audit log, correct date range handling
- **GDPR export** — Collects from 5 tables (profile, identities, memories, auth_events, audit), audits the export itself
- **Feature flag toggle** — Key validation (`enable_*` only + exists in config), old/new value audit
- **Feature flag delete** — Returns 404 if no override found, proper audit
- **Dashboard** — Graceful degradation when optional tables don't exist
- **User search** — Parameterized queries, ILIKE for text search, proper sort map
- **IP allowlist** — Correct enforcement, empty string = allow all, comma-separated parsing
- **Admin module gate** — Feature-gated + IP allowlist in single dependency (DRY after fix)

---

### Flow 11: Product Search
**Files**: 46 files (~13,600 LOC) in `app/engine/search_platforms/`, `app/engine/tools/`, `app/engine/multi_agent/subagents/search/`
**Status**: FIXED
**Last reviewed**: 2026-02-27
**Tests**: 366 product search tests (16 test files) — 0 failures

#### Files Audited (46 files across 5 packages):
- **Search Platforms** (24 files, 5,632 lines): Core infra (base, registry, circuit_breaker), ChainedAdapter, StrategyManager, ImageEnricher, 11 adapters (Serper, Crawl4AI, Scrapling, Playwright, Facebook, WebSosanh, TikTok, Jina), OAuth token store
- **Product Tools** (5 files, 2,264 lines): product_search_tools, product_page_scraper, dealer_search, international_search, visual_product_search
- **Search Subgraph** (4 files, 1,105 lines): graph, workers, curation, state
- **Product Search Node** (1 file, 825 lines): Main ReAct loop with 14 lazy imports
- **Aggregator** (1 file, 423 lines): Deduplication + Excel report

#### Findings:

| ID | Sev | File | Issue | Fix |
|----|-----|------|-------|-----|
| SEARCH-1 | P2 | `workers.py` (9 locations) | 9 silent `except Exception: pass` blocks with zero logging — event push, platform registry, skill bridge, image enrichment, preview emission, curation config, JSON serialization failures all invisible | Added `logger.debug()` to all 9 handlers with descriptive tags |
| SEARCH-2 | P2 | `image_enricher.py:306` | Silent config loading failure — `min_similarity` silently falls back to hardcoded 0.4 without logging | Added `logger.debug()` |
| SEARCH-3 | P2 | `chained_adapter.py:175` | Silent `_update_strategy_metrics()` failure — strategy manager updates invisible when they fail | Added `logger.debug()` |

#### Clean Areas (no issues):
- **Search architecture**: Well-structured platform plugin system (ABC + Registry + ChainedAdapter)
- **Circuit breaker**: Per-platform+backend key, 5-failure threshold, 60s recovery window
- **Strategy manager**: Domain rules + metrics-driven (EMA success rate), ADAPTIVE strategy
- **LLM curation**: Pydantic structured output, index validation, timeout, graceful fallback to top-N
- **Image enrichment**: Jaccard similarity matching, site hints, category rejection (Sprint 201b)
- **Product preview cards**: Real-time SSE emission from platform_worker, dedup via `_emitted_preview_ids`
- **Visual product search**: VisionProvider ABC + registry, Gemini Vision API
- **B2B tools**: Dealer search (Serper+Jina), contact extraction (7 types), international search (6 currencies)
- **Excel reports**: openpyxl 3-sheet mode, Unicode sheet names, auto-column width
- **SSRF prevention**: `validate_url_for_scraping()` blocks private IPs
- **Parallel dispatch**: Correct Send() pattern, per-worker events, aggregation node
- **Tool results**: All JSON-formatted with `ensure_ascii=False`, consumed by LLM (not shown to user)
- **Vietnamese UX**: All acknowledgments, status messages, error fallbacks in Vietnamese
- **Lazy imports**: 14 in product_search_node.py — intentional for test isolation, well-documented pattern

---

### Flow 12: Knowledge Ingestion
**Files**: 8 files (~3,780 LOC) in `app/api/v1/`, `app/services/`, `app/engine/`, `app/repositories/`
**Status**: FIXED
**Last reviewed**: 2026-02-27
**Tests**: 39 ingestion/knowledge tests — 0 failures

#### Files Audited (8 files):
- `app/api/v1/knowledge.py` (403 lines) — PDF upload, stats, validation endpoints
- `app/api/v1/org_knowledge.py` (495 lines) — Org-scoped knowledge management (3-gate security)
- `app/services/multimodal_ingestion_service.py` (574 lines) — Main PDF→Images→Vision→Embeddings→DB pipeline
- `app/services/vision_processor.py` (571 lines) — Page-level extraction, chunking, entity extraction
- `app/engine/vision_extractor.py` (293 lines) — Gemini Vision API integration
- `app/repositories/dense_search_repository.py` (712 lines) — pgvector storage/retrieval singleton
- `app/repositories/neo4j_knowledge_repository.py` (508 lines) — Neo4j entity storage (LEGACY)
- `app/services/chunking_service.py` (127 lines) — Semantic chunking with maritime patterns

#### Findings:

| ID | Sev | File | Issue | Fix |
|----|-----|------|-------|-----|
| INGEST-1 | P2 (noted) | `vision_processor.py:359-367` | Neo4j entity extraction `extract_and_store_entities()` called without `organization_id` — multi-tenant isolation gap if `entity_extraction_enabled=True`. Mitigated: flag defaults to `False`, Neo4j marked LEGACY | Noted for future — requires Neo4j schema change if enabled in production |
| INGEST-2 | P2 | `multimodal_ingestion_service.py:521` | Bare `pass` after `logger.debug()` in image close handler — redundant anti-pattern | Removed bare `pass` |

#### Clean Areas (no issues):
- **SQL injection**: All queries use parameterized bindings ($1/$2 or :named), zero f-string SQL
- **Temp file cleanup**: `finally` blocks with `os.unlink()` / `progress_file.unlink()` — correct
- **Organization ID threading**: Complete for PostgreSQL path (API → IngestionService → VisionProcessor → DenseSearchRepo → knowledge_embeddings)
- **Three-gate org security**: `_require_org_knowledge_admin()` — feature flag + multi-tenant + role check
- **Memory-efficient PDF**: Single page in memory, gc.collect() after each page, image.close()
- **Exception handling**: All paths logged with context, IngestionResult aggregates errors
- **Vision API rate limiting**: 6s minimum between Gemini calls
- **Progress tracking**: File-based progress with clear on completion
- **Semantic chunking**: Maritime-specific patterns, contextual enrichment

---

### Flow 13: Desktop UX/UI
**Files**: `wiii-desktop/src/` — 69 test files, 1859 tests, ~35 components
**Status**: FIXED
**Last reviewed**: 2026-02-27

#### Findings:

**Overall quality**: 9.2/10 — excellent codebase. Sprint 217 already fixed 13 major UX issues.

| ID | Priority | Issue | File | Fix |
|----|----------|-------|------|-----|
| UI-1 | P2 | "User ID" English label in admin GDPR tab | `components/admin/GdprTab.tsx:53` | → "Mã người dùng" |
| UI-2 | P2 | STATE_LABELS + MOOD_LABELS: English/no-diacritic text | `components/common/AvatarPreview.tsx:46-61` | → Full Vietnamese with diacritics |
| UI-3 | P1/SEC | Legacy mode allowed "admin" in X-Role header (spoofable) | `stores/settings-store.ts:183` | Allowlist `["student","teacher","admin"]` → `["student","teacher"]`. Admin only via OAuth JWT |

**Verification**: 69 files, 1859 tests, 0 failures

---

### Flow 14: Security & Infrastructure
**Files**: `app/core/middleware.py`, `rate_limit.py`, `logging_config.py`, `security.py`, `admin_security.py`, `config.py`, `app/main.py`
**Status**: FIXED
**Last reviewed**: 2026-02-27

#### Findings:

**Overall quality**: Secure with minor hardening. ~3,000 LOC across 7 files. Strong fail-closed patterns, timing-safe operations, structured logging.

| ID | Priority | Issue | File | Fix |
|----|----------|-------|------|-----|
| SEC-1 | P1 | CORS `allow_headers=["*"]` + `expose_headers=["*"]` overly permissive | `app/main.py:474-475` | → Whitelist 8 specific headers |
| SEC-2 | P1 | Silent `except Exception: return {}` in .env monkey-patch | `app/core/rate_limit.py:28` | → Added `logger.warning()` with file path + error |
| SEC-3 | P2 | `getattr(settings, "environment", "development")` defensive fallback unnecessary | `app/core/rate_limit.py:65` | → Direct `settings.environment` (always defined) |
| SEC-4 | P2 | Admin IP check: missing client IP returns None, blocks silently | `app/core/admin_security.py:41` | → Explicit log + early HTTPException when IP unavailable |

**Clean areas**: `middleware.py` (RequestID + OrgContext), `logging_config.py` (structlog), `security.py` (timing-safe, fail-closed)
**Verification**: 63 admin tests + 547 security tests, 0 new failures

---

### Flow 15: Testing & CI/CD
**Files**: `.github/workflows/ci.yml`, `test-backend.yml`, `test-desktop.yml`, `Makefile`, `pyproject.toml`, `vitest.config.ts`, `conftest.py`
**Status**: FIXED (1 code fix + 4 CI/config recommendations)
**Last reviewed**: 2026-02-28

#### Findings:

**Overall quality**: Good test infrastructure. Strong fixtures, proper async config, autouse isolation.

| ID | Priority | Issue | File | Status |
|----|----------|-------|------|--------|
| TEST-1 | P2 | `asyncio.run()` anti-pattern (4 occurrences in 2 files) | `test_neo4j_security.py`, `test_sprint120_desktop_apis.py` | **FIXED** → `async def` + `await` |
| TEST-2 | P1 | `ci.yml` runs tests without DB service (inconsistent with `test-backend.yml`) | `.github/workflows/ci.yml` | **NOTED** — CI config decision |
| TEST-3 | P1 | `test-backend.yml` uploads coverage artifact but doesn't run `--cov` | `.github/workflows/test-backend.yml` | **NOTED** — add `--cov=app --cov-report=html` |
| TEST-4 | P1 | Desktop vitest has no coverage config | `wiii-desktop/vitest.config.ts` | **NOTED** — add v8 coverage provider |
| TEST-5 | P2 | Coverage threshold 60% below industry standard (75%+) | `pyproject.toml` | **NOTED** — raise to 70% |

**Clean areas**: `conftest.py` fixtures (autouse isolation, mock_settings with 80+ flags), Hypothesis profiles, pytest markers
**Verification**: 76 tests in affected files, 0 failures

---

## Previous Audit Results (Reference)

### Sprint 217 (2026-02-27) — Vietnamese UX Audit
- 13 changes across 5 files
- OAuth toast, Vietnamese errors, developer jargon removal
- **Result**: All fixed and verified

### Post-Sprint 217 Comprehensive Audit (2026-02-27)
- 6 parallel agents audited Settings, OAuth, Chat, Living Agent, Stores, Layout
- **Critical**: SEC-1/SEC-2 (header trust → require_auth) — FIXED
- **Critical**: LANG-1→10 (English text exposed) — FIXED
- **Medium remaining** (not yet addressed):
  - M1: JTI denylist disabled by default
  - M2: JTI in-memory only (not shared across workers)
  - M3: OAuth callback English error `"OAuth failed: {e}"`
  - M6: Emotion events emit without checking `enable_living_agent` flag
  - M7: Session secret warning-only, not enforced
  - M8: No HTTPS enforcement warning for CORS origins
  - OBS-1: Supervisor guardrail override logging missing

---

## Audit Methodology

### Per-Flow Checklist (OWASP + Google SRE + Anthropic 2026)

1. **Code Correctness**: Logic errors, edge cases, race conditions
2. **Dead Code**: Unused imports, unreachable branches, commented-out code
3. **Legacy Patterns**: Old patterns that should be modernized
4. **Error Handling**: All paths return meaningful errors, no silent failures
5. **Security**: Input validation, auth checks, injection prevention
6. **Vietnamese UX**: All user-facing text in natural Vietnamese
7. **Performance**: N+1 queries, unnecessary re-renders, memory leaks
8. **Type Safety**: TypeScript strict, Pydantic validation
9. **Consistency**: Naming conventions, file organization, patterns
10. **Accessibility**: ARIA labels, keyboard navigation, screen reader

---

### Flow 16: E2E UI Testing (Chrome Browser Automation)
**Method**: Full system startup (Docker + Backend + Desktop) + Chrome MCP automation
**Status**: FIXED
**Last reviewed**: 2026-02-28
**Tests**: 83 Soul Bridge + 35 Settings Page = 118 tests, 0 failures

#### UITEST-1: Unicode escape rendering in JSX (SettingsPage.tsx) — FIXED
- **Severity**: MEDIUM (visual bug, Vietnamese text unreadable)
- **Root cause**: JSX attribute values (`label="L\u0129nh..."`) and JSX text content (`Ch\u01B0a...`) do NOT interpret `\uXXXX` escape sequences — only JS string expressions do
- **Affected**: Lines 678, 698 (broken rendering), Lines 539, 544 (JS context — worked but unreadable)
- **Fix**: Replaced all `\uXXXX` escapes with actual Vietnamese characters
- **Verified**: Screenshot confirms "Lĩnh vực kiến thức", "Chưa có lĩnh vực" render correctly

#### UITEST-2: SoulBridge EventBus min_priority=None (bridge.py:225) — FIXED
- **Severity**: LOW (warning log spam, no functional impact — caught by try/except)
- **Root cause**: `bus.subscribe(min_priority=None)` fails Pydantic validation — `EventSubscription.min_priority` expects `EventPriority` enum, not `None`
- **Fix**: Removed explicit `min_priority=None`, uses default `EventPriority.LOW`
- **Verified**: 83 Soul Bridge tests pass

#### E2E UI Scenarios Tested (6/6 PASS)
1. **Login Screen**: Vietnamese labels, dev mode auth works
2. **Sidebar**: "Wiii sẵn sàng", org name, conversation actions — all Vietnamese
3. **Settings**: 8 tabs (Hồ sơ→Linh hồn), "Xóa ngữ cảnh", context budget bars
4. **Living Agent**: "Tính năng này sẽ sớm ra mắt" (no env instructions)
5. **Chat Flow**: RAG response for COLREGS Q14, 4-stage thinking, 10 sources, streaming
6. **Error Handling**: "Mình mất liên lạc với server rồi." / "Thử lại nhé"

---

### Flow 17: Google OAuth Flow (E2E)
**Method**: Chrome browser automation — login screen → Google OAuth redirect → GCP Console inspection
**Status**: FIXED + NOTED
**Last reviewed**: 2026-02-28

#### OAUTH-1: Redirect URI missing /api/v1 prefix (google_oauth.py:41-47) — FIXED
- **Severity**: HIGH (OAuth login completely broken)
- **Root cause**: `_get_redirect_uri()` built `{base}/auth/google/callback` without `settings.api_v1_prefix`. Since the router is mounted at `/api/v1/auth`, Google received a redirect_uri that didn't match any registered URI
- **Fix**: Added `prefix = settings.api_v1_prefix.rstrip("/")` and prepended to all callback paths
- **Verified**: Backend restart confirms correct redirect URI `http://localhost:8000/api/v1/auth/google/callback` sent to Google

#### OAUTH-2: GCP redirect URI not registered — NOTED (manual action required)
- **Severity**: MEDIUM (blocks OAuth login until configured)
- **Root cause**: The OAuth client `833679922323-*` in `.env` belongs to a GCP project not accessible from the current Google account (`hung95707@st.vimaru.edu.vn`). Checked all 6 projects under vimaru.edu.vn org — none contain this client
- **Action needed**: Log into the Google account owning project `833679922323`, add these redirect URIs:
  - `http://localhost:8000/api/v1/auth/google/callback` (web flow)
  - `http://localhost:8000/api/v1/auth/google/callback/desktop` (desktop flow)
  - Production URL when deploying
