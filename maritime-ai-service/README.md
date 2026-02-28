# Wiii -- Backend Service

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-purple?style=flat-square)](https://langchain.com)
[![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev)
[![pgvector](https://img.shields.io/badge/pgvector-0.7-00E599?style=flat-square&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Tests](https://img.shields.io/badge/tests-9830%20passed-brightgreen?style=flat-square)](tests/)

**Soul AGI Backend -- Multi-Domain Agentic RAG with Living Agent Autonomy**

*by The Wiii Lab -- February 2026*

[Quick Start](#quick-start) | [API Reference](#api-reference) | [Architecture](#architecture) | [Testing](#testing) | [Docker](#docker)

</div>

---

## Quick Start

```bash
# Clone & install
git clone <repo-url>
cd maritime-ai-service
python -m venv .venv && .venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env -- at minimum set GOOGLE_API_KEY and API_KEY

# Run migrations
alembic upgrade head

# Run
uvicorn app.main:app --reload
```

**API Base:** `http://localhost:8000/api/v1`

---

## Key Features

| Category | Feature | Description |
|----------|---------|-------------|
| **Multi-Agent** | LangGraph Agent Graph | 9 agents: Guardian, Supervisor, RAG, Tutor, Memory, Direct, ProductSearch, Grader, Synthesizer + parallel dispatch subagents |
| **Corrective RAG** | Self-Correcting Pipeline | Hybrid search (dense+sparse+RRF), tiered grading (MiniJudge->Full LLM), self-correction loop, LLM fallback |
| **Advanced RAG** | 5 Strategies | Simple, Decompose, Step-Back, HyDE (hypothetical document embeddings), Multi-Query |
| **Graph RAG** | Knowledge Graph | Entity extraction -> Neo4j/PostgreSQL dual-mode with temporal subgraphs |
| **Visual RAG** | Vision Context | Query-time visual context enrichment via Gemini Vision |
| **Living Agent** | Autonomous Soul | Heartbeat (30-min), 4D emotion engine, SOTA LLM sentiment analysis, skill lifecycle, daily journal, social browsing, all via local LLM |
| **Identity Core** | Three-Layer Identity | Immutable soul core + self-evolving identity (weekly reflection) + per-turn context state |
| **Narrative Layer** | Life Story | NarrativeSynthesizer compiles 6 data sources into coherent autobiography for prompt context |
| **Skill-Tool Bridge** | Feedback Loops | Tool execution -> skill advancement, mastered skills -> tool priority boost |
| **Natural Conversation** | Phase-Aware | Conversation phases (opening/engaged/deep/closing), positive framing, no canned responses |
| **Product Search** | 7 Adapters | SerperShopping, SerperSite (5 platforms), WebSosanh, Facebook, TikTok, Crawl4AI, Scrapling |
| **Browser Scraping** | Playwright Worker | Dedicated thread, Facebook cookie login, GraphQL interception, screenshot streaming |
| **B2B Sourcing** | Professional Search | Dealer search (DuckDuckGo+Jina), contact extraction (7 types), international search (USD/EUR/GBP->VND) |
| **LLM Curation** | Smart Cards | LLM selects top 8 from 70+ raw results, real-time SSE preview cards |
| **Streaming** | V3 SSE | Thinking lifecycle, tool events, progressive rendering, multi-phase thinking chain |
| **Memory** | Semantic Facts | 15 categories, Ebbinghaus decay, vector retrieval, cross-platform sync |
| **Authentication** | Multi-Provider | Google OAuth (PKCE S256), JWT (jti + family_id replay), LMS HMAC, OTP linking, auth audit |
| **Multi-Tenant** | Org Isolation | 16 repos org-aware, branding, permissions, RBAC, two-tier admin (system + org) |
| **MCP** | Protocol Support | Server (`/mcp`), Client (external tools), Tool Server (individual tool exposure) |
| **Unified Skills** | 4-Source Index | UnifiedSkillIndex aggregates tools, domains, living_agent skills, MCP external tools |
| **LMS** | Integration | Webhook enrichment, token exchange, student data pull, teacher dashboards, AI reports |

---

## Project Structure

```
maritime-ai-service/
+-- app/
|   +-- api/v1/                # 19 REST API routers (63+ endpoints)
|   +-- auth/                  # Google OAuth, JWT, LMS token exchange, OTP, identity resolver, auth audit
|   +-- core/                  # Config (70+ feature flags), security, middleware, org filter, org settings
|   +-- channels/              # Multi-channel gateway (WebSocket, Telegram)
|   +-- domains/               # Domain plugins (maritime/, traffic_law/, _template/)
|   +-- engine/                # AI engine
|   |   +-- agentic_rag/       # Corrective RAG, HyDE, Adaptive RAG, Graph RAG, Visual RAG
|   |   +-- multi_agent/       # LangGraph agents (9 nodes, supervisor, subagent dispatch)
|   |   |   +-- agents/        # rag_node, tutor_node, product_search_node
|   |   |   +-- subagents/     # Parallel search/RAG/tutor workers + aggregator
|   |   +-- living_agent/      # 19 modules: soul, emotion, heartbeat, skills, journal, narrative, identity
|   |   +-- skills/            # UnifiedSkillIndex, IntelligentToolSelector, SkillMetricsTracker, SkillToolBridge
|   |   +-- search_platforms/  # 7 adapters, ChainedAdapter, ScrapingStrategyManager, circuit_breaker
|   |   +-- tools/             # 12 tool modules (RAG, web, product, chart, LMS, B2B, international)
|   |   +-- semantic_memory/   # Temporal graph, visual memory, cross-platform sync
|   |   +-- llm_providers/     # Gemini, OpenAI, Ollama + UnifiedLLMClient
|   |   +-- character/         # Stanford Generative Agents + per-user isolation
|   |   +-- personality_mode.py # Professional <-> Soul mode switching
|   +-- integrations/          # LMS (webhook, enrichment, push service, connectors)
|   +-- mcp/                   # MCP server + client + adapter + tool_server
|   +-- models/                # Pydantic schemas (chat, organization, user, knowledge_graph)
|   +-- prompts/               # YAML persona configs + soul YAML + domain overlays
|   +-- repositories/          # 16 data access repositories (all org-aware)
|   +-- services/              # 25+ service files (orchestrator, streaming, session, vision, admin)
+-- alembic/                   # 34 database migrations
+-- docs/                      # Architecture, API, integration guides
+-- scripts/                   # Utility and test scripts
+-- tests/                     # 350+ test files, 9703 unit tests
|   +-- unit/                  # Unit tests (mock-based, no services required)
|   +-- integration/           # Integration tests (require DB, Redis, etc.)
|   +-- property/              # Property-based tests (Hypothesis)
+-- docker-compose.yml         # Standard stack (app + postgres + neo4j + minio)
+-- docker-compose.soul-agi.yml # Soul AGI stack (+ Ollama + Cloudflare Tunnel)
```

---

## API Reference

### Chat

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat` | POST | JSON response (non-streaming) |
| `/api/v1/chat/stream/v3` | POST | SSE streaming (thinking lifecycle, tool events, progressive rendering) |

```http
POST /api/v1/chat/stream/v3
Content-Type: application/json
X-API-Key: {api_key}
X-User-ID: student-123
X-Session-ID: session-abc

{
  "message": "Dieu 15 COLREGs noi gi?",
  "user_id": "student-123",
  "role": "student",
  "domain_id": "maritime",
  "organization_id": "lms-hang-hai"
}
```

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/google/login` | GET | Initiate Google OAuth (PKCE S256) |
| `/api/v1/auth/google/callback` | GET | OAuth callback -> JWT pair |
| `/api/v1/auth/token/refresh` | POST | Refresh JWT access token |
| `/api/v1/auth/lms/token` | POST | LMS token exchange (HMAC-SHA256 signed) |
| `/api/v1/auth/lms/token/refresh` | POST | Refresh LMS-issued token |
| `/api/v1/auth/lms/health` | GET | LMS integration health check |

### Users

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/users/me` | GET | Current user profile |
| `/api/v1/users/me` | PATCH | Update own profile |
| `/api/v1/users/me/identities` | GET | Linked identity providers |
| `/api/v1/users/me/identities/{id}` | DELETE | Unlink identity provider |
| `/api/v1/users/me/organizations` | GET | Current user's organizations |
| `/api/v1/users/me/admin-context` | GET | Admin capabilities (system/org level) |
| `/api/v1/users` | GET | Admin: list all users |
| `/api/v1/users/{id}/role` | PATCH | Admin: update user role |
| `/api/v1/users/{id}/deactivate` | POST | Admin: deactivate user |

### Organizations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/organizations` | GET | List organizations (admin: all, user: own) |
| `/api/v1/organizations` | POST | Create organization (admin only) |
| `/api/v1/organizations/{id}` | GET/PATCH/DELETE | CRUD operations |
| `/api/v1/organizations/{id}/members` | GET/POST | Member management |
| `/api/v1/organizations/{id}/members/{uid}` | DELETE | Remove member |
| `/api/v1/organizations/{id}/settings` | GET/PATCH | Org settings (branding, features) |
| `/api/v1/organizations/{id}/permissions` | GET | User permissions in org |

### Conversation Context

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat/context/info` | GET | Token budget, utilization, message count |
| `/api/v1/chat/context/compact` | POST | Trigger conversation compaction |
| `/api/v1/chat/context/clear` | POST | Clear conversation context |

### Living Agent

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/living-agent/status` | GET | Full status (soul, mood, heartbeat, counts) |
| `/api/v1/living-agent/emotional-state` | GET | Current 4D emotional state |
| `/api/v1/living-agent/journal` | GET | Recent journal entries |
| `/api/v1/living-agent/skills` | GET | All skills with lifecycle status |
| `/api/v1/living-agent/heartbeat` | GET | Heartbeat scheduler info |
| `/api/v1/living-agent/heartbeat/trigger` | POST | Manually trigger heartbeat cycle |
| `/api/v1/living-agent/goals` | GET | Active goals with progress and milestones |
| `/api/v1/living-agent/reflections` | GET | Daily self-reflections with insights |
| `/api/v1/living-agent/narrative` | GET | Compiled life story narrative |
| `/api/v1/living-agent/identity` | GET | Self-evolving identity core state |

### Knowledge & Admin

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/admin/documents` | POST/GET | Ingest and list documents |
| `/api/v1/admin/domains` | GET | List registered domain plugins |
| `/api/v1/admin/domains/{id}` | GET | Domain plugin details |
| `/api/v1/admin/domains/{id}/skills` | GET | Domain skill manifest |
| `/api/v1/admin/stats` | GET | System statistics |
| `/api/v1/admin/dashboard/overview` | GET | Admin dashboard metrics |
| `/api/v1/admin/feature-flags` | GET/PATCH | Feature flag management |
| `/api/v1/admin/analytics/usage` | GET | Usage analytics |
| `/api/v1/admin/audit/events` | GET | Audit event log |

### LMS Integration

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/lms/webhook/{connector_id}` | POST | Receive LMS events (HMAC-signed) |
| `/api/v1/lms/students/{id}/profile` | GET | Pull student profile |
| `/api/v1/lms/students/{id}/grades` | GET | Pull student grades |
| `/api/v1/lms/dashboard/courses/{id}/overview` | GET | Course overview |
| `/api/v1/lms/dashboard/courses/{id}/at-risk` | GET | At-risk student detection |
| `/api/v1/lms/dashboard/org/overview` | GET | Organization overview (admin) |

### Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/threads` | GET/POST | Thread CRUD |
| `/api/v1/threads/{id}` | GET/DELETE | Get or delete thread |
| `/api/v1/insights/{user_id}` | GET | Learning analytics |
| `/api/v1/memories/{user_id}` | GET/DELETE | User memory management |
| `/api/v1/sources/{node_id}` | GET | Citation sources |
| `/api/v1/preferences` | GET/PATCH | User preferences |
| `/api/v1/feedback` | POST | Response feedback |

### Webhooks

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/zalo/webhook` | POST | Zalo OA incoming messages |
| `/api/v1/messenger/webhook` | GET/POST | Facebook Messenger verification + messages |

### Health

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Service health (all components) |
| `/api/v1/health/db` | GET | Database connectivity |
| `/api/v1/health/ollama` | GET | Ollama availability |

---

## Architecture

### Multi-Agent Graph (LangGraph)

```
               Guardian (safety filter, fail-open)
                   |
               Supervisor (LLM-first routing + keyword fallback)
              /    |    |    \         \
           RAG  Tutor Memory  Direct  ProductSearch
           (subagent        (8 tools   (parallel dispatch
            dispatch)        bound)     + aggregation)
              \    |    |    /         /
               Grader (quality scoring, re-routing)
                   |
               Synthesizer (Vietnamese output, natural conversation)
```

### Corrective RAG Pipeline

```
1. SemanticCache check (0.99 similarity threshold)
2. HybridSearch: Dense (pgvector) + Sparse (tsvector) + RRF reranking
3. [Optional] Visual RAG: Gemini Vision context enrichment
4. Tiered Grading: Hybrid pre-filter -> MiniJudge LLM -> Full LLM batch (early exit)
5. Generation with GraphRAG context enrichment
6. Self-correction loop if confidence < 0.85
7. LLM Fallback: uses general knowledge when 0 documents found
```

### Living Agent System

```
app/engine/living_agent/ (22 modules, 7,500+ LOC)
+-- soul_loader.py          # YAML soul config (identity, truths, boundaries)
+-- emotion_engine.py       # 4D state (mood/energy/social/engagement), 3-tier relationship dampening
+-- sentiment_analyzer.py   # Sprint 210d: SOTA LLM sentiment via Gemini Flash structured output
+-- heartbeat.py            # AsyncIO scheduler (30-min interval, aggregate processing)
+-- skill_builder.py        # DISCOVER -> LEARN -> PRACTICE -> EVALUATE -> MASTER
+-- skill_learner.py        # SM-2 spaced repetition algorithm
+-- journal.py              # Daily journal via local LLM
+-- social_browser.py       # Serper + HackerNews API browsing + insight extraction
+-- reflector.py            # Daily self-reflection (Sprint 210: was weekly)
+-- goal_manager.py         # Goal tracking, progress, soul-based seeding
+-- autonomy_manager.py     # Graduated autonomy levels
+-- proactive_messenger.py  # Context-aware outreach (anti-spam guardrails)
+-- routine_tracker.py      # User activity patterns
+-- narrative_synthesizer.py # Life story compilation from 6 sources
+-- identity_core.py        # Self-evolving identity Layer 2
+-- channel_sender.py       # Multi-channel message delivery
+-- briefing_composer.py    # Morning briefing generation
+-- weather_service.py      # Weather context for briefings
+-- local_llm.py            # Ollama qwen3:8b async client (zero API cost)
+-- safety.py               # Content safety for autonomous actions
+-- models.py               # EmotionalState, SkillEntry, JournalEntry, HeartbeatResult
```

### Domain Plugin System

```bash
# Create a new domain in 5 steps:
cp -r app/domains/_template app/domains/my_domain
# Edit domain.yaml -> add keywords, descriptions, prompts
# Add to config: active_domains=["maritime","my_domain"]
# Restart -> auto-discovered by DomainLoader
```

---

## Configuration

### Required Environment Variables

```env
GOOGLE_API_KEY=AIza...              # Gemini API key (required)
API_KEY=your-api-key                # API authentication key
DATABASE_URL=postgresql+asyncpg://wiii:wiii_secret@localhost:5433/wiii_ai
```

### Feature Flags

70+ feature flags in `app/core/config.py`. Key flags:

| Flag | Default | Description |
|------|---------|-------------|
| `use_multi_agent` | `True` | Multi-Agent graph (LangGraph) |
| `enable_corrective_rag` | `True` | Self-correction RAG loop |
| `enable_structured_outputs` | `True` | Constrained decoding for routing |
| `enable_product_search` | `False` | Product search agent (7 adapters) |
| `enable_browser_scraping` | `False` | Playwright-based scraping |
| `enable_multi_tenant` | `False` | Multi-organization support |
| `enable_google_oauth` | `False` | Google OAuth 2.0 (PKCE S256) |
| `enable_living_agent` | `False` | Autonomous soul, emotion, heartbeat, skills |
| `enable_natural_conversation` | `False` | Phase-aware natural conversation |
| `enable_skill_tool_bridge` | `False` | Skill<->Tool feedback loops |
| `enable_narrative_context` | `False` | Inject life narrative into system prompt |
| `enable_unified_skill_index` | `False` | Cross-system skill discovery |
| `enable_intelligent_tool_selection` | `False` | 4-step tool selection pipeline |
| `enable_mcp_server` | `False` | Expose tools via MCP at `/mcp` |
| `enable_mcp_client` | `False` | Connect to external MCP servers |
| `enable_cross_platform_identity` | `False` | Canonical identity across platforms |
| `enable_lms_integration` | `False` | LMS webhook + data pull + dashboard |

See `.env.example` and `app/core/config.py` for the full list.

---

## Testing

```bash
# All unit tests (Windows -- requires PYTHONIOENCODING for Unicode output)
set PYTHONIOENCODING=utf-8 && pytest tests/unit/ -v -p no:capture --tb=short

# Specific sprint tests
pytest tests/unit/test_sprint209_e2e_living_agent.py -v -p no:capture

# Integration tests (require running services)
pytest tests/integration/ -v

# Property-based tests
pytest tests/property/ -v

# With coverage report
pytest tests/unit/ --cov=app --cov-report=html
```

**Stats:** 9,830 unit tests across 342 test files. All passing, 0 failures. (as of Sprint 210d, Feb 26, 2026)

---

## Docker

```bash
cd maritime-ai-service
cp .env.example .env        # Copy and set GOOGLE_API_KEY
docker compose up -d        # Standard stack

# Or: Soul AGI full stack (includes Ollama for Living Agent)
docker compose -f docker-compose.soul-agi.yml up -d
```

**Services:**
- **App:** `http://localhost:8000`
- **PostgreSQL:** `localhost:5433` (user: `wiii`, db: `wiii_ai`)
- **Neo4j Browser:** `http://localhost:7474`
- **MinIO Console:** `http://localhost:9001`
- **PgAdmin:** `http://localhost:5050` (with `--profile tools`)

---

## Database Migrations

Managed via Alembic (34 migrations as of Sprint 209):

```bash
alembic upgrade head          # Run all pending migrations
alembic revision --autogenerate -m "description"  # Create new migration
alembic current               # Check current revision
```

Key migrations: initial schema, pgvector extension, semantic memories, character system, organization tables, org isolation columns, auth audit events, living agent tables, soul AGI tables, refresh token families, OTP link codes, admin module, organization documents, scraping metrics, tool execution metrics.

---

## License

Proprietary -- All rights reserved.

*Wiii by The Wiii Lab*
