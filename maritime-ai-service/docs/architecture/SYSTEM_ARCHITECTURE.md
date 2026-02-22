# Wiii - System Architecture

**Version:** 7.2 (Post-Sprint 171b — Production Hardening)
**Updated:** 2026-02-22
**Product:** Wiii by The Wiii Lab
**Pattern:** Multi-Domain Agentic RAG with Plugin Architecture, Product Search Platform, Browser Scraping, Authentication & Identity Federation, Multi-Tenant Data Isolation, Org-Level Customization, Living Agent Autonomy
**Codebase:** 286+ Python files, ~80,000 LOC, 60+ API endpoints, 7076+ backend + 1468 desktop tests

---

## Table of Contents

1. [High-Level Architecture](#1-high-level-architecture)
2. [Project Structure](#2-project-structure)
3. [Technology Stack](#3-technology-stack)
4. [Core Components Deep Dive](#4-core-components-deep-dive)
   - 4.1 [API & Middleware Layer](#41-api--middleware-layer)
   - 4.2 [Chat Processing Pipeline](#42-chat-processing-pipeline)
   - 4.3 [Multi-Agent System (LangGraph)](#43-multi-agent-system-langgraph)
   - 4.4 [Corrective RAG Pipeline](#44-corrective-rag-pipeline)
   - 4.5 [Search Architecture](#45-search-architecture)
   - 4.6 [LLM Provider Layer](#46-llm-provider-layer)
   - 4.7 [Domain Plugin System](#47-domain-plugin-system)
   - 4.8 [Memory & Personalization](#48-memory--personalization)
   - 4.9 [Streaming Architecture](#49-streaming-architecture)
   - 4.10 [MCP Integration](#410-mcp-integration)
   - 4.11 [Proactive Agent System](#411-proactive-agent-system)
   - 4.12 [Multi-Tenant Architecture](#412-multi-tenant-architecture)
   - 4.13 [Product Search Platform](#413-product-search-platform)
   - 4.14 [Browser Scraping (Playwright)](#414-browser-scraping-playwright)
   - 4.15 [Authentication & Identity Federation](#415-authentication--identity-federation)
   - 4.16 [LMS Integration](#416-lms-integration)
   - 4.17 [Multi-Tenant Data Isolation](#417-multi-tenant-data-isolation)
   - 4.18 [Org-Level Customization](#418-org-level-customization)
   - 4.19 [Living Agent System](#419-living-agent-system)
5. [Data Layer](#5-data-layer)
6. [Security Architecture](#6-security-architecture)
7. [Desktop Application](#7-desktop-application)
8. [Infrastructure & Deployment](#8-infrastructure--deployment)
9. [Integration Points for LMS](#9-integration-points-for-lms)
10. [Design Principles](#10-design-principles)

---

## 1. High-Level Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        DESK["Wiii Desktop<br/>Tauri v2 + React 18"]
        LMS["LMS Frontend"]
        EXT["External Tools<br/>Claude Desktop / VS Code"]
    end

    subgraph "Channel Gateway"
        REST["REST /api/v1/chat"]
        SSE["SSE /chat/stream/v1,v2,v3"]
        WS["WebSocket /ws"]
        TG["Telegram /webhook/{id}"]
        MCP_EP["MCP /mcp"]
    end

    subgraph "Middleware Stack"
        RID["RequestID Middleware"]
        ORG_MW["OrgContext Middleware"]
        RATE["Rate Limiting (slowapi)"]
        AUTH["Auth (API Key + JWT)"]
    end

    subgraph "Orchestration Layer"
        ORCH["ChatOrchestrator<br/>6-stage pipeline"]
        INPUT["InputProcessor"]
        OUTPUT["OutputProcessor"]
        SESSION["SessionManager"]
        DROUTER["DomainRouter<br/>5-priority"]
    end

    subgraph "Multi-Agent System (LangGraph)"
        GUARD["Guardian"]
        SUP["Supervisor"]
        RAG_A["RAG Agent"]
        TUTOR_A["Tutor Agent"]
        MEM_A["Memory Agent"]
        DIRECT_A["Direct Response"]
        PROD_A["Product Search Agent"]
        GRADE_A["Grader"]
        SYNTH["Synthesizer"]
    end

    subgraph "Knowledge Engine"
        CRAG["CorrectiveRAG"]
        HYBRID["HybridSearch"]
        CACHE["SemanticCache"]
        GRAPHRAG["GraphRAG"]
        ALOOP["Agentic Loop"]
    end

    subgraph "Product Search Platform"
        SREG["SearchPlatformRegistry"]
        SERP["Serper (Shopping+Site)"]
        WSS["WebSosanh"]
        FB_S["Facebook (Search+Groups)"]
        TIKTOK["TikTok Research"]
        APIFY_S["Apify"]
    end

    subgraph "Browser Scraping"
        PW["Playwright Worker"]
        FB_SCROLL["Facebook Scroll+Extract"]
        SCREENSHOT["Screenshot Stream"]
    end

    subgraph "Authentication"
        OAUTH["Google OAuth 2.0"]
        JWT_AUTH["JWT + Refresh Tokens"]
        LMS_TE["LMS Token Exchange<br/>HMAC-SHA256"]
        USER_SVC["User Service<br/>Identity Federation"]
    end

    subgraph "LLM Provider Layer"
        POOL["LLM Pool (3-tier)"]
        UNIFIED["UnifiedLLMClient"]
        GEM["Gemini"]
        OAI["OpenAI"]
        OLL["Ollama"]
    end

    subgraph "Domain Plugins"
        MARITIME["Maritime"]
        TRAFFIC["Traffic Law"]
        TEMPLATE["_template"]
    end

    subgraph "Memory & Learning"
        SMEM["SemanticMemoryEngine"]
        FACT["FactExtractor"]
        INSIGHT["InsightExtractor"]
        LPROF["LearningProfile"]
    end

    subgraph "Data Layer"
        PG["PostgreSQL 15<br/>pgvector + tsvector"]
        NEO["Neo4j 5<br/>Knowledge Graph"]
        MINIO["MinIO S3<br/>Document Storage"]
        VALKEY["Valkey<br/>Cache/Sessions"]
    end

    DESK & LMS --> REST & SSE
    EXT --> MCP_EP
    REST & SSE & WS & TG --> RID
    RID --> ORG_MW --> RATE --> AUTH
    AUTH --> ORCH
    ORCH --> INPUT & OUTPUT & SESSION & DROUTER
    ORCH --> GUARD
    GUARD --> SUP
    SUP --> RAG_A & TUTOR_A & MEM_A & DIRECT_A & PROD_A
    RAG_A & TUTOR_A --> CRAG
    GRADE_A --> SYNTH
    CRAG --> HYBRID & CACHE & GRAPHRAG
    POOL --> GEM & OAI & OLL
    HYBRID --> PG
    GRAPHRAG --> NEO
    SMEM --> PG
    DROUTER --> MARITIME & TRAFFIC
    PROD_A --> SREG
    SREG --> SERP & WSS & FB_S & TIKTOK & APIFY_S
    FB_S --> PW
    PW --> FB_SCROLL & SCREENSHOT
    OAUTH & JWT_AUTH & LMS_TE --> USER_SVC
    USER_SVC --> PG
```

---

## 2. Project Structure

```
maritime-ai-service/                    # Backend (Python)
├── app/                                # 254 files, ~75,000 LOC
│   ├── main.py                         # FastAPI app + lifespan startup/shutdown
│   │
│   ├── api/                            # API Layer (60+ endpoints across 18 routers)
│   │   ├── deps.py                     # Auth dependencies (RequireAuth, RequireAdmin)
│   │   └── v1/
│   │       ├── chat.py                 # POST /chat (JSON response)
│   │       ├── chat_stream.py          # POST /chat/stream/v1,v2,v3 (SSE)
│   │       ├── websocket.py            # WS /ws (persistent connection)
│   │       ├── webhook.py              # POST /webhook/{id} (Telegram + LMS)
│   │       ├── health.py               # GET /health, /health/db, /health/ollama
│   │       ├── admin.py                # Admin: ingest, stats, domains, skills
│   │       ├── threads.py              # Thread CRUD per user
│   │       ├── knowledge.py            # Knowledge ingest + stats
│   │       ├── insights.py             # GET /insights/{user_id}
│   │       ├── memories.py             # GET/DELETE /memories/{user_id}
│   │       ├── sources.py              # GET /sources/{node_id}
│   │       ├── organizations.py        # Multi-tenant org CRUD + membership + settings
│   │       └── context.py              # Context management (token budget, compaction)
│   │
│   ├── auth/                           # Authentication & Identity (Sprint 157-159)
│   │   ├── google_oauth.py             # Google OAuth 2.0 flow + callback
│   │   ├── token_service.py            # JWT creation, refresh, revocation
│   │   ├── user_service.py             # Identity federation (3-step: provider→email→create)
│   │   ├── user_router.py              # /users/me, /users (admin), role/deactivate
│   │   ├── lms_token_exchange.py       # HMAC-signed LMS→Wiii token exchange
│   │   └── lms_auth_router.py          # /auth/lms/token, /auth/lms/health
│   │
│   ├── core/                           # Framework & Cross-cutting (15 files)
│   │   ├── config.py                   # Pydantic Settings (120+ fields, 46 feature flags, validators)
│   │   ├── database.py                 # PostgreSQL pool + Neo4j driver
│   │   ├── security.py                 # API Key (hmac) + JWT auth
│   │   ├── rate_limit.py               # slowapi with per-endpoint limits
│   │   ├── middleware.py               # RequestID + OrgContext middleware
│   │   ├── org_context.py              # Multi-tenant ContextVars
│   │   ├── org_filter.py               # App-level org_id filtering helpers (Sprint 160)
│   │   ├── org_settings.py             # 4-layer settings cascade + permissions (Sprint 161)
│   │   ├── thread_utils.py             # Composite thread ID builder (org-aware)
│   │   ├── token_tracker.py            # Per-request LLM usage accounting
│   │   ├── resilience.py               # Circuit breaker, retry patterns
│   │   ├── exceptions.py               # WiiiException hierarchy
│   │   ├── constants.py                # Centralized magic numbers
│   │   ├── observability.py            # OpenTelemetry (NoOp fallback)
│   │   └── logging_config.py           # structlog JSON/console
│   │
│   ├── channels/                       # Multi-Channel Gateway
│   │   ├── base.py                     # ChannelMessage ABC
│   │   ├── registry.py                 # Channel registration
│   │   ├── websocket_adapter.py        # WebSocket handler + ConnectionManager
│   │   └── telegram_adapter.py         # Telegram Bot API adapter
│   │
│   ├── domains/                        # Domain Plugin System
│   │   ├── base.py                     # DomainPlugin ABC + YamlDomainPlugin
│   │   ├── registry.py                 # Singleton DomainRegistry
│   │   ├── loader.py                   # Auto-discovery from domain.yaml
│   │   ├── router.py                   # 5-priority domain resolution
│   │   ├── skill_manager.py            # Runtime SKILL.md CRUD
│   │   ├── maritime/                   # Maritime domain plugin
│   │   │   ├── domain.yaml             # Config: keywords, tools, description
│   │   │   ├── plugin.py               # MaritimeDomainPlugin
│   │   │   └── prompts/                # Domain-specific prompts
│   │   ├── traffic_law/                # Traffic law domain plugin
│   │   └── _template/                  # Skeleton for new domains
│   │
│   ├── mcp/                            # Model Context Protocol
│   │   ├── server.py                   # MCP Server (fastapi-mcp, /mcp endpoint)
│   │   ├── client.py                   # MCPToolManager (langchain-mcp-adapters)
│   │   └── adapter.py                  # Schema: MCP <-> OpenAI <-> LangChain
│   │
│   ├── engine/                         # Core AI Engine (60+ files)
│   │   ├── llm_pool.py                 # 3-tier LLM singleton (Deep/Moderate/Light)
│   │   ├── llm_factory.py              # LLM creation + ThinkingTier enum
│   │   ├── conversation_window.py      # Sliding window context management (Sprint 77)
│   │   ├── context_manager.py          # Token budget allocation (Sprint 78)
│   │   │
│   │   ├── llm_providers/              # Multi-Provider Architecture
│   │   │   ├── base.py                 # LLMProvider ABC
│   │   │   ├── gemini_provider.py      # Google Gemini (thinking_budget)
│   │   │   ├── openai_provider.py      # OpenAI (reasoning_effort)
│   │   │   ├── ollama_provider.py      # Ollama (Qwen3/DeepSeek-R1 thinking)
│   │   │   └── unified_client.py       # AsyncOpenAI SDK (feature-gated)
│   │   │
│   │   ├── multi_agent/                # LangGraph Multi-Agent System
│   │   │   ├── graph.py                # Graph definition + compile
│   │   │   ├── graph_streaming.py      # SSE event emission + lifecycle + drain
│   │   │   ├── state.py                # AgentState TypedDict (org_id, tool_events)
│   │   │   ├── checkpointer.py         # AsyncPostgresSaver singleton
│   │   │   ├── agent_loop.py           # Generalized ReAct (Path A/B)
│   │   │   └── agents/                 # Agent nodes (9 agents)
│   │   │       ├── supervisor.py       # LLM-first routing (RoutingDecision)
│   │   │       ├── guardian.py         # Content safety (fail-open)
│   │   │       ├── tutor_node.py       # Teaching + ReAct tool calling
│   │   │       ├── rag_node.py         # Knowledge retrieval
│   │   │       ├── memory_node.py      # User memory retrieval
│   │   │       ├── grader_node.py      # Quality scoring (1-10)
│   │   │       ├── synthesizer.py      # Final response formatting
│   │   │       ├── direct_response.py  # General + web/news/legal search tools
│   │   │       └── product_search_node.py  # Product search (7 tools, 5 platforms)
│   │   │
│   │   ├── search_platforms/           # Product Search Platform (Sprint 148-151)
│   │   │   ├── base.py                 # SearchPlatformAdapter ABC
│   │   │   ├── registry.py             # SearchPlatformRegistry singleton
│   │   │   ├── circuit_breaker.py      # Per-platform circuit breaker
│   │   │   ├── adapters/               # 8 platform adapters
│   │   │   │   ├── serper_shopping.py  # Serper Shopping API
│   │   │   │   ├── serper_site.py      # Serper site-specific (5 sites)
│   │   │   │   ├── websosanh.py        # WebSosanh.vn price comparison
│   │   │   │   ├── facebook_search.py  # Facebook Marketplace (Playwright)
│   │   │   │   ├── facebook_group.py   # Facebook Groups (scroll+extract)
│   │   │   │   ├── tiktok_research.py  # TikTok Research API
│   │   │   │   ├── apify.py            # Apify web scraping
│   │   │   │   ├── allweb.py           # AllWeb adapter
│   │   │   │   └── browser_base.py     # Playwright browser base class
│   │   │   └── oauth/                  # Platform OAuth (skeleton)
│   │   │
│   │   ├── character/                  # Character System (Sprint 97+124)
│   │   │   ├── character_repository.py # Per-user character blocks CRUD
│   │   │   ├── character_tools.py      # Introspection/update tools
│   │   │   └── reflection_engine.py    # Stanford Generative Agents reflection
│   │   │
│   │   ├── agentic_rag/               # Corrective RAG Pipeline
│   │   │   ├── corrective_rag.py       # 6-step orchestration
│   │   │   ├── rag_agent.py            # LLM generation
│   │   │   ├── retrieval_grader.py     # Tiered grading (3-tier)
│   │   │   ├── hybrid_search.py        # Search orchestration
│   │   │   ├── query_analyzer.py       # Intent + entity extraction
│   │   │   ├── answer_generator.py     # Response generation
│   │   │   └── verifier.py             # Self-correction loop
│   │   │
│   │   ├── tools/                      # LangChain Tool Registry (15+ tools)
│   │   │   ├── rag_tools.py            # maritime_search, rag_search
│   │   │   ├── memory_tools.py         # save/recall/clear memories
│   │   │   ├── tutor_tools.py          # teaching-specific tools
│   │   │   ├── product_search_tools.py # 7 platform-based search tools
│   │   │   ├── scheduler_tools.py      # schedule_task, list_tasks
│   │   │   ├── preference_tools.py     # get/set user preferences
│   │   │   ├── character_tools.py      # character introspection/update
│   │   │   ├── filesystem_tools.py     # Sandboxed file operations
│   │   │   ├── code_execution_tools.py # Sandboxed Python exec
│   │   │   └── skill_tools.py          # Self-extending agent skills
│   │   │
│   │   ├── semantic_memory/            # Memory Engine
│   │   │   ├── memory_engine.py        # Orchestration
│   │   │   ├── memory_manager.py       # Deduplication
│   │   │   ├── memory_compression.py   # Summarization
│   │   │   └── memory_consolidator.py  # Long-term consolidation
│   │   │
│   │   └── evaluation/                 # Quality Evaluation
│   │       └── evaluator.py            # Faithfulness/Relevancy scoring
│   │
│   ├── services/                       # Business Logic Layer
│   │   ├── chat_orchestrator.py        # 6-stage pipeline (main entry)
│   │   ├── chat_service.py             # Facade for backward compat
│   │   ├── input_processor.py          # Validation + parallel context
│   │   ├── output_processor.py         # Formatting + fact extraction
│   │   ├── session_manager.py          # Session lifecycle + pronouns
│   │   ├── hybrid_search_service.py    # Dense + Sparse + RRF
│   │   ├── graph_rag_service.py        # Neo4j entity enrichment
│   │   ├── learning_graph_service.py   # Learning progress tracking
│   │   ├── session_summarizer.py       # Long conversation compression
│   │   ├── conversation_analyzer.py    # Context analysis
│   │   ├── scheduled_task_executor.py  # Proactive agent (asyncio poll)
│   │   ├── notification_dispatcher.py  # Thin wrapper → registry routing
│   │   ├── notifications/              # Plugin architecture (Sprint 172)
│   │   │   ├── base.py                 # NotificationChannelAdapter ABC
│   │   │   ├── registry.py             # NotificationChannelRegistry singleton
│   │   │   └── adapters/               # 4 channel adapters
│   │   │       ├── websocket.py        # WebSocket push
│   │   │       ├── telegram.py         # Telegram Bot API
│   │   │       ├── messenger.py        # CallMeBot Messenger
│   │   │       └── zalo.py             # Zalo OA API v3
│   │   ├── multimodal_ingestion_service.py  # PDF/image ingestion
│   │   ├── pdf_processor.py            # PyMuPDF page extraction
│   │   ├── vision_processor.py         # Gemini Vision for images
│   │   └── fact_extractor.py           # User fact discovery
│   │
│   ├── repositories/                   # Data Access Layer (15 repos)
│   │   ├── semantic_memory_repository.py    # Memory CRUD + similarity search
│   │   ├── neo4j_knowledge_repository.py    # Graph operations
│   │   ├── dense_search_repository.py       # pgvector similarity (org-aware)
│   │   ├── sparse_search_repository.py      # tsvector FTS (org-aware)
│   │   ├── thread_repository.py             # Thread persistence (org-aware)
│   │   ├── scheduler_repository.py          # Scheduled task CRUD (org-aware)
│   │   ├── organization_repository.py       # Org + membership + settings CRUD
│   │   ├── user_preferences_repository.py   # Learning prefs (org-aware)
│   │   ├── fact_repository.py               # User facts (org-aware)
│   │   ├── insight_repository.py            # Learning insights (org-aware)
│   │   ├── learning_profile_repository.py   # Learning progress (org-aware)
│   │   ├── chat_message_repository.py       # Chat messages (org-aware)
│   │   └── chat_history_repository.py       # Chat sessions (org-aware)
│   │
│   ├── cache/                          # Caching Layer
│   │   └── semantic_cache.py           # 3-tier TTL, asyncio.Lock
│   │
│   ├── models/                         # Pydantic Schemas
│   │   ├── schemas.py                  # API request/response models
│   │   └── organization.py             # Org + OrgSettings + OrgBranding + OrgPermissions
│   │
│   ├── integrations/                   # LMS Integration (Sprint 155)
│   │   ├── lms_client.py              # Outbound LMS API client
│   │   └── lms_enrichment.py          # Webhook data enrichment
│   │
│   └── prompts/                        # Prompt System
│       ├── prompt_loader.py            # YAML persona loader + persona overlay (Sprint 161)
│       └── agents/                     # Persona configs (tutor.yaml, rag.yaml, etc.)
│
├── tests/                              # Test Suite
│   ├── conftest.py                     # Hypothesis + sample fixtures
│   ├── unit/                           # 324 test files, 6520+ tests
│   │   └── conftest.py                 # Autouse: disable rate limiter
│   ├── integration/                    # 31 files (require services)
│   ├── property/                       # Hypothesis property tests
│   └── e2e/                            # End-to-end tests
│
├── scripts/                            # Utility Scripts
│   ├── test_streaming_v3.py            # V3 SSE integration test
│   ├── test_production_api.py          # Full API test suite
│   ├── ingest_full_pdf.py              # PDF ingestion script
│   └── init-db/                        # PostgreSQL init scripts
│
├── docs/architecture/                  # Architecture Documentation
│   ├── SYSTEM_FLOW.md                  # Flow diagrams (v5.0)
│   └── SYSTEM_ARCHITECTURE.md          # This file (v5.0)
│
├── docker-compose.yml                  # 6 services + network
├── Dockerfile                          # Multi-stage Python image
├── requirements.txt                    # ~60 dependencies
└── .env.example                        # Configuration template

wiii-desktop/                           # Desktop App (Tauri v2)
├── src/                                # React 18 + TypeScript (158 files)
│   ├── api/                            # 15 API modules (HTTP, SSE, auth, orgs, users)
│   ├── components/
│   │   ├── auth/                       # LoginScreen, OAuth callback
│   │   ├── chat/                       # ChatView, MessageBubble, ThinkingBlock, ThinkingTimeline
│   │   ├── layout/                     # AppShell, TitleBar, Sidebar, StatusBar
│   │   ├── settings/                   # SettingsPage (5 tabs), OrgSettingsTab
│   │   ├── common/                     # PermissionGate, ErrorBoundary, MarkdownRenderer
│   │   └── welcome/                    # WelcomeScreen (org-aware branding)
│   ├── stores/                         # 11 Zustand stores (auth, org, avatar, chat, ...)
│   ├── hooks/                          # useSSEStream, useAutoScroll, useKeyboardShortcuts
│   ├── lib/                            # 28 utilities (avatar, org-branding, storage, theme)
│   │   └── avatar/                     # WiiiAvatar, Rive integration, emotion engine
│   └── __tests__/                      # 54 test files, 1346 Vitest tests
├── src-tauri/                          # Rust backend (Tauri plugins, splash screen)
└── package.json                        # Vite 5, Tailwind 3.4
```

---

## 3. Technology Stack

### Backend

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Framework** | FastAPI | 0.109.2 | Async REST + WebSocket |
| **Runtime** | Uvicorn | 0.27.1 | ASGI server |
| **Validation** | Pydantic | >=2.9.0 | Settings + request models |
| **Orchestration** | LangGraph | >=1.0.0 | Multi-agent state machine |
| **LLM (primary)** | Google Gemini | 2.0 Flash | via langchain-google-genai >=3.2.0 |
| **LLM (failover 1)** | OpenAI | GPT-4o | via openai >=1.40.0 |
| **LLM (failover 2)** | Ollama | Qwen3:8b | via langchain-community >=0.4.0 |
| **LLM SDK** | AsyncOpenAI | >=1.40.0 | Unified provider (feature-gated) |
| **Embeddings** | Gemini | embedding-001 (768d) | Dense vector search |
| **Vector DB** | PostgreSQL 15 + pgvector | asyncpg 0.30.0 | HNSW similarity search |
| **Full-Text** | PostgreSQL 15 tsvector | built-in | Sparse keyword search |
| **Graph DB** | Neo4j | ~5.28.0 | Knowledge graph + entities |
| **Object Storage** | MinIO | S3-compatible | PDF/image storage |
| **Cache** | Valkey | Redis-compatible | Sessions + cache |
| **Rate Limiting** | slowapi | 0.1.9 | Per-endpoint limits |
| **Logging** | structlog | >=24.1.0 | JSON (prod) / console (dev) |
| **HTTP Client** | httpx | >=0.28.1 | Async HTTP requests |
| **MCP Server** | fastapi-mcp | >=0.3.0 | Expose tools via MCP |
| **MCP Client** | langchain-mcp-adapters | - | Consume external MCP tools |
| **Browser** | Playwright | - | Headless Chrome for scraping (Facebook, web) |
| **PDF** | PyMuPDF (fitz) | - | Page extraction + images |
| **Tracing** | OpenTelemetry | - | Distributed tracing (opt-in) |
| **Auth** | Authlib | - | Google OAuth 2.0 + OIDC |
| **JWT** | PyJWT | - | Token creation + validation |

### Desktop

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Framework** | Tauri | v2 | Cross-platform desktop shell |
| **UI** | React | 18 | Component framework |
| **Language** | TypeScript | - | Type safety |
| **Build** | Vite | 5 | Dev server + bundler |
| **Styling** | Tailwind CSS | 3.4 | Utility-first CSS |
| **State** | Zustand | 5.x | 11 stores (auth, org, chat, avatar, settings, ...) |
| **Persistence** | @tauri-apps/plugin-store | - | Conversation + settings + auth tokens |
| **HTTP** | @tauri-apps/plugin-http | - | CORS bypass for backend |
| **Icons** | Lucide React | - | Icon library |
| **Tests** | Vitest + jsdom | - | 1346 tests across 54 files |

### Infrastructure

| Component | Image / Tool | Purpose |
|-----------|-------------|---------|
| App Container | `wiii-app` | Python FastAPI backend |
| PostgreSQL | `pgvector/pgvector:pg15` | Vectors + FTS + checkpoints |
| Neo4j | `neo4j:5-community` | Knowledge graph (APOC plugin) |
| MinIO | `minio/minio` | S3-compatible document storage |
| Valkey | `valkey/valkey` | Redis-compatible cache |
| PgAdmin | `dpage/pgadmin4` | DB admin (--profile tools) |
| Network | `wiii-network` | Docker bridge network |

---

## 4. Core Components Deep Dive

### 4.1 API & Middleware Layer

**60+ endpoints** across 18 route files, all rate-limited (except health probes).

```mermaid
flowchart LR
    subgraph Middleware["Middleware Pipeline (per-request)"]
        direction TB
        M1["1. RequestIDMiddleware<br/>Generate X-Request-ID<br/>Bind structlog context"]
        M2["2. OrgContextMiddleware<br/>Extract X-Organization-ID<br/>Set ContextVars (if multi-tenant)"]
        M3["3. CORSMiddleware<br/>Cross-origin headers"]
        M1 --> M2 --> M3
    end

    subgraph Deps["FastAPI Dependencies (per-endpoint)"]
        D1["require_auth<br/>API Key or JWT → AuthenticatedUser"]
        D2["@limiter.limit<br/>Per-endpoint rate control"]
        D3["RequireAdmin<br/>Role-based access control"]
    end

    subgraph Routes["Route Groups"]
        R1["Chat: /chat, /chat/stream/*"]
        R2["Management: /threads, /insights, /memories, /sources"]
        R3["Admin: /admin/ingest, /admin/domains, /admin/skills"]
        R4["Orgs: /organizations/*, /organizations/{id}/settings"]
        R5["Health: /health, /health/db, /health/ollama"]
        R6["Channels: /ws, /webhook/{id}"]
        R7["MCP: /mcp (feature-gated)"]
        R8["Auth: /auth/google/*, /auth/token/*, /auth/lms/*"]
        R9["Users: /users/me, /users (admin)"]
        R10["Context: /chat/context/info, /context/compact"]
    end

    Middleware --> Deps --> Routes
```

**Rate Limit Categories:**
| Category | Rate | Applied To |
|----------|------|-----------|
| Chat | 30/min | `/chat`, `/chat/stream/*` |
| Read | 60/min | `/threads`, `/insights/*`, `/memories/*`, `/sources/*`, `/stats` |
| Write/Delete | 30/min | `DELETE /threads/*`, `DELETE /memories/*`, `PATCH /*` |
| Admin | 10-60/min | `/admin/*` (ingest=10, read=60) |
| Organizations | 10-30/min | `/organizations/*` |
| Auth | 10-30/min | `/auth/*` (login=10, refresh=30) |
| Users | 30-60/min | `/users/me` (read=60, write=30) |
| Health | Unlimited | `/health`, `/health/db`, `/health/ollama` |

---

### 4.2 Chat Processing Pipeline

The `ChatOrchestrator` implements a 6-stage pipeline for every chat request.

```mermaid
flowchart TB
    REQ["ChatRequest"] --> S1

    subgraph S1["Stage 1: Session Resolution"]
        SM["SessionManager.get_or_create_session()"]
        SM --> STATE["Load: pronoun style, anti-repeat, preferences"]
    end

    S1 --> S2

    subgraph S2["Stage 2: Domain Resolution"]
        DR["DomainRouter.resolve()"]
        DR --> PRI["5-priority: explicit → session → keyword → default → org"]
        PRI --> PLUGIN["DomainPlugin (prompts, tools, config)"]
    end

    S2 --> S3

    subgraph S3["Stage 3: Input Processing"]
        IP["InputProcessor.process()"]
        IP --> PAR["Parallel Retrieval"]
        PAR --> H["History"] & F["Facts"] & I["Insights"] & P["Pronouns"] & SUM["Summary"]
        H & F & I & P & SUM --> CTX["Build system prompt + user context"]
    end

    S3 --> S4

    subgraph S4["Stage 4: Agent Execution"]
        GRAPH["process_with_multi_agent(state)"]
        GRAPH --> RESPONSE["{'response': str, 'sources': list, 'thinking': str}"]
    end

    S4 --> S5

    subgraph S5["Stage 5: Output Processing"]
        OP["OutputProcessor.process()"]
        OP --> FMT["Format citations + pronoun adaptation + suggested questions"]
    end

    S5 --> S6

    subgraph S6["Stage 6: Background Tasks (async)"]
        BG["FastAPI BackgroundTasks"]
        BG --> FACTS["Extract user facts"]
        BG --> INS["Generate insights"]
        BG --> SUMM["Summarize if long"]
        BG --> LPROF["Update learning profile"]
        BG --> SCACHE["Cache in SemanticCache"]
    end

    S6 --> RESP["InternalChatResponse"]
```

**Key Design Decisions:**
- **Parallel retrieval** in Stage 3 minimizes latency (history, memory, facts retrieved concurrently)
- **Pronoun dedup** (Sprint 65b): LLM validation only runs when regex detection fails (not both)
- **Background tasks** are non-blocking — response returns before fact extraction completes
- **Domain plugin** provides context-specific prompts and tools per request

---

### 4.3 Multi-Agent System (LangGraph)

9 agents in a directed graph with conditional edges, compiled via `StateGraph`.

```mermaid
stateDiagram-v2
    [*] --> guardian_agent

    guardian_agent --> supervisor: SAFE (or fail-open on error)
    guardian_agent --> synthesizer_node: BLOCKED (harmful content)

    supervisor --> direct_response_node: DIRECT
    supervisor --> memory_agent: MEMORY
    supervisor --> tutor_agent: TUTOR
    supervisor --> rag_agent: RAG
    supervisor --> product_search_agent: PRODUCT_SEARCH

    direct_response_node --> synthesizer_node

    state rag_check <<choice>>
    rag_agent --> rag_check
    rag_check --> synthesizer_node: confidence >= 0.85 [EARLY EXIT]
    rag_check --> quality_check: confidence < 0.85

    state tutor_check <<choice>>
    tutor_agent --> tutor_check
    tutor_check --> synthesizer_node: confidence >= 0.85 [EARLY EXIT]
    tutor_check --> quality_check: confidence < 0.85

    memory_agent --> quality_check

    product_search_agent --> synthesizer_node

    quality_check --> synthesizer_node: score >= 6 [PASS]
    quality_check --> tutor_agent: score < 6 [RETRY, max 1]

    synthesizer_node --> [*]
```

| Agent | Responsibility | Key Features |
|-------|---------------|--------------|
| **Guardian** | Content safety, relevance | Fail-open on errors, skip <3 char messages |
| **Supervisor** | LLM-first routing (Sprint 103) | `RoutingDecision` structured output with CoT reasoning, confidence gating at 0.7, keyword guardrails as fallback (social→DIRECT, personal→MEMORY). Intents: lookup, learning, personal, social, off_topic, web_search, product_search |
| **RAG Agent** | Knowledge retrieval | CorrectiveRAG pipeline, LLM fallback on empty KB |
| **Tutor Agent** | Teaching, explanation | ReAct tool-calling loop with domain tools |
| **Memory Agent** | User context retrieval | Cross-session semantic memory |
| **Direct Response** | General queries + tool dispatch | 8 tools: 3 character + datetime + 4 web search (web, news, legal, maritime). Handles off-topic, web_search intents |
| **Product Search** | Product comparison & pricing | 7 tools across 5 platforms (Serper, WebSosanh, Facebook, TikTok, Apify). Plugin architecture with circuit breakers. Handles product_search intent |
| **Grader** | Quality control | Score 1-10, early exit at confidence >= 0.85 |
| **Synthesizer** | Final formatting | Vietnamese output, thinking extraction, citations |

**AgentState** fields: `messages`, `query`, `context`, `domain_id`, `organization_id`, `thinking`, `agent_outputs`, `tool_call_events`, `confidence`, `sources`, `next_agent`, `retry_count`

**Checkpoint persistence:** `AsyncPostgresSaver` — per-user-session LangGraph state stored in PostgreSQL.

---

### 4.4 Corrective RAG Pipeline

6-step self-correcting retrieval pipeline with tiered grading.

```mermaid
flowchart TB
    Q["Query"] --> CACHE{"SemanticCache<br/>similarity >= 0.99?"}

    CACHE -->|HIT| ADAPT["ThinkingAdapter<br/>Adapt cached answer"] --> RESULT

    CACHE -->|MISS| ANALYZE["QueryAnalyzer<br/>Entity + intent extraction"]

    ANALYZE --> SEARCH["HybridSearch<br/>Dense + Sparse + RRF"]

    SEARCH --> |0 results| FALLBACK["LLM Fallback<br/>General knowledge (Vietnamese)"]
    FALLBACK --> RESULT

    SEARCH --> |N results| GRADE["Tiered Grading"]

    subgraph GRADE["Tiered Grading (3 tiers)"]
        T1["Tier 1: Hybrid Pre-filter<br/>(0ms, score thresholds)"]
        T1 -->|AUTO PASS >= 0.8| GRADED
        T1 -->|AUTO FAIL <= 0.3| GRADED
        T1 -->|UNCERTAIN| T2["Tier 2: MiniJudge LLM<br/>(3-4s, parallel LIGHT)"]
        T2 -->|>= 2 relevant| GRADED["Graded Docs"]
        T2 -->|< 2 relevant| T3["Tier 3: Full LLM Batch<br/>(~19s, MODERATE)"]
        T3 --> GRADED
    end

    GRADED --> ENRICH["GraphRAG Enrichment<br/>Neo4j entity context"]
    ENRICH --> GEN["RAG Agent Generation<br/>Gemini + domain prompts"]

    GEN --> VERIFY{"Confidence?"}
    VERIFY -->|>= 0.85| RESULT["CorrectiveRAGResult"]
    VERIFY -->|0.5-0.85| QVERIFY["Quick Verify"] --> RESULT
    VERIFY -->|< 0.5| FULL["Full Verify + Rewrite"] -->|retry max 1| ANALYZE

    RESULT --> STORE["Store in SemanticCache<br/>3-tier TTL"]

    style ADAPT fill:#87CEEB
    style FALLBACK fill:#FFE4B5
```

**SemanticCache TTL Tiers:**
| Confidence | TTL | Description |
|------------|-----|-------------|
| >= 0.90 | 4 hours | High-quality, stable answers |
| >= 0.70 | 2 hours | Standard answers |
| < 0.70 | 30 minutes | Low-confidence, refresh soon |

**Confidence Scale:** RAG pipeline uses 0-100 internally (`CorrectiveRAGResult.confidence`), normalized to 0-1 at boundary in `rag_tools.py`.

---

### 4.5 Search Architecture

```mermaid
flowchart LR
    subgraph Query["Query Processing"]
        Q["User Query"] --> QA["QueryAnalyzer<br/>Intent + entities"]
    end

    subgraph Hybrid["HybridSearchService"]
        DENSE["Dense Search<br/>Gemini Embeddings (768d)<br/>pgvector HNSW"]
        SPARSE["Sparse Search<br/>PostgreSQL tsvector<br/>Vietnamese tokenization"]
        RRF["RRF Reranker<br/>k=60, title boost"]
    end

    subgraph Graph["GraphRAG Context"]
        NEO["Neo4j 5"] --> ENTITIES["Entity relationships<br/>regulations, concepts"]
    end

    QA --> DENSE & SPARSE
    DENSE --> RRF
    SPARSE --> RRF
    RRF --> RESULTS["Top 10 documents"]
    ENTITIES --> ENRICH["Context enrichment"]
```

| Search Component | Technology | Performance |
|-----------------|-----------|-------------|
| Dense Search | pgvector HNSW (768-dim) | ~50ms for 100K vectors |
| Sparse Search | PostgreSQL tsvector | ~10ms |
| RRF Reranker | Custom (k=60) | ~1ms |
| Title Match Boost | Strong (3.0) if >=1 strong + >=2 total | Improves precision |
| GraphRAG | Neo4j Cypher queries | ~100ms |

**RRF Title Match Boost:**
- Strong boost (3.0): `strong_matches >= 1 AND total_matches >= 2`
- Medium boost (1.5): Single proper noun match
- No boost: No title matches

---

### 4.6 LLM Provider Layer

Multi-provider architecture with automatic failover and 3-tier resource allocation.

```mermaid
flowchart TB
    subgraph Consumers["LLM Consumers"]
        C1["CorrectiveRAG"] & C2["TutorAgent"] & C3["Supervisor"]
        C4["Grader"] & C5["Guardian"] & C6["MiniJudge"]
    end

    subgraph Pool["LLM Pool (Singleton)"]
        DEEP["DEEP tier<br/>max_tokens=8192<br/>Complex reasoning"]
        MOD["MODERATE tier<br/>max_tokens=4096<br/>Standard tasks"]
        LIGHT["LIGHT tier<br/>max_tokens=1024<br/>Quick scoring"]
    end

    subgraph Providers["LangChain Providers"]
        GEM["GeminiProvider<br/>thinking_budget"]
        OAI["OpenAIProvider<br/>reasoning_effort"]
        OLL["OllamaProvider<br/>think: true (Qwen3)"]
    end

    subgraph Unified["Unified Client (feature-gated)"]
        UC["UnifiedLLMClient<br/>AsyncOpenAI SDK"]
    end

    subgraph Failover["Failover Chain"]
        F1["1. Google Gemini<br/>(primary)"]
        F2["2. OpenAI<br/>(cloud fallback)"]
        F3["3. Ollama<br/>(local fallback)"]
        F1 -->|error| F2 -->|error| F3
    end

    Consumers --> Pool --> Providers --> Failover
    UC --> F1 & F2 & F3
```

| Provider | Deep Model | Moderate Model | Light Model | Thinking |
|----------|-----------|---------------|-------------|----------|
| Gemini | gemini-2.0-flash | gemini-2.0-flash | gemini-2.0-flash | `thinking_budget` |
| OpenAI | gpt-4o | gpt-4o-mini | gpt-4o-mini | `reasoning_effort` |
| Ollama | qwen3:8b | qwen3:8b | qwen3:8b | `extra_body: {think: true}` |

**Thinking-Capable Ollama Models:** `qwen3`, `deepseek-r1`, `qwq` (detected by prefix)

**Unified Client** (`enable_unified_client=False`): AsyncOpenAI SDK for direct API access, used by Agentic Loop and MCP tools. All three providers expose OpenAI-compatible endpoints.

**Token Tracking:** `TokenTrackingCallback` records per-request LLM usage via ContextVar (`app/core/token_tracker.py`).

---

### 4.7 Domain Plugin System

Plugin-based architecture for adding new knowledge domains without modifying core code.

```mermaid
flowchart TB
    subgraph Startup["Application Startup"]
        LOADER["DomainLoader.load_all()"]
        LOADER --> SCAN["Scan app/domains/*/domain.yaml"]
        SCAN --> M["maritime/domain.yaml"] & T["traffic_law/domain.yaml"]
        M & T --> REG["DomainRegistry (singleton)"]
    end

    subgraph Runtime["Per-Request Routing"]
        REQ["ChatRequest"] --> ROUTER["DomainRouter.resolve()"]
        ROUTER --> P1["1. Explicit: request.domain_id"]
        P1 --> P2["2. Session: session.domain_id"]
        P2 --> P3["3. Keyword: Vietnamese match"]
        P3 --> P4["4. Default: settings.default_domain"]
        P4 --> P5["5. Org: org.allowed_domains[0]"]
    end

    subgraph Plugin["DomainPlugin"]
        YAML["domain.yaml<br/>id, name, keywords"]
        PROMPTS["prompts/<br/>system prompts"]
        TOOLS["tools/<br/>domain tools"]
        SKILLS["skills/<br/>SKILL.md (runtime)"]
    end

    ROUTER --> Plugin
```

**Creating a New Domain:**
```bash
cp -r app/domains/_template app/domains/my_domain
# Edit domain.yaml, add prompts, add to active_domains config
# Restart — auto-discovered by DomainLoader
```

**Configuration:**
- `settings.active_domains = ["maritime", "traffic_law"]` — enabled plugins
- `settings.default_domain = "maritime"` — fallback when no match
- Org-aware filtering restricts available domains per organization

**Runtime Skills:** SKILL.md files with YAML frontmatter in `{workspace_root}/skills/{domain_id}/{skill_name}/`. Managed via `SkillManager` (create/update/delete/list).

---

### 4.8 Memory & Personalization

```mermaid
flowchart TB
    subgraph PerRequest["Per-Request (Stage 3: InputProcessor)"]
        MSG["User message"] --> PARALLEL["Parallel retrieval"]
        PARALLEL --> HIST["Conversation history<br/>(last N messages)"]
        PARALLEL --> FACTS["User facts<br/>(semantic similarity)"]
        PARALLEL --> INS["User insights<br/>(learning patterns)"]
        PARALLEL --> PRON["Pronoun detection<br/>(regex → LLM fallback)"]
        PARALLEL --> SUMM["Session summary<br/>(if history > threshold)"]
        HIST & FACTS & INS & PRON & SUMM --> PROMPT["Dynamic system prompt"]
    end

    subgraph Background["Background (Stage 6)"]
        RESP["Agent response"] --> FE["FactExtractor"]
        RESP --> IE["InsightExtractor"]
        RESP --> SS["SessionSummarizer"]
        RESP --> LP["LearningProfile update"]
    end

    subgraph Storage["PostgreSQL Storage"]
        FE --> SM_TABLE["semantic_memories<br/>(user_fact, 768-dim embedding)"]
        IE --> INS_TABLE["insights<br/>(learning patterns)"]
        SS --> SUMM_TABLE["conversation_summaries"]
        LP --> PREF_TABLE["user_preferences"]
    end
```

| Memory Type | Table | Source | Query Method |
|------------|-------|--------|-------------|
| User Facts | `semantic_memories` | FactExtractor (async) | Cosine similarity search |
| Insights | `insights` | InsightExtractor (async) | Type-based query |
| Summaries | `conversation_summaries` | SessionSummarizer | Per-session lookup |
| Preferences | `user_preferences` | User API / tools | Direct key-value |

**Memory Components:**
- **MemoryManager**: Deduplication via LLM before writing new facts
- **MemoryCompression**: Summarize old memories to save context window
- **MemoryConsolidator**: Long-term consolidation of related facts

**Pronoun Adaptation** (Vietnamese):
- Regex detects user self-reference: `minh/cau`, `em/anh`, `toi/ban`
- LLM validation only runs when regex fails (Sprint 65b dedup fix)
- AI adapts its pronoun style to match the user

---

### 4.9 Streaming Architecture

SSE V3 provides full event lifecycle for rich desktop rendering.

```mermaid
sequenceDiagram
    participant C as Client
    participant API as chat_stream.py
    participant GS as graph_streaming.py
    participant NODES as LangGraph Nodes
    participant SU as stream_utils.py

    C->>API: POST /chat/stream/v3

    rect rgb(240, 245, 255)
        Note over API: _keepalive_generator() wraps stream (15s heartbeat)
    end

    loop For each LangGraph node
        NODES->>SU: create_status_event(label)
        SU-->>GS: StreamEvent(type="status")
        GS-->>API: SSE event: status

        NODES->>SU: create_thinking_event(reasoning)
        SU-->>GS: StreamEvent(type="thinking")
        GS-->>API: SSE event: thinking

        opt Tool calling
            NODES->>SU: create_tool_call_event(name, args)
            GS-->>API: SSE event: tool_call
            NODES->>SU: create_tool_result_event(result)
            GS-->>API: SSE event: tool_result
        end
    end

    GS->>GS: _ensure_vietnamese() via LLM
    GS-->>API: SSE event: answer (token-by-token)
    GS-->>API: SSE event: done (sources, metadata)
    API-->>C: Stream complete
```

**Thinking Lifecycle (Sprint 64):**
Each node emits `thinking_start` → processing → `thinking_end`:
```
thinking_start {label: "Kiem tra an toan"}      ← Guardian
thinking_end   {duration_ms: 150}
thinking_start {label: "Phan tich cau hoi"}     ← Supervisor
status         {content: "Routing to RAG"}
thinking_end   {duration_ms: 2000}
thinking_start {label: "Tim kiem kien thuc"}     ← RAG Agent
thinking       {content: "AI reasoning..."}
thinking_end   {duration_ms: 5000}
answer         {content: "partial answer"}       ← RAG partial
thinking_start {label: "Tong hop cau tra loi"}   ← Synthesizer
answer         {content: "final tokens..."}
thinking_end   {duration_ms: 3000}
done           {sources: [...]}
```

**Status vs Thinking distinction** (Sprint 63):
- `status` events = pipeline progress (routing decisions, grader scores)
- `thinking` events = raw AI reasoning content

**Streaming Timeouts:**
- Per-chunk: 120s (LLM), 300s (graph node)
- Total: 600s (LLM), 900s (graph)

---

### 4.10 MCP Integration

Model Context Protocol support for tool interoperability.

```mermaid
flowchart LR
    subgraph Server["MCP Server"]
        FAPI["FastAPI App"] --> MOUNT["fastapi-mcp<br/>mount_http()"]
        MOUNT --> EP["/mcp endpoint<br/>Streamable HTTP"]
        EP --> TOOLS_OUT["All REST endpoints<br/>exposed as MCP tools"]
    end

    subgraph Client["MCP Client"]
        CONFIG["Config:<br/>server URLs + transport"] --> MGR["MCPToolManager"]
        MGR --> ADAPT["Schema Adapter<br/>MCP ↔ OpenAI ↔ LangChain"]
        ADAPT --> TOOLS_IN["LangChain tools<br/>available to agents"]
    end

    subgraph External["External"]
        CLAUDE["Claude Desktop"] & VSCODE["VS Code"] --> Server
        EXT_SERVERS["External MCP Servers"] --> Client
    end
```

**Feature Flags:**
- `enable_mcp_server=False` — Expose Wiii tools at `/mcp`
- `enable_mcp_client=False` — Connect to external MCP servers

**Transport:** Streamable HTTP (2026 standard). SSE transport deprecated.

**Schema Adapter** converts between three formats:
1. **MCP format** — standard MCP tool schema
2. **OpenAI format** — `{"type": "function", "function": {...}}`
3. **LangChain format** — `@tool` decorated functions

---

### 4.11 Proactive Agent System

Scheduled tasks with automatic execution and failure tracking.

```mermaid
flowchart TB
    subgraph Input["Task Creation"]
        USER["User (via scheduler_tools)"] --> DB["scheduled_tasks table"]
        ADMIN["Admin API"] --> DB
    end

    subgraph Executor["ScheduledTaskExecutor"]
        POLL["asyncio poll loop<br/>(every 60s)"] --> QUERY["Query: next_run_at <= NOW"]
        QUERY --> SEM["asyncio.Semaphore(5)"]
        SEM --> TYPE{"type?"}
        TYPE -->|notification| SEND["Send description as reminder"]
        TYPE -->|agent| INVOKE["Invoke multi-agent graph"]
    end

    subgraph Dispatch["Delivery (Plugin Architecture)"]
        SEND & INVOKE --> REG["NotificationChannelRegistry"]
        REG --> WS["WebSocket push"]
        REG --> TG["Telegram Bot API"]
        REG --> MSG["Messenger (CallMeBot)"]
        REG --> ZALO["Zalo OA API v3"]
    end

    subgraph Failure["Failure Tracking"]
        INVOKE -->|error| COUNT["failure_count++"]
        COUNT -->|>= 3| DISABLE["Auto-disable task"]
        COUNT -->|< 3| RESCHEDULE["Calculate next_run_at"]
    end
```

**Feature-Gated:** `enable_scheduler=False` by default. Wired in `main.py` lifespan.

#### Notification Plugin Architecture (Sprint 172)

Notification delivery uses a plugin pattern (same as `search_platforms/`):

```
app/services/notifications/
├── base.py          # NotificationChannelAdapter ABC, ChannelConfig, NotificationResult
├── registry.py      # NotificationChannelRegistry singleton (thread-safe)
├── __init__.py      # init_notification_channels() — auto-register from config
└── adapters/
    ├── websocket.py # WebSocket push (enable_websocket)
    ├── telegram.py  # Telegram Bot API (enable_telegram + telegram_bot_token)
    ├── messenger.py # CallMeBot Messenger (living_agent_callmebot_api_key)
    └── zalo.py      # Zalo OA API v3 (enable_zalo + zalo_oa_access_token)
```

**Adding a new channel:**
1. Create `adapters/new_channel.py` implementing `NotificationChannelAdapter`
2. Register in `__init__.py` with feature flag guard
3. Done — `NotificationDispatcher` routes automatically via `registry.get(channel).send()`

**Config:** `enable_zalo`, `zalo_oa_access_token`, `zalo_oa_refresh_token`, `zalo_oa_app_id`, `zalo_oa_secret_key`

---

### 4.12 Multi-Tenant Architecture

Organization-scoped domain access with data isolation.

```mermaid
flowchart TB
    HDR["X-Organization-ID header"] --> MW["OrgContextMiddleware"]
    MW --> CV["ContextVars:<br/>current_org_id<br/>current_org_allowed_domains"]

    CV --> DR["DomainRouter<br/>Filter domains by org.allowed_domains"]
    CV --> TID["Thread ID:<br/>org_{org}__user_{uid}__session_{sid}"]
    TID --> CHECK["LangGraph checkpoints<br/>(per org-user-session)"]

    subgraph Admin["Organization Admin API"]
        CRUD["CRUD organizations"]
        MEM["Member management"]
        DOM["allowed_domains config"]
    end
```

**Feature-Gated:** `enable_multi_tenant=False`. When disabled, all domains available, no org ContextVars set.

**Data Models:**
- `organizations` table: id, name, slug, allowed_domains, settings (JSONB)
- `user_organizations` table: user_id, org_id, role (member/admin/owner)
- `AddMemberRequest.role`: `Literal["member", "admin", "owner"]` (Sprint 65b)

---

### 4.13 Product Search Platform

Plugin-based product search across 5 platforms with circuit breakers and LLM extraction (Sprints 148-151).

```mermaid
flowchart TB
    subgraph Registry["SearchPlatformRegistry (Singleton)"]
        REG["Registry"] --> CONFIG["product_search_platforms config"]
        CONFIG --> ENABLED["Enabled adapters list"]
    end

    subgraph Adapters["Platform Adapters (8)"]
        SERP_SHOP["SerperShopping<br/>Google Shopping API"]
        SERP_SITE["SerperSite<br/>5 site-specific searches"]
        WSS["WebSosanh<br/>94+ shop price comparison"]
        FB_SEARCH["FacebookSearch<br/>Playwright + LLM extraction"]
        FB_GROUP["FacebookGroup<br/>Scroll + GraphQL capture"]
        TIKTOK["TikTokResearch<br/>Native API + Serper fallback"]
        APIFY["Apify<br/>Web scraping actors"]
        ALLWEB["AllWeb<br/>General web search"]
    end

    subgraph Tools["Product Search Tools (7)"]
        T1["tool_search_serper_shopping"]
        T2["tool_search_websosanh"]
        T3["tool_search_facebook"]
        T4["tool_search_facebook_group"]
        T5["tool_search_tiktok"]
        T6["tool_search_apify"]
        T7["tool_search_allweb"]
    end

    subgraph Safety["Resilience"]
        CB["CircuitBreaker<br/>Per-platform"]
        TIMEOUT["Request timeout<br/>30s default"]
    end

    REG --> Adapters
    Adapters --> Tools
    Adapters --> Safety
```

**Key Design Decisions:**
- **Plugin architecture**: `SearchPlatformAdapter` ABC — add new platforms without modifying core
- **Tool generation**: `StructuredTool.from_function()` (NOT `@tool(name=...)`)
- **Circuit breaker**: Per-platform, 5 failures → open for 60s
- **Feature flag**: `enable_product_search=False` — tool list empty when disabled
- **Output format**: `{"platform": str, "results": [...], "count": int}`
- **Deep search** (Sprint 150): Pagination + page scraper + 15-iteration LLM search loop

---

### 4.14 Browser Scraping (Playwright)

Headless browser automation for sites that require JavaScript rendering (Sprints 152-154).

```mermaid
flowchart TB
    subgraph Worker["Playwright Worker Thread"]
        PW["Playwright Browser<br/>(Chromium headless)"]
        PW --> PAGE["Page Navigation"]
        PAGE --> SCROLL["Infinite Scroll<br/>+ Network Interception"]
        SCROLL --> EXTRACT["Content Extraction"]
    end

    subgraph Extraction["Dual Extraction Mode"]
        LLM_EXT["LLM Extraction<br/>Screenshot → Gemini Vision"]
        GQL_EXT["GraphQL Capture<br/>Network intercept (Sprint 156)"]
        EXTRACT --> LLM_EXT
        EXTRACT --> GQL_EXT
    end

    subgraph Output["Output"]
        SCREENSHOTS["Screenshots<br/>Streamed to UI via SSE"]
        PRODUCTS["Product Data<br/>Structured JSON"]
    end

    LLM_EXT & GQL_EXT --> SCREENSHOTS & PRODUCTS
```

**Key Features:**
- **Worker thread**: Dedicated thread to avoid greenlet "Cannot switch" errors (Sprint 154b)
- **Facebook login**: Cookie-based persistent session (Sprint 154)
- **Network interception**: GraphQL capture during scroll — skip LLM when >= 3 products captured (Sprint 156)
- **Screenshot streaming**: Browser screenshots streamed to desktop UI via SSE events (Sprint 153)
- **SSRF prevention**: URL validation blocks private IPs and internal networks (Sprint 153)
- **Feature flag**: `enable_browser_scraping=False`

---

### 4.15 Authentication & Identity Federation

Multi-method authentication with generalized identity federation (Sprints 157-158).

```mermaid
flowchart TB
    subgraph Methods["Auth Methods"]
        APIKEY["API Key<br/>(X-API-Key header)"]
        GOOGLE["Google OAuth 2.0<br/>(OIDC + Authlib)"]
        JWT_M["JWT Bearer<br/>(Authorization header)"]
        LMS_M["LMS Token Exchange<br/>(HMAC-SHA256)"]
    end

    subgraph Federation["Identity Federation"]
        FED["find_or_create_by_provider()"]
        FED --> S1["Step 1: Match by provider + sub"]
        S1 -->|not found| S2["Step 2: Match by verified email"]
        S2 -->|not found| S3["Step 3: Create new user"]
    end

    subgraph Storage["User Storage"]
        USERS["users table"]
        IDENT["federated_identities table<br/>(provider, sub, email)"]
        TOKENS["refresh_tokens table<br/>(auth_method column)"]
    end

    Methods --> Federation --> Storage
```

**Key Design Decisions:**
- **Generalized federation**: `find_or_create_by_provider(provider, sub, email, email_verified)` — works for Google, LMS, future providers
- **Email auto-link guard**: Only links by email when `email_verified=True` (Sprint 160b security fix)
- **Token delivery**: URL fragment `#` (not `?`) — fragments never sent to server
- **Backward compatibility**: `find_or_create_by_google()` is thin wrapper around generic function
- **Desktop**: Parse tokens from `#fragment` with `?query` fallback

---

### 4.16 LMS Integration

Webhook-based integration with Learning Management Systems (Sprints 155, 159).

```mermaid
flowchart TB
    subgraph Inbound["Inbound (LMS → Wiii)"]
        WH["POST /webhook/lms<br/>Grade/enrollment events"]
        WH --> ENRICH["LMS Enrichment<br/>Student context injection"]
        ENRICH --> MEM["Semantic Memory<br/>Store learning context"]
    end

    subgraph TokenExchange["Token Exchange (Sprint 159)"]
        LMS["LMS Backend"] --> SIGN["HMAC-SHA256 sign"]
        SIGN --> POST["POST /auth/lms/token"]
        POST --> VERIFY["Verify signature<br/>+ timestamp replay check"]
        VERIFY --> FED["find_or_create_by_provider('lms')"]
        FED --> ORG["ensure_org_membership()"]
        ORG --> JWT_PAIR["Return JWT pair"]
    end

    subgraph Outbound["Outbound (Wiii → LMS)"]
        CLIENT["LMS API Client"]
        CLIENT --> GRADE["Post grades"]
        CLIENT --> PROGRESS["Report progress"]
    end
```

**Key Features:**
- **Token exchange**: HMAC-SHA256 signed backend-to-backend (RFC 8693 pattern)
- **Secret resolution**: 3-level fallback (JSON connectors → LMSConnectorRegistry → flat secret)
- **Replay protection**: Timestamp ± `lms_token_exchange_max_age` (default 300s)
- **Role mapping**: instructor/professor→teacher, admin/administrator→admin, default→student
- **Feature flag**: `enable_lms_token_exchange=False`

---

### 4.17 Multi-Tenant Data Isolation

App-level `organization_id` filtering across all repositories (Sprint 160, hardened Sprint 170c).

```mermaid
flowchart TB
    subgraph Request["Per-Request Flow"]
        HDR["X-Organization-ID"] --> MW["OrgContextMiddleware"]
        MW --> CV["ContextVar: current_org_id"]
    end

    subgraph Pipeline["Pipeline Threading"]
        CV --> CTX["ChatContext.organization_id"]
        CTX --> STATE["AgentState.organization_id"]
        STATE --> REPOS["Repository Layer"]
    end

    subgraph Filtering["Filtering Helpers (org_filter.py)"]
        EFF["get_effective_org_id()"]
        NAMED["org_where_clause()<br/>SQLAlchemy :param style"]
        POS["org_where_positional()<br/>asyncpg $N style"]
    end

    subgraph Tables["Filtered Tables (Migrations 011, 012, 017)"]
        T1["semantic_memories"]
        T2["chat_messages"]
        T3["chat_sessions"]
        T4["chat_history"]
        T5["learning_profile"]
        T6["org_audit_log"]
        T7["knowledge_embeddings"]
        T8["wiii_character_blocks"]
        T9["refresh_tokens"]
    end

    REPOS --> Filtering --> Tables
```

**Key Design Decisions:**
- **App-level filtering** (Phase 1) — RLS is Phase 2 follow-up
- **Feature gate**: `enable_multi_tenant=False` → all helpers return empty/None (zero behavior change)
- **NULL-aware**: `allow_null=True` for shared knowledge base (knowledge_embeddings uses `OR organization_id IS NULL`)
- **Cache isolation**: Cache key = `"{org_id}:{user_id}"` when org present
- **Backfill**: Existing rows → `'default'`; knowledge_embeddings → NULL (shared)
- **B-tree indexes** on `organization_id` for all filtered tables + composite `(user_id, organization_id)` indexes (Migration 017)
- **Thread isolation**: `build_thread_id()` embeds org_id → cross-org LangGraph checkpoint isolation
- **86 tests** across `test_sprint160_data_isolation.py` (56) + `test_sprint170c_tenant_hardening.py` (30)

---

### 4.18 Org-Level Customization

Per-organization branding, features, AI config, and RBAC (Sprint 161).

```mermaid
flowchart TB
    subgraph Admin["Admin Interface"]
        PATCH["PATCH /organizations/{id}/settings"]
        PATCH --> DB["organizations.settings JSONB"]
    end

    subgraph Cascade["4-Layer Settings Cascade"]
        L1["1. Platform Defaults<br/>(config.py)"]
        L2["2. Org Settings<br/>(DB JSONB)"]
        L3["3. Role Overrides<br/>(permissions map)"]
        L4["4. User Preferences<br/>(user_preferences table)"]
        L1 --> L2 --> L3 --> L4 --> EFF["get_effective_settings()"]
    end

    subgraph Settings["OrgSettings Schema"]
        BRAND["OrgBranding<br/>colors, name, avatar, welcome"]
        FEAT["OrgFeatureFlags<br/>enable_*, visible_agents, max_iterations"]
        AI["OrgAIConfig<br/>persona overlay, temperature, domain"]
        PERMS["OrgPermissions<br/>student/teacher/admin permission lists"]
        ONBOARD["OrgOnboarding<br/>quick_start_questions, suggestions"]
    end

    subgraph Desktop["Desktop Rendering"]
        CSS["CSS Custom Properties<br/>--accent, --accent-hover"]
        GATE["PermissionGate<br/>Declarative RBAC component"]
        TAB["OrgSettingsTab<br/>Admin panel for branding/features"]
    end

    EFF --> Settings --> Desktop
```

**Key Design Decisions:**
- **deep_merge()**: Recursive dict merge — org settings override platform defaults
- **RBAC UX-only**: PermissionGate is UX convenience, backend is actual security boundary
- **Persona overlay**: `persona_prompt_overlay` injected into system prompt via PromptLoader
- **Permissions format**: `"action:resource"` strings (e.g., `"manage:settings"`, `"read:chat"`)
- **API**: `GET/PATCH /organizations/{id}/settings`, `GET /organizations/{id}/permissions`
- **37 backend + 14 desktop tests**

### 4.19 Living Agent System

**Sprint 170 — "Linh Hồn Sống"**

Makes Wiii a continuously living agent with its own soul, emotions, skills, and daily activities — inspired by OpenClaw autonomous agent architecture.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Living Agent System                          │
│                                                                 │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │   Soul    │  │   Emotion    │  │  Heartbeat   │             │
│  │  Loader   │  │   Engine     │  │  Scheduler   │             │
│  │ (YAML)    │  │  (4D state)  │  │ (30min cron) │             │
│  └─────┬─────┘  └──────┬───────┘  └──────┬───────┘             │
│        │               │                 │                      │
│        ▼               ▼                 ▼                      │
│  ┌─────────────────────────────────────────────┐               │
│  │           build_system_prompt()              │               │
│  │    (Soul + Emotion prompt injection)         │               │
│  └─────────────────────────────────────────────┘               │
│                                                                 │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │  Local   │  │   Skill      │  │   Social     │             │
│  │  LLM     │  │   Builder    │  │   Browser    │             │
│  │ (Ollama) │  │  (lifecycle) │  │  (Serper+HN) │             │
│  └─────┬─────┘  └──────┬───────┘  └──────┬───────┘             │
│        │               │                 │                      │
│        ▼               ▼                 ▼                      │
│  ┌─────────────────────────────────────────────┐               │
│  │              Journal Writer                  │               │
│  │   (Daily entries via local LLM reflection)   │               │
│  └─────────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

**Components:**

| Component | Module | Description |
|-----------|--------|-------------|
| Soul Loader | `soul_loader.py` | Loads YAML soul config (`wiii_soul.yaml`), compiles identity/truths/boundaries into system prompt |
| Emotion Engine | `emotion_engine.py` | Rule-based 4D state (mood, energy, social_battery, engagement), 13 event types, natural recovery |
| Heartbeat Scheduler | `heartbeat.py` | AsyncIO background task, 30-min interval, active hours 08:00-23:00 UTC+7 |
| Local LLM | `local_llm.py` | Ollama `qwen3:8b` via httpx async — zero-cost 24/7 inference |
| Skill Builder | `skill_builder.py` | DISCOVER → LEARN → PRACTICE → EVALUATE → MASTER lifecycle |
| Journal Writer | `journal.py` | Daily structured entries via local LLM (mood_summary, learnings, goals_next) |
| Social Browser | `social_browser.py` | Serper API + HackerNews API, keyword/LLM relevance scoring |

**Feature gate:** `enable_living_agent=False` (default)

**Integration points:**
- `main.py` lifespan: heartbeat start/stop
- `prompt_loader.py`: soul + emotion prompt injection in `build_system_prompt()`
- `chat_stream.py`: USER_CONVERSATION emotion event after each response

**API:** 6 endpoints at `/api/v1/living-agent/` (status, emotional-state, journal, skills, heartbeat, trigger)

**Desktop:** `LivingAgentPanel` in Settings "Linh hồn" tab — MoodIndicator, SkillTree, JournalView, HeartbeatStatus

**Database:** Migration 014 — `wiii_skills`, `wiii_journal`, `wiii_browsing_log`, `wiii_emotional_snapshots`

**Tests:** 99 backend + 14 desktop = 113

---

## 5. Data Layer

### Database Schema Overview

```mermaid
erDiagram
    knowledge_embeddings {
        uuid id PK
        text content
        vector embedding "768-dim"
        text source
        jsonb metadata
        tsvector search_vector
    }

    semantic_memories {
        uuid id PK
        text user_id
        text organization_id "org-aware (Sprint 160)"
        text memory_type "user_fact|insight|summary"
        text content
        vector embedding "768-dim"
        timestamp created_at
    }

    conversation_history {
        uuid id PK
        text thread_id
        text role "user|assistant"
        text content
        timestamp created_at
    }

    threads {
        uuid id PK
        text thread_id "composite: user__session"
        text user_id
        text title
        timestamp created_at
    }

    scheduled_tasks {
        uuid id PK
        text user_id
        text task_type "notification|agent"
        text description
        timestamp next_run_at
        text interval "1h30m format"
        int failure_count
        text status
    }

    users {
        uuid id PK
        text email UK
        text name
        text role "student|teacher|admin"
        boolean is_active
        timestamp created_at
    }

    federated_identities {
        uuid id PK
        uuid user_id FK
        text provider "google|lms|..."
        text provider_sub "unique per provider"
        text provider_issuer
        text email
        timestamp created_at
    }

    refresh_tokens {
        uuid id PK
        uuid user_id FK
        text token_hash
        text auth_method "google|lms"
        text organization_id "org-aware (Sprint 170c)"
        timestamp expires_at
        boolean revoked
    }

    organizations {
        uuid id PK
        text name
        text slug UK
        jsonb allowed_domains
        jsonb settings "OrgSettings schema"
        boolean is_active
    }

    user_organizations {
        text user_id
        uuid org_id FK
        text role "member|admin|owner"
    }

    org_audit_log {
        uuid id PK
        text organization_id
        text action
        text user_id
        jsonb details
        timestamp created_at
    }

    user_preferences {
        text user_id PK
        text organization_id "org-aware (Sprint 160)"
        text pronoun_style
        text learning_style
        text difficulty_level
    }

    wiii_character_blocks {
        uuid id PK
        text label "learned_lessons|favorite_topics|self_notes|user_patterns"
        text content
        int char_limit "default 1000"
        int version
        text user_id "per-user isolation (Sprint 124)"
        jsonb metadata
        timestamp created_at
        timestamp updated_at
    }

    langgraph_checkpoints {
        text thread_id PK
        bytea checkpoint
        jsonb metadata
    }

    users ||--o{ federated_identities : has
    users ||--o{ refresh_tokens : has
    users ||--o{ user_organizations : joins
    organizations ||--o{ user_organizations : has
    organizations ||--o{ org_audit_log : logs
    threads ||--o{ conversation_history : contains
    semantic_memories }o--|| user_preferences : "per user"
```

### Database Responsibilities

| Database | Tables | Purpose |
|----------|--------|---------|
| **PostgreSQL 17** | `knowledge_embeddings`, `semantic_memories`, `conversation_history`, `threads`, `scheduled_tasks`, `organizations`, `user_organizations`, `user_preferences`, `wiii_character_blocks`, `langgraph_checkpoints`, `users`, `federated_identities`, `refresh_tokens`, `org_audit_log`, `learning_profile`, `chat_messages`, `chat_sessions`, `wiii_skills`, `wiii_journal`, `wiii_browsing_log`, `wiii_emotional_snapshots` | Primary OLTP + vector search (HNSW) + FTS |
| **Neo4j 5** | Nodes: `Regulation`, `Concept`, `Entity`; Rels: `REFERENCES`, `RELATED_TO` | Knowledge graph relationships |
| **MinIO** | `wiii-docs` bucket | PDF pages, extracted images |
| **Valkey** | Key-value | Session cache, rate limit counters |

---

## 6. Security Architecture

### Authentication Flow

```mermaid
flowchart TB
    REQ["Incoming Request"] --> CHECK{"Auth Method?"}

    CHECK -->|X-API-Key header| APIKEY["API Key Auth"]
    APIKEY --> HMAC["hmac.compare_digest<br/>(timing-safe)"]
    HMAC --> HEADERS["Trust X-User-ID, X-Role<br/>from headers (LMS backend)"]

    CHECK -->|Authorization: Bearer| JWT["JWT Auth"]
    JWT --> DECODE["Decode + verify signature"]
    DECODE --> PAYLOAD["Role from token payload ONLY<br/>(ignores X-Role header)"]

    CHECK -->|Google OAuth| OAUTH_F["Google OAuth 2.0"]
    OAUTH_F --> OIDC["OIDC userinfo<br/>(email, sub, email_verified)"]
    OIDC --> FEDERATE["Identity Federation<br/>find_or_create_by_provider()"]
    FEDERATE --> JWT_PAIR["Issue JWT pair"]

    CHECK -->|LMS HMAC| LMS_F["LMS Token Exchange"]
    LMS_F --> HMAC_V["Verify HMAC-SHA256<br/>+ timestamp replay check"]
    HMAC_V --> LMS_FED["Federation + org membership"]
    LMS_FED --> JWT_PAIR

    HEADERS & PAYLOAD & JWT_PAIR --> USER["AuthenticatedUser<br/>{user_id, role, auth_method}"]

    CHECK -->|No auth (dev mode)| DEV{"Environment?"}
    DEV -->|development| ALLOW["Allow (anonymous)"]
    DEV -->|production| DENY["403 Forbidden"]
```

### Security Measures

| Area | Implementation | Notes |
|------|---------------|-------|
| **API Key** | `hmac.compare_digest` | Timing-safe comparison |
| **JWT** | Role from payload only | Prevents X-Role header override |
| **Ownership** | Endpoint-level checks | Students access only own data |
| **Admin** | `RequireAdmin` dependency | Role-based (admin only) |
| **Rate Limiting** | Per-endpoint slowapi | In-memory storage |
| **Input Validation** | Pydantic max 10,000 chars | `ChatRequest.message` |
| **Error Messages** | Generic in HTTP responses | Details logged server-side |
| **WebSocket** | Fail-closed auth (Sprint 65) | 4001/4003 close codes |
| **Google OAuth** | Authlib + OIDC | email_verified guard on auto-link |
| **JWT Tokens** | Access (15m) + Refresh (7d) | Refresh revocation, auth_method tracking |
| **LMS Token Exchange** | HMAC-SHA256 signed | Replay protection (timestamp ± max_age) |
| **Token Delivery** | URL fragment `#` (not `?`) | Fragments never sent to server |
| **Identity Federation** | 3-step provider matching | provider→email→create (email_verified required) |
| **SSRF Prevention** | URL validation (Sprint 153) | Block private IPs in browser scraping |
| **Org Data Isolation** | App-level org_id filtering | All repos filter by organization_id |
| **Config** | Validators for bounds | JWT expiry, ports, intervals, secrets |
| **Org Roles** | `Literal["member", "admin", "owner"]` | Sprint 65b validation |
| **Org RBAC** | `action:resource` permissions | UX gate + backend enforcement |

---

## 7. Desktop Application

### Architecture

```mermaid
flowchart TB
    subgraph Tauri["Tauri v2 Shell"]
        RUST["Rust Backend<br/>Window management, IPC"]
        PLUGINS["Plugins:<br/>http, store, shell, process"]
    end

    subgraph React["React 18 Frontend"]
        subgraph Stores["Zustand Stores (11)"]
            S1["settings-store<br/>Server URL, API key, user prefs"]
            S2["chat-store<br/>Conversations, messages, streaming"]
            S3["connection-store<br/>Backend connectivity"]
            S4["domain-store<br/>Available domains"]
            S5["ui-store<br/>Sidebar, modals"]
            S6["auth-store<br/>JWT tokens, OAuth state"]
            S7["org-store<br/>Organizations, permissions, org settings"]
            S8["avatar-store<br/>Avatar state, animations"]
        end

        subgraph Components["Key Components"]
            SHELL["AppShell<br/>TitleBar + Sidebar + StatusBar"]
            CHAT["ChatView<br/>MessageList + ChatInput"]
            BUBBLE["MessageBubble<br/>BlockRenderer | LegacyRenderer"]
            THINK["ThinkingBlock<br/>Markdown + inline tool cards"]
            TIMELINE["ThinkingTimeline<br/>Multi-phase thinking chain"]
            STREAM["StreamingIndicator<br/>Pipeline steps + elapsed timer"]
            SETTINGS["SettingsPage<br/>5 tabs incl. OrgSettingsTab"]
            LOGIN["LoginScreen<br/>Google OAuth + API key"]
            WELCOME["WelcomeScreen<br/>Org-aware branding"]
            PERM_GATE["PermissionGate<br/>Declarative RBAC"]
            AVATAR["WiiiAvatar<br/>Kawaii/Manga + Rive"]
        end

        subgraph Hooks["Custom Hooks"]
            H1["useSSEStream<br/>V3 event parsing + callbacks"]
            H2["useAutoScroll<br/>Smart scroll behavior"]
            H3["useKeyboardShortcuts<br/>Ctrl+Enter, etc."]
        end
    end

    subgraph Backend["Backend Communication"]
        HTTP_C["/api/v1/chat (JSON)"]
        SSE_C["/chat/stream/v3 (SSE)"]
        AUTH_C["/auth/* (OAuth + JWT)"]
        ORG_C["/organizations/* (settings)"]
    end

    RUST --> React
    Stores --> Components
    H1 --> SSE_C
    Components --> HTTP_C
```

### Message Rendering (ContentBlock System)

```
Message.blocks?: ContentBlock[]
  ├── ThinkingBlockData { type, label, content, tools[], startTime, endTime }
  └── AnswerBlockData   { type, content }
```

- **New messages** (with `blocks`): `BlockRenderer` → interleaved thinking + answer blocks
- **Old messages** (without `blocks`): `LegacyRenderer` → flat `thinking` + `content` fields
- **ThinkingBlock**: Markdown rendering, inline tool cards (gear spin, shimmer bar, result box)
- **Auto-collapse**: 500ms after `thinking_end`. Sparkle rotation: 5s.

### Persistence

| Store | Backend | Trigger |
|-------|---------|---------|
| `settings-store` | `@tauri-apps/plugin-store` | On every change |
| `chat-store` | `@tauri-apps/plugin-store` | Immediate: create/delete/rename/finalize. Debounced 2s: addUserMessage |
| Fallback | `localStorage` | When Tauri plugin unavailable |

---

## 8. Infrastructure & Deployment

### Docker Compose Services

```mermaid
flowchart LR
    subgraph Docker["docker-compose.yml"]
        APP["wiii-app<br/>Python FastAPI<br/>Port 8000"]
        PG["wiii-postgres<br/>pgvector:pg15<br/>Port 5433"]
        NEO["neo4j<br/>5-community<br/>Ports 7474, 7687"]
        MINIO_S["wiii-minio<br/>minio/minio<br/>Ports 9000, 9001"]
        MINIO_I["minio-init<br/>Bucket creation"]
        VALKEY["valkey<br/>Port 6379"]
        PGA["wiii-pgadmin<br/>(--profile tools)<br/>Port 5050"]
    end

    subgraph Network["wiii-network"]
        APP --> PG & NEO & MINIO_S & VALKEY
        MINIO_I --> MINIO_S
        PGA --> PG
    end
```

| Service | Image | Ports | Credentials |
|---------|-------|-------|-------------|
| `wiii-app` | Custom Dockerfile | 8000 | API_KEY from .env |
| `wiii-postgres` | `pgvector/pgvector:pg15` | 5433:5432 | wiii / wiii_secret / wiii_ai |
| `neo4j` | `neo4j:5-community` | 7474, 7687 | neo4j / neo4j_password |
| `wiii-minio` | `minio/minio` | 9000, 9001 | wiii / wiii_secret |
| `valkey` | `valkey/valkey` | 6379 | - |
| `wiii-pgadmin` | `dpage/pgadmin4` | 5050 | admin@wiii.local |

### Environment Variables (Required)

```bash
GOOGLE_API_KEY=AIza...          # Gemini API (required)
API_KEY=your-api-key            # Authentication

# Optional providers
OPENAI_API_KEY=sk-...           # OpenAI failover
OLLAMA_BASE_URL=http://localhost:11434  # Ollama local

# Auto-configured by Docker Compose
DATABASE_URL=postgresql+asyncpg://wiii:wiii_secret@localhost:5433/wiii_ai
NEO4J_URI=bolt://localhost:7687
MINIO_ENDPOINT=localhost:9000
```

### Feature Flags (46 total)

| Flag | Default | Description |
|------|---------|-------------|
| **Core** | | |
| `use_multi_agent` | `True` | LangGraph multi-agent system |
| `enable_corrective_rag` | `True` | Self-correction loop |
| `enable_llm_failover` | `True` | Multi-provider chain |
| `deep_reasoning_enabled` | `True` | `<thinking>` tags |
| `enable_structured_outputs` | `True` | Constrained decoding (Supervisor, Grader, Guardian) |
| **Channels** | | |
| `enable_websocket` | `False` | WebSocket endpoint |
| `enable_telegram` | `False` | Telegram webhook |
| **Extensions** | | |
| `enable_filesystem_tools` | `False` | Sandboxed file operations |
| `enable_code_execution` | `False` | Sandboxed Python exec |
| `enable_skill_creation` | `False` | Self-extending agent |
| `enable_scheduler` | `False` | Proactive task execution |
| `enable_unified_client` | `False` | AsyncOpenAI SDK |
| `enable_mcp_server` | `False` | MCP tool server at /mcp |
| `enable_mcp_client` | `False` | External MCP connections |
| `enable_agentic_loop` | `False` | Generalized ReAct loop |
| **Character** | | |
| `enable_character_tools` | `True` | Character introspection/update (per-user) |
| `enable_character_reflection` | `True` | Stanford Generative Agents reflection |
| `enable_soul_emotion` | `False` | Soul emotion engine for avatar |
| **Product Search** | | |
| `enable_product_search` | `False` | Product search agent (7 tools) |
| `enable_browser_scraping` | `False` | Playwright browser automation |
| `enable_tiktok_native_api` | `False` | TikTok Research API (vs Serper fallback) |
| `enable_thinking_chain` | `False` | Multi-phase thinking chain UX |
| **Authentication** | | |
| `enable_google_oauth` | `False` | Google OAuth 2.0 login |
| `enable_lms_token_exchange` | `False` | LMS HMAC token exchange |
| **Multi-Tenant** | | |
| `enable_multi_tenant` | `False` | Organization support + data isolation |
| **Memory** | | |
| `enable_tool_selection` | `False` | Dynamic tool selection |
| `enable_semantic_fact_retrieval` | `True` | Vector-based fact search |
| **Evaluation** | | |
| `enable_evaluation` | `False` | Quality scoring |

---

## 9. Integration Points for LMS

### API Endpoints

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/v1/chat` | POST | RequireAuth | Main chat (JSON) |
| `/api/v1/chat/stream/v3` | POST | RequireAuth | Real-time streaming (SSE) |
| `/api/v1/threads` | GET | RequireAuth | List user threads |
| `/api/v1/threads/{id}` | GET/DELETE/PATCH | RequireAuth | Thread operations |
| `/api/v1/memories/{user_id}` | GET/DELETE | RequireAuth | User memory |
| `/api/v1/insights/{user_id}` | GET | RequireAuth | Learning analytics |
| `/api/v1/sources/{node_id}` | GET | RequireAuth | Citation sources |
| `/api/v1/auth/google/login` | GET | None | Initiate Google OAuth |
| `/api/v1/auth/google/callback` | GET | None | OAuth callback |
| `/api/v1/auth/token/refresh` | POST | None | JWT refresh |
| `/api/v1/auth/lms/token` | POST | HMAC | LMS token exchange |
| `/api/v1/auth/lms/token/refresh` | POST | None | LMS token refresh |
| `/api/v1/auth/lms/health` | GET | None | LMS connector health |
| `/api/v1/users/me` | GET/PATCH | JWT | User profile |
| `/api/v1/users/me/identities` | GET/DELETE | JWT | Linked accounts |
| `/api/v1/users` | GET | RequireAdmin | List users |
| `/api/v1/organizations/{id}/settings` | GET/PATCH | RequireAuth | Org settings (Sprint 161) |
| `/api/v1/organizations/{id}/permissions` | GET | RequireAuth | User permissions |
| `/api/v1/chat/context/info` | GET | RequireAuth | Token budget utilization |
| `/api/v1/chat/context/compact` | POST | RequireAuth | Force conversation compaction |
| `/api/v1/health` | GET | None | Health check |

### LMS Integration Flow

```mermaid
sequenceDiagram
    participant LMS as LMS Frontend
    participant GW as API Gateway
    participant AUTH as LMS Auth
    participant WIII as Wiii Backend
    participant DB as LMS Database

    LMS->>GW: Chat request + JWT
    GW->>AUTH: Validate JWT
    AUTH-->>GW: User context (user_id, role)
    GW->>WIII: Forward with X-API-Key, X-User-ID, X-Role
    alt Multi-tenant
        GW->>WIII: + X-Organization-ID
    end
    WIII-->>GW: Response (answer + sources + thinking)
    GW->>DB: Log interaction
    GW-->>LMS: Response + citations

    Note over LMS,WIII: SSE streaming: same flow but<br/>response is event stream
```

### Authentication Modes

```python
# Mode 1: API Key + LMS headers (recommended for LMS proxy)
headers = {
    "X-API-Key": "your-api-key",
    "X-User-ID": "student-123",
    "X-Session-ID": "session-abc",
    "X-Role": "student",             # trusted with API Key auth
    "X-Organization-ID": "lms-org",  # optional multi-tenant
}

# Mode 2: JWT (recommended for desktop + direct access)
headers = {
    "Authorization": "Bearer eyJ...",
    # Role extracted from JWT payload, X-Role header ignored
}

# Mode 3: LMS Token Exchange (backend-to-backend, Sprint 159)
import hmac, hashlib, time, json
payload = {
    "user_id": "student-123", "email": "student@uni.edu",
    "role": "student", "org_id": "lms-org",
    "timestamp": str(int(time.time()))
}
payload["signature"] = hmac.new(
    secret.encode(), json.dumps(payload).encode(), hashlib.sha256
).hexdigest()
# POST /api/v1/auth/lms/token → {access_token, refresh_token, user}
```

---

## 10. Design Principles

### Architecture Principles

| Principle | Implementation |
|-----------|---------------|
| **Feature-gated** | All extensions behind boolean flags, zero impact when disabled |
| **Plugin-based** | Domains as self-contained plugins with auto-discovery |
| **Fail-open safety** | Guardian agent, middleware — errors don't block requests |
| **Multi-provider** | LLM failover chain with automatic switching |
| **Async-first** | All I/O operations async (`asyncpg`, `httpx`, `asyncio`) |
| **Per-request isolation** | ContextVars for org, request-ID, token tracking |
| **Background processing** | Fact extraction, insights, summarization — non-blocking |
| **Vietnamese-first** | All prompts, responses, UI in Vietnamese |

### Code Conventions

| Convention | Pattern |
|-----------|---------|
| **Config** | Pydantic Settings from `.env` (`app/core/config.py`) |
| **Auth** | `RequireAuth` / `RequireAdmin` FastAPI dependencies |
| **Logging** | structlog with bound context (request-id, user-id) |
| **Exceptions** | `WiiiException` hierarchy (`app/core/exceptions.py`) |
| **Constants** | Centralized in `app/core/constants.py` |
| **Lazy imports** | Tools and providers import inside function bodies |
| **Repository pattern** | Data access via `app/repositories/` |
| **ContextVars** | Per-request state isolation (org, token tracking, user, character) |

### Testing Strategy

| Layer | Framework | Count | Notes |
|-------|-----------|-------|-------|
| Unit | pytest + AsyncMock | 7076+ | 278 test files, autouse rate-limit disable |
| Integration | pytest | 31 files | Require running services |
| Property | Hypothesis | - | Invariant testing |
| Desktop | Vitest + jsdom | 1468 | 55 test files |

```bash
# Backend (Windows)
set PYTHONIOENCODING=utf-8 && .venv\Scripts\python.exe -m pytest tests/unit/ -v -p no:capture --tb=short

# Desktop
cd wiii-desktop && npx vitest run
```

---

**Document Version:** 7.2
**Last Updated:** 2026-02-22
**Architecture Pattern:** Multi-Domain Agentic RAG with Plugin System, Product Search Platform, Browser Scraping, Authentication & Identity Federation, Multi-Tenant Data Isolation, Org-Level Customization, Living Agent Autonomy
**Total Components:** 286 Python files, 60+ endpoints, 120+ config fields (47 feature flags), 7076 backend + 1468 desktop tests
**Sprints Covered:** 1–171b (Production Hardening)
