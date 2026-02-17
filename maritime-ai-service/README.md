# Wiii

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-purple?style=flat-square)](https://langchain.com)
[![Gemini](https://img.shields.io/badge/Gemini-3.0_Flash-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev)
[![Neon](https://img.shields.io/badge/Neon-pgvector-00E599?style=flat-square&logo=postgresql&logoColor=white)](https://neon.tech)

**Multi-Domain Agentic RAG Platform with Long-term Memory**

*by The Wiii Lab*

[Quick Start](#-quick-start) | [API Reference](#-api-reference) | [Architecture](docs/architecture/SYSTEM_FLOW.md) | [Changelog](CHANGELOG.md)

</div>

---

## Quick Start

```bash
# Clone & install
git clone <repo-url>
cd maritime-ai-service
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API keys (GOOGLE_API_KEY, DATABASE_URL, etc.)

# Run
uvicorn app.main:app --reload
```

**API Base:** `http://localhost:8000/api/v1`

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Multi-Domain Plugins** | Add new knowledge domains via YAML config (maritime, traffic law, etc.) |
| **Agentic RAG** | Self-correcting RAG with grading & verification |
| **Multi-Agent System** | Supervisor + RAG/Tutor/Memory/Grader agents (LangGraph) |
| **SOTA Streaming** | True token-by-token SSE streaming |
| **Early Exit Grading** | Skip quality_check at high confidence (saves latency) |
| **Semantic Cache** | 2hr TTL response caching |
| **Hybrid Search** | Dense (pgvector) + Sparse (tsvector) + RRF reranking |
| **Memory System** | Cross-session facts, insights, learning patterns |
| **Multimodal RAG** | Vision-based PDF understanding |
| **Web Search** | DuckDuckGo integration for real-time info |
| **Utility Tools** | Calculator, datetime (UTC+7) |

---

## Project Structure

```
maritime-ai-service/
├── app/
│   ├── api/v1/          # REST endpoints (chat, admin, health)
│   ├── cache/           # Semantic cache system
│   ├── core/            # Config, database, security
│   ├── domains/         # Domain plugins (maritime/, traffic_law/, _template/)
│   ├── engine/          # AI logic (agents, RAG, memory, tools)
│   ├── models/          # Pydantic schemas
│   ├── prompts/         # YAML prompt configs
│   ├── repositories/    # Data access layer
│   └── services/        # Business logic orchestration
├── docs/architecture/   # System diagrams & flows
├── scripts/             # Utility & test scripts
└── tests/               # Test suites (unit, integration, property)
```

---

## API Reference

### Chat Endpoint

```http
POST /api/v1/chat
Content-Type: application/json
X-API-Key: {api_key}

{
  "message": "Your question here",
  "user_id": "user-123",
  "role": "student",
  "domain_id": "maritime"
}
```

### Streaming Endpoint

```http
POST /api/v1/chat/stream/v2
Content-Type: application/json
X-API-Key: {api_key}
```

### Other Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/chat` | POST | Main chat |
| `/api/v1/chat/stream/v2` | POST | SSE token streaming |
| `/api/v1/admin/documents` | POST/GET | Document management |
| `/api/v1/admin/domains` | GET | List domain plugins |
| `/api/v1/admin/domains/{id}` | GET | Domain details |
| `/api/v1/health` | GET | Service health |

---

## Architecture

See [docs/architecture/SYSTEM_FLOW.md](docs/architecture/SYSTEM_FLOW.md) for complete diagrams.

### High-Level Flow

```
User → API → ChatOrchestrator → DomainRouter → Supervisor → Agent (RAG/Tutor/Memory/Direct) → Response
                                     ↓
                               DomainPlugin
                          (prompts, tools, config)
```

### Domain Plugin System

```
app/domains/
├── base.py          # DomainPlugin ABC
├── registry.py      # Singleton registry
├── loader.py        # Auto-discovery
├── router.py        # 4-priority routing
├── maritime/        # Maritime domain (COLREGs, SOLAS, MARPOL)
├── traffic_law/     # Traffic law domain
└── _template/       # Skeleton for new domains
```

---

## Configuration

Key environment variables:

```env
# Required
GOOGLE_API_KEY=your-gemini-api-key
DATABASE_URL=postgresql://...

# Optional
NEO4J_URI=neo4j+s://...
SUPABASE_URL=https://...
```

See [.env.example](.env.example) for full list.

---

## Domain Plugin Development

```bash
# 1. Copy template
cp -r app/domains/_template app/domains/my_domain
# 2. Edit domain.yaml with keywords, descriptions
# 3. Write prompts in prompts/agents/
# 4. Add to config: active_domains=["maritime","my_domain"]
# 5. Restart — auto-discovered
```

---

## Testing

```bash
pytest tests/unit/ -v -p no:capture    # Unit tests
pytest tests/integration/ -v           # Integration tests
pytest tests/property/ -v              # Property-based tests
```

---

## License

Proprietary - All rights reserved.

*Wiii by The Wiii Lab*
