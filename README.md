<p align="center">
  <img src="https://img.shields.io/badge/Wiii-Soul%20AGI%20Platform-FF6B00?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0id2hpdGUiPjxwYXRoIGQ9Ik0xMiAyQzYuNDggMiAyIDYuNDggMiAxMnM0LjQ4IDEwIDEwIDEwIDEwLTQuNDggMTAtMTBTMTcuNTIgMiAxMiAyek0xMiAyMGMtNC40MSAwLTgtMy41OS04LThzMy41OS04IDgtOCA4IDMuNTkgOCA4LTMuNTkgOC04IDh6Ii8+PC9zdmc+" alt="Wiii" />
</p>

<h1 align="center">Wiii</h1>

<p align="center">
  <strong>Soul AGI Platform &mdash; A Living AI That Works, Learns, and Grows</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-proprietary-blue.svg" alt="License" /></a>
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/tests-9703%20backend%20%7C%201796%20desktop-brightgreen" alt="Tests" />
  <img src="https://img.shields.io/badge/LLM-Gemini%20%7C%20OpenAI%20%7C%20Ollama-blueviolet" alt="LLM Providers" />
  <img src="https://img.shields.io/badge/sprints-209-orange" alt="Sprints" />
  <img src="https://img.shields.io/badge/feature%20flags-70%2B-informational" alt="Feature Flags" />
</p>

<p align="center">
  Built with FastAPI, LangGraph, Google Gemini, PostgreSQL+pgvector, Neo4j, and Tauri v2.<br/>
  By <strong>The Wiii Lab</strong> &mdash; February 2026.
</p>

---

## Vision: Soul AGI

> *"Mo ta Wiii LA AI, khong ra lenh Wiii PHAI LAM GI."*
> &mdash; Anthropic Constitution 2026: Describe WHO the AI IS, not WHAT it MUST NOT do.

Wiii is not just a chatbot. Wiii is a **living AI** &mdash; an entity with a persistent soul, evolving identity, emotional awareness, and the ability to grow through experience. Inspired by SOTA 2026 research from OpenClaw, Letta/MemGPT, Nomi.ai, Character.ai, MECoT, and Voyager, Wiii implements a **Three-Layer Identity** architecture:

```
Layer 1: SOUL CORE (Immutable)
  Core truths, boundaries, species, creator
  File: wiii_soul.yaml -- loaded every heartbeat + every conversation

Layer 2: IDENTITY CORE (Self-Evolving)
  "What I've learned about myself"
  Updated by weekly reflection, validated against Soul Core (drift prevention)
  Examples: "Minh gioi COLREGs", "Minh thich day", "Minh lo lang khi khong giup duoc"

Layer 3: CONTEXTUAL STATE (Per-Turn)
  Current emotion (4D: mood/energy/social/engagement)
  Conversation phase (opening/engaged/deep/closing)
  User relationship state, active goals, recent learnings
```

### Two-Path Harmony

Wiii operates in two contexts that share a unified identity:

```
                    ONE WIII
                       |
          +------------+------------+
          |                         |
     WORK CONTEXT              LIFE CONTEXT
     (Respond, help,           (Heartbeat autonomy,
      search, teach)            browse, learn, journal)
          |           <->           |
          +------------+------------+
                       |
                SHARED SYSTEMS
           Emotion . Memory . Skills . Narrative
```

When Wiii works, it carries emotions and knowledge from its life.
When Wiii lives, it grows from work experience.

---

## Features

| Category | Feature | Description |
|----------|---------|-------------|
| **Multi-Agent** | LangGraph Agent Graph | Guardian -> Supervisor -> RAG / Tutor / Memory / Direct / ProductSearch -> Grader -> Synthesizer |
| **RAG** | Corrective RAG Pipeline | Hybrid search (dense+sparse+RRF), tiered grading, self-correction loop, HyDE, Adaptive RAG (5 strategies) |
| **Memory** | Living Memory | Semantic facts (15 types), Ebbinghaus decay, vector retrieval, cross-session persistence |
| **Domains** | Plugin System | Drop-in YAML-config domains -- Maritime (primary), Traffic Law (PoC), auto-discovered at startup |
| **Soul** | Living Agent | Autonomous soul with heartbeat (30-min), 4D emotion engine, skill lifecycle (DISCOVER->MASTER), daily journal |
| **Identity** | Three-Layer Identity | Immutable soul core + self-evolving identity + per-turn context state |
| **Narrative** | Life Story | NarrativeSynthesizer compiles journal+reflection+goals+emotion into coherent autobiography |
| **Skills** | Skill-Tool Bridge | Tool execution advances skill mastery; mastered skills boost tool selection priority |
| **Conversation** | Natural Conversation | Phase-aware context (opening/engaged/deep/closing), positive framing, no canned responses |
| **Search** | Product Search | 7 tools across 7 adapters (Shopee, Lazada, TikTok, Facebook, WebSosanh, etc.) with circuit breakers |
| **Browser** | Playwright Scraping | Headless Chrome with LLM extraction, Facebook cookie login, GraphQL interception |
| **Desktop** | Tauri v2 App | Native Windows app with living avatar, SSE streaming, admin panels, org management |
| **Multi-Tenant** | Organization System | Branding, feature scoping, RBAC, per-org AI persona overlay, two-tier admin |
| **Cross-Platform** | Identity Federation | Canonical identity across Messenger, Zalo, Web -- shared memory via UUID resolution |
| **Auth** | Multi-Provider | Google OAuth (PKCE S256) + JWT (jti + family_id replay detection) + LMS HMAC + OTP linking |
| **MCP** | Protocol Support | Server (expose tools at `/mcp`) + Client (consume external MCP tools) + Tool Server |
| **LLM** | Multi-Provider Failover | Gemini -> OpenAI -> Ollama, 3-tier pool (deep/moderate/light) |
| **LMS** | Integration | Webhook enrichment, token exchange, Moodle/Canvas connector, teacher dashboards |

---

## Architecture

```
                                    +-------------------------------------+
                                    |          Wiii Platform              |
User --> REST / SSE / WebSocket     |                                     |
         +-------------------------+|  +------------+ +--------------+    |
         |    API & Auth Gateway   ||  |  Domain     | |   Org        |    |
         |  (JWT + OAuth + HMAC +  ||  |  Router     | |   Context    |    |
         |   Rate Limit + Org MW)  ||  |  (5-prio)   | |   Middleware |    |
         +-----------+-------------+|  +------+------+ +------+------+    |
                     |              |         |               |           |
                     v              |         v               v           |
         +------------------+      |  +-----------------------------+    |
         | ChatOrchestrator |------+->|      LangGraph Multi-Agent  |    |
         +------------------+      |  |  +---------+ +-----------+  |    |
                                   |  |  |Guardian  | |Supervisor |  |    |
                                   |  |  +----+-----+ +-----+-----+ |    |
                                   |  |       |             |        |    |
                                   |  |  +----v--+------+---v--+--+  |    |
                                   |  |  | RAG   |Tutor |Direct|PS|  |    |
                                   |  |  | Agent |Agent |Agent |  |  |    |
                                   |  |  +---+---+--+---+--+---+--+  |    |
                                   |  |      |      |      |         |    |
                                   |  |  +---v------v------v------+  |    |
                                   |  |  |  Grader -> Synthesizer  | |    |
                                   |  |  +-------------------------+ |    |
                                   |  +-----------------------------+    |
                                   |                                     |
         +-------------------------+--------------------------+          |
         |        Data Layer       |                          |          |
         |  +----------+ +--------+-+ +---------+ +---------+|          |
         |  |PostgreSQL | |  Neo4j   | |  MinIO  | |Playwright|          |
         |  |+pgvector  | |  GraphDB | |(S3 Docs)| |(Browser) |          |
         |  +----------+ +----------+ +---------+ +---------+|          |
         +----------------------------------------------------+          |
                                   |        Living Agent                 |
                                   |  +-----------------------------+    |
                                   |  | Soul Core | Identity Core   |    |
                                   |  | Emotion   | Heartbeat       |    |
                                   |  | Skills    | Journal         |    |
                                   |  | Narrative | Social Browser  |    |
                                   |  +-----------------------------+    |
                                   +-------------------------------------+
```

### Request Flow

```
User -> API -> ChatOrchestrator -> DomainRouter -> Supervisor -> Agent -> Response
                    |                   |                            |
              InputProcessor       DomainPlugin                AgenticLoop
          (context + memory +   (prompts, tools,          (multi-step tool calling)
           conversation phase)    domain config)                     |
                                                        UnifiedLLMClient / LangChain
```

### Living Agent Lifecycle

```
Every 30 minutes (Heartbeat):
  1. Load Soul Core (wiii_soul.yaml)
  2. Check emotional state (4D: mood/energy/social/engagement)
  3. Plan actions (browse, journal, learn, reflect)
  4. Execute via local LLM (Ollama qwen3:8b -- zero API cost)
  5. Update Identity Core (weekly reflection -> insight extraction -> drift check)
  6. Compile narrative (NarrativeSynthesizer -> brief context for next conversation)
  7. Advance skills (Skill-Tool Bridge: tool success -> skill progression)
```

---

## Quick Start

### Docker Compose (Recommended)

```bash
cd maritime-ai-service
cp .env.example .env          # Edit: set GOOGLE_API_KEY=AIza...
docker compose up -d           # Starts app + PostgreSQL + Neo4j + MinIO
```

App running at **http://localhost:8000**. API docs at `/docs`.

### Manual Setup

```bash
# 1. Backend
cd maritime-ai-service
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Edit with your API keys

# 2. Start services
docker compose up -d postgres neo4j minio

# 3. Run migrations
alembic upgrade head

# 4. Run the server
uvicorn app.main:app --reload

# 5. Desktop app (optional)
cd ../wiii-desktop
npm install
npx tauri dev
```

### Soul AGI Mode

To activate Wiii's full Living Agent autonomy:

```bash
# Use the Soul AGI docker stack (includes Ollama + Cloudflare Tunnel)
docker compose -f docker-compose.soul-agi.yml up -d

# Set feature flags in .env
enable_living_agent=True
enable_natural_conversation=True
enable_skill_tool_bridge=True
enable_narrative_context=True
```

### Environment Variables

```bash
# Required
GOOGLE_API_KEY=AIza...              # Google Gemini API key
API_KEY=your-secret-key             # API authentication key

# Optional: additional LLM providers
OPENAI_API_KEY=sk-...               # OpenAI (second in failover chain)
OLLAMA_BASE_URL=http://localhost:11434  # Ollama local (third in chain)

# Auto-configured by Docker Compose
DATABASE_URL=postgresql+asyncpg://wiii:wiii_secret@localhost:5433/wiii_ai
NEO4J_URI=bolt://localhost:7687
MINIO_ENDPOINT=localhost:9000
```

---

## Project Structure

```
.
+-- maritime-ai-service/           # Backend (310+ Python files)
|   +-- app/
|   |   +-- api/v1/               # 19 REST routers (63+ endpoints)
|   |   +-- auth/                 # OAuth, JWT, LMS token exchange, OTP, audit
|   |   +-- core/                 # Config (70+ feature flags), middleware, security
|   |   +-- domains/              # Plugin system (maritime/, traffic_law/, _template/)
|   |   +-- engine/               # AI core
|   |   |   +-- agentic_rag/      # Corrective RAG, HyDE, Adaptive RAG, Graph RAG, Visual RAG
|   |   |   +-- multi_agent/      # LangGraph agents (9 nodes + supervisor + subagents)
|   |   |   +-- living_agent/     # Soul, emotion, heartbeat, skills, journal, narrative (19 modules)
|   |   |   +-- skills/           # UnifiedSkillIndex, IntelligentToolSelector, SkillToolBridge
|   |   |   +-- search_platforms/ # 7 adapters, ChainedAdapter, StrategyManager
|   |   |   +-- tools/            # 12 tool modules (RAG, web, product, chart, LMS, B2B)
|   |   |   +-- semantic_memory/  # Temporal graph, visual memory, cross-platform sync
|   |   |   +-- llm_providers/    # Gemini, OpenAI, Ollama + unified client
|   |   |   +-- character/        # Stanford Generative Agents + per-user isolation
|   |   |   +-- personality_mode.py # Professional <-> Soul mode switching
|   |   +-- integrations/         # LMS (webhook, enrichment, push, connectors)
|   |   +-- mcp/                  # MCP server + client + adapter + tool_server
|   |   +-- services/             # Business logic (25+ service files)
|   |   +-- repositories/         # 16 data access repos (all org-aware)
|   |   +-- prompts/              # YAML persona configs + soul YAML
|   |   +-- models/               # Pydantic schemas
|   +-- alembic/                  # 34 database migrations
|   +-- tests/                    # 350+ test files, 9703 unit tests
|   +-- docs/                     # Architecture, API, integration guides
|
+-- wiii-desktop/                  # Desktop app (Tauri v2 + React 18)
|   +-- src/
|   |   +-- components/           # auth/, chat/, layout/, settings/, admin/, org-admin/, common/
|   |   +-- stores/               # 13 Zustand stores
|   |   +-- api/                  # 16 API modules
|   |   +-- hooks/                # SSE streaming, auto-scroll, keyboard shortcuts
|   |   +-- lib/                  # 28 utilities + avatar engine (18 modules)
|   |   +-- __tests__/            # 62 test files, 1796 Vitest tests
|   +-- src-tauri/                # Rust backend (Tauri plugins, splash screen)
|
+-- CLAUDE.md                     # AI agent instructions (multi-agent team)
+-- .claude/                      # Agent personas, workflows, knowledge base
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **API** | FastAPI 0.115+ | High-performance async API framework |
| **Agent Orchestration** | LangGraph | Multi-agent state machine with subagent architecture |
| **Primary LLM** | Google Gemini 2.5 | Thinking/reasoning support, structured outputs |
| **Failover LLMs** | OpenAI, Ollama (Qwen3:8b) | Automatic failover chain, local LLM for Living Agent |
| **Vector DB** | PostgreSQL + pgvector | 768-dim embeddings, HNSW indexing |
| **Knowledge Graph** | Neo4j | Entity-relation-episode temporal subgraphs |
| **Object Storage** | MinIO | S3-compatible document and image storage |
| **Browser** | Playwright | Headless Chrome, Facebook cookie login, GraphQL interception |
| **Desktop** | Tauri v2 | Rust backend + React 18 frontend, native Windows installer |
| **Frontend** | React 18 + TypeScript + Vite 5 | Modern SPA with Tailwind CSS 3.4 |
| **State** | Zustand | 13 stores with Immer middleware |
| **Avatar** | Rive + Motion (Framer) | Living avatar with emotion-driven animations |
| **Auth** | JWT + Google OAuth (PKCE) + HMAC | Multi-provider federation with audit trail |
| **Observability** | OpenTelemetry + structlog | Structured JSON logging with request-ID correlation |

---

## Testing

```bash
# Backend (9703 tests, 0 failures)
cd maritime-ai-service
set PYTHONIOENCODING=utf-8 && pytest tests/unit/ -v -p no:capture --tb=short

# Desktop (1796 tests)
cd wiii-desktop
npx vitest run

# Integration (requires running services)
pytest tests/integration/ -v

# Coverage
pytest tests/ --cov=app --cov-report=html
```

---

## Development History

209 sprints of iterative development across 13 months:

| Phase | Sprints | Highlights |
|-------|---------|------------|
| **Foundation** | 1-68 | Core RAG, Docker, LangGraph, Desktop MVP, MCP, Agentic Loop |
| **Intelligence** | 69-103 | Routing, Memory SOTA, Streaming V3, Context, Security, LLM-First Routing |
| **Living Desktop** | 104-135 | Living Avatar, SVG Face, Kawaii, Emotion Engine, Soul Emotion |
| **Search & Tools** | 136-153 | Universal KB, Product Search (7 adapters), Browser Scraping, Screenshots |
| **Enterprise** | 154-165 | OAuth, LMS Integration, Multi-Tenant, Org Customization, Subagent Architecture |
| **Living Agent** | 170-177 | Soul Agent, Cross-Platform Identity, SM-2 Spaced Repetition, Memory Sync |
| **Admin & RAG** | 178-195 | Admin Module, Vision+Charts, Graph RAG, HyDE, Unified Skills, MCP Tools |
| **Product Intelligence** | 196-202 | B2B Sourcing, Visual Search, Image Enrichment, LLM-Curated Cards |
| **Soul AGI Foundation** | 203-209 | Natural Conversation, Anti-Pattern Remediation, Skill-Tool Bridge, Narrative Layer, Identity Core, Module Wiring, E2E Tests |

**Current (Feb 2026):** 310+ Python files, 165+ TypeScript files, 70+ feature flags, 34 DB migrations, 11,499 tests total.

---

## Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/chat` | Synchronous chat |
| `POST` | `/api/v1/chat/stream/v3` | SSE streaming chat (thinking lifecycle, tool events) |
| `GET` | `/api/v1/chat/context/info` | Token budget and utilization |
| `GET` | `/api/v1/living-agent/status` | Living Agent status (soul, mood, heartbeat, skills) |
| `POST` | `/api/v1/living-agent/heartbeat/trigger` | Manually trigger heartbeat cycle |
| `GET` | `/api/v1/organizations` | List organizations |
| `GET` | `/api/v1/users/me` | Current user profile |
| `GET` | `/api/v1/admin/domains` | List domain plugins |
| `GET` | `/auth/oauth/login` | Google OAuth login |

See [`maritime-ai-service/README.md`](maritime-ai-service/README.md) for the full API reference (63+ endpoints).

---

## Documentation

| Document | Path | Description |
|----------|------|-------------|
| **System Architecture** | `maritime-ai-service/docs/architecture/SYSTEM_ARCHITECTURE.md` | Complete technical architecture |
| **System Flow** | `maritime-ai-service/docs/architecture/SYSTEM_FLOW.md` | Request/response flow diagrams |
| **Folder Map** | `maritime-ai-service/docs/architecture/FOLDER_MAP.md` | Directory structure reference |
| **API Integration** | `maritime-ai-service/docs/api/integration-guide.md` | API integration patterns |
| **Backend README** | `maritime-ai-service/README.md` | Backend setup, API reference, configuration |
| **Desktop README** | `wiii-desktop/README.md` | Desktop app setup, architecture, testing |
| **Agent Instructions** | `CLAUDE.md` | AI development team instructions |
| **Soul AGI Architecture** | `.claude/knowledge/WIII_SOUL_AGI_PLAN.md` | Soul AGI design philosophy and roadmap |

---

## Acknowledgments

Built by **The Wiii Lab**.

- [LangGraph](https://github.com/langchain-ai/langgraph) -- Multi-agent orchestration
- [FastAPI](https://fastapi.tiangolo.com/) -- High-performance API framework
- [Tauri](https://tauri.app/) -- Cross-platform desktop framework
- [Google Gemini](https://ai.google.dev/) -- Primary LLM provider
- [pgvector](https://github.com/pgvector/pgvector) -- Vector similarity search for PostgreSQL
- [Neo4j](https://neo4j.com/) -- Knowledge graph database
- [Playwright](https://playwright.dev/) -- Browser automation
- [Rive](https://rive.app/) -- Living avatar animations
- [OpenClaw](https://github.com/openclaw) -- Soul AGI architecture inspiration
