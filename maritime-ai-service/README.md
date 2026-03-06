# Wiii Backend Service

This service is the FastAPI backend for Wiii. It handles chat orchestration, multi-agent routing, retrieval, memory, LMS integration, organization-aware access control, streaming, and production deployment packaging.

Use this README as the backend entry point. For full architecture detail, defer to the architecture and integration documents linked below.

## What This Service Owns

- FastAPI API surface for chat, streaming, threads, auth, organizations, admin, LMS, and health endpoints
- request middleware for request IDs, organization context, auth, and rate limiting
- `ChatOrchestrator` pipeline, session handling, domain routing, and output shaping
- LangGraph multi-agent execution across RAG, tutor, memory, direct-response, and tool-assisted flows
- retrieval and memory subsystems backed by PostgreSQL, pgvector, sparse search, and optional Neo4j context
- LMS token exchange, webhook ingestion, dashboard/data pull endpoints, and tool exposure
- production packaging, runtime config validation, and Docker Compose deployment assets

## Authoritative Docs

- `docs/architecture/SYSTEM_ARCHITECTURE.md`: primary architecture reference
- `docs/architecture/SYSTEM_FLOW.md`: request and streaming flow reference
- `docs/integration/WIII_LMS_INTEGRATION.md`: LMS contract and security model
- `scripts/deploy/README.md`: deployment runbook

## Runtime Flow

The main request path is:

1. HTTP or SSE request enters the API router.
2. Middleware applies request correlation, organization context, rate limiting, and auth.
3. `ChatOrchestrator` resolves session state and domain/plugin context.
4. The multi-agent graph routes work into retrieval, tutoring, memory, direct response, or external tools.
5. The output layer formats the final response as JSON or SSE V3 events.
6. Background tasks update facts, insights, or other post-response state.

Key supporting flows:

- LMS integration adds token exchange, webhook ingestion, data pull, and insight push paths.
- Semantic memory and learning profile paths adapt retrieval and follow-up behavior.
- Production deploy serves `/embed/` from image-contained assets rather than from a checked-out frontend bundle.

## Project Layout

```text
maritime-ai-service/
├── app/
│   ├── api/v1/          # HTTP, SSE, WebSocket, admin, org, LMS, and management routers
│   ├── auth/            # Google OAuth, JWT, LMS token exchange, user/identity services
│   ├── core/            # config, middleware, security, org context/filtering, logging
│   ├── domains/         # domain plugins and routing
│   ├── engine/          # RAG, multi-agent, memory, skills, tools, living-agent, MCP, context
│   ├── integrations/    # LMS integration and external adapters
│   ├── repositories/    # data-access layer
│   ├── services/        # orchestrator and business workflows
│   └── models/          # request/response and domain schemas
├── alembic/             # database migrations
├── docs/                # backend architecture and integration docs
├── scripts/             # deployment and operational scripts
└── tests/               # unit, integration, and property tests
```

## Quick Start

```bash
cd maritime-ai-service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

At minimum, set `GOOGLE_API_KEY` and `API_KEY` in `.env`.

Start local dependencies:

```bash
docker compose up -d postgres neo4j minio valkey
```

Run migrations and start the app:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

API base URL:

```text
http://localhost:8000/api/v1
```

## Testing

### Unit tests

```bash
cd maritime-ai-service
set PYTHONIOENCODING=utf-8 && pytest tests/unit/ -p no:capture --tb=short -q
```

### Integration tests

```bash
cd maritime-ai-service
pytest -m integration
```

### Property tests

```bash
cd maritime-ai-service
pytest tests/property/
```

## Deployment Notes

Production deploys use image tags, not host-side frontend rebuilds.

Current production packaging model:

- `scripts/deploy/.env.production.template` provides the required env shape
- `Dockerfile.prod` packages the backend app together with embed assets at `/app-embed`
- `nginx/Dockerfile.prod` packages the nginx layer together with embed assets at `/usr/share/nginx/embed`
- `.github/workflows/build-production-images.yml` builds and publishes immutable images to GHCR on push to `main`
- `scripts/deploy/smoke-test.sh` verifies health, `/embed/`, and chat behavior after rollout

Use the deployment runbook for operational steps:

- `scripts/deploy/README.md`

## Related Entry Points

- `../README.md`: repository overview
- `docs/architecture/README.md`: architecture docs index
- `docs/integration/WIII_LMS_INTEGRATION.md`: LMS contract

## License

See `../LICENSE` for repository licensing terms.