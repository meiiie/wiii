<p align="center">
  <img src="https://img.shields.io/badge/Wiii-AI%20Platform-FF6B00?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0id2hpdGUiPjxwYXRoIGQ9Ik0xMiAyQzYuNDggMiAyIDYuNDggMiAxMnM0LjQ4IDEwIDEwIDEwIDEwLTQuNDggMTAtMTBTMTcuNTIgMiAxMiAyek0xMiAyMGMtNC40MSAwLTgtMy41OS04LThzMy41OS04IDgtOCA4IDMuNTkgOCA4LTMuNTkgOC04IDh6Ii8+PC9zdmc+" alt="Wiii" />
</p>

<h1 align="center">Wiii</h1>

<p align="center">
  <strong>Multi-Domain Agentic RAG Platform with Long-term Memory</strong>
</p>

<p align="center">
  <a href="https://github.com/meiiie/LMS_AI/actions/workflows/test-backend.yml"><img src="https://github.com/meiiie/LMS_AI/actions/workflows/test-backend.yml/badge.svg" alt="Backend Tests" /></a>
  <a href="https://github.com/meiiie/LMS_AI/actions/workflows/test-desktop.yml"><img src="https://github.com/meiiie/LMS_AI/actions/workflows/test-desktop.yml/badge.svg" alt="Desktop Tests" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT" /></a>
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/tests-5537%20backend%20%7C%20479%20desktop-brightgreen" alt="Tests" />
  <img src="https://img.shields.io/badge/LLM-Gemini%20%7C%20OpenAI%20%7C%20Ollama-blueviolet" alt="LLM Providers" />
</p>

<p align="center">
  Built with FastAPI, LangGraph, Google Gemini, PostgreSQL+pgvector, Neo4j, and Tauri v2.<br/>
  By <strong>The Wiii Lab</strong>.
</p>

---

## Features

| Feature | Description |
|---------|-------------|
| **Multi-Agent System** | LangGraph-powered agent graph — Guardian, Supervisor, RAG, Tutor, Memory, Direct, Grader, Synthesizer |
| **Corrective RAG** | Hybrid search (dense + sparse + RRF), tiered grading, self-correction loop, LLM fallback |
| **Living Memory** | Semantic memory with importance-aware eviction, Ebbinghaus decay, provenance tracking, active pruning |
| **Domain Plugins** | Drop-in domain support via `domain.yaml` — Maritime (primary), Traffic Law (PoC), extensible |
| **Character System** | VTuber-card personality, Stanford Generative Agents reflection, 2D emotional state, per-user isolation |
| **Desktop App** | Tauri v2 + React 18 — native cross-platform app with living avatar, SSE streaming, offline support |
| **MCP Support** | Model Context Protocol server (expose tools) and client (consume external tools) |
| **Multi-Provider LLM** | Failover chain: Google Gemini → OpenAI → Ollama with 3-tier token budget (deep/moderate/light) |
| **Multi-Tenant** | Organization-scoped domain filtering, per-request isolation via ContextVar, admin API |

## Architecture

```
                                    ┌─────────────────────────────────────┐
                                    │          Wiii Platform              │
User ──► REST / WebSocket / Telegram│                                     │
         ┌──────────────────────────┤                                     │
         │       API Gateway        │  ┌───────────┐  ┌───────────────┐  │
         │  (Auth + Rate Limit +    │  │  Domain    │  │  Input        │  │
         │   Request-ID Middleware) │  │  Router    │  │  Processor    │  │
         └──────────┬───────────────┤  └─────┬─────┘  │  (context +   │  │
                    │               │        │        │   memory)     │  │
                    ▼               │        ▼        └───────┬───────┘  │
         ┌──────────────────┐       │  ┌───────────┐          │          │
         │ ChatOrchestrator │───────┼─►│ LangGraph │◄─────────┘          │
         └──────────────────┘       │  │  Multi-   │                     │
                                    │  │  Agent    │                     │
                                    │  │  Graph    │                     │
                                    │  └─────┬─────┘                     │
                                    │        │                           │
                    ┌───────────────┼────────┼───────────────────┐       │
                    │               │        │                   │       │
               ┌────▼────┐    ┌────▼────┐ ┌──▼───┐  ┌──────┐   │       │
               │Guardian │    │  RAG    │ │Tutor │  │Memory│   │       │
               │  Agent  │    │  Agent  │ │Agent │  │Agent │   │       │
               └────┬────┘    └────┬────┘ └──┬───┘  └──┬───┘   │       │
                    │              │          │         │       │       │
                    ▼              ▼          ▼         ▼       │       │
               ┌─────────┐  ┌──────────┐ ┌────────┐ ┌──────┐  │       │
               │Supervisor│  │Corrective│ │Agentic │ │Fact  │  │       │
               │(LLM-1st)│  │RAG       │ │Loop    │ │Store │  │       │
               └─────────┘  │Pipeline  │ │(ReAct) │ └──────┘  │       │
                             └──────────┘ └────────┘           │       │
                                    │                          │       │
                    ┌───────────────┼──────────────────────┐   │       │
                    │   Data Layer  │                      │   │       │
                    │  ┌────────┐ ┌─▼──────┐ ┌─────────┐  │   │       │
                    │  │PostgreSQL│ │Neo4j  │ │  MinIO  │  │   │       │
                    │  │+pgvector│ │GraphDB │ │(S3 Docs)│  │   │       │
                    │  └────────┘ └────────┘ └─────────┘  │   │       │
                    └─────────────────────────────────────┘   │       │
                                    └─────────────────────────┘       │
                                    └─────────────────────────────────┘
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

# Optional (failover providers)
OPENAI_API_KEY=sk-...               # OpenAI (second in failover chain)
OLLAMA_BASE_URL=http://localhost:11434  # Ollama local (third in chain)

# Auto-configured by Docker Compose
DATABASE_URL=postgresql+asyncpg://wiii:wiii_secret@localhost:5433/wiii_ai
NEO4J_URI=bolt://localhost:7687
MINIO_ENDPOINT=localhost:9000
```

## Project Structure

```
.
├── maritime-ai-service/           # Backend (FastAPI)
│   ├── app/
│   │   ├── api/v1/               # REST, WebSocket, Webhook endpoints
│   │   ├── core/                 # Config, security, middleware, DB
│   │   ├── domains/              # Plugin system (maritime/, traffic_law/)
│   │   ├── engine/               # AI core: RAG, multi-agent, tools, LLM
│   │   ├── services/             # Business logic, orchestration
│   │   ├── repositories/         # Data access layer
│   │   ├── prompts/              # YAML persona configs
│   │   └── models/               # Pydantic schemas
│   ├── tests/                    # 5537 unit + integration tests
│   ├── scripts/                  # Ingestion, test, utility scripts
│   └── docker-compose.yml        # Full stack orchestration
│
├── wiii-desktop/                  # Desktop app (Tauri v2 + React 18)
│   ├── src/                      # React UI (TypeScript, Tailwind, Zustand)
│   ├── src-tauri/                # Rust backend (Tauri plugins)
│   └── src/__tests__/            # 479 Vitest tests
│
└── CLAUDE.md                     # AI agent instructions
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **API Framework** | FastAPI 0.115+ with async/await |
| **Agent Orchestration** | LangGraph (multi-agent state machine) |
| **Primary LLM** | Google Gemini 2.5 (with thinking support) |
| **Vector Database** | PostgreSQL 15 + pgvector |
| **Knowledge Graph** | Neo4j 5 Community |
| **Object Storage** | MinIO (S3-compatible) |
| **Desktop Framework** | Tauri v2 + React 18 + TypeScript |
| **State Management** | Zustand (persisted via Tauri Store) |
| **Styling** | Tailwind CSS 3.4 |
| **Observability** | OpenTelemetry + structlog |
| **Authentication** | API Key + JWT (dual auth) |

## Configuration

Key feature flags in `app/core/config.py`:

```python
use_multi_agent = True              # LangGraph multi-agent system
enable_corrective_rag = True        # Self-correction RAG loop
enable_character_tools = True       # VTuber-card personality system
enable_character_reflection = True  # Stanford Generative Agents reflection
enable_structured_outputs = True    # Constrained decoding for routing
enable_llm_failover = True          # Multi-provider failover
enable_unified_client = False       # AsyncOpenAI SDK (alongside LangChain)
enable_mcp_server = False           # Expose tools via MCP
enable_mcp_client = False           # Consume external MCP tools
enable_agentic_loop = False         # Generalized ReAct loop
enable_multi_tenant = False         # Multi-organization support
```

## Testing

```bash
# Backend (5537 tests)
cd maritime-ai-service
pytest tests/unit/ -v -p no:capture --tb=short

# Desktop (479 tests)
cd wiii-desktop
npx vitest run

# Integration (requires running services)
pytest tests/integration/ -v

# Coverage
pytest tests/ --cov=app --cov-report=html
```

## API

### Authentication

```
X-API-Key: your-api-key
X-User-ID: student-123
X-Session-ID: session-abc
X-Role: student|teacher|admin
```

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/chat` | Synchronous chat |
| `POST` | `/api/v1/chat/stream/v3` | SSE streaming chat |
| `GET` | `/api/v1/chat/context/info` | Token budget & utilization |
| `GET` | `/api/v1/character/state` | Character personality blocks |
| `GET` | `/api/v1/mood` | Current emotional state (2D) |
| `GET/PUT` | `/api/v1/preferences` | User learning preferences |
| `GET` | `/api/v1/health` | Service health check |
| `GET` | `/api/v1/admin/domains` | List domain plugins |
| `WS` | `/api/v1/ws` | WebSocket real-time chat |

### Domain Plugin Development

```bash
cp -r app/domains/_template app/domains/my_domain
# Edit domain.yaml → add keywords, descriptions, prompts
# Add to config: active_domains=["maritime", "my_domain"]
# Restart — auto-discovered
```

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
