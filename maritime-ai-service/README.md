# Wiii -- Backend Service

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-purple?style=flat-square)](https://langchain.com)
[![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev)
[![pgvector](https://img.shields.io/badge/pgvector-0.7-00E599?style=flat-square&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)

**Multi-Domain Agentic RAG Platform with Long-term Memory, Product Search & Multi-Tenant Architecture**

*by The Wiii Lab*

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
# Edit .env — at minimum set GOOGLE_API_KEY and API_KEY

# Run
uvicorn app.main:app --reload
```

**API Base:** `http://localhost:8000/api/v1`

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Multi-Domain Plugins** | YAML-config domain plugins with auto-discovery (maritime, traffic law) |
| **Agentic RAG** | Self-correcting 6-step Corrective RAG with tiered grading and LLM fallback |
| **Multi-Agent System** | 8 agents via LangGraph: Guardian, Supervisor, RAG, Tutor, Memory, Direct, ProductSearch, Grader, Synthesizer |
| **Product Search** | 7 tools across 5+ platforms (Serper, WebSosanh, Facebook, TikTok, Apify) with circuit breakers |
| **Browser Scraping** | Playwright-based with LLM extraction (Facebook groups, search, web pages, screenshots) |
| **SOTA Streaming** | V3 SSE with thinking lifecycle, tool events, progressive rendering, multi-phase thinking chain |
| **Semantic Cache** | 3-tier TTL response caching with 0.99 similarity threshold |
| **Hybrid Search** | Dense (pgvector) + Sparse (tsvector) + RRF reranking |
| **Memory System** | Cross-session facts, insights, learning patterns, character system with Stanford reflection |
| **Authentication** | Google OAuth 2.0, JWT (access + refresh), LMS Token Exchange (HMAC-signed) |
| **Multi-Tenant** | Org-level data isolation, domain filtering, org-prefixed thread IDs, RBAC |
| **LMS Integration** | Webhook enrichment, backend-to-backend token exchange, Moodle/Canvas compatibility |
| **MCP Support** | Server (`/mcp` endpoint via fastapi-mcp) + Client (external MCP tool consumption) |
| **Web Search** | DuckDuckGo, News, Legal, Maritime-specific, price comparison (WebSosanh) |
| **LLM Failover** | Multi-provider chain (Gemini, OpenAI, Ollama) with 3-tier pool (deep/moderate/light) |
| **Conversation Context** | Sliding window (15 turns) + token budget manager + auto-compaction |
| **Structured Outputs** | Constrained decoding for Supervisor, Grader, Guardian routing decisions |

---

## Project Structure

```
maritime-ai-service/
├── app/
│   ├── api/v1/                # 18 REST API routers
│   ├── auth/                  # Google OAuth, JWT, LMS token exchange, user service
│   ├── cache/                 # Semantic cache system
│   ├── channels/              # Multi-channel gateway (WebSocket, Telegram)
│   ├── core/                  # Config (46+ feature flags), security, middleware, org filtering
│   ├── domains/               # Domain plugins (maritime/, traffic_law/, _template/)
│   ├── engine/                # AI engine
│   │   ├── agentic_rag/       # Corrective RAG pipeline (hybrid search, grading, generation)
│   │   ├── multi_agent/       # LangGraph agents (8 nodes, supervisor, streaming)
│   │   ├── search_platforms/  # Product search adapters (9 adapters, circuit breaker, OAuth)
│   │   ├── tools/             # LangChain tool registry (web, product, knowledge, datetime)
│   │   ├── character/         # Character system (blocks, reflection, per-user isolation)
│   │   ├── semantic_memory/   # Memory engine (facts, insights, consolidation)
│   │   ├── llm_providers/     # Gemini, OpenAI, Ollama providers + unified client
│   │   └── evaluation/        # Faithfulness & relevancy scoring
│   ├── integrations/          # LMS integration (webhook, enrichment, connectors)
│   ├── mcp/                   # MCP server + client + schema adapter
│   ├── models/                # Pydantic schemas (chat, organization, user)
│   ├── prompts/               # YAML persona configs (tutor, rag, supervisor, etc.)
│   ├── repositories/          # 15 data access repositories
│   ├── services/              # Business logic (orchestrator, session, scheduler, notifications)
│   └── tasks/                 # Background task infrastructure
├── alembic/                   # 12 database migrations
├── docs/architecture/         # SYSTEM_FLOW.md, SYSTEM_ARCHITECTURE.md
├── scripts/                   # Utility & test scripts
└── tests/                     # 319 test files, 6200+ unit tests
    ├── unit/                  # Unit tests (mock-based, no services required)
    ├── integration/           # Integration tests (require DB, Redis, etc.)
    ├── property/              # Property-based tests (Hypothesis)
    └── e2e/                   # End-to-end tests
```

---

## API Reference

### Chat

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat` | POST | JSON response (non-streaming) |
| `/api/v1/chat/stream/v1` | POST | SSE streaming (legacy) |
| `/api/v1/chat/stream/v2` | POST | SSE streaming (tool events) |
| `/api/v1/chat/stream/v3` | POST | SSE streaming (thinking lifecycle, progressive rendering) |

```http
POST /api/v1/chat/stream/v3
Content-Type: application/json
X-API-Key: {api_key}
X-User-ID: student-123
X-Session-ID: session-abc

{
  "message": "Your question here",
  "user_id": "student-123",
  "role": "student",
  "domain_id": "maritime",
  "organization_id": "lms-hang-hai"
}
```

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/google/login` | GET | Initiate Google OAuth flow |
| `/api/v1/auth/google/callback` | GET | OAuth callback (exchanges code for JWT) |
| `/api/v1/auth/token/refresh` | POST | Refresh JWT access token |
| `/api/v1/auth/lms/token` | POST | LMS token exchange (HMAC-signed, backend-to-backend) |
| `/api/v1/auth/lms/token/refresh` | POST | Refresh LMS-issued token |
| `/api/v1/auth/lms/health` | GET | LMS integration health check |

### Users

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/users/me` | GET | Current user profile |
| `/api/v1/users/me` | PATCH | Update own profile |
| `/api/v1/users/me/identities` | GET | List linked identity providers |
| `/api/v1/users/me/identities/{id}` | DELETE | Unlink identity provider |
| `/api/v1/users` | GET | Admin: list all users |
| `/api/v1/users/{id}/role` | PATCH | Admin: update user role |
| `/api/v1/users/{id}/deactivate` | POST | Admin: deactivate user |

### Organizations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/organizations` | GET | List organizations (admin: all, user: own) |
| `/api/v1/organizations` | POST | Create organization (admin only) |
| `/api/v1/organizations/{id}` | GET | Get organization details |
| `/api/v1/organizations/{id}` | PATCH | Update organization (admin only) |
| `/api/v1/organizations/{id}` | DELETE | Soft-delete organization (admin only) |
| `/api/v1/organizations/{id}/members` | GET | List members |
| `/api/v1/organizations/{id}/members` | POST | Add member (admin) |
| `/api/v1/organizations/{id}/members/{uid}` | DELETE | Remove member (admin) |
| `/api/v1/users/me/organizations` | GET | Current user's organizations |

### Conversation Context

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat/context/info` | GET | Token budget, utilization, message count |
| `/api/v1/chat/context/compact` | POST | Trigger conversation compaction |
| `/api/v1/chat/context/clear` | POST | Clear conversation context for session |

### Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/threads` | GET/POST | Thread CRUD (list, create) |
| `/api/v1/threads/{id}` | GET/DELETE | Get or delete thread |
| `/api/v1/insights/{user_id}` | GET | Learning analytics and insights |
| `/api/v1/memories/{user_id}` | GET/DELETE | User memory management |
| `/api/v1/sources/{node_id}` | GET | Citation sources for a response |
| `/api/v1/preferences` | GET/PATCH | User preferences (learning style, pronoun) |
| `/api/v1/feedback` | POST | Submit response feedback |

### Admin

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/admin/documents` | POST | Ingest documents (PDF, text) |
| `/api/v1/admin/documents` | GET | List ingested documents |
| `/api/v1/admin/domains` | GET | List registered domain plugins |
| `/api/v1/admin/domains/{id}` | GET | Domain plugin details |
| `/api/v1/admin/domains/{id}/skills` | GET | Domain skill manifest |
| `/api/v1/admin/stats` | GET | System statistics |

### Health

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Service health (all components) |
| `/api/v1/health/db` | GET | Database connectivity |
| `/api/v1/health/ollama` | GET | Ollama availability and model list |

### LMS Webhook

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/lms/webhook` | POST | Receive LMS events (enrollment, grade, etc.) |

---

## Architecture

See [docs/architecture/SYSTEM_FLOW.md](docs/architecture/SYSTEM_FLOW.md) for complete diagrams.

### Request Flow

```
User --> API --> ChatOrchestrator --> DomainRouter --> Supervisor --> Agent --> Response
                      |                   |                            |
                InputProcessor       DomainPlugin                AgenticLoop
            (context + memory)    (prompts, tools)         (multi-step tool calling)
                                                                       |
                                                           UnifiedLLMClient / LangChain
```

### Multi-Agent Graph (LangGraph)

```
               Guardian (safety filter, fail-open)
                   |
               Supervisor (LLM-first routing + keyword fallback)
              /    |    |    \         \
           RAG  Tutor Memory  Direct  ProductSearch
              \    |    |    /         /
               Grader (quality scoring, re-routing)
                   |
               Synthesizer (final formatting, Vietnamese output)
```

### Domain Plugin System

```
app/domains/
├── base.py            # DomainPlugin ABC, DomainConfig, SkillManifest
├── registry.py        # Singleton DomainRegistry
├── loader.py          # Auto-discovery from domains/*/domain.yaml
├── router.py          # 5-priority domain resolution + org-aware filtering
├── skill_manager.py   # Runtime SKILL.md CRUD
├── maritime/          # Maritime domain (COLREGs, SOLAS, MARPOL)
├── traffic_law/       # Vietnamese traffic law domain
└── _template/         # Skeleton for creating new domains
```

### Product Search Architecture

```
app/engine/search_platforms/
├── base.py            # SearchPlatformAdapter ABC
├── registry.py        # SearchPlatformRegistry singleton
├── circuit_breaker.py # Per-adapter circuit breaker
├── adapters/
│   ├── serper_shopping.py    # Google Shopping via Serper
│   ├── serper_site.py        # Site-specific search (Shopee, Lazada, Tiki, Sendo, Amazon)
│   ├── serper_all_web.py     # General web product search
│   ├── websosanh.py          # WebSosanh.vn price aggregator (94+ shops)
│   ├── facebook_search.py    # Facebook Marketplace (Playwright)
│   ├── facebook_group.py     # Facebook Group deep scan (GraphQL + scroll)
│   ├── apify_generic.py      # Apify actor-based scraping
│   ├── tiktok_research.py    # TikTok Research API (native + Serper fallback)
│   └── browser_base.py       # Base Playwright browser adapter
└── oauth/             # OAuth token management for platform APIs
```

---

## Configuration

### Required Environment Variables

```env
GOOGLE_API_KEY=AIza...              # Gemini API key (required)
API_KEY=your-api-key                # API authentication key

DATABASE_URL=postgresql+asyncpg://wiii:wiii_secret@localhost:5433/wiii_ai
```

### Optional Environment Variables

```env
# Additional LLM providers
OPENAI_API_KEY=sk-...
OLLAMA_BASE_URL=http://localhost:11434

# Graph database
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Object storage
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# Google OAuth
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback

# Product search
SERPER_API_KEY=...
APIFY_API_TOKEN=...

# LMS integration
LMS_WEBHOOK_SECRET=...
```

### Feature Flags

The application uses 46+ feature flags in `app/core/config.py`. Key flags:

| Flag | Default | Description |
|------|---------|-------------|
| `use_multi_agent` | `True` | Multi-Agent graph (LangGraph) |
| `enable_corrective_rag` | `True` | Self-correction loop |
| `enable_structured_outputs` | `True` | Constrained decoding for routing |
| `enable_character_tools` | `True` | Character introspection/update |
| `enable_multi_tenant` | `False` | Multi-organization support |
| `enable_product_search` | `False` | Product search agent |
| `enable_browser_scraping` | `False` | Playwright-based scraping |
| `enable_unified_client` | `False` | AsyncOpenAI SDK provider |
| `enable_mcp_server` | `False` | Expose tools via MCP |
| `enable_mcp_client` | `False` | Connect to external MCP servers |
| `enable_agentic_loop` | `False` | Generalized ReAct loop |
| `enable_scheduler` | `False` | Background task execution |
| `enable_lms_token_exchange` | `False` | LMS backend token exchange |
| `enable_llm_failover` | `True` | Multi-provider failover chain |

See `.env.example` and `app/core/config.py` for the full list.

---

## Domain Plugin Development

```bash
# 1. Copy template
cp -r app/domains/_template app/domains/my_domain

# 2. Edit domain.yaml with domain keywords, descriptions, and config
# 3. Write prompts in prompts/agents/
# 4. Add to config: active_domains=["maritime","my_domain"]
# 5. Restart — auto-discovered by DomainLoader
```

### Domain Admin API

```
GET /api/v1/admin/domains              # List all registered domains
GET /api/v1/admin/domains/{id}         # Get domain details
GET /api/v1/admin/domains/{id}/skills  # List domain skills
```

---

## Testing

```bash
# All unit tests (Windows — requires PYTHONIOENCODING for Unicode output)
set PYTHONIOENCODING=utf-8 && pytest tests/unit/ -v -p no:capture --tb=short

# Specific sprint tests
pytest tests/unit/test_sprint160_data_isolation.py -v -p no:capture

# Integration tests (require running services)
pytest tests/integration/ -v

# Property-based tests
pytest tests/property/ -v

# With coverage report
pytest tests/unit/ --cov=app --cov-report=html
```

**Stats:** 6200+ unit tests across 319 test files. All passing.

---

## Docker

```bash
cd maritime-ai-service
cp .env.example .env        # Copy and set GOOGLE_API_KEY
docker compose up -d        # Start all services
```

**Services:**
- **App:** `http://localhost:8000`
- **PostgreSQL:** `localhost:5433` (user: `wiii`, db: `wiii_ai`)
- **Neo4j Browser:** `http://localhost:7474`
- **MinIO Console:** `http://localhost:9001`
- **PgAdmin:** `http://localhost:5050` (with `--profile tools`)

---

## Database Migrations

Managed via Alembic (12 migrations as of Sprint 160):

```bash
# Run all pending migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "description"

# Check current revision
alembic current
```

Key migrations include: initial schema, pgvector extension, semantic memory tables, character system, organization tables, org data isolation columns, auth method tracking.

---

## License

Proprietary - All rights reserved.

*Wiii by The Wiii Lab*
