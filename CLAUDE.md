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

**Wiii** by **The Wiii Lab** — a multi-domain agentic RAG platform with plugin architecture, long-term memory, product search across 5 platforms, browser scraping (Playwright+Crawl4AI+Scrapling), Google OAuth + LMS integration, multi-tenant data isolation, org-level customization, two-tier admin (system + org), Living Agent autonomy system (Soul AGI — all coding phases complete), spaced repetition skill learning, cross-platform memory sync, unified skill architecture, and MCP tool exposure. Built with FastAPI, LangGraph, Google Gemini, PostgreSQL (pgvector), and Neo4j. 354 Python files, 70+ API endpoints, 81 feature flags, 10017 backend tests, 1863 desktop tests. Connection pool: min=10, max=50 (Sprint 173).

### Domain Plugin System (Feb 2026)
- **Plugin architecture**: `app/domains/*/domain.yaml` — add new domains by creating a folder + YAML config
- **Active domains**: Maritime (primary), Traffic Law (PoC)
- **Auto-discovery**: `DomainLoader` scans plugins at startup, registers via `DomainRegistry`
- **Domain routing**: 5-priority resolution (explicit → session → keyword → default → org fallback) with org-aware filtering
- **Config**: `settings.active_domains`, `settings.default_domain`

### Multi-Organization Architecture (Sprint 24, enhanced Sprint 181)
- **Feature-gated**: `enable_multi_tenant=False` by default — zero behavioral change for single-tenant
- **Organization model**: `organizations` table + `user_organizations` (many-to-many)
- **Per-request isolation**: `app/core/org_context.py` ContextVar (`current_org_id`, `current_org_allowed_domains`)
- **Middleware**: `OrgContextMiddleware` extracts `X-Organization-ID` header, loads allowed_domains from DB
- **Domain filtering**: Orgs restrict which domain plugins users can access via `allowed_domains`
- **Thread isolation**: Org-prefixed thread IDs (`org_{org_id}__user_{uid}__session_{sid}`)
- **Admin API**: Full CRUD at `/api/v1/organizations` + membership management
- **Two-tier admin** (Sprint 181): `enable_org_admin=False` — system admin (platform) vs org admin/owner (scoped)
- **Org admin**: Can manage members (add/remove), update branding. Cannot escalate, cannot change features/AI config
- **Permission helper**: `_require_org_admin_or_platform_admin()` returns caller level for downstream checks
- **Admin context**: `GET /users/me/admin-context` — desktop uses to show Shield (system) or Building2 (org) icon

### Unified Provider Layer (Sprint 55)
- **Feature-gated**: `enable_unified_client=False` by default
- **AsyncOpenAI SDK**: Direct API access alongside existing LangChain providers
- **Provider configs**: Google Gemini, OpenAI, Ollama — all via OpenAI-compatible endpoints
- **Singleton**: `UnifiedLLMClient` with `get_client(provider)` → `AsyncOpenAI`
- **Tier mapping**: `get_model(provider, tier)` → deep/moderate/light model names
- **Location**: `app/engine/llm_providers/unified_client.py`

### MCP Support (Sprint 56, enhanced Sprint 194)
- **Feature-gated**: `enable_mcp_server=False`, `enable_mcp_client=False`, `enable_mcp_tool_server=False`
- **MCP Server**: `app/mcp/server.py` — `fastapi-mcp` exposes REST endpoints as MCP tools at `/mcp`
- **MCP Client**: `app/mcp/client.py` — `MCPToolManager` connects to external MCP servers via `langchain-mcp-adapters`
- **Schema Adapter**: `app/mcp/adapter.py` — converts between MCP, OpenAI, and LangChain tool formats
- **MCP Tool Server** (Sprint 194): `app/mcp/tool_server.py` — exposes individual tools as MCP tool definitions
- **Auto-register** (Sprint 194): `MCPToolManager.register_discovered_tools()` bridges MCP external tools → ToolRegistry
- **Transport**: Streamable HTTP (2026 standard), stdio, SSE (deprecated)

### Agentic Loop (Sprint 57)
- **Feature-gated**: `enable_agentic_loop=False`
- **Generalized ReAct**: `app/engine/multi_agent/agent_loop.py` — extracted from `tutor_node._react_loop()`
- **Two paths**: Path A (AsyncOpenAI SDK when unified client available), Path B (LangChain `bind_tools` fallback)
- **Config**: `LoopConfig(max_steps, temperature, tier, early_exit_confidence)`
- **Result**: `LoopResult(response, tool_calls, sources, thinking, steps, confidence)`
- **Streaming**: `agentic_loop_streaming()` yields TOOL_CALL, THINKING, ANSWER events

### Streaming & UX (Sprints 58-74)
- **Events**: `stream_utils.py` — tool_call, tool_result, status (pipeline), thinking (AI reasoning), answer_delta
- **RAG fallback** (Sprint 60): `_generate_fallback()` uses LLM knowledge when 0 documents found

### Conversation Context (Sprints 77-78b)
- Sliding window (15 turns) + summary + TokenBudgetManager (4-layer) + auto-compaction at 75%
- **Context API**: `/api/v1/chat/context/info`, `/context/compact`, `/context/clear`

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
- **Thread System**: Composite IDs (`user_{uid}__session_{sid}` or `org_{org}__user_{uid}__session_{sid}`), per-user LangGraph checkpoints
- **Session Manager**: lifecycle, anti-repetition, pronoun tracking, auto-summarize

### Corrective RAG Pipeline
1. **SemanticCache check** (0.99 similarity threshold)
2. **HybridSearch**: Dense (pgvector) + Sparse (tsvector) + RRF reranking
3. **Tiered Grading**: Hybrid pre-filter → MiniJudge LLM → Full LLM batch (early exit)
4. **Generation** with GraphRAG context enrichment
5. **Self-correction loop** if confidence < 0.85
6. **LLM Fallback** (Sprint 60): If 0 documents found, `_generate_fallback()` uses LLM general knowledge instead of returning static error

### Advanced RAG Strategies (Sprints 179-189)
- **HyDE** (Sprint 187): `hyde_generator.py` — hypothetical document embeddings. Gate: `enable_hyde=False`
- **Adaptive RAG** (Sprint 187): `adaptive_rag.py` — 5 strategies (SIMPLE, DECOMPOSE, STEP_BACK, HyDE, MULTI_QUERY). Gate: `enable_adaptive_rag=False`
- **Visual RAG** (Sprint 179): `visual_rag.py` — query-time visual context via Gemini Vision. Gate: `enable_visual_rag=False`
- **Graph RAG** (Sprint 182): `graph_rag_retriever.py` — entity extraction → Neo4j/PostgreSQL. Gate: `enable_graph_rag=False`

### RAG Ingestion Org Isolation (Sprint 189)
- **Fix**: `organization_id` threaded through entire ingestion pipeline (knowledge API → ingestion → vision_processor)
- **Citation**: `content_type` propagated, source dedup by `(document_id, page_number)`

### Source Flow Integrity (Sprint 189b — 21 fixes, 73 tests)
- **Source fields**: `content_type` + `bounding_boxes` + `evidence_images` propagated through all paths (sync, streaming, CRAG, rag_tools, cache)
- **Error resilience**: All streaming error paths emit "done" event
- **Sync/streaming parity**: `thinking_content`, `was_rewritten`, `node_id`, `routing_metadata` matched between `process()` and `process_streaming()`

### LLM Provider Architecture (Sprints 55, 59)
- **LLM Pool** (3-tier singleton): DEEP/MODERATE/LIGHT. Failover: `["google", "openai", "ollama"]`
- Access: `from app.engine.llm_pool import get_llm_deep` or `UnifiedLLMClient.get_client("google")`

### Product Search Platform (Sprints 148-151, enhanced Sprints 190, 200-201b)
- **Feature flag**: `enable_product_search=False` — 7 tools, 5 platforms
- **Package**: `app/engine/search_platforms/` — `SearchPlatformAdapter` ABC + `SearchPlatformRegistry` singleton
- **Adapters**: SerperShopping, SerperSite, WebSosanh, Facebook (Playwright), TikTok, Apify, AllWeb, Crawl4AI, Scrapling, ScrapeGraph
- **ChainedAdapter** (Sprint 190): Multi-backend priority with per-platform circuit breaker + **ScrapingStrategyManager** (EMA metrics)
- **Deep search** (Sprint 150): Pagination + page scraper + 15-iteration LLM search loop
- **Image Enrichment** (Sprint 201/201b): `image_enricher.py` — Google-cached thumbnails via Serper /images. Gate: `enable_product_image_enrichment=False`
  - Sprint 201b: Skip tiktok_shop, category mismatch rejection, min_similarity raised to 0.4, Instagram key fix
- **Card Data Quality** (Sprint 201b): Rating/sold_count regex extraction from Serper snippets in `workers.py`

### Browser Scraping (Sprints 152-154)
- **Feature flag**: `enable_browser_scraping=False` — Playwright worker thread, Facebook cookie login, GraphQL interception
- **Screenshot streaming** (Sprint 153): Streamed to UI via SSE. **SSRF prevention**: URL validation blocks private IPs

### Unified Skill Architecture (Sprints 191-194)
- **Package**: `app/engine/skills/` — 4 skill types (TOOL, DOMAIN_KNOWLEDGE, LIVING_AGENT, MCP_EXTERNAL)
- **UnifiedSkillIndex**: Read-only projection across 4 systems. Composite IDs: `"tool:name"`, `"domain:id:skill"`, `"living:name"`, `"mcp:server:name"`
- **IntelligentToolSelector** (Sprint 192): 4-step pipeline (category→semantic→LLM→metrics). CORE_TOOLS always included
- **MCPToolServer** (Sprint 194): Exposes tools as MCP definitions + auto-register bridges MCP→ToolRegistry
- **SkillToolBridge** (Sprint 205): 3-loop feedback (Tool→Metrics, Tool→SkillBuilder, Skill→ToolSelector mastery boost)
- **Feature gates**: `enable_unified_skill_index`, `enable_skill_metrics`, `enable_intelligent_tool_selection`, `enable_mcp_tool_server`, `enable_skill_tool_bridge` (all `False`)

### Authentication & Identity (Sprints 157-159, 176, 194c)
- **Google OAuth**: Authlib + OIDC, `app/auth/google_oauth.py`, redirect to desktop via URL fragment
- **PKCE** (Sprint 176): Explicit `code_challenge_method: S256` — OAuth 2.1 compliance
- **JWT**: Access (15m) + Refresh (7d), `app/auth/token_service.py`
- **JWT `jti` claim** (Sprint 176): UUID per token for individual revocation tracking
- **Refresh token `family_id`** (Sprint 176): Groups tokens by login session, replay attack detection
- **Identity federation**: `find_or_create_by_provider()` — 3-step: provider→email→create
- **LMS Token Exchange** (Sprint 159): HMAC-SHA256 signed backend-to-backend, replay protection
- **User Management** (Sprint 158): CRUD, role management, identity linking/unlinking
- **OTP store** (Sprint 176): Database-backed (`otp_link_codes` table), cluster-safe
- **OTP exponential backoff** (Sprint 194c): `delay = min(2^(attempts-1), 60)` seconds between failed attempts, probabilistic cleanup (10%)
- **Auth audit** (Sprint 176): `auth_events` table — login, logout, refresh, revoke, replay, link/unlink events
- **WebSocket first-message auth** (Sprint 194c): API key via first JSON message (not query param), 10s timeout, production role downgrade
- **Admin-context `require_auth`** (Sprint 194c): `/users/me/admin-context` uses `Depends(require_auth)` — no X-User-ID/X-Role trust
- **OrgContextMiddleware fail-closed** (Sprint 194c): DB error clears org context (ContextVar reset)
- **Session secret validation** (Sprint 194c): `session_secret_key >= 32 chars` warning in config + main.py
- **Embed config validation** (Sprint 194c): org/domain regex, server URL origin normalization, HTTPS-only parent origin fallback
- **Desktop**: OAuth-aware LoginScreen, auth-store, secure token storage (Sprint 176), refresh mutex

### Multi-Tenant Data Isolation (Sprint 160)
- **App-level filtering**: `org_filter.py` — all 14 repos org-aware (NULL-aware for shared KB)
- **Pipeline threading**: ChatContext → AgentState → repos → search → cache. Key = `"{org_id}:{user_id}"`

### Org-Level Customization (Sprint 161)
- **4-layer cascade**: Platform Defaults ← Org Settings ← Role Overrides ← User Preferences
- **Permissions**: `"action:resource"` strings. **Persona overlay**: Org-specific prompt via PromptLoader
- **API**: `GET/PATCH /organizations/{id}/settings`, `GET /organizations/{id}/permissions`

### Living Agent System (Sprint 170, enhanced Sprints 177-210d)
- **Feature-gated**: `enable_living_agent=False`, `enable_living_continuity=False` — 22 modules in `app/engine/living_agent/` (8,500+ LOC)
- **Core**: Soul (`wiii_soul.yaml`), 4D emotion (mood/energy/social/engagement), 30-min heartbeat, Ollama `qwen3:8b`
- **Skills**: DISCOVER→LEARN→PRACTICE→EVALUATE→MASTER lifecycle + SM-2 spaced repetition (Sprint 177)
- **Modules**: soul_loader, emotion_engine, heartbeat, skill_builder, skill_learner, journal, social_browser, reflector, goal_manager, autonomy_manager, proactive_messenger, briefing_composer, routine_tracker, weather_service, channel_sender, local_llm, safety, models, identity_core, narrative_synthesizer, sentiment_analyzer
- **Persistent Emotion** (Sprint 188): save/load from DB, circadian rhythm (40% blend energy curve), survives restarts
- **Module Wiring** (Sprint 208): RoutineTracker→ChatOrchestrator, ProactiveMessenger→Heartbeat, AutonomyManager→Heartbeat
- **Living Continuity** (Sprint 210): Chat→Emotion feedback, episodic memory, daily reflection, journal morning+evening, insight extraction from browsing, goal seeding from soul, LLM 60s timeout
- **Emotional Dampening** (Sprint 210b): Mood cooldown (30s) + sentiment accumulator (3-event threshold) prevents mood ping-pong from concurrent users
- **Relationship Tiers** (Sprint 210c): 3-tier psychology model — CREATOR (admin, immediate mood) → KNOWN (50+ msgs, aggregate-only) → OTHER (no mood impact). In-memory buffering, heartbeat aggregate processing. Min 10 samples before aggregate nudge. Scales to 10K+ users
- **SOTA LLM Sentiment** (Sprint 210d): Gemini Flash structured output replaces keyword matching. Fire-and-forget async (zero latency). Fallback: structured → raw JSON → default neutral. Understands Vietnamese without diacritics, sarcasm, context. Episode summaries in Vietnamese first-person from Wiii's perspective
- **API**: 19 endpoints at `/api/v1/living-agent/`. **Desktop**: `LivingAgentPanel` (5-tab dashboard: Tổng quan, Kỹ năng, Mục tiêu, Nhật ký, Suy ngẫm)
- **Docker**: `docker-compose.soul-agi.yml` — full stack with Ollama + Cloudflare Tunnel for VPS
- **Status**: All coding phases complete (1A-5B + SOTA 204-210d). Live tested. Remaining: VPS deployment (Phase 6)

### Natural Conversation System (Sprint 203, SOTA 2026)
- **Feature-gated**: `enable_natural_conversation=False` — phase-aware natural conversation
- **Conversation phase**: `"opening"` (0) → `"engaged"` (1-4) → `"deep"` (5-19) → `"closing"` (20+) from `total_responses`
- **Philosophy**: Anthropic 2026 — "Describe WHO the AI IS, not WHAT it MUST NOT do." Positive framing > prohibitions
- **Changes**: Canned greeting bypass, positive phase framing, greeting strip bypass, phase-aware fallback, natural synthesis prompt
- **Diversity**: `llm_presence_penalty` + `llm_frequency_penalty` for response variation

### Soul AGI Two-Path Architecture (Sprints 204-210d — LIVE TESTED)
- **Audit report**: `.claude/reports/SOUL-AGI-AUDIT-2026-02-25.md`
- **SOTA reference**: `memory/soul-agi-architecture.md` — OpenClaw, Letta, Nomi, Voyager, MECoT patterns
- **Three-Layer Identity**: Soul Core (immutable) → Identity Core (self-evolving, Sprint 207) → Context State (per-turn)
- **Two Paths**: Work (multi-agent RAG/tools) ↔ Life (heartbeat autonomy/browsing/learning) — shared Emotion, Memory, Skill Library
- **Skill↔Tool Bridge** (Sprint 205): 3 feedback loops — Tool→Metrics, Tool→SkillBuilder, Skill→ToolSelector mastery boost. Gate: `enable_skill_tool_bridge`
- **Narrative Layer** (Sprint 206): NarrativeSynthesizer compiles journal+reflection+goals+emotion into coherent life story. Gate: `enable_narrative_context`
- **Identity Core** (Sprint 207): Self-evolving Layer 2 — insights from reflections, drift prevention via Soul Core validation. Gate: `enable_identity_core`
- **Module Wiring** (Sprint 208): All Living Agent modules wired into pipeline (RoutineTracker, ProactiveMessenger, AutonomyManager)
- **E2E Tests** (Sprint 209): 74 integration tests across 15 groups validating full pipeline
- **Living Continuity** (Sprint 210): 8 bug fixes — chat→emotion feedback, mood reset (6h→NEUTRAL), daily reflection, expanded journal, insight extraction, goal seeding, episodic memory, LLM timeout
- **Relationship Psychology** (Sprint 210b/c): Construal Level Theory + Dunbar's Number — 3-tier model (CREATOR/KNOWN/OTHER), dampening, aggregate processing, 10K-scale safe

### Soul-to-Soul Communication Bridge (Sprint 213)
- **Feature-gated**: `enable_soul_bridge=False` — real-time cross-service soul communication
- **3-Layer Architecture**: Agent Cards (A2A-inspired identity at `/.well-known/agent.json`) + SoulBridge (WebSocket + HTTP transport) + EventBus integration
- **Package**: `app/engine/soul_bridge/` — 5 modules: models, agent_card, transport, bridge, __init__
- **Models**: `AgentCard` (soul identity), `SoulBridgeMessage` (envelope), `PeerConnection` (transport), `SoulBridge` (core)
- **Transport**: WebSocket primary + HTTP POST fallback. Exponential backoff reconnect (1s→2s→4s→...→max). Priority-based retry (CRITICAL 1s/30x, HIGH 5s/10x, NORMAL 30s/3x, LOW no retry)
- **Anti-Echo**: Events with `source: "bridge:<peer>"` never re-forwarded. Prevents infinite loops
- **Dedup Cache**: UUID-based, 5-min TTL, background cleanup every 60s
- **Bridge-worthy events**: ESCALATION, STATUS_UPDATE, MOOD_CHANGE, DISCOVERY, DAILY_REPORT (configurable)
- **Heartbeat integration**: `HeartbeatScheduler._broadcast_soul_bridge()` sends status after each cycle
- **Bro side**: `E:\Sach\DuAn\bro-subsoul\core\soul_bridge.py` — lightweight client connecting TO Wiii
- **API**: 7 endpoints at `/api/v1/soul-bridge/` (status, peers, card, events, ws, connect, disconnect) + `/.well-known/agent.json`
- **Tests**: 77 Wiii tests + 30 Bro tests, 0 failures

### Cross-Platform Identity & Soul Wiii (Sprint 174, enhanced Sprint 177)
- **Feature-gated**: `enable_cross_platform_identity=False` — canonical identity + dual personality (Professional vs Soul)
- **IdentityResolver**: Maps `(channel, sender_id)` → canonical UUID. **PersonalityMode**: explicit → channel_map → default → "professional"
- **Zalo Webhook**: POST /zalo/webhook, MAC verify, Zalo OA API v3 reply
- **Cross-Platform Memory Sync** (Sprint 177): Memory merge on OTP link, conflict resolution. Gate: `enable_cross_platform_memory=False`

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
│   │   ├── api/               # 16 API modules (HTTP, SSE, auth, orgs, users, living-agent)
│   │   ├── components/        # auth/, chat/, layout/, living-agent/, settings/, common/, welcome/, admin/, org-admin/
│   │   ├── stores/            # 13 Zustand stores (auth, org, chat, avatar, settings, living-agent, admin, ...)
│   │   ├── hooks/             # useSSEStream, useAutoScroll, useKeyboardShortcuts
│   │   ├── lib/               # 28 utilities (avatar, org-branding, storage, theme, embed-auth)
│   │   └── __tests__/         # 67 test files, 1841 Vitest tests
│   └── src-tauri/             # Rust backend (Tauri plugins, splash screen)
│
└── maritime-ai-service/       # Main backend (297+ Python files)
    ├── app/
    │   ├── api/v1/            # 19 REST routers (60+ endpoints)
    │   ├── auth/              # Google OAuth, JWT, user service, LMS token exchange, identity resolver, auth audit
    │   ├── core/              # config.py (75+ flags), security, middleware, org_filter, org_settings
    │   ├── channels/          # Multi-channel gateway (WebSocket, Telegram)
    │   ├── domains/           # Domain plugins (maritime/, traffic_law/, _template/)
    │   ├── mcp/               # MCP server (fastapi-mcp), client (MCPToolManager), adapter, tool_server
    │   ├── engine/            # Core AI: agentic_rag/, multi_agent/ (9 agents), tools/, search_platforms/, llm_providers/, character/, semantic_memory/, living_agent/, skills/, soul_bridge/
    │   ├── integrations/      # LMS integration (webhook, enrichment, API client)
    │   ├── services/          # Business logic: chat_orchestrator, graph_streaming, session_manager
    │   ├── repositories/      # 15 data access repos (all org-aware since Sprint 160)
    │   ├── prompts/           # YAML persona configs + persona overlay + soul config
    │   └── models/            # Pydantic schemas (schemas.py, organization.py + OrgSettings)
    ├── alembic/               # 34 database migrations
    ├── scripts/               # Test and ingestion scripts
    ├── tests/                 # 342+ test files, 9830 unit tests (Sprint 210d: 0 failures, all clean)
    └── docs/architecture/     # SYSTEM_ARCHITECTURE.md (v7.0), SYSTEM_FLOW.md, FOLDER_MAP.md
```

---

## Key Configuration

70+ feature flags in `app/core/config.py` (key flags listed):
```python
# Core
use_multi_agent: bool = True           # Multi-Agent graph (LangGraph)
enable_corrective_rag: bool = True     # Self-correction loop
enable_structured_outputs: bool = True  # Constrained decoding
deep_reasoning_enabled: bool = True    # <thinking> tags

# LLM Providers
enable_llm_failover: bool = True       # Multi-provider failover chain
enable_unified_client: bool = False   # AsyncOpenAI SDK

# Product Search (Sprints 148-151, 190, 200-201b)
enable_product_search: bool = False    # Product search agent (7 tools, 5 platforms)
enable_browser_scraping: bool = False  # Playwright browser automation
enable_tiktok_native_api: bool = False # TikTok Research API
enable_thinking_chain: bool = False    # Multi-phase thinking chain
enable_crawl4ai: bool = False          # Crawl4AI scraping backend (Sprint 190)
enable_scrapling: bool = False         # Scrapling scraping backend (Sprint 190)
enable_scrapegraph: bool = False       # ScrapeGraph scraping backend (Sprint 190)
enable_product_preview_cards: bool = True  # SSE preview cards in UI (Sprint 200)
enable_visual_product_search: bool = False # Vision LLM product ID (Sprint 200)
enable_product_image_enrichment: bool = False # Google-cached thumbnails (Sprint 201)
image_enrichment_min_similarity: float = 0.4  # Jaccard threshold (Sprint 201b: raised from 0.25)

# Authentication (Sprints 157-159, 176)
enable_google_oauth: bool = False      # Google OAuth 2.0 login
enable_lms_token_exchange: bool = False # LMS HMAC token exchange
enable_auth_audit: bool = True         # Auth event logging (Sprint 176)

# Multi-Tenant (Sprints 24, 160-161, 181)
enable_multi_tenant: bool = False      # Organization support + data isolation
# When enabled: org_id filtering on all 15 repos, org settings cascade
enable_org_admin: bool = False         # Two-tier admin: system admin + org admin (Sprint 181)

# Character System (Sprint 97, per-user Sprint 124)
enable_character_tools: bool = True     # Character introspection/update (per-user)
enable_character_reflection: bool = True # Stanford Generative Agents reflection
enable_soul_emotion: bool = False      # Soul emotion engine for avatar

# Living Agent (Sprint 170, enhanced 210c)
enable_living_agent: bool = False     # Autonomous soul, emotion, heartbeat, skills, journal
enable_living_continuity: bool = False # Chat→emotion feedback + episodic memory + tier system (Sprint 210)
living_agent_creator_user_ids: str = "" # Comma-separated Tier 0 creator IDs (Sprint 210c)
living_agent_known_user_threshold: int = 50 # Min messages for Tier 1 known user (Sprint 210c)

# Skill Learning, Cross-Platform, Memory (Sprints 174, 177)
living_agent_enable_skill_learning: bool = False  # SM-2 spaced repetition
enable_cross_platform_identity: bool = False  # Canonical identity across platforms
enable_cross_platform_memory: bool = False   # Memory merge on OTP link

# Natural Conversation (Sprint 203, SOTA 2026)
enable_natural_conversation: bool = False  # Phase-aware natural conversation (no canned greetings)
llm_presence_penalty: float = 0.0    # LLM presence penalty for diversity
llm_frequency_penalty: float = 0.0   # LLM frequency penalty against repetition

# Unified Skill Architecture (Sprints 191-194, 205)
enable_unified_skill_index: bool = False  # Cross-system skill discovery
enable_skill_metrics: bool = False    # Tool execution metrics tracking
enable_intelligent_tool_selection: bool = False  # 4-step tool selection pipeline
tool_selection_strategy: str = "hybrid"  # all/category/semantic/metrics/hybrid
tool_selection_max_candidates: int = 15  # Max tools per query
enable_skill_tool_bridge: bool = False  # Skill↔Tool bridge: tool execution → skill advancement (Sprint 205)
enable_narrative_context: bool = False  # Inject Wiii's life narrative into system prompt (Sprint 206)
enable_identity_core: bool = False  # Self-evolving identity — Wiii learns about itself from reflections (Sprint 207)

# Soul Bridge (Sprint 213)
enable_soul_bridge: bool = False     # Soul-to-soul communication (WebSocket + HTTP)
soul_bridge_peers: str = ""          # Comma-separated peer URLs
soul_bridge_heartbeat_interval: int = 30  # Peer heartbeat ping interval (seconds)
soul_bridge_reconnect_max: int = 60  # Max reconnect delay (seconds)
soul_bridge_ws_path: str = "/api/v1/soul-bridge/ws"  # WebSocket path
soul_bridge_bridge_events: str = "ESCALATION,STATUS_UPDATE,MOOD_CHANGE,DISCOVERY,DAILY_REPORT"

# MCP, Channels, Extensions
enable_mcp_server: bool = False       # Expose tools via MCP at /mcp
enable_mcp_client: bool = False       # Connect to external MCP servers
enable_mcp_tool_server: bool = False  # Expose individual tools as MCP definitions (Sprint 194)
mcp_auto_register_external: bool = False  # Auto-register MCP tools into ToolRegistry
enable_websocket: bool = False        # WebSocket endpoint
enable_telegram: bool = False         # Telegram webhook
enable_scheduler: bool = False        # Proactive task execution
enable_agentic_loop: bool = False     # Generalized ReAct loop
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

### Organization Admin API (Sprint 24, enhanced Sprints 161, 181)
```
GET    /api/v1/organizations              # List orgs (admin: all, user: own)
GET    /api/v1/organizations/{org_id}     # Get org details
POST   /api/v1/organizations              # Create org (admin only)
PATCH  /api/v1/organizations/{org_id}     # Update org (admin only)
DELETE /api/v1/organizations/{org_id}     # Soft-delete org (admin only)
POST   /api/v1/organizations/{org_id}/members        # Add member (admin or org admin)
DELETE /api/v1/organizations/{org_id}/members/{uid}   # Remove member (admin or org admin)
GET    /api/v1/organizations/{org_id}/members         # List members (admin or org admin)
GET    /api/v1/users/me/organizations     # List current user's orgs
GET    /api/v1/organizations/{org_id}/settings        # Org settings (Sprint 161)
PATCH  /api/v1/organizations/{org_id}/settings        # Update org settings (org admin: branding only)
GET    /api/v1/organizations/{org_id}/permissions     # User permissions for org (incl. org_role)
GET    /api/v1/users/me/admin-context     # Admin capabilities (Sprint 181)
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

### Living Agent API (Sprint 170)
```
GET  /api/v1/living-agent/status           # Full status (soul, mood, heartbeat, counts)
GET  /api/v1/living-agent/emotional-state  # Current 4D emotional state
GET  /api/v1/living-agent/journal          # Recent journal entries
GET  /api/v1/living-agent/skills           # All skills with lifecycle status
GET  /api/v1/living-agent/heartbeat        # Heartbeat scheduler info
POST /api/v1/living-agent/heartbeat/trigger # Manually trigger heartbeat cycle
```

### Soul Bridge API (Sprint 213)
```
GET  /api/v1/soul-bridge/status              # Bridge status + peer connection states
GET  /api/v1/soul-bridge/peers               # List connected peers with agent cards
GET  /api/v1/soul-bridge/peers/{peer_id}/card  # Specific peer's agent card
POST /api/v1/soul-bridge/events              # HTTP fallback for receiving events
POST /api/v1/soul-bridge/connect             # Manual peer connection
POST /api/v1/soul-bridge/disconnect          # Manual peer disconnect
WS   /api/v1/soul-bridge/ws                  # WebSocket real-time connection
GET  /.well-known/agent.json                 # Soul identity card (A2A-inspired)
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
- `OrgContextMiddleware`: extracts `X-Organization-ID`, sets ContextVar, loads `allowed_domains`. Fail-closed on DB error (Sprint 194c)

### Observability
- OpenTelemetry (`observability.py`), exception hierarchy (`WiiiException`), centralized constants

### Security
- API key comparison uses `hmac.compare_digest` (timing-safe)
- Production mode rejects requests when no API key is configured
- Ownership checks on `/insights/{user_id}` and `/memories/{user_id}` (non-admin users can only access own data)
- Chat history deletion uses `auth.role` (verified) instead of `request.role` (untrusted)
- Input validation: `ChatRequest.message` max 10,000 chars (Pydantic)
- Rate limiting via slowapi with role-based tiers
- Config validators: JWT expiration (1–43200 min), port (1–65535), rate limits (positive), scheduler bounds
- **PKCE S256** (Sprint 176): OAuth 2.1 explicit code_challenge_method
- **JWT `jti`** (Sprint 176): Unique token ID (UUID) for per-token revocation
- **Refresh token families** (Sprint 176): `family_id` + replay attack detection (purge entire family)
- **Secure token storage** (Sprint 176): Desktop tokens in dedicated store, separated from settings
- **OTP database** (Sprint 176): Cluster-safe OTP codes in `otp_link_codes` table
- **OTP exponential backoff** (Sprint 194c): `min(2^(n-1), 60)` cooldown + probabilistic cleanup (10% of generate calls)
- **Auth audit log** (Sprint 176): `auth_events` table — fire-and-forget event logging for all auth actions
- **WebSocket first-message auth** (Sprint 194c): No API key in query params (log-safe), first JSON `{"type":"auth","api_key":"..."}` within 10s
- **Admin-context hardened** (Sprint 194c): Uses `require_auth()` Depends — no header trust in production
- **Middleware fail-closed** (Sprint 194c): `OrgContextMiddleware` clears org context on DB error instead of proceeding with partial state
- **Embed input validation** (Sprint 194c): org/domain format-validated, server URL normalized to origin, HTTPS-only parent origin fallback
- **Session secret validation** (Sprint 194c): Warning when `session_secret_key < 32 chars` (OAuth CSRF state integrity)

---

## Desktop App (Tauri v2)

**Project**: `wiii-desktop/` — Tauri v2 + React 18 + TypeScript + Tailwind 3.4 + Zustand + Vite 5

### Quick Start
```bash
cd wiii-desktop
npm install
npm run dev          # Vite dev server at localhost:1420
npx tauri dev        # Full Tauri app with Rust backend
npx vitest run       # Run 1796 tests
```

### Architecture
- **State**: 13 Zustand stores (settings, chat, auth, org, org-admin, connection, domain, ui, avatar, character, context, living-agent, memory)
- **Persistence**: `settings-store.ts` + `chat-store.ts` use `@tauri-apps/plugin-store` (localStorage fallback)
- **HTTP**: `@tauri-apps/plugin-http` bypasses CORS; adaptive fallback to browser fetch
- **Streaming**: SSE parser for `/chat/stream/v3` endpoint
- **Window**: Frameless (decorations: false) + custom TitleBar component

### Key Components
- `AppShell` (layout), `ChatView` (chat), `SettingsPage` (4 tabs), `ThinkingBlock`, `StreamingIndicator`
- `LivingAgentPanel` (5-tab dashboard: overview, skills, goals, journal, reflections), `OrgManagerPanel` (4-tab org admin), `AdminPanel` (7-tab system admin)

### Conversation Persistence (Sprint 15)
- **Immediate persist**: create/delete/rename/finalize. **Debounced** (2s): addUserMessage
- **Storage**: `conversations.json` via `loadStore`/`saveStore` from `lib/storage.ts`

---

## Testing

```bash
pytest tests/unit/ -v -p no:capture    # Unit tests (with capture disabled for Windows)
pytest -m integration                   # Tests requiring real services
pytest tests/property/ -v               # Property-based tests (Hypothesis)
```

**Current: Backend 10017 unit tests, Desktop 1863 Vitest tests** (as of Sprint 219b, 2026-02-28)

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
