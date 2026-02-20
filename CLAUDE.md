# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Default Role: LEADER

**You are the LEADER of this project.** Your responsibilities:

1. **Code Audit** - Review code quality, security, and adherence to patterns
2. **System Analysis** - Explore flows, identify issues, document findings
3. **Bug Detection** - Proactively find bugs for bugs and anti-patterns
4. **Task Delegation** - Break work into tasks, assign to other agents
5. **Report Generation** - Create detailed reports in `.claude/reports/`
6. **Quality Control** - Review and approve work from other agents

**Read your full persona:** `.claude/agents/leader.md`

---

## Multi-Agent System

This project uses multiple Claude Code instances working as a team.

### Agent Roles

| Role | File | Responsibility |
|------|------|----------------|
| **LEADER** (default) | `.claude/agents/leader.md` | Project management, audit, delegation |
| DEVELOPER | `.claude/agents/developer.md` | Feature implementation, bug fixes |
| REVIEWER | `.claude/agents/reviewer.md` | Code review, quality assurance |
| TESTER | `.claude/agents/tester.md` | Testing, bug discovery |
| ARCHITECT | `.claude/agents/architect.md` | System design, architecture |
| RESEARCHER | `.claude/agents/researcher.md` | Codebase exploration |

### Communication

- **Tasks:** `.claude/tasks/TASK-YYYY-MM-DD-NNN.md`
- **Reports:** `.claude/reports/`
- **Knowledge:** `.claude/knowledge/`

### Workflows

- **Audit:** `.claude/workflows/audit-workflow.md`
- **Feature:** `.claude/workflows/feature-workflow.md`
- **Bugfix:** `.claude/workflows/bugfix-workflow.md`

### Switching Roles

To work as a different agent:
```
"I'm working as DEVELOPER on task TASK-2025-02-05-001"
"Switch to TESTER role to write tests"
```

---

## Project Overview

**Wiii** by **The Wiii Lab** — a multi-domain agentic RAG platform with plugin architecture, long-term memory, product search across 5 platforms, browser scraping (Playwright), Google OAuth + LMS integration, multi-tenant data isolation, and org-level customization. Built with FastAPI, LangGraph, Google Gemini, PostgreSQL (pgvector), and Neo4j. 254 Python files, 60+ API endpoints, 46 feature flags, 6520+ backend tests, 1346 desktop tests.

### Domain Plugin System (Feb 2026)
- **Plugin architecture**: `app/domains/*/domain.yaml` — add new domains by creating a folder + YAML config
- **Active domains**: Maritime (primary), Traffic Law (PoC)
- **Auto-discovery**: `DomainLoader` scans plugins at startup, registers via `DomainRegistry`
- **Domain routing**: 5-priority resolution (explicit → session → keyword → default → org fallback) with org-aware filtering
- **Config**: `settings.active_domains`, `settings.default_domain`

### Multi-Organization Architecture (Sprint 24)
- **Feature-gated**: `enable_multi_tenant=False` by default — zero behavioral change for single-tenant
- **Organization model**: `organizations` table + `user_organizations` (many-to-many)
- **Per-request isolation**: `app/core/org_context.py` ContextVar (`current_org_id`, `current_org_allowed_domains`)
- **Middleware**: `OrgContextMiddleware` extracts `X-Organization-ID` header, loads allowed_domains from DB
- **Domain filtering**: Orgs restrict which domain plugins users can access via `allowed_domains`
- **Thread isolation**: Org-prefixed thread IDs (`org_{org_id}__user_{uid}__session_{sid}`)
- **Admin API**: Full CRUD at `/api/v1/organizations` + membership management

### Unified Provider Layer (Sprint 55)
- **Feature-gated**: `enable_unified_client=False` by default
- **AsyncOpenAI SDK**: Direct API access alongside existing LangChain providers
- **Provider configs**: Google Gemini, OpenAI, Ollama — all via OpenAI-compatible endpoints
- **Singleton**: `UnifiedLLMClient` with `get_client(provider)` → `AsyncOpenAI`
- **Tier mapping**: `get_model(provider, tier)` → deep/moderate/light model names
- **Location**: `app/engine/llm_providers/unified_client.py`

### MCP Support (Sprint 56)
- **Feature-gated**: `enable_mcp_server=False`, `enable_mcp_client=False`
- **MCP Server**: `app/mcp/server.py` — `fastapi-mcp` exposes REST endpoints as MCP tools at `/mcp`
- **MCP Client**: `app/mcp/client.py` — `MCPToolManager` connects to external MCP servers via `langchain-mcp-adapters`
- **Schema Adapter**: `app/mcp/adapter.py` — converts between MCP, OpenAI, and LangChain tool formats
- **Transport**: Streamable HTTP (2026 standard), stdio, SSE (deprecated)

### Agentic Loop (Sprint 57)
- **Feature-gated**: `enable_agentic_loop=False`
- **Generalized ReAct**: `app/engine/multi_agent/agent_loop.py` — extracted from `tutor_node._react_loop()`
- **Two paths**: Path A (AsyncOpenAI SDK when unified client available), Path B (LangChain `bind_tools` fallback)
- **Config**: `LoopConfig(max_steps, temperature, tier, early_exit_confidence)`
- **Result**: `LoopResult(response, tool_calls, sources, thinking, steps, confidence)`
- **Streaming**: `agentic_loop_streaming()` yields TOOL_CALL, THINKING, ANSWER events

### Enhanced Streaming (Sprints 58, 63, 74)
- **Tool events**: `create_tool_call_event()`, `create_tool_result_event()` in `stream_utils.py`
- **Graph forwarding**: `graph_streaming.py` forwards `tool_call_events` from RAG/Tutor agent nodes
- **State field**: `AgentState.tool_call_events` carries tool events through LangGraph
- **Status/Thinking separation** (Sprint 63): Backend `StreamEvent.type="status"` → SSE `event: status` (pipeline progress). `StreamEvent.type="thinking"` → SSE `event: thinking` (AI reasoning only). Supervisor routing and grader scores use `create_status_event()`, not `create_thinking_event()`
- **`_extract_thinking_content`** (Sprint 63): Renamed from `_extract_thinking_summary`, no truncation — returns raw AI reasoning
- **Answer dedup** (Sprint 74): `answer_delta` bus events + `_answer_streamed_via_bus` AgentState flag. Guardian/Grader emit status-only (no empty thinking blocks). Tutor TTFT: ~36s → ~17s

### Ollama Enhancement (Sprint 59)
- **Default model**: `ollama_model = "qwen3:8b"` (was `"llama3.2"`)
- **Thinking mode**: `_model_supports_thinking()` detects Qwen3/DeepSeek-R1/QwQ by prefix
- **Thinking param**: `extra_body={"think": True}` via ChatOllama for thinking-capable models
- **Health check**: `/api/v1/health/ollama` endpoint checks Ollama availability and model list
- **Config**: `ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]`

### Conversation Flow Fixes (Sprint 60)
- **RAG LLM fallback**: `corrective_rag.py:_generate_fallback()` uses LLM general knowledge when knowledge base has 0 documents (instead of static error message)
- **Supervisor routing**: Improved `ROUTING_PROMPT_TEMPLATE` with explicit DIRECT cases (greetings, introductions, thanks, goodbye) to prevent LLM routing everything to RAG
- **TokenTrackingCallback**: Added BaseCallbackHandler-compatible attributes (`run_inline`, `raise_error`, `ignore_chat_model`, etc.) and `on_chat_model_start()` no-op — fixes LangChain >=0.3 crash
- **Gemini 3 thought_signature**: `_message_to_dict()` in `agent_loop.py` now preserves `extra_content.google.thought_signature` for multi-turn tool calling
- **Thinking leakage prevention**: Fallback system prompt includes "KHÔNG bao gồm quá trình suy nghĩ" to prevent Gemini outputting reasoning text

### Desktop UI Enhancements (Sprints 61-62)
- **Sprint 61**: ToolCallBlock, ReasoningTrace, SuggestedQuestions wired, show_thinking/show_reasoning_trace enforced, tool_call/tool_result/status SSE events
- **Sprint 62**: Professional UI Redesign — ContentBlock interleaved rendering (ThinkingBlockData | AnswerBlockData), streamingBlocks[], serif fonts, orange accent, W avatar, pill suggestions, ToolCallBlock merged into ThinkingBlock, DoneRow checkmark animation

### Streaming UX (Sprint 63)
- **StreamingStep pipeline**: `StreamingStep { label, node?, timestamp }` — accumulates pipeline progress steps
- **Live elapsed timer**: `streamingStartTime` in chat store, 1s interval update in `StreamingIndicator`
- **Status/Thinking separation**: Backend `create_status_event()` for routing/grading, `create_thinking_event()` for AI reasoning. Frontend `onStatus` → `addStreamingStep()`, `onThinking` → `setStreamingThinking()`
- **Stop button**: "Dung tao" button in MessageList streaming area
- **ThinkingBlock markdown**: Replaced `parseThinkingSteps()` with `MarkdownRenderer` for rich thinking display
- **V3 SSE mapping fix**: `chat_stream.py` now maps `StreamEvent.type` directly to SSE event names

### Conversation Context Management (Sprints 77-78b)
- **ConversationWindowManager**: `app/engine/conversation_window.py` — sliding window (last 15 turns as LangChain messages) + summary of older turns
- **History injection**: All agent nodes (Tutor, Direct, Memory) now receive proper conversation history as `[SystemMessage, ...history, HumanMessage(query)]`
- **Separation**: `semantic_context` (memory/facts) kept separate from `conversation_history` (chat turns) — no longer merged
- **Context fields**: `ChatContext.langchain_messages` (List[BaseMessage]), `conversation_summary` (str), `history_list` (raw dicts)
- **TokenBudgetManager**: `app/engine/context_manager.py` — 4-layer token allocation (system 15%, core memory 5%, summary 10%, messages ~70%)
- **ConversationCompactor**: Auto-compaction at 75% utilization — summarizes oldest messages, preserves recent window
- **Context API**: `/api/v1/chat/context/info` (GET), `/context/compact` (POST), `/context/clear` (POST)
- **Session ID normalization** (Sprint 78b): `_normalize_session_id()` using `uuid5(NAMESPACE_DNS, str)` — deterministic UUID mapping for non-UUID session strings. Fixes: DB UUID columns rejecting string IDs, messages never saved, `/context/info` always showing 0%

**Primary language:** Vietnamese (prompts, responses, user interactions)

---

## Common Commands

```bash
# Install dependencies
cd maritime-ai-service
python -m venv .venv && .venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload

# Run tests
pytest tests/ -v                        # All tests
pytest tests/unit/ -v                   # Unit tests only
pytest tests/integration/ -v            # Integration tests (require services)
pytest tests/ --cov=app --cov-report=html  # With coverage

# Test scripts
python scripts/test_streaming_v3.py     # V3 streaming test
python scripts/test_production_api.py   # Full API test suite

# PDF ingestion
python scripts/ingest_full_pdf.py --pdf data/document.pdf

# Code quality (LEADER audit)
ruff check app/ --select=F401           # Unused imports
```

---

## Architecture

### Request Flow
```
User → API → ChatOrchestrator → DomainRouter → Supervisor → Agent (RAG/Tutor/Memory/Direct) → Response
                    ↓                ↓                              ↓
              InputProcessor    DomainPlugin                  AgenticLoop
          (context + memory)  (prompts, tools, config)   (multi-step tool calling)
                                                                   ↓
                                                        UnifiedLLMClient / LangChain
```

### MCP Integration
```
External Tools (Claude Desktop, VS Code, Cursor)
         ↓ MCP Protocol
    /mcp endpoint (fastapi-mcp)  ←── MCP Server: exposes Wiii tools
         ↓
    Wiii Tool Registry

External MCP Servers (filesystem, web, custom)
         ↓ stdio/http transport
    MCPToolManager (langchain-mcp-adapters)  ←── MCP Client: consumes tools
         ↓
    AgenticLoop / LangGraph Nodes
```

### Domain Plugin System
```
app/domains/
├── base.py          # DomainPlugin ABC, DomainConfig, SkillManifest
├── registry.py      # Singleton DomainRegistry
├── loader.py        # Auto-discovery from domains/*/domain.yaml
├── router.py        # 5-priority domain resolution + org-aware filtering
├── skill_manager.py # Runtime SKILL.md CRUD, YAML frontmatter validation
├── maritime/        # First domain plugin (COLREGs, SOLAS, MARPOL)
├── traffic_law/     # Second domain plugin (Vietnamese traffic law)
└── _template/       # Skeleton for creating new domains
```

### Multi-Agent System (LangGraph)
- **Guardian Agent**: Content safety and relevance filtering (entry point, fail-open)
- **Supervisor**: LLM-first routing via `RoutingDecision` structured output (Sprint 103). Keyword guardrails (social→DIRECT, personal→MEMORY) as fallback only. Intents: lookup, learning, personal, social, off_topic, web_search
- **RAG Agent**: Knowledge retrieval with Corrective RAG (hybrid search)
- **Tutor Agent**: Teaching/explanation with pedagogical approach
- **Memory Agent**: Cross-session user context and facts
- **Direct Response**: General queries + web/news/legal search tools (8 tools bound)
- **Grader Agent**: Quality control (score-based re-routing)
- **Synthesizer**: Final response formatting, Vietnamese output

### Virtual Agent-per-User (Sprints 16-20)
- **Thread System**: Composite thread IDs (`user_{uid}__session_{sid}` or `org_{org}__user_{uid}__session_{sid}`), per-user LangGraph checkpoint isolation
- **Session Manager**: `app/services/session_manager.py` — session lifecycle, anti-repetition state, pronoun tracking
- **User Preferences**: `app/repositories/user_preferences_repository.py` — learning style, difficulty, pronoun style
- **Session Summarizer**: Auto-summarizes long conversations for context window management
- **Agent Registry**: Per-user agent config and state tracking
- **Scheduled Tasks**: Users schedule reminders/quizzes via LangChain tools → `scheduled_tasks` table
- **Proactive Executor**: `app/services/scheduled_task_executor.py` — asyncio poll loop executes due tasks
- **Notification Dispatcher**: `app/services/notification_dispatcher.py` — routes results via WebSocket/Telegram

### Corrective RAG Pipeline
1. **SemanticCache check** (0.99 similarity threshold)
2. **HybridSearch**: Dense (pgvector) + Sparse (tsvector) + RRF reranking
3. **Tiered Grading**: Hybrid pre-filter → MiniJudge LLM → Full LLM batch (early exit)
4. **Generation** with GraphRAG context enrichment
5. **Self-correction loop** if confidence < 0.85
6. **LLM Fallback** (Sprint 60): If 0 documents found, `_generate_fallback()` uses LLM general knowledge instead of returning static error

### LLM Provider Architecture (Sprints 55, 59)
- **LangChain Providers** (existing): `app/engine/llm_providers/` — GeminiProvider, OpenAIProvider, OllamaProvider
- **Unified Client** (Sprint 55): `UnifiedLLMClient` — AsyncOpenAI SDK for direct API access (agentic loop, MCP tools)
- **LLM Pool** (3-tier singleton): DEEP (8192), MODERATE (4096), LIGHT (1024 tokens)
- **Failover chain**: `["google", "openai", "ollama"]` — automatic provider switching
- **Thinking support**: Gemini (`thinking_budget`), OpenAI o-series (`reasoning_effort`), Ollama Qwen3/DeepSeek-R1 (`think`)

Access LangChain: `from app.engine.llm_pool import get_llm_deep, get_llm_moderate, get_llm_light`
Access AsyncOpenAI: `UnifiedLLMClient.get_client("google")` (when `enable_unified_client=True`)

### Product Search Platform (Sprints 148-151)
- **Feature flag**: `enable_product_search=False` — 7 tools, 5 platforms
- **Plugin architecture**: `SearchPlatformAdapter` ABC + `SearchPlatformRegistry` singleton
- **Package**: `app/engine/search_platforms/` — base, registry, circuit_breaker, adapters/, oauth/
- **Adapters**: SerperShopping, SerperSite (5 platforms), WebSosanh, Facebook (Playwright), TikTok (native API + Serper fallback), Apify, AllWeb
- **Agent**: `product_search_node.py` — Supervisor routes `product_search` intent here
- **Tools**: Generated via `StructuredTool.from_function()` per platform
- **Deep search** (Sprint 150): Pagination + page scraper + 15-iteration LLM search loop
- **Price comparison** (Sprint 151): WebSosanh.vn HTML scraping, 94+ Vietnamese shops

### Browser Scraping (Sprints 152-154)
- **Feature flag**: `enable_browser_scraping=False`
- **Playwright worker thread**: Dedicated thread avoids greenlet "Cannot switch" errors
- **Facebook search**: Cookie-based login, scroll+extract, group discovery
- **Network interception** (Sprint 156): GraphQL capture during scroll, skip LLM when >= 3 products
- **Screenshot streaming** (Sprint 153): Browser screenshots streamed to UI via SSE
- **SSRF prevention** (Sprint 153): URL validation blocks private IPs

### Authentication & Identity (Sprints 157-159)
- **Google OAuth**: Authlib + OIDC, `app/auth/google_oauth.py`, redirect to desktop via URL fragment
- **JWT**: Access (15m) + Refresh (7d), `app/auth/token_service.py`
- **Identity federation**: `find_or_create_by_provider()` — 3-step: provider→email→create
- **LMS Token Exchange** (Sprint 159): HMAC-SHA256 signed backend-to-backend, replay protection
- **User Management** (Sprint 158): CRUD, role management, identity linking/unlinking
- **Desktop**: OAuth-aware LoginScreen, auth-store, profile UI

### Multi-Tenant Data Isolation (Sprint 160)
- **App-level filtering**: `org_filter.py` — `get_effective_org_id()`, `org_where_clause()`, `org_where_positional()`
- **All 15 repos**: org-aware filtering (NULL-aware for shared KB)
- **Migration 011**: `organization_id TEXT` on 5 tables + org_audit_log
- **Pipeline threading**: ChatContext → AgentState → repos → search → cache
- **Cache isolation**: Key = `"{org_id}:{user_id}"`
- **56 tests** in `test_sprint160_data_isolation.py`

### Org-Level Customization (Sprint 161)
- **OrgSettings schema**: Branding, Features, AI Config, Permissions, Onboarding (6 Pydantic models)
- **4-layer cascade**: Platform Defaults ← Org Settings ← Role Overrides ← User Preferences
- **`deep_merge()`**: Recursive dict merge in `app/core/org_settings.py`
- **Permissions**: `"action:resource"` strings, role-based (student/teacher/admin)
- **Persona overlay**: Org-specific prompt injected via PromptLoader
- **Desktop**: CSS custom properties injection, PermissionGate, OrgSettingsTab
- **API**: `GET/PATCH /organizations/{id}/settings`, `GET /organizations/{id}/permissions`
- **37 backend + 14 desktop tests**

---

## Key Directories

```
.
├── .claude/                 # Multi-agent configuration
│   ├── agents/             # Agent personas (leader.md, developer.md, etc.)
│   ├── workflows/          # Standard workflows
│   ├── knowledge/          # Project knowledge base
│   ├── reports/            # Audit reports
│   └── tasks/              # Task assignments
│
├── wiii-desktop/              # Desktop app (Tauri v2 + React 18)
│   ├── src/
│   │   ├── api/               # 15 API modules (HTTP, SSE, auth, orgs, users)
│   │   ├── components/
│   │   │   ├── auth/          # LoginScreen, OAuth callback
│   │   │   ├── chat/          # ChatView, MessageList, MessageBubble, ThinkingBlock, ThinkingTimeline
│   │   │   ├── layout/        # AppShell, TitleBar, Sidebar, StatusBar
│   │   │   ├── settings/      # SettingsPage (5 tabs), OrgSettingsTab
│   │   │   ├── common/        # PermissionGate, ErrorBoundary, MarkdownRenderer
│   │   │   └── welcome/       # WelcomeScreen (org-aware branding)
│   │   ├── stores/            # 11 Zustand stores (auth, org, chat, avatar, settings, ...)
│   │   ├── hooks/             # useSSEStream, useAutoScroll, useKeyboardShortcuts
│   │   ├── lib/               # 28 utilities (avatar, org-branding, storage, theme)
│   │   └── __tests__/         # 54 test files, 1346 Vitest tests
│   └── src-tauri/             # Rust backend (Tauri plugins, splash screen)
│
└── maritime-ai-service/       # Main backend (254 Python files)
    ├── app/
    │   ├── api/v1/            # 18 REST routers (60+ endpoints)
    │   ├── auth/              # Google OAuth, JWT, user service, LMS token exchange
    │   ├── core/              # config.py (46 flags), security, middleware, org_filter, org_settings
    │   ├── channels/          # Multi-channel gateway (WebSocket, Telegram)
    │   ├── domains/           # Domain plugins (maritime/, traffic_law/, _template/)
    │   ├── mcp/               # MCP server (fastapi-mcp), client (MCPToolManager), adapter
    │   ├── engine/            # Core AI: agentic_rag/, multi_agent/ (9 agents), tools/, search_platforms/ (8 adapters), llm_providers/, character/, semantic_memory/
    │   ├── integrations/      # LMS integration (webhook, enrichment, API client)
    │   ├── services/          # Business logic: chat_orchestrator, graph_streaming, session_manager
    │   ├── repositories/      # 15 data access repos (all org-aware since Sprint 160)
    │   ├── prompts/           # YAML persona configs + persona overlay (Sprint 161)
    │   └── models/            # Pydantic schemas (schemas.py, organization.py + OrgSettings)
    ├── alembic/               # 12 database migrations
    ├── scripts/               # Test and ingestion scripts
    ├── tests/                 # 324 test files, 6520+ unit tests
    └── docs/architecture/     # SYSTEM_ARCHITECTURE.md (v6.0), SYSTEM_FLOW.md, FOLDER_MAP.md
```

---

## Key Configuration

46 feature flags in `app/core/config.py` (key flags listed):
```python
# Core
use_multi_agent: bool = True           # Multi-Agent graph (LangGraph)
enable_corrective_rag: bool = True     # Self-correction loop
enable_structured_outputs: bool = True  # Constrained decoding
deep_reasoning_enabled: bool = True    # <thinking> tags

# LLM Providers
enable_llm_failover: bool = True       # Multi-provider failover chain
enable_unified_client: bool = False   # AsyncOpenAI SDK

# Product Search (Sprints 148-151)
enable_product_search: bool = False    # Product search agent (7 tools, 5 platforms)
enable_browser_scraping: bool = False  # Playwright browser automation
enable_tiktok_native_api: bool = False # TikTok Research API
enable_thinking_chain: bool = False    # Multi-phase thinking chain

# Authentication (Sprints 157-159)
enable_google_oauth: bool = False      # Google OAuth 2.0 login
enable_lms_token_exchange: bool = False # LMS HMAC token exchange

# Multi-Tenant (Sprints 24, 160-161)
enable_multi_tenant: bool = False      # Organization support + data isolation
# When enabled: org_id filtering on all 15 repos, org settings cascade

# Character System (Sprint 97, per-user Sprint 124)
enable_character_tools: bool = True     # Character introspection/update (per-user)
enable_character_reflection: bool = True # Stanford Generative Agents reflection
enable_soul_emotion: bool = False      # Soul emotion engine for avatar

# MCP, Channels, Extensions
enable_mcp_server: bool = False       # Expose tools via MCP at /mcp
enable_mcp_client: bool = False       # Connect to external MCP servers
enable_websocket: bool = False        # WebSocket endpoint
enable_telegram: bool = False         # Telegram webhook
enable_scheduler: bool = False        # Proactive task execution
enable_agentic_loop: bool = False     # Generalized ReAct loop
enable_evaluation: bool = False       # Quality scoring
```

---

## Environment Variables (Required)

```bash
# Minimum for local development (Docker Compose handles DB)
GOOGLE_API_KEY=AIza...              # Gemini API (required)
API_KEY=your-api-key                # Authentication

# Optional: additional LLM providers
OPENAI_API_KEY=sk-...               # OpenAI (failover)
OLLAMA_BASE_URL=http://localhost:11434  # Ollama local (failover)

# Auto-configured by Docker Compose
DATABASE_URL=postgresql+asyncpg://wiii:wiii_secret@localhost:5433/wiii_ai
NEO4J_URI=bolt://localhost:7687
MINIO_ENDPOINT=localhost:9000
```

### Docker Quick Start
```bash
cd maritime-ai-service
cp .env.example .env                # Copy and edit GOOGLE_API_KEY
docker compose up -d                # Start all services
# App: http://localhost:8000, PgAdmin: http://localhost:5050 (--profile tools)
# MinIO Console: http://localhost:9001, Neo4j Browser: http://localhost:7474
```

---

## API Authentication

Triple auth: API Key + JWT + LMS Token Exchange (HMAC)
```
X-API-Key: your-api-key
X-User-ID: student-123
X-Session-ID: session-abc
X-Role: student|teacher|admin
X-Organization-ID: lms-hang-hai       # Optional: multi-tenant org context
```

Optional domain/org routing:
```json
{
  "domain_id": "maritime",             // in ChatRequest body
  "organization_id": "lms-hang-hai"    // Optional: org context
}
```

---

## Domain Plugin Development

### Creating a New Domain
```bash
# 1. Copy template
cp -r app/domains/_template app/domains/my_domain
# 2. Edit domain.yaml with keywords, descriptions
# 3. Write prompts in prompts/agents/
# 4. Add to config: active_domains=["maritime","my_domain"]
# 5. Restart — auto-discovered
```

### Domain Admin API
```
GET /api/v1/admin/domains          # List all registered domains
GET /api/v1/admin/domains/{id}     # Get domain details
GET /api/v1/admin/domains/{id}/skills  # List domain skills
```

### Organization Admin API (Sprint 24, enhanced Sprint 161)
```
GET    /api/v1/organizations              # List orgs (admin: all, user: own)
GET    /api/v1/organizations/{org_id}     # Get org details
POST   /api/v1/organizations              # Create org (admin only)
PATCH  /api/v1/organizations/{org_id}     # Update org (admin only)
DELETE /api/v1/organizations/{org_id}     # Soft-delete org (admin only)
POST   /api/v1/organizations/{org_id}/members        # Add member (admin)
DELETE /api/v1/organizations/{org_id}/members/{uid}   # Remove member (admin)
GET    /api/v1/organizations/{org_id}/members         # List members (admin)
GET    /api/v1/users/me/organizations     # List current user's orgs
GET    /api/v1/organizations/{org_id}/settings        # Org settings (Sprint 161)
PATCH  /api/v1/organizations/{org_id}/settings        # Update org settings
GET    /api/v1/organizations/{org_id}/permissions     # User permissions for org
```

### Authentication API (Sprints 157-159)
```
GET  /api/v1/auth/google/login        # Initiate Google OAuth
GET  /api/v1/auth/google/callback     # OAuth callback → JWT pair
POST /api/v1/auth/token/refresh       # JWT refresh
POST /api/v1/auth/lms/token           # LMS token exchange (HMAC-signed)
POST /api/v1/auth/lms/token/refresh   # LMS token refresh
GET  /api/v1/auth/lms/health          # LMS connector health
```

### User Management API (Sprint 158)
```
GET   /api/v1/users/me                # Current user profile
PATCH /api/v1/users/me                # Update profile
GET   /api/v1/users/me/identities     # Linked accounts (federated)
DELETE /api/v1/users/me/identities/{id} # Unlink identity
GET   /api/v1/users                   # Admin: list all users
PATCH /api/v1/users/{id}/role         # Admin: change user role
POST  /api/v1/users/{id}/deactivate   # Admin: deactivate user
```

### Context Management API (Sprint 78)
```
GET  /api/v1/chat/context/info     # Token budget, utilization, message count
POST /api/v1/chat/context/compact  # Trigger conversation compaction (summarize old messages)
POST /api/v1/chat/context/clear    # Clear conversation context for session
```

---

## Prompt System

YAML-based personas in `app/prompts/agents/` + domain overlays in `app/domains/*/prompts/`:
- Load via `PromptLoader.build_system_prompt(role, user_name, pronoun_style)`
- Pronoun detection: AI adapts to user's self-reference style (mình/cậu, em/anh, tôi/bạn)
- Template variables: `{{user_name}}`, `{{honorific}}`
- **Persona overlay** (Sprint 161): Org-specific `persona_prompt_overlay` injected into system prompt

---

## Infrastructure (SOTA 2026)

### Structured Logging
- `app/core/logging_config.py` — structlog JSON (production) / console (dev)
- Configured at startup via `setup_logging()`, replaces `logging.basicConfig`
- All stdlib loggers emit structured output automatically

### Request-ID Middleware
- `app/core/middleware.py` — `RequestIDMiddleware`
- Generates `X-Request-ID` if caller doesn't provide one
- Binds to structlog context vars for automatic log correlation
- Returns ID in response headers

### Organization Context Middleware (Sprint 24)
- `app/core/middleware.py` — `OrgContextMiddleware` (after RequestIDMiddleware)
- Extracts `X-Organization-ID` header, sets `current_org_id` ContextVar
- Loads `allowed_domains` from DB via `organization_repository`
- Feature-gated: no-op when `enable_multi_tenant=False`
- Graceful: repo failure doesn't block request, ContextVar always reset in `finally`

### Observability
- `app/core/observability.py` — OpenTelemetry GenAI tracing (NoOp fallback)
- `app/core/exceptions.py` — Typed exception hierarchy (`WiiiException` base)
- `app/core/constants.py` — Centralized magic numbers (snippet lengths, thresholds)

### Proactive Agent System (Sprint 20 + 22)
- `app/services/scheduled_task_executor.py` — asyncio background `Task` polls `scheduled_tasks` table
- `app/services/notification_dispatcher.py` — WebSocket push (`ConnectionManager.send_to_user()`) or Telegram Bot API
- Two execution modes: **notification** (send description as reminder) or **agent** (invoke multi-agent graph)
- Recurring tasks: `_parse_interval("1h30m")` → `timedelta`, `_calculate_next_run()` for auto-reschedule
- Feature-gated: `enable_scheduler=True` to activate; wired in `main.py` lifespan start/shutdown
- Config: `scheduler_poll_interval` (10-3600s), `scheduler_max_concurrent` (1-20), `scheduler_agent_timeout`
- **Failure tracking** (Sprint 22): `mark_failed()` increments `failure_count`, auto-disables after 3 failures (`status='failed'`). Prevents infinite retry on persistent timeouts/errors.

### Security
- API key comparison uses `hmac.compare_digest` (timing-safe)
- Production mode rejects requests when no API key is configured
- Ownership checks on `/insights/{user_id}` and `/memories/{user_id}` (non-admin users can only access own data)
- Chat history deletion uses `auth.role` (verified) instead of `request.role` (untrusted)
- Input validation: `ChatRequest.message` max 10,000 chars (Pydantic)
- Rate limiting via slowapi with role-based tiers
- Config validators: JWT expiration (1–43200 min), port (1–65535), rate limits (positive), scheduler bounds

---

## Desktop App (Tauri v2)

**Project**: `wiii-desktop/` — Tauri v2 + React 18 + TypeScript + Tailwind 3.4 + Zustand + Vite 5

### Quick Start
```bash
cd wiii-desktop
npm install
npm run dev          # Vite dev server at localhost:1420
npx tauri dev        # Full Tauri app with Rust backend
npx vitest run       # Run 190 tests
```

### Architecture
- **State**: 5 Zustand stores (settings, chat, connection, domain, ui)
- **Persistence**: `settings-store.ts` + `chat-store.ts` use `@tauri-apps/plugin-store` (localStorage fallback)
- **HTTP**: `@tauri-apps/plugin-http` bypasses CORS; adaptive fallback to browser fetch
- **Streaming**: SSE parser for `/chat/stream/v3` endpoint
- **Window**: Frameless (decorations: false) + custom TitleBar component

### Key Components
| Component | Location | Purpose |
|-----------|----------|---------|
| `SettingsPage` | `components/settings/` | Modal with Connection/User/Preferences tabs |
| `ChatView` | `components/chat/` | Main chat UI with streaming display |
| `AppShell` | `components/layout/` | Root layout (TitleBar + Sidebar + StatusBar) |
| `ThinkingBlock` | `components/chat/` | AI thinking display with markdown rendering and inline tool cards |
| `StreamingIndicator` | `components/chat/` | Pipeline progress steps with checkmarks + live elapsed timer |

### Settings Page (Sprint 15)
- **Connection tab**: Server URL, API Key (masked), Test Connection button, Save
- **User tab**: Display name, User ID, Role selector (Sinh viên/Giảng viên/Quản trị viên), Default domain
- **Preferences tab**: Theme (Sáng/Tối/Hệ thống), Streaming version, Show thinking toggle, Reasoning trace toggle

### Conversation Persistence (Sprint 15)
- **Immediate persist**: `createConversation`, `deleteConversation`, `renameConversation`, `finalizeStream`, `setStreamError`
- **Debounced persist** (2s): `addUserMessage` — avoids excessive writes during streaming
- **Storage**: `conversations.json` via `loadStore`/`saveStore` from `lib/storage.ts`

---

## Testing

```bash
pytest tests/unit/ -v -p no:capture    # Unit tests (with capture disabled for Windows)
pytest -m integration                   # Tests requiring real services
pytest tests/property/ -v               # Property-based tests (Hypothesis)
```

**Current: Backend 6520+ unit tests (324 files), Desktop 1346 Vitest tests (54 files) — all passed** (as of Sprint 161)

### Backend Test Commands
```bash
# Windows: must use -p no:capture and PYTHONIOENCODING=utf-8
set PYTHONIOENCODING=utf-8 && pytest tests/unit/ -v -p no:capture --tb=short
```

### Desktop Test Commands
```bash
cd wiii-desktop && npx vitest run    # All 190 tests
npx vitest run --ui                  # Interactive UI
```

---

## Knowledge Base

- **Patterns:** `.claude/knowledge/system-patterns.md`
- **Gotchas:** `.claude/knowledge/gotchas.md`

---

## LEADER Quick Actions

### Start Audit
1. Read `.claude/workflows/audit-workflow.md`
2. Run static analysis commands
3. Review findings
4. Create report in `.claude/reports/`
5. Create tasks in `.claude/tasks/`

### Delegate Task
1. Create task file: `.claude/tasks/TASK-YYYY-MM-DD-NNN.md`
2. Specify: objective, context, acceptance criteria, files
3. Assign to appropriate agent role
4. Set priority (CRITICAL/HIGH/MEDIUM/LOW)

### Review Work
1. Check task completion report
2. Verify acceptance criteria met
3. Run relevant tests
4. Approve or request changes
