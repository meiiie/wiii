<p align="center">
  <img src="https://img.shields.io/badge/Wiii-AI%20Platform-FF6B00?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0id2hpdGUiPjxwYXRoIGQ9Ik0xMiAyQzYuNDggMiAyIDYuNDggMiAxMnM0LjQ4IDEwIDEwIDEwIDEwLTQuNDggMTAtMTBTMTcuNTIgMiAxMiAyek0xMiAyMGMtNC40MSAwLTgtMy41OS04LThzMy41OS04IDgtOCA4IDMuNTkgOCA4LTMuNTkgOC04IDh6Ii8+PC9zdmc+" alt="Wiii" />
</p>

<h1 align="center">Wiii</h1>

<p align="center">
  <strong>Multi-Domain Agentic RAG Platform with Long-term Memory & Multi-Tenant Organization Support</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT" /></a>
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/tests-6520%20backend%20%7C%201346%20desktop-brightgreen" alt="Tests" />
  <img src="https://img.shields.io/badge/LLM-Gemini%20%7C%20OpenAI%20%7C%20Ollama-blueviolet" alt="LLM Providers" />
  <img src="https://img.shields.io/badge/sprints-161-orange" alt="Sprints" />
</p>

<p align="center">
  Built with FastAPI, LangGraph, Google Gemini, PostgreSQL+pgvector, Neo4j, and Tauri v2.<br/>
  By <strong>The Wiii Lab</strong>.
</p>

---

## Features

| Feature | Description |
|---------|-------------|
| **Multi-Agent System** | LangGraph-powered agent graph: Guardian → Supervisor → RAG / Tutor / Memory / Direct / Product Search → Grader → Synthesizer |
| **Corrective RAG** | Hybrid search (dense + sparse + RRF), tiered grading (MiniJudge → Full LLM), self-correction loop, LLM fallback |
| **Living Memory** | Semantic fact extraction (15 types), importance-aware eviction, Ebbinghaus decay, vector retrieval, active pruning |
| **Domain Plugins** | Drop-in domain support via `domain.yaml` — Maritime (primary), Traffic Law (PoC), auto-discovered at startup |
| **Character System** | VTuber-card personality, Stanford Generative Agents reflection, 2D emotional state, per-user isolation |
| **Product Search** | Plugin-based search across 8 platforms (Shopee, Lazada, TikTok Shop, Facebook, WebSosanh, etc.) with browser scraping |
| **Desktop App** | Tauri v2 + React 18 — native Windows app with living avatar, multi-phase thinking UX, SSE streaming |
| **Multi-Tenant** | Organization-level branding, feature scoping, RBAC permissions, per-org AI persona overlay |
| **Authentication** | Google OAuth + JWT + LMS Token Exchange (HMAC-SHA256) + Identity Federation |
| **MCP Support** | Model Context Protocol server (expose tools) and client (consume external tools) |
| **Multi-Provider LLM** | Failover chain: Google Gemini → OpenAI → Ollama with 3-tier token budget (deep/moderate/light) |
| **LMS Integration** | Webhook enrichment, token exchange, Moodle/Canvas/Sakai connector framework |

## Architecture

```
                                    ┌─────────────────────────────────────┐
                                    │          Wiii Platform              │
User ──► REST / SSE / WebSocket     │                                     │
         ┌──────────────────────────┤  ┌────────────┐ ┌──────────────┐   │
         │    API & Auth Gateway    │  │  Domain     │ │   Org        │   │
         │  (JWT + OAuth + HMAC +   │  │  Router     │ │   Context    │   │
         │   Rate Limit + Org MW)   │  │  (5-prio)   │ │   Middleware │   │
         └──────────┬───────────────┤  └──────┬──────┘ └──────┬──────┘   │
                    │               │         │               │          │
                    ▼               │         ▼               ▼          │
         ┌──────────────────┐       │  ┌─────────────────────────────┐   │
         │ ChatOrchestrator │───────┼─►│      LangGraph Multi-Agent  │   │
         └──────────────────┘       │  │  ┌─────────┐ ┌───────────┐ │   │
                                    │  │  │Guardian  │ │Supervisor │ │   │
                                    │  │  └────┬─────┘ └─────┬─────┘ │   │
                                    │  │       │             │       │   │
                                    │  │  ┌────▼──┬──────┬───▼──┬──┐ │   │
                                    │  │  │ RAG   │Tutor │Direct│PS│ │   │
                                    │  │  │ Agent │Agent │Agent │  │ │   │
                                    │  │  └───┬───┴──┬───┴──┬───┴──┘ │   │
                                    │  │      │      │      │        │   │
                                    │  │  ┌───▼──────▼──────▼──────┐ │   │
                                    │  │  │  Grader → Synthesizer  │ │   │
                                    │  │  └────────────────────────┘ │   │
                                    │  └─────────────────────────────┘   │
                                    │                                     │
         ┌──────────────────────────┼─────────────────────────────┐      │
         │        Data Layer        │                             │      │
         │  ┌──────────┐ ┌─────────┴─┐ ┌─────────┐ ┌─────────┐  │      │
         │  │PostgreSQL │ │  Neo4j    │ │  MinIO  │ │Playwright│  │      │
         │  │+pgvector  │ │  GraphDB  │ │(S3 Docs)│ │(Browser) │  │      │
         │  └──────────┘ └───────────┘ └─────────┘ └─────────┘  │      │
         └────────────────────────────────────────────────────────┘      │
                                    └─────────────────────────────────────┘
```

## Quick Start

### Docker Compose (Recommended)

```bash
cd maritime-ai-service
cp .env.example .env          # Edit: set GOOGLE_API_KEY=AIza...
docker compose up -d           # Starts app + PostgreSQL + Neo4j + MinIO
```

App is now running at **http://localhost:8000**. API docs at `/docs`.

### Manual Setup

```bash
# 1. Backend
cd maritime-ai-service
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Edit with your API keys

# 2. Start services (PostgreSQL, Neo4j, MinIO)
docker compose up -d postgres neo4j minio

# 3. Run the server
uvicorn app.main:app --reload

# 4. Desktop app (optional)
cd ../wiii-desktop
npm install
npx tauri dev
```

### Environment Variables

```bash
# Required
GOOGLE_API_KEY=AIza...              # Google Gemini API key
API_KEY=your-secret-key             # API authentication key

# Optional: additional LLM providers
OPENAI_API_KEY=sk-...               # OpenAI (second in failover chain)
OLLAMA_BASE_URL=http://localhost:11434  # Ollama local (third in chain)

# Optional: authentication
GOOGLE_CLIENT_ID=...                # Google OAuth 2.0
GOOGLE_CLIENT_SECRET=...            # Google OAuth 2.0

# Auto-configured by Docker Compose
DATABASE_URL=postgresql+asyncpg://wiii:wiii_secret@localhost:5433/wiii_ai
NEO4J_URI=bolt://localhost:7687
MINIO_ENDPOINT=localhost:9000
```

## Project Structure

```
.
├── maritime-ai-service/           # Backend (FastAPI + LangGraph)
│   ├── app/
│   │   ├── api/v1/               # 18 REST/WebSocket/Webhook routers
│   │   ├── auth/                 # OAuth, JWT, LMS token exchange
│   │   ├── core/                 # Config (46 feature flags), middleware, DB
│   │   ├── domains/              # Plugin system (maritime/, traffic_law/)
│   │   ├── engine/               # AI core: RAG, multi-agent, tools, LLM,
│   │   │   │                     #   search platforms, character system
│   │   │   ├── agentic_rag/      # Corrective RAG pipeline
│   │   │   ├── multi_agent/      # LangGraph agent graph
│   │   │   ├── llm_providers/    # Gemini, OpenAI, Ollama + unified client
│   │   │   ├── search_platforms/ # 8 search adapters (plugin architecture)
│   │   │   ├── tools/            # 8 tool modules
│   │   │   ├── character/        # Stanford Generative Agents
│   │   │   └── semantic_memory/  # Fact extraction + decay
│   │   ├── integrations/         # LMS webhook + API client
│   │   ├── services/             # Business logic (23 service files)
│   │   ├── repositories/         # Data access (15 repository files)
│   │   ├── prompts/              # YAML persona configs
│   │   ├── mcp/                  # MCP server + client
│   │   └── models/               # Pydantic schemas
│   ├── alembic/                  # 12 database migrations
│   ├── tests/                    # 6520+ unit + integration tests
│   └── docker-compose.yml        # Full stack orchestration
│
├── wiii-desktop/                  # Desktop app (Tauri v2 + React 18)
│   ├── src/
│   │   ├── components/           # Chat, Layout, Settings, Auth, Common
│   │   ├── stores/               # 11 Zustand stores
│   │   ├── api/                  # 15 API modules
│   │   ├── hooks/                # 4 custom hooks
│   │   ├── lib/                  # 28 utility modules + avatar system
│   │   └── __tests__/            # 54 test files (1346 tests)
│   └── src-tauri/                # Rust backend (Tauri plugins, commands)
│
├── docs/                         # Architecture, flow, API documentation
└── CLAUDE.md                     # AI agent instructions
```

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| **API Framework** | FastAPI | 0.115+ |
| **Agent Orchestration** | LangGraph | Multi-agent state machine |
| **Primary LLM** | Google Gemini 2.5 | With thinking/reasoning support |
| **Failover LLMs** | OpenAI, Ollama (Qwen3:8b) | Automatic failover chain |
| **Vector Database** | PostgreSQL + pgvector | 15+ (768-dim embeddings) |
| **Knowledge Graph** | Neo4j | 5 Community |
| **Object Storage** | MinIO | S3-compatible |
| **Browser Engine** | Playwright | Headless Chrome (feature-gated) |
| **Desktop Framework** | Tauri v2 | Rust backend + web frontend |
| **Frontend** | React 18 + TypeScript | Vite 5 |
| **State Management** | Zustand | 11 stores, Immer middleware |
| **Styling** | Tailwind CSS | 3.4 |
| **Animation** | Rive + Motion (Framer) | Living avatar system |
| **Auth** | JWT + Google OAuth + HMAC | Multi-provider federation |
| **Observability** | OpenTelemetry + structlog | Structured JSON logging |

## Feature Flags

46 feature flags in `app/core/config.py` — all major subsystems are gated for safe incremental rollout:

```python
# Core AI (enabled by default)
use_multi_agent = True              # LangGraph multi-agent system
enable_corrective_rag = True        # Self-correction RAG loop
enable_structured_outputs = True    # Constrained decoding for routing
enable_agentic_loop = True          # Generalized ReAct tool-calling

# Memory & Character (enabled by default)
enable_character_tools = True       # Character introspection/update
enable_character_reflection = True  # Stanford reflection loop
enable_semantic_fact_retrieval = True  # Vector-based fact search

# Search & Browser (opt-in)
enable_product_search = False       # Product search agent (8 platforms)
enable_browser_scraping = False     # Playwright headless browser
enable_browser_screenshots = False  # Stream screenshots to UI
enable_network_interception = True  # GraphQL capture during scroll

# Authentication (opt-in)
enable_google_oauth = False         # Google OAuth 2.0 login
enable_lms_token_exchange = False   # Backend-to-backend HMAC JWT
enable_multi_tenant = False         # Multi-org data isolation

# Infrastructure (opt-in)
enable_mcp_server = False           # Expose tools via MCP
enable_mcp_client = False           # Consume external MCP tools
enable_scheduler = False            # Background task execution
enable_lms_integration = False      # LMS webhook enrichment
```

## Testing

```bash
# Backend (6520+ tests)
cd maritime-ai-service
PYTHONIOENCODING=utf-8 pytest tests/unit/ -v -p no:capture --tb=short

# Desktop (1346 tests)
cd wiii-desktop
npx vitest run

# Integration (requires running services)
pytest tests/integration/ -v

# Coverage
pytest tests/ --cov=app --cov-report=html
```

## API Reference

### Authentication

Dual auth: API Key + JWT with LMS headers.

```
X-API-Key: your-api-key
X-User-ID: student-123
X-Session-ID: session-abc
X-Role: student|teacher|admin
X-Organization-ID: lms-hang-hai       # Optional: multi-tenant context
Authorization: Bearer <jwt-token>      # Optional: OAuth JWT
```

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/chat` | Synchronous chat |
| `POST` | `/api/v1/chat/stream/v3` | SSE streaming chat |
| `GET` | `/api/v1/chat/context/info` | Token budget & utilization |
| `POST` | `/api/v1/chat/context/compact` | Trigger conversation compaction |
| `GET` | `/api/v1/character/state` | Character personality blocks |
| `GET` | `/api/v1/mood` | Current emotional state (2D) |
| `GET/PUT` | `/api/v1/preferences` | User learning preferences |
| `GET` | `/api/v1/health` | Service health check |
| `GET` | `/api/v1/admin/domains` | List domain plugins |
| `GET/PATCH` | `/api/v1/organizations/{id}/settings` | Org settings (Sprint 161) |
| `GET` | `/api/v1/organizations/{id}/permissions` | User permissions in org |
| `GET/PATCH` | `/api/v1/users/me` | User profile management |
| `POST` | `/api/v1/auth/lms/token` | LMS token exchange (HMAC) |
| `GET` | `/auth/oauth/login` | Google OAuth login |
| `WS` | `/api/v1/ws` | WebSocket real-time chat |

### Domain Plugin Development

```bash
cp -r app/domains/_template app/domains/my_domain
# Edit domain.yaml → add keywords, descriptions, prompts
# Add to config: active_domains=["maritime", "my_domain"]
# Restart — auto-discovered at startup
```

## Documentation

| Document | Path | Description |
|----------|------|-------------|
| **System Architecture** | `maritime-ai-service/docs/architecture/SYSTEM_ARCHITECTURE.md` | Complete technical architecture (55 KB) |
| **System Flow** | `maritime-ai-service/docs/architecture/SYSTEM_FLOW.md` | Request/response flows (38 KB) |
| **Folder Map** | `maritime-ai-service/docs/architecture/FOLDER_MAP.md` | Directory structure reference (25 KB) |
| **API Integration** | `maritime-ai-service/docs/api/integration-guide.md` | API integration patterns |
| **Local Development** | `maritime-ai-service/docs/LOCAL_DEV.md` | Development setup guide |
| **Agent Instructions** | `CLAUDE.md` | AI agent coding instructions |

## Development History

161 sprints of iterative development:

| Phase | Sprints | Highlights |
|-------|---------|------------|
| **Foundation** | 1-68 | Core RAG, Docker, LangGraph, Desktop, MCP, Agentic Loop |
| **Intelligence** | 69-103 | Routing, Memory, Streaming, Context, Security, LLM-First Routing |
| **Living Desktop** | 104-135 | Living Avatar, SVG Face, Kawaii, Emotion Engine, Soul Emotion |
| **Search & Tools** | 136-153 | Universal KB, Product Search (8 platforms), Browser Scraping |
| **Enterprise** | 154-161 | OAuth, User Management, LMS Integration, Multi-Tenant, Org Customization |

**Current:** 254 Python files, 158 TypeScript files, 46 feature flags, 12 DB migrations, 7866 tests total.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards, and pull request process.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Acknowledgments

Built by **The Wiii Lab**.

- [LangGraph](https://github.com/langchain-ai/langgraph) — Multi-agent orchestration
- [FastAPI](https://fastapi.tiangolo.com/) — High-performance API framework
- [Tauri](https://tauri.app/) — Cross-platform desktop framework
- [Google Gemini](https://ai.google.dev/) — Primary LLM provider
- [pgvector](https://github.com/pgvector/pgvector) — Vector similarity search for PostgreSQL
- [Playwright](https://playwright.dev/) — Browser automation for product search
- [Rive](https://rive.app/) — Living avatar animations
